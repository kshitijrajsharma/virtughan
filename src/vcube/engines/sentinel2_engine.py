import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import rasterio
from tqdm import tqdm
from PIL import Image

from ..utils.common import (
    filter_intersected_features,
    search_stac_api,
    smart_filter_images,
    zip_files,
)
from ..utils.sentinel2_utils import (
    remove_overlapping_sentinel2_tiles,
)
from .engine_common import EngineCommon  # Inherit common methods

matplotlib.use("Agg")


class VCubeProcessor(EngineCommon):
    """
    Processor for Sentinel-2 virtual computation cubes.
    """

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
        log_file=sys.stdout,
        cmap="RdYlGn",
        workers=1,
        smart_filter=True,
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
        self.workers = workers
        self.result_list = []
        self.dates = []
        self.crs = None
        self.transform = None
        self.intermediate_images = []
        self.intermediate_images_with_text = []
        self.use_smart_filter = smart_filter
    def _get_band_urls(self, features):
        band1_urls = [feature["assets"][self.band1]["href"] for feature in features]
        band2_urls = (
            [feature["assets"][self.band2]["href"] for feature in features]
            if self.band2
            else [None] * len(features)
        )
        return band1_urls, band2_urls

    def fetch_process_custom_band(self, band1_url, band2_url):
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
                        min_x, min_y, max_x, max_y = self._transform_bbox(band2_cog.crs)
                        band2_window = self._calculate_window(
                            band2_cog, min_x, min_y, max_x, max_y
                        )
                        if self._is_window_out_of_bounds(band2_window):
                            return None, None, None
                        band2 = band2_cog.read(window=band2_window).astype(float)
                        result = eval(self.formula)
                else:
                    result = eval(self.formula) if band1.shape[0] == 1 else band1

            return (
                result,
                band1_cog.crs,
                band1_cog.window_transform(band1_window),
                band1_url,
            )
        except Exception as e:
            print(f"Error fetching image: {e}")
            return None, None, None
    def _process_images(self):
        features = search_stac_api(
            self.bbox,
            self.start_date,
            self.end_date,
            self.cloud_cover,
            collection="sentinel-2-l2a"
        )
        print(f"Total scenes found: {len(features)}")
        filtered_features = filter_intersected_features(features, self.bbox)
        print(f"Scenes covering input area: {len(filtered_features)}")
        overlapping_features_removed = remove_overlapping_sentinel2_tiles(
            filtered_features
        )
        print(f"Scenes after removing overlaps: {len(overlapping_features_removed)}")

        if self.use_smart_filter:
            overlapping_features_removed = smart_filter_images(
                overlapping_features_removed, self.start_date, self.end_date
            )
            print(f"Scenes after applying smart filter: {len(overlapping_features_removed)}")

        band1_urls, band2_urls = self._get_band_urls(overlapping_features_removed)

        if self.workers > 1:
            print("Using Parallel Processing...")
            with ThreadPoolExecutor(max_workers=self.workers) as executor:
                futures = [
                    executor.submit(
                        self.fetch_process_custom_band, band1_url, band2_url
                    )
                    for band1_url, band2_url in zip(band1_urls, band2_urls)
                ]
                for future in tqdm(
                    as_completed(futures),
                    total=len(futures),
                    desc="Computing Band Calculation",
                    file=self.log_file,
                ):
                    result, crs, transform, name_url = future.result()
                    if result is not None:
                        self.result_list.append(result)
                        self.crs = crs
                        self.transform = transform
                        parts = name_url.split("/")
                        image_name = parts[-2]
                        self.dates.append(image_name.split("_")[2])
                        if self.timeseries:
                            self._save_intermediate_image(result, image_name)
        else:
            for band1_url, band2_url in tqdm(
                zip(band1_urls, band2_urls),
                total=len(band1_urls),
                desc="Computing Band Calculation",
                file=self.log_file,
            ):
                result, self.crs, self.transform, name_url = (
                    self.fetch_process_custom_band(band1_url, band2_url)
                )
                if result is not None:
                    self.result_list.append(result)
                    parts = name_url.split("/")
                    image_name = parts[-2]
                    self.dates.append(image_name.split("_")[2])
                    if self.timeseries:
                        self._save_intermediate_image(result, image_name)
    def _save_intermediate_image(self, result, image_name):
        output_file = os.path.join(self.output_dir, f"{image_name}_result.tif")
        self._save_geotiff(result, output_file)
        self.intermediate_images.append(output_file)
        self.intermediate_images_with_text.append(
            self.add_text_to_image(output_file, image_name)
        )

    def _aggregate_results(self):
        sorted_dates_and_results = sorted(
            zip(self.dates, self.result_list), key=lambda x: x[0]
        )
        sorted_dates, sorted_results = zip(*sorted_dates_and_results)
        max_shape = tuple(max(s) for s in zip(*[arr.shape for arr in sorted_results]))
        padded_result_list = [self._pad_array(arr, max_shape) for arr in sorted_results]
        result_stack = np.ma.stack(padded_result_list)

        operations = {
            "mean": np.ma.mean,
            "median": np.ma.median,
            "max": np.ma.max,
            "min": np.ma.min,
            "std": np.ma.std,
            "sum": np.ma.sum,
            "var": np.ma.var,
        }
        aggregated_result = operations[self.operation](result_stack, axis=0)

        dates = sorted_dates
        dates_numeric = np.arange(len(dates))
        values_per_date = operations[self.operation](result_stack, axis=(1, 2, 3))

        slope, intercept = np.polyfit(dates_numeric, values_per_date, 1)
        trend_line = slope * dates_numeric + intercept

        plt.figure(figsize=(10, 5))
        plt.plot(dates, values_per_date, marker="o", linestyle="-", label=f"{self.operation.capitalize()} Value")
        plt.plot(dates, trend_line, color="red", linestyle="--", label="Trend Line")
        plt.xlabel("Date")
        plt.ylabel(f"{self.operation.capitalize()} Value")
        plt.title(f"{self.operation.capitalize()} Value Over Time")
        plt.grid(True)
        plt.xticks(rotation=45)
        plt.legend()
        plt.tight_layout()

        plt.savefig(os.path.join(self.output_dir, "values_over_time.png"))
        plt.close()

        return aggregated_result

    def compute(self):
        print("Engine starting...")
        os.makedirs(self.output_dir, exist_ok=True)
        if not self.band1:
            raise Exception("Band1 is required")
        print("Searching STAC .....")
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
                zip_files(
                    self.intermediate_images,
                    os.path.join(self.output_dir, "tiff_files.zip"),
                )
            else:
                print("No images found for the given parameters")

    def save_aggregated_result_with_colormap(self, result_aggregate, output_file):
        result_aggregate = np.ma.masked_invalid(result_aggregate)
        image = self._create_image(result_aggregate)
        self._plot_result(image, output_file)
        self._save_geotiff(result_aggregate, output_file)


if __name__ == "__main__":
    bbox = [83.84765625, 28.22697003891833, 83.935546875, 28.304380682962773]
    start_date = "2024-12-15"
    end_date = "2024-12-31"
    cloud_cover = 30
    formula = "(band2-band1)/(band2+band1)"
    band1 = "red"
    band2 = "nir"
    operation = "median"
    timeseries = True
    output_dir = "./output"
    workers = 1

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
        workers=workers,
    )
    processor.compute()
