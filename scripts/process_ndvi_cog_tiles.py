"""
Script to process NDVI tiles from a STAC API over the time. Give median output of the ndvi in the region

Usage:
    python process_ndvi_cog_tiles.py --lat <latitude> --lon <longitude> --z <zoom_level> --sd <start_date> --ed <end_date> --cc <cloud_cover>

Arguments:
    --lat       Latitude (default: 28.202082)
    --lon       Longitude (default: 83.987222)
    --z         Zoom level (default: 10)
    --sd        Start date in YYYY-MM-DD format (default: first day of last 2 month)
    --ed        End date in YYYY-MM-DD format (default: today)
    --cc        Cloud cover percentage (default: 30)

Requirements:
    - requests
    - matplotlib
    - mercantile
    - numpy
    - Pillow
    - rio-tiler
    - tqdm

Install the required packages using:
    pip install requests matplotlib mercantile numpy Pillow rio-tiler tqdm

Author : Kshitij Raj Sharma @ 2025
"""

import argparse
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from io import BytesIO

import matplotlib.pyplot as plt
import mercantile
import numpy as np
import requests
from PIL import Image
from rio_tiler.io import COGReader
from tqdm import tqdm


def fetch_and_process_tile(red_url, nir_url, tile_x, tile_y, z):
    try:
        with COGReader(red_url) as red_cog, COGReader(nir_url) as nir_cog:
            red_tile, _ = red_cog.tile(tile_x, tile_y, z)
            nir_tile, _ = nir_cog.tile(tile_x, tile_y, z)

            r = red_tile[0]
            nir = nir_tile[0]

            ndvi = (nir.astype(float) - r.astype(float)) / (nir + r)
            ndvi = np.ma.masked_invalid(ndvi)

            return ndvi
    except Exception as e:
        print(f"Error fetching tile: {e}")
        return None


def main(args):
    lat = args.lat
    lon = args.lon
    z = args.z
    cc = args.cc

    tile = mercantile.tile(lon, lat, z)
    bbox = mercantile.bounds(tile)

    start_date = args.sd
    end_date = args.ed

    STAC_API_URL = "https://earth-search.aws.element84.com/v0/search"

    # Search parameters
    search_params = {
        "collections": ["sentinel-s2-l2a-cogs"],
        "datetime": f"{start_date}T00:00:00Z/{end_date}T23:59:59Z",
        "query": {"eo:cloud_cover": {"lt": cc}},
        "bbox": [bbox.west, bbox.south, bbox.east, bbox.north],
        "limit": 100,
    }

    response = requests.post(STAC_API_URL, json=search_params)
    if response.status_code != 200:
        raise Exception("Error searching STAC API")

    results = response.json()
    print(len(results["features"]))
    red_band_urls = [
        feature["assets"]["B04"]["href"] for feature in results["features"]
    ]
    nir_band_urls = [
        feature["assets"]["B08"]["href"] for feature in results["features"]
    ]

    ndvi_list = []

    num_cores = os.cpu_count()
    max_workers = max(1, num_cores - 2)  # Leave 2 cores for other processes

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            executor.submit(fetch_and_process_tile, red_url, nir_url, tile.x, tile.y, z)
            for red_url, nir_url in zip(red_band_urls, nir_band_urls)
        ]

        for future in tqdm(
            as_completed(futures), total=len(futures), desc="Processing tiles"
        ):
            ndvi = future.result()
            if ndvi is not None:
                ndvi_list.append(ndvi)

    if ndvi_list:
        ndvi_stack = np.ma.stack(ndvi_list)
        ndvi_median = np.ma.median(ndvi_stack, axis=0)
        ndvi_normalized = (ndvi_median + 1) / 2

        colormap = plt.get_cmap("RdYlGn")
        ndvi_colored = colormap(ndvi_normalized)

        ndvi_image = (ndvi_colored[:, :, :3] * 255).astype(np.uint8)
        image = Image.fromarray(ndvi_image)

        plt.figure(figsize=(10, 10))
        plt.imshow(image)
        plt.title("Median NDVI for Tile")
        plt.xlabel(
            f"Normalized Range: {ndvi_normalized.min():.2f} to {ndvi_normalized.max():.2f}"
        )
        plt.ylabel(
            f"Date Range: {start_date} to {end_date}\nTotal Images: {len(ndvi_list)}"
        )
        cbar = plt.colorbar(plt.cm.ScalarMappable(cmap=colormap), ax=plt.gca())
        cbar.set_label("NDVI Normalized Value")

        if args.out:
            plt.savefig(args.out)
        else:
            plt.show()
    else:
        print("No images found for the given parameters")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Process NDVI tiles from STAC API.")
    parser.add_argument(
        "--sd",
        type=str,
        default=(datetime.now() - timedelta(days=30 * 2)).strftime("%Y-%m-01"),
        help="Start date in YYYY-MM-DD format (default: first day of last 2 month)",
    )
    parser.add_argument(
        "--ed",
        type=str,
        default=datetime.now().strftime("%Y-%m-%d"),
        help="End date in YYYY-MM-DD format (default: today)",
    )
    parser.add_argument(
        "--lat", type=float, default=28.202082, help="Latitude (default: 28.202082)"
    )
    parser.add_argument(
        "--lon", type=float, default=83.987222, help="Longitude (default: 83.987222)"
    )
    parser.add_argument("--z", type=int, default=10, help="Zoom level (default: 10)")
    parser.add_argument(
        "--cc", type=int, default=30, help="Cloud cover percentage (default: 20)"
    )
    parser.add_argument(
        "--out",
        type=str,
        help="Output file path to save the image (default: only show)",
    )

    args = parser.parse_args()
    main(args)
