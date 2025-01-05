import os
import sys
import zipfile

import imageio.v3 as iio
import matplotlib
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

matplotlib.use("Agg")


class VCubeProcessor:
    def __init__(
        self,
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
        log_file=None,
        cmap="RdYlGn",
    ):
        self.bbox = bbox
        self.start_date = start_date
        self.end_date = end_date
        self.cloud_cover = cloud_cover
        self.formula = formula or "band1"
        self.band1 = band1
        self.band2 = band2
        self.operation = operation
        self.timeseries = timeseries
        self.output_dir = output_dir
        self.log_file = log_file
        self.cmap = cmap
        self.STAC_API_URL = "https://earth-search.aws.element84.com/v1/search"
        self.result_list = []
        self.crs = None
        self.transform = None
        self.intermediate_images = []
        self.intermediate_images_with_text = []

    def fetch_process_custom_band(self, band1_url, band2_url):
        """Fetch and process custom band data."""
        try:
            with rasterio.open(band1_url) as band1_cog:
                min_x, min_y, max_x, max_y = self._transform_bbox(band1_cog.crs)
                band1_window = self._calculate_window(
                    band1_cog, min_x, min_y, max_x, max_y
                )

                if self._is_window_out_of_bounds(band1_window):
                    return None, None, None

                band1 = band1_cog.read(window=band1_window).astype(float)

                if band2_url:
                    with rasterio.open(band2_url) as band2_cog:
                        band2_window = self._calculate_window(
                            band2_cog, min_x, min_y, max_x, max_y
                        )

                        if self._is_window_out_of_bounds(band2_window):
                            return None, None, None

                        band2 = band2_cog.read(window=band2_window).astype(float)
                        result = eval(self.formula)
                else:
                    result = eval(self.formula) if band1.shape[0] == 1 else band1

                return result, band1_cog.crs, band1_cog.window_transform(band1_window)
        except Exception as e:
            print(f"Error fetching image: {e}")
            return None, None, None

    def _transform_bbox(self, crs):
        transformer = Transformer.from_crs("epsg:4326", crs, always_xy=True)
        min_x, min_y = transformer.transform(self.bbox[0], self.bbox[1])
        max_x, max_y = transformer.transform(self.bbox[2], self.bbox[3])
        return min_x, min_y, max_x, max_y

    def _calculate_window(self, cog, min_x, min_y, max_x, max_y):
        return from_bounds(min_x, min_y, max_x, max_y, cog.transform)

    def _is_window_out_of_bounds(self, window):
        return (
            window.col_off < 0
            or window.row_off < 0
            or window.width <= 0
            or window.height <= 0
        )

    def _search_stac_api(self):
        search_params = {
            "collections": ["sentinel-2-l2a"],
            "datetime": f"{self.start_date}T00:00:00Z/{self.end_date}T23:59:59Z",
            "query": {"eo:cloud_cover": {"lt": self.cloud_cover}},
            "bbox": self.bbox,
            "limit": 100,
        }

        response = requests.post(self.STAC_API_URL, json=search_params)
        response.raise_for_status()
        return response.json()["features"]

    def _filter_features(self, features):
        bbox_polygon = box(self.bbox[0], self.bbox[1], self.bbox[2], self.bbox[3])
        return [
            feature
            for feature in features
            if shape(feature["geometry"]).contains(bbox_polygon)
        ]

    def _get_band_urls(self, features):
        band1_urls = [feature["assets"][self.band1]["href"] for feature in features]
        band2_urls = (
            [feature["assets"][self.band2]["href"] for feature in features]
            if self.band2
            else [None] * len(features)
        )
        return band1_urls, band2_urls

    def _process_images(self):
        features = self._search_stac_api()
        print(f"Found {len(features)} items")
        filtered_features = self._filter_features(features)
        band1_urls, band2_urls = self._get_band_urls(filtered_features)

        print(
            f"Filtered {len(filtered_features)} items that are completely within the input bounding box"
        )

        for band1_url, band2_url in tqdm(
            zip(band1_urls, band2_urls),
            total=len(band1_urls),
            desc="Computing Band Calculation",
            file=self.log_file if self.log_file is not None else sys.stdout,
        ):

            result, self.crs, self.transform = self.fetch_process_custom_band(
                band1_url, band2_url
            )
            if result is not None:
                self.result_list.append(result)
                if self.timeseries:
                    self._save_intermediate_image(result, band1_url)

    def _save_intermediate_image(self, result, band1_url):
        parts = band1_url.split("/")
        image_name = parts[-2]
        output_file = os.path.join(self.output_dir, f"{image_name}_result.tif")
        self._save_geotiff(result, output_file)
        self.intermediate_images.append(output_file)
        self.intermediate_images_with_text.append(
            self.add_text_to_image(output_file, image_name)
        )

    def _save_geotiff(self, data, output_file):
        with rasterio.open(
            output_file,
            "w",
            driver="GTiff",
            height=data.shape[1],
            width=data.shape[2],
            count=data.shape[0],
            dtype=data.dtype,
            crs=self.crs,
            transform=self.transform,
        ) as dst:
            for band in range(1, data.shape[0] + 1):
                dst.write(data[band - 1], band)

    def _aggregate_results(self):
        max_shape = tuple(max(s) for s in zip(*[arr.shape for arr in self.result_list]))
        padded_result_list = [
            self._pad_array(arr, max_shape) for arr in self.result_list
        ]
        result_stack = np.ma.stack(padded_result_list)

        operations = {
            "mean": np.ma.mean,
            "median": np.ma.median,
            "max": np.ma.max,
            "min": np.ma.min,
            "std": np.ma.std,
            "sum": np.ma.sum,
            "var": np.ma.var,
            "mode": lambda arr: mode(arr, axis=0, nan_policy="omit")[0].squeeze(),
        }

        return operations[self.operation](result_stack, axis=0)

    def save_aggregated_result_with_colormap(self, result_aggregate, output_file):
        result_aggregate = np.ma.masked_invalid(result_aggregate)
        image = self._create_image(result_aggregate)
        self._plot_result(image, output_file)
        self._save_geotiff(result_aggregate, output_file)

    def _create_image(self, data):
        if data.shape[0] == 1:
            result_normalized = (data[0] - data[0].min()) / (
                data[0].max() - data[0].min()
            )
            colormap = plt.get_cmap(self.cmap)
            result_colored = colormap(result_normalized)
            return (result_colored[:, :, :3] * 255).astype(np.uint8)
        else:
            image_array = np.transpose(data, (1, 2, 0))
            image_array = (
                (image_array - image_array.min())
                / (image_array.max() - image_array.min())
                * 255
            )
            return image_array.astype(np.uint8)

    def _plot_result(self, image, output_file):
        plt.figure(figsize=(10, 10))
        plt.imshow(image)
        plt.title(f"Aggregated {self.operation} Custom Band Calculation")
        plt.ylabel(
            f"From {self.start_date} to {self.end_date}\nCloud Cover < {self.cloud_cover}%\nBounding Box: {self.bbox}\nTotal Images: {len(self.result_list)}"
        )
        if image.ndim == 2:
            plt.xlabel(f"Normalized Range: {image.min():.2f} to {image.max():.2f}")
            cbar = plt.colorbar(
                plt.cm.ScalarMappable(
                    norm=Normalize(vmin=image.min(), vmax=image.max()),
                    cmap=plt.get_cmap(self.cmap),
                ),
                ax=plt.gca(),
            )
            cbar.set_label("Normalized Value")
        plt.savefig(output_file.replace(".tif", "_colormap.png"))
        plt.close()

    def _pad_array(self, array, target_shape, fill_value=np.nan):
        pad_width = [
            (0, max(0, target - current))
            for current, target in zip(array.shape, target_shape)
        ]
        return np.pad(array, pad_width, mode="constant", constant_values=fill_value)

    def add_text_to_image(self, image_path, text):
        with rasterio.open(image_path) as src:
            image_array = (
                src.read(1)
                if src.count == 1
                else np.dstack([src.read(i) for i in range(1, 4)])
            )
            image_array = (
                (image_array - image_array.min())
                / (image_array.max() - image_array.min())
                * 255
            )
            image = Image.fromarray(image_array.astype(np.uint8))

        plt.figure(figsize=(10, 10))
        plt.imshow(image, cmap=self.cmap if src.count == 1 else None)
        plt.axis("off")
        plt.text(10, 10, text, color="white", fontsize=12, backgroundcolor="black")
        temp_image_path = os.path.splitext(image_path)[0] + "_text.png"
        plt.savefig(temp_image_path, bbox_inches="tight", pad_inches=0)
        plt.close()
        return temp_image_path

    @staticmethod
    def create_gif(image_list, output_path, duration=10):
        images = [Image.open(image_path) for image_path in image_list]
        max_width = max(image.width for image in images)
        max_height = max(image.height for image in images)
        resized_images = [
            image.resize((max_width, max_height), Image.LANCZOS) for image in images
        ]
        iio.imwrite(output_path, resized_images, duration=duration, loop=0)
        print(f"Saved GIF to {output_path}")

    @staticmethod
    def zip_files(file_list, zip_path):
        with zipfile.ZipFile(zip_path, "w") as zipf:
            for file in file_list:
                zipf.write(file, os.path.basename(file))
        print(f"Saved ZIP to {zip_path}")
        for file in file_list:
            os.remove(file)

    def compute(self):
        print("Engine starting...")
        os.makedirs(self.output_dir, exist_ok=True)
        if not self.band1:
            raise Exception("Band1 is required")

        print("Searching STAC API...")
        self._process_images()

        if self.result_list and self.operation:
            print("Aggregating results...")
            result_aggregate = self._aggregate_results()
            output_file = os.path.join(
                self.output_dir, "custom_band_output_aggregate.tif"
            )
            print("Saving aggregated result with colormap...")
            self.save_aggregated_result_with_colormap(result_aggregate, output_file)

        if self.timeseries:
            print("Creating GIF and zipping TIFF files...")
            if self.intermediate_images:
                self.create_gif(
                    self.intermediate_images_with_text,
                    os.path.join(self.output_dir, "output.gif"),
                )
                self.zip_files(
                    self.intermediate_images,
                    os.path.join(self.output_dir, "tiff_files.zip"),
                )
            else:
                print("No images found for the given parameters")


if __name__ == "__main__":
    # Example usage
    bbox = [83.84765625, 28.22697003891833, 83.935546875, 28.304380682962773]
    start_date = "2024-12-15"
    end_date = "2024-12-31"
    cloud_cover = 30
    formula = "(band2-band1)/(band2+band1)"  # NDVI formula
    band1 = "red"
    band2 = "nir"
    operation = "median"
    timeseries = True
    output_dir = "./output"
    os.makedirs(output_dir, exist_ok=True)

    processor = VCubeProcessor(
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
    )
    processor.compute()
