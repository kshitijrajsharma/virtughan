import os
import zipfile

import imageio.v3 as iio
import matplotlib.pyplot as plt
import numpy as np
import rasterio
import requests
from matplotlib.colors import Normalize
from PIL import Image
from pyproj import Transformer
from rasterio.windows import from_bounds
from scipy.stats import mode
from shapely.geometry import box, shape
from tqdm import tqdm


def fetch_process_custom_band(band1_url, band2_url, bbox, formula):
    try:
        with rasterio.open(band1_url) as band1_cog:
            transformer = Transformer.from_crs(
                "epsg:4326", band1_cog.crs, always_xy=True
            )

            min_x, min_y = transformer.transform(bbox[0], bbox[1])
            max_x, max_y = transformer.transform(bbox[2], bbox[3])

            band1_window = from_bounds(min_x, min_y, max_x, max_y, band1_cog.transform)

            if (
                band1_window.col_off < 0
                or band1_window.row_off < 0
                or band1_window.width <= 0
                or band1_window.height <= 0
            ):
                print("Calculated window is out of bounds.")
                return None, None, None

            band1 = band1_cog.read(window=band1_window)

            if band2_url:
                with rasterio.open(band2_url) as band2_cog:
                    band2_window = from_bounds(
                        min_x, min_y, max_x, max_y, band2_cog.transform
                    )

                    if (
                        band2_window.col_off < 0
                        or band2_window.row_off < 0
                        or band2_window.width <= 0
                        or band2_window.height <= 0
                    ):
                        print("Calculated window is out of bounds.")
                        return None, None, None

                    band2 = band2_cog.read(window=band2_window)
                    band2 = band2.astype(float)
            else:
                band2 = None
            if band2 is not None:
                band1 = band1.astype(float)
                result = eval(formula)
            else:
                inner_bands = band1.shape[0]
                band1 = band1.astype(float)
                if inner_bands == 1:
                    result = eval(formula)
                else:
                    result = band1
            # result = np.ma.masked_invalid(result)

            return result, band1_cog.crs, band1_cog.window_transform(band1_window)
    except Exception as e:
        print(f"Error fetching image: {e}")
        return None, None, None


def add_text_to_image(image_path, text, cmap="RdYlGn"):
    with rasterio.open(image_path) as src:
        if src.count == 1:
            # Single band image
            image_array = src.read(1)
            image_array = (
                (image_array - image_array.min())
                / (image_array.max() - image_array.min())
                * 255
            )
            image_array = image_array.astype(np.uint8)
            image = Image.fromarray(image_array)
        elif src.count == 3:
            # RGB image
            image_array = np.dstack([src.read(i) for i in range(1, 4)])
            image_array = (
                (image_array - image_array.min())
                / (image_array.max() - image_array.min())
                * 255
            )
            image_array = image_array.astype(np.uint8)
            image = Image.fromarray(image_array)
            cmap = None
        else:
            raise ValueError("Unsupported number of bands: {}".format(src.count))

    plt.figure(figsize=(10, 10))
    plt.imshow(image, cmap=cmap)
    plt.axis("off")
    plt.text(10, 10, text, color="white", fontsize=12, backgroundcolor="black")
    temp_image_path = os.path.splitext(image_path)[0] + "_text.png"
    plt.savefig(temp_image_path, bbox_inches="tight", pad_inches=0)
    plt.close()
    return temp_image_path


def create_gif(image_list, output_path, duration=10):
    images = [Image.open(image_path) for image_path in image_list]
    max_width = max(image.width for image in images)
    max_height = max(image.height for image in images)

    resized_images = [
        image.resize((max_width, max_height), Image.LANCZOS) for image in images
    ]

    iio.imwrite(output_path, resized_images, duration=duration, loop=0)
    print(f"Saved GIF to {output_path}")


def zip_files(file_list, zip_path):
    with zipfile.ZipFile(zip_path, "w") as zipf:
        for file in file_list:
            zipf.write(file, os.path.basename(file))
    print(f"Saved ZIP to {zip_path}")


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
    cmap="RdYlGn",
):
    colormap = plt.get_cmap(cmap)

    if result_aggregate.shape[0] == 1:
        # Single-band image
        result_aggregate_m = result_aggregate[0]
        result_normalized = (result_aggregate_m - result_aggregate_m.min()) / (
            result_aggregate_m.max() - result_aggregate_m.min()
        )
        colormap = plt.get_cmap("RdYlGn")
        result_colored = colormap(result_normalized)

        # Convert to image
        result_image = (result_colored[:, :, :3] * 255).astype(np.uint8)
        image = Image.fromarray(result_image)
    else:
        # Multi-band image
        result_normalized = (
            result_aggregate - result_aggregate.min(axis=(0, 1), keepdims=True)
        ) / (
            result_aggregate.max(axis=(0, 1), keepdims=True)
            - result_aggregate.min(axis=(0, 1), keepdims=True)
        )
        result_image = np.transpose(result_normalized, (1, 2, 0))
        result_image = (result_image * 255).astype(np.uint8)
        image = Image.fromarray(result_image)

    plt.figure(figsize=(10, 10))
    plt.imshow(image)
    plt.title(f"Aggregated {operation} Custom Band Calculation")
    plt.xlabel(
        f"Normalized Range: {result_normalized.min():.2f} to {result_normalized.max():.2f}"
    )
    plt.ylabel(
        f"From {start_date} to {end_date}\nCloud Cover < {cloud_cover}%\nBounding Box: {bbox}\nTotal Images: {total_images}"
    )

    if result_aggregate.shape[0] == 1:
        cbar = plt.colorbar(
            plt.cm.ScalarMappable(
                norm=Normalize(
                    vmin=result_normalized.min(), vmax=result_normalized.max()
                ),
                cmap=colormap,
            ),
            ax=plt.gca(),
        )
        cbar.set_label("Normalized Value")

    plt.savefig(output_file.replace(".tif", "_colormap.png"))
    plt.close()

    result_aggregate = np.transpose(result_aggregate, (1, 2, 0))

    with rasterio.open(
        output_file,
        "w",
        driver="GTiff",
        height=result_aggregate.shape[0],
        width=result_aggregate.shape[1],
        count=result_aggregate.shape[2],
        dtype=result_aggregate.dtype,
        crs=crs,
        transform=transform,
    ) as dst:
        for band in range(1, result_aggregate.shape[2] + 1):
            dst.write(result_aggregate[:, :, band - 1], band)

    print(f"Saved aggregated custom band result to {output_file}")
    print(f"Saved color-mapped image to {output_file.replace('.tif', '_colormap.png')}")


def pad_array(array, target_shape, fill_value=np.nan):
    """
    Pad an array to the target shape
    """
    pad_width = [
        (0, max(0, target - current))
        for current, target in zip(array.shape, target_shape)
    ]
    return np.pad(array, pad_width, mode="constant", constant_values=fill_value)


def compute(
    bbox,
    start_date,
    end_date,
    cloud_cover,
    formula,
    band1,
    band2,
    operation,
    timeseries,
    output_dir,
    cmap="RdYlGn",
):
    print("Engine starting...")

    os.makedirs(output_dir, exist_ok=True)
    if band1 is None:
        raise Exception("Band1 is required")

    if formula is None:
        formula = "band1"

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
    band2_urls = (
        [feature["assets"][band2]["href"] for feature in filtered_features]
        if band2
        else [None] * len(filtered_features)
    )

    print(
        f"Filtered {len(filtered_features)} items that are completely within the input bounding box"
    )

    # Process custom band calculation
    if formula:
        result_list = []
        crs = None
        transform = None
        intermediate_images = []
        intermediate_images_with_text = []
        print("Processing images along time dimention...")
        for band1_url, band2_url in tqdm(
            zip(band1_urls, band2_urls),
            total=len(band1_urls),
            desc="Computing Band Calculation",
        ):
            result, crs, transform = fetch_process_custom_band(
                band1_url, band2_url, bbox, formula
            )
            if result is not None:
                result_list.append(result)

                if timeseries:
                    # Save intermediate result as GeoTIFF
                    parts = band1_url.split("/")
                    image_name = parts[-2]
                    output_file = os.path.join(output_dir, f"{image_name}_result.tif")
                    with rasterio.open(
                        output_file,
                        "w",
                        driver="GTiff",
                        height=result.shape[1],
                        width=result.shape[2],
                        count=result.shape[0],
                        dtype=result.dtype,
                        crs=crs,
                        transform=transform,
                    ) as dst:
                        for band in range(1, result.shape[0] + 1):
                            dst.write(result[band - 1], band)
                    intermediate_images.append(output_file)
                    intermediate_images_with_text.append(
                        add_text_to_image(output_file, image_name)
                    )

        if result_list and operation:

            max_shape = tuple(max(s) for s in zip(*[arr.shape for arr in result_list]))
            padded_result_list = [pad_array(arr, max_shape) for arr in result_list]
            result_stack = np.ma.stack(padded_result_list)

            if operation == "mean":
                result_aggregate = np.ma.mean(result_stack, axis=0)
            elif operation == "median":
                result_aggregate = np.ma.median(result_stack, axis=0)
            elif operation == "max":
                result_aggregate = np.ma.max(result_stack, axis=0)
            elif operation == "min":
                result_aggregate = np.ma.min(result_stack, axis=0)
            elif operation == "std":
                result_aggregate = np.ma.std(result_stack, axis=0)
            elif operation == "sum":
                result_aggregate = np.ma.sum(result_stack, axis=0)
            elif operation == "var":
                result_aggregate = np.ma.var(result_stack, axis=0)
            elif operation == "mode":
                result_aggregate, _ = mode(result_stack, axis=0, nan_policy="omit")
                result_aggregate = result_aggregate.squeeze()
            else:
                raise ValueError(
                    "Invalid operation. Choose from 'mean', 'median', 'max', 'min', 'std', 'sum', 'var', 'mode'."
                )

            # Save the aggregated result with colormap
            output_file = os.path.join(
                output_dir, f"custom_band_{operation}_aggregate.tif"
            )
            print("Saving aggregated result with colormap...")
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
                cmap,
            )

    # Create GIF and ZIP if timeseries is enabled
    if timeseries:
        print("Creating GIF and zipping TIFF files...")
        if intermediate_images:
            create_gif(
                intermediate_images_with_text, os.path.join(output_dir, "output.gif")
            )
            zip_files(intermediate_images, os.path.join(output_dir, "tiff_files.zip"))
        else:
            print("No images found for the given parameters")
