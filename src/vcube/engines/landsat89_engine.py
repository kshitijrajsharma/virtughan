import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import rasterio
from tqdm import tqdm
from PIL import Image
from planetary_computer import sign
from urllib.parse import urlparse
from datetime import datetime

from ..utils.common import (
    filter_intersected_features,
    search_stac_api,
    smart_filter_images,
    zip_files,
)
from ..utils.landsat89_utils import (
    remove_overlapping_landsat_tiles,
)
from ..engines.engine_common import EngineCommon

matplotlib.use("Agg")

class LandsatProcessor(EngineCommon):
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
    
    def _parse_dates(self, image_name):
        date = image_name.split("_")[3]
        parsed_date = datetime.strptime(date, "%Y%m%d").strftime("%Y-%m-%d")
        return parsed_date

    def _get_band_urls(self, features):
        band1_urls = [sign(feature["assets"][self.band1]["href"]) for feature in features]
        band2_urls = (
            [sign(feature["assets"][self.band2]["href"]) for feature in features]
            if self.band2 else [None] * len(features)
        )
        return band1_urls, band2_urls

    def fetch_process_custom_band(self, band1_url, band2_url):
        try:
            # print(f"Fetching Band1 URL: {band1_url}")
            with rasterio.open(band1_url) as band1_cog:
                min_x, min_y, max_x, max_y = self._transform_bbox(band1_cog.crs)
                band1_window = self._calculate_window(band1_cog, min_x, min_y, max_x, max_y)
                if self._is_window_out_of_bounds(band1_window):
                    return None, None, None, None
                band1 = band1_cog.read(window=band1_window).astype(float)

                if band2_url:
                    # print(f"Fetching Band2 URL: {band2_url}")
                    with rasterio.open(band2_url) as band2_cog:
                        band2_window = self._calculate_window(band2_cog, min_x, min_y, max_x, max_y)
                        if self._is_window_out_of_bounds(band2_window):
                            return None, None, None, None
                        band2 = band2_cog.read(window=band2_window).astype(float)
                        result = eval(self.formula, {}, {"band1": band1, "band2": band2})
                else:
                    result = eval(self.formula, {}, {"band1": band1}) if band1.shape[0] == 1 else band1

            return result, band1_cog.crs, band1_cog.window_transform(band1_window), band1_url

        except Exception as e:
            print(f"Error fetching image: {e}")
            return None, None, None, None

    def _process_images(self):
        features = search_stac_api(
            self.bbox,
            self.start_date,
            self.end_date,
            self.cloud_cover,
            collection="landsat-c2-l2"
        )
        print(f"Total scenes found: {len(features)}")
        features = filter_intersected_features(features, self.bbox)
        print(f"Scenes covering input area: {len(features)}")
        features = remove_overlapping_landsat_tiles(features)
        print(f"Scenes after removing overlaps: {len(features)}")

        if self.use_smart_filter:
            features = smart_filter_images(features, self.start_date, self.end_date)
            print(f"Scenes after smart filtering: {len(features)}")

        band1_urls, band2_urls = self._get_band_urls(features)

        if self.workers > 1:
            with ThreadPoolExecutor(max_workers=self.workers) as executor:
                futures = [executor.submit(self.fetch_process_custom_band, b1, b2)
                           for b1, b2 in zip(band1_urls, band2_urls)]
                for future in tqdm(as_completed(futures), total=len(futures), desc="Computing Band Calculation", file=self.log_file):
                    try:
                        result, crs, transform, url = future.result()
                        if result is not None:
                            self.result_list.append(result)
                            self.crs = crs
                            self.transform = transform
                            self.dates.append((self._parse_dates(url.split("/")[-2]), url.split("/")[-2]))
                            if self.timeseries:
                                self._save_intermediate_image(result, url.split("/")[-2])
                    except Exception as e:
                        print(f"Error processing future result: {e}")
        else:
            for b1, b2 in tqdm(zip(band1_urls, band2_urls), total=len(band1_urls), desc="Computing Band Calculation", file=self.log_file):
                result, crs, transform, url = self.fetch_process_custom_band(b1, b2)
                if result is not None:
                    self.result_list.append(result)
                    self.crs = crs
                    self.transform = transform
                    self.dates.append((self._parse_dates(url.split("/")[-2]), url.split("/")[-2]))
                    if self.timeseries:
                        self._save_intermediate_image(result, url.split("/")[-2])

    def compute(self):
        print("Engine starting...")
        os.makedirs(self.output_dir, exist_ok=True)

        if not self.band1:
            raise Exception("Band1 is required")

        self._process_images()

        if self.result_list and self.operation:
            print("Aggregating results...")
            
            result_agg, sorted_dates, result_stack = self._aggregate_results()
            out_tif = os.path.join(self.output_dir, "custom_band_output_aggregate.tif")
            self._save_geotiff(result_agg, out_tif)
            self._plot_result(result_agg, out_tif)

            if self.timeseries:
                self._plot_values_over_time(sorted_dates, result_stack)
                zip_files(self.intermediate_images, os.path.join(self.output_dir, "tiff_files.zip"))
                self.create_gif(self.intermediate_images_with_text, os.path.join(self.output_dir, "output.gif"))

    def _aggregate_results(self):
        # sorted_dates, sorted_results = zip(*sorted(zip(self.dates, self.result_list)))
        sorted_info = sorted(zip(self.dates, self.result_list), key=lambda x: x[0][0])  # sort by date
        sorted_dates = [datetime.strptime(date_url[0], "%Y-%m-%d").strftime("%Y-%m-%d") for date_url, _ in sorted_info]
        sorted_results = [res for _, res in sorted_info]

        max_shape = tuple(max(s) for s in zip(*[r.shape for r in sorted_results]))
        padded = [self._pad_array(r, max_shape) for r in sorted_results]
        stack = np.ma.stack(padded)

        ops = {
            "mean": np.ma.mean,
            "median": np.ma.median,
            "max": np.ma.max,
            "min": np.ma.min,
            "std": np.ma.std,
        }
        return ops[self.operation](stack, axis=0), sorted_dates, stack

    def _plot_result(self, result, output_file):
        result = np.ma.masked_invalid(result)
        image = self._create_image(result)
        plt.figure(figsize=(10, 10))
        plt.imshow(image)
        plt.axis("off")
        plt.title("Landsat Aggregated Output")
        plt.savefig(output_file.replace(".tif", "_colormap.png"), bbox_inches="tight")
        plt.close()

    def _create_image(self, result):
        if result.ndim == 3 and result.shape[0] == 1:
            result = result[0]
        norm = (result - result.min()) / (result.max() - result.min() + 1e-6)
        cmap = plt.get_cmap(self.cmap)
        colored = cmap(norm)
        return (colored[:, :, :3] * 255).astype(np.uint8)

    def _extract_image_name(self, url):
        path = urlparse(url).path
        filename = os.path.basename(path)  # e.g., 'LC09_L2SP_142041_20250424_20250425_02_T1_SR_B4.TIF'
        return filename.split("_SR_")[0]  # e.g., 'LC09_L2SP_142041_20250424_20250425_02_T1'


    def _save_intermediate_image(self, result, image_name):
        image_name = self._extract_image_name(image_name)
        out_file = os.path.join(self.output_dir, f"{image_name}_result.tif")
        self._save_geotiff(result, out_file)
        self.intermediate_images.append(out_file)

        # Optional: add image name text overlay
        image_with_text = self.add_text_to_image(out_file, image_name)
        self.intermediate_images_with_text.append(image_with_text)


    def _plot_values_over_time(self, sorted_dates, result_stack):
        # parsed_dates = [
        #     datetime.strptime(name.split("_")[3], "%Y%m%d").strftime("%Y-%m-%d")
        #     for name in sorted_dates
        # ]
        dates = sorted_dates
        # print(dates)
        dates_numeric = np.arange(len(dates))

        operations = {
            "mean": np.ma.mean,
            "median": np.ma.median,
            "max": np.ma.max,
            "min": np.ma.min,
            "std": np.ma.std,
            "sum": np.ma.sum,
            "var": np.ma.var,
        }

        # Mask NaNs in the stack
        result_stack = np.ma.masked_invalid(result_stack)
        values_per_date = operations[self.operation](result_stack, axis=(1, 2, 3))

        # Ensure no masked entries before regression
        valid = ~values_per_date.mask if hasattr(values_per_date, "mask") else np.ones_like(values_per_date, dtype=bool)
        dates_numeric_valid = dates_numeric[valid]
        values_valid = values_per_date[valid]

        # Compute trend only on valid data
        slope, intercept = np.polyfit(dates_numeric_valid, values_valid, 1)
        trend_line = slope * dates_numeric_valid + intercept

        plt.figure(figsize=(10, 5))
        plt.plot(np.array(dates)[valid], values_valid, marker="o", linestyle="-", label=f"{self.operation.capitalize()} Value")
        plt.plot(np.array(dates)[valid], trend_line, color="red", linestyle="--", label="Trend Line")
        plt.xlabel("Date")
        plt.ylabel(f"{self.operation.capitalize()} Value")
        plt.title(f"{self.operation.capitalize()} Value Over Time")
        plt.grid(True)
        plt.xticks(rotation=45)
        plt.legend()
        plt.tight_layout()
        plt.savefig(os.path.join(self.output_dir, "values_over_time.png"))
        plt.close()



if __name__ == "__main__":
    bbox = [83.84765625, 28.22697003891833, 83.935546875, 28.304380682962773]
    start_date = "2024-12-15"
    end_date = "2024-12-31"
    cloud_cover = 30
    formula = "(band2-band1)/(band2+band1)"
    band1 = "red"
    band2 = "nir08"
    operation = "median"
    timeseries = True
    output_dir = "./output"

    processor = LandsatProcessor(
        bbox, start_date, end_date, cloud_cover,
        formula, band1, band2, operation,
        timeseries, output_dir
    )
    processor.compute()
