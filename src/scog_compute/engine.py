"""Compute engine for the STAC COG Data Cube.
Author : @kshitijrajsharma 2024
"""

import argparse
import os
import zipfile

import imageio
import matplotlib.pyplot as plt
import numpy as np
import rasterio
import requests
from matplotlib.colors import Normalize
from PIL import Image
from pyproj import Transformer
from rasterio.windows import from_bounds
from shapely.geometry import box, shape
from tqdm import tqdm


def fetch_process_custom_band(band1_url, band2_url, bbox, formula):
    try:
        with rasterio.open(band1_url) as band1_cog, rasterio.open(
            band2_url
        ) as band2_cog:
            transformer = Transformer.from_crs(
                "epsg:4326", band1_cog.crs, always_xy=True
            )

            min_x, min_y = transformer.transform(bbox[0], bbox[1])
            max_x, max_y = transformer.transform(bbox[2], bbox[3])

            band1_window = from_bounds(min_x, min_y, max_x, max_y, band1_cog.transform)
            band2_window = from_bounds(min_x, min_y, max_x, max_y, band2_cog.transform)

            if (
                band1_window.col_off < 0
                or band1_window.row_off < 0
                or band1_window.width <= 0
                or band1_window.height <= 0
                or band2_window.col_off < 0
                or band2_window.row_off < 0
                or band2_window.width <= 0
                or band2_window.height <= 0
            ):
                print("Calculated window is out of bounds.")
                return None, None, None

            band1 = band1_cog.read(1, window=band1_window)
            band2 = band2_cog.read(1, window=band2_window)

            band1 = band1.astype(float)
            band2 = band2.astype(float)

            # Perform the custom calculation
            result = eval(formula)

            result = np.ma.masked_invalid(result)

            return result, band1_cog.crs, band1_cog.window_transform(band1_window)
    except Exception as e:
        print(f"Error fetching image: {e}")
        return None, None, None


def fetch_process_save_band(url, bbox, output_dir):
    try:
        with rasterio.open(url) as cog:
            transformer = Transformer.from_crs("epsg:4326", cog.crs, always_xy=True)

            min_x, min_y = transformer.transform(bbox[0], bbox[1])
            max_x, max_y = transformer.transform(bbox[2], bbox[3])

            cog_window = from_bounds(min_x, min_y, max_x, max_y, cog.transform)

            if (
                cog_window.col_off < 0
                or cog_window.row_off < 0
                or cog_window.width <= 0
                or cog_window.height <= 0
            ):
                print("Calculated window is out of bounds.")
                return None

            # Read all bands within the window
            image = cog.read(window=cog_window)

            parts = url.split("/")
            image_name = parts[-2]
            output_file = os.path.join(output_dir, f"{image_name}_band.tif")

            with rasterio.open(
                output_file,
                "w",
                driver="GTiff",
                height=image.shape[1],
                width=image.shape[2],
                count=image.shape[0],
                dtype=image.dtype,
                crs=cog.crs,
                transform=cog.window_transform(cog_window),
            ) as dst:
                for i in range(image.shape[0]):
                    dst.write(image[i], i + 1)

            return output_file, image_name
    except Exception as e:
        print(f"Error fetching image: {e}")
        return None


def save_aggregated_result_with_colormap(
    result_aggregate,
    crs,
    transform,
    output_file,
    start_date,
    end_date,
    cloud_cover,
    bbox,
    total_images,
    operation,
):
    # Normalize the result
    result_normalized = (result_aggregate - result_aggregate.min()) / (
        result_aggregate.max() - result_aggregate.min()
    )
    colormap = plt.get_cmap("RdYlGn")
    result_colored = colormap(result_normalized)

    # Convert to image
    result_image = (result_colored[:, :, :3] * 255).astype(np.uint8)
    image = Image.fromarray(result_image)

    # Plot and save the image with metadata
    plt.figure(figsize=(10, 10))
    plt.imshow(image)
    plt.title(f"Aggregated {operation} Custom Band Calculation")
    plt.xlabel(
        f"Normalized Range: {result_normalized.min():.2f} to {result_normalized.max():.2f}"
    )
    plt.ylabel(
        f"From {start_date} to {end_date}\nCloud Cover < {cloud_cover}%\nBounding Box: {bbox}\nTotal Images: {total_images}"
    )
    cbar = plt.colorbar(
        plt.cm.ScalarMappable(
            norm=Normalize(vmin=result_normalized.min(), vmax=result_normalized.max()),
            cmap=colormap,
        ),
        ax=plt.gca(),
    )
    cbar.set_label("Normalized Value")

    plt.savefig(output_file.replace(".tif", "_colormap.png"))
    plt.close()

    # Save the result as a GeoTIFF
    with rasterio.open(
        output_file,
        "w",
        driver="GTiff",
        height=result_aggregate.shape[0],
        width=result_aggregate.shape[1],
        count=1,
        dtype=result_aggregate.dtype,
        crs=crs,
        transform=transform,
    ) as dst:
        dst.write(result_aggregate, 1)

    print(f"Saved aggregated custom band result to {output_file}")
    print(f"Saved color-mapped image to {output_file.replace('.tif', '_colormap.png')}")


def add_text_to_image(image_path, text):
    image = Image.open(image_path)
    plt.figure(figsize=(10, 10))
    plt.imshow(image)
    plt.axis("off")
    plt.text(10, 10, text, color="white", fontsize=12, backgroundcolor="black")
    temp_image_path = os.path.splitext(image_path)[0] + "_text.png"
    plt.savefig(temp_image_path, bbox_inches="tight", pad_inches=0)
    plt.close()
    return temp_image_path


def create_gif(image_list, output_path, duration=0.5):
    images = [imageio.imread(image_path) for image_path in image_list]
    imageio.mimsave(output_path, images, duration=duration)
    print(f"Saved GIF to {output_path}")
    [os.remove(image) for image in image_list]


def zip_files(file_list, zip_path):
    with zipfile.ZipFile(zip_path, "w") as zipf:
        for file in file_list:
            zipf.write(file, os.path.basename(file))
    print(f"Saved ZIP to {zip_path}")


def compute(
    bbox,
    start_date,
    end_date,
    cloud_cover,
    formula,
    band1,
    band2,
    operation,
    export_band,
    output_dir,
):
    print("Engine starting...")

    os.makedirs(output_dir, exist_ok=True)

    bbox_polygon = box(bbox[0], bbox[1], bbox[2], bbox[3])

    STAC_API_URL = "https://earth-search.aws.element84.com/v1/search"

    # Search parameters
    search_params = {
        "collections": ["sentinel-2-l2a"],
        "datetime": f"{start_date}T00:00:00Z/{end_date}T23:59:59Z",
        "query": {"eo:cloud_cover": {"lt": cloud_cover}},
        "bbox": bbox,
        "limit": 100,
    }

    print("Searching STAC API...")
    response = requests.post(STAC_API_URL, json=search_params)
    if response.status_code != 200:
        raise Exception("Error searching STAC API")

    results = response.json()
    print(f"Found {len(results['features'])} items")

    # Filter features that are completely within the bounding box
    filtered_features = [
        feature
        for feature in results["features"]
        if shape(feature["geometry"]).contains(bbox_polygon)
    ]

    # Get the band URLs for the filtered features
    band1_urls = [feature["assets"][band1]["href"] for feature in filtered_features]
    band2_urls = [feature["assets"][band2]["href"] for feature in filtered_features]
    band_urls = [
        feature["assets"][export_band]["href"] for feature in filtered_features
    ]

    print(
        f"Filtered {len(filtered_features)} items that are completely within the input bounding box"
    )

    # Process custom band calculation
    if formula:
        result_list = []
        crs = None
        transform = None
        print("Processing custom band calculation...")
        for band1_url, band2_url in tqdm(
            zip(band1_urls, band2_urls),
            total=len(band1_urls),
            desc="Custom Band Calculation",
        ):
            result, crs, transform = fetch_process_custom_band(
                band1_url, band2_url, bbox, formula
            )
            if result is not None:
                result_list.append(result)

        if result_list:
            result_stack = np.ma.stack(result_list)
            if operation == "mean":
                result_aggregate = np.ma.mean(result_stack, axis=0)
            elif operation == "median":
                result_aggregate = np.ma.median(result_stack, axis=0)
            elif operation == "max":
                result_aggregate = np.ma.max(result_stack, axis=0)
            elif operation == "min":
                result_aggregate = np.ma.min(result_stack, axis=0)
            else:
                raise ValueError(
                    "Invalid operation. Choose from 'mean', 'median', 'max', 'min'."
                )

            # Save the aggregated result as a GeoTIFF
            output_file = os.path.join(
                output_dir, f"custom_band_{operation}_aggregate.tif"
            )
            save_aggregated_result_with_colormap(
                result_aggregate,
                crs,
                transform,
                output_file,
                start_date,
                end_date,
                cloud_cover,
                bbox,
                len(result_list),
                operation,
            )

    # Export single band and create GIF
    if export_band:
        image_list = []
        tiff_files = []
        print("Exporting single band and creating GIF...")
        for band_url in tqdm(band_urls, total=len(band_urls), desc="Exporting Images"):
            image_path, image_name = fetch_process_save_band(band_url, bbox, output_dir)
            if image_path is not None:
                tiff_files.append(image_path)
                image_with_text = add_text_to_image(image_path, image_name)
                image_list.append(image_with_text)

        if image_list:
            create_gif(image_list, os.path.join(output_dir, "output.gif"))
            zip_files(tiff_files, os.path.join(output_dir, "tiff_files.zip"))
        else:
            print("No images found for the given parameters")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Data Cube Compute Engine based on COG"
    )
    parser.add_argument(
        "--bbox",
        type=float,
        nargs=4,
        required=True,
        help="Bounding box in the format 'min_x min_y max_x max_y'",
    )
    parser.add_argument(
        "--start_date", type=str, required=True, help="Start date in YYYY-MM-DD format"
    )
    parser.add_argument(
        "--end_date", type=str, required=True, help="End date in YYYY-MM-DD format"
    )
    parser.add_argument(
        "--cloud_cover", type=int, default=20, help="Maximum cloud cover percentage"
    )
    parser.add_argument(
        "--formula",
        type=str,
        help="Formula for custom band calculation (e.g., '(band1 + band2) / (band1 - band2)')",
    )
    parser.add_argument("--band1", type=str, help="First band for custom calculation")
    parser.add_argument("--band2", type=str, help="Second band for custom calculation")
    parser.add_argument(
        "--operation",
        type=str,
        choices=["mean", "median", "max", "min"],
        help="Operation for aggregating results",
    )
    parser.add_argument(
        "--export_band", type=str, help="Band to export as TIFF and create GIF"
    )
    parser.add_argument(
        "--output_dir",
        type=str,
        default=".",
        help="Output directory for saving results",
    )

    args = parser.parse_args()

    compute(
        args.bbox,
        args.start_date,
        args.end_date,
        args.cloud_cover,
        args.formula,
        args.band1,
        args.band2,
        args.operation,
        args.export_band,
        args.output_dir,
    )
