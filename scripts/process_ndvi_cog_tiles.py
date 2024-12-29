import argparse
import asyncio
import os
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta

import httpx
import matplotlib.pyplot as plt
import mercantile
import numpy as np
from PIL import Image
from rio_tiler.io import COGReader
from tqdm.asyncio import tqdm_asyncio

default_max_workers = min(32, os.cpu_count() + 4)

executor = ThreadPoolExecutor(max_workers=default_max_workers)

print(f"Using {default_max_workers} parallel workers")


async def fetch_tile(url, tile_x, tile_y, z):
    def read_tile():
        with COGReader(url) as cog:
            tile, _ = cog.tile(tile_x, tile_y, z)
            return tile[0]

    return await asyncio.to_thread(read_tile)


async def fetch_and_process_tile(red_url, nir_url, tile_x, tile_y, z):
    try:
        red_tile, nir_tile = await asyncio.gather(
            fetch_tile(red_url, tile_x, tile_y, z),
            fetch_tile(nir_url, tile_x, tile_y, z),
        )

        r = red_tile
        nir = nir_tile

        ndvi = (nir.astype(float) - r.astype(float)) / (nir + r)
        ndvi = np.ma.masked_invalid(ndvi)

        return ndvi
    except Exception as e:
        print(f"Error fetching tile: {e}")
        return None


async def process_tiles_parallel(tile_urls, tile_x, tile_y, z):
    tasks = [
        fetch_and_process_tile(red_url, nir_url, tile_x, tile_y, z)
        for red_url, nir_url in tile_urls
    ]
    ndvi_tiles = []
    for task in tqdm_asyncio.as_completed(
        tasks, total=len(tasks), desc="Processing tiles"
    ):
        ndvi = await task
        if ndvi is not None:
            ndvi_tiles.append(ndvi)
    return ndvi_tiles


async def main(args):
    lat = args.lat
    lon = args.lon
    z = args.z
    cc = args.cc

    tile = mercantile.tile(lon, lat, z)
    bbox = mercantile.bounds(tile)

    start_date = args.sd
    end_date = args.ed

    STAC_API_URL = "https://earth-search.aws.element84.com/v1/search"

    search_params = {
        "collections": ["sentinel-2-l2a"],
        "datetime": f"{start_date}T00:00:00Z/{end_date}T23:59:59Z",
        "query": {"eo:cloud_cover": {"lt": cc}},
        "bbox": [bbox.west, bbox.south, bbox.east, bbox.north],
        "limit": 100,
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(STAC_API_URL, json=search_params)
    if response.status_code != 200:
        raise Exception("Error searching STAC API")

    results = response.json()
    red_band_urls = [
        feature["assets"]["red"]["href"] for feature in results["features"]
    ]
    nir_band_urls = [
        feature["assets"]["nir"]["href"] for feature in results["features"]
    ]

    print(f"Processing {len(red_band_urls)} images...")

    tile_urls = list(zip(red_band_urls, nir_band_urls))

    start_time = time.time()
    ndvi_tiles = await process_tiles_parallel(tile_urls, tile.x, tile.y, z)
    end_time = time.time()

    print(f"Processed {len(ndvi_tiles)} tiles in {end_time - start_time} seconds")

    if ndvi_tiles:
        ndvi_stack = np.ma.stack(ndvi_tiles, axis=0)
        ndvi_median = np.ma.median(ndvi_stack, axis=0)

        ndvi_normalized = (ndvi_median - ndvi_median.min()) / (
            ndvi_median.max() - ndvi_median.min()
        )
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
        plt.ylabel(f"From {start_date} to {end_date}\nTotal Images: {len(ndvi_tiles)}")
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
        "--lat",
        type=float,
        default=28.202082,
        help="Latitude (default: 28.202082)",
    )
    parser.add_argument(
        "--lon",
        type=float,
        default=83.987222,
        help="Longitude (default: 83.987222)",
    )
    parser.add_argument("--z", type=int, default=10, help="Zoom level (default: 10)")
    parser.add_argument(
        "--cc", type=int, default=30, help="Cloud cover percentage (default: 30)"
    )
    parser.add_argument(
        "--sd",
        type=str,
        default=(datetime.now() - timedelta(days=30 * 2)).strftime("%Y-%m-01"),
        help="Start date in YYYY-MM-DD format (default: first day of last 2 months)",
    )
    parser.add_argument(
        "--ed",
        type=str,
        default=datetime.now().strftime("%Y-%m-%d"),
        help="End date in YYYY-MM-DD format (default: today)",
    )
    parser.add_argument(
        "--out",
        type=str,
        help="Output file path to save the plot (default: only show)",
    )
    args = parser.parse_args()

    asyncio.run(main(args))
