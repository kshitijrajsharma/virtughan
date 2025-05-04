import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import rasterio
from PIL import Image
from tqdm import tqdm
from pyproj import Transformer
from rasterio.windows import from_bounds

from ..utils.common import (
    filter_intersected_features,
    search_stac_api,
    smart_filter_images,
    zip_files,
)
from ..utils.landsat89_utils import (
    remove_overlapping_landsat_tiles,
)
# from ..engines.engine_common import (
#     _transform_bbox as transform_bbox,
#     calculate_window,
#     is_window_out_of_bounds,
#     pad_array,
#     add_text_to_image,
#     create_gif,
# )
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
    # def _transform_bbox(self, crs):
    #     return transform_bbox(self.bbox, crs)

    # def _calculate_window(self, cog, min_x, min_y, max_x, max_y):
    #     return calculate_window(cog, min_x, min_y, max_x, max_y)

    # def _is_window_out_of_bounds(self, window):
    #     return is_window_out_of_bounds(window)

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
            collection="landsat-c2-l2"
        )
        print(f"Total scenes found: {len(features)}")
        filtered_features = filter_intersected_features(features, self.bbox)
        print(f"Scenes covering input area: {len(filtered_features)}")
        filtered_features = remove_overlapping_landsat_tiles(filtered_features)
        print(f"Scenes after removing overlaps: {len(filtered_features)}")

        if self.use_smart_filter:
            filtered_features = smart_filter_images(
                filtered_features, self.start_date, self.end_date
            )
            print(f"Scenes after smart filtering: {len(filtered_features)}")

        band1_urls, band2_urls = self._get_band_urls(filtered_features)

        if self.workers > 1:
            print("Using parallel processing...")
            with ThreadPoolExecutor(max_workers=self.workers) as executor:
                futures = [
                    executor.submit(self.fetch_process_custom_band, b1, b2)
                    for b1, b2 in zip(band1_urls, band2_urls)
                ]
                for future in tqdm(
                    as_completed(futures),
                    total=len(futures),
                    desc="Computing",
                    file=self.log_file,
                ):
                    result, crs, transform, url = future.result()
                    if result is not None:
                        self.result_list.append(result)
                        self.crs = crs
                        self.transform = transform
                        self.dates.append(url.split("/")[-2])
                        if self.timeseries:
                            self._save_intermediate_image(result, url.split("/")[-2])
        else:
            for b1, b2 in tqdm(
                zip(band1_urls, band2_urls),
                total=len(band1_urls),
                desc="Computing",
                file=self.log_file,
            ):
                result, crs, transform, url = self.fetch_process_custom_band(b1, b2)
                if result is not None:
                    self.result_list.append(result)
                    self.crs = crs
                    self.transform = transform
                    self.dates.append(url.split("/")[-2])
                    if self.timeseries:
                        self._save_intermediate_image(result, url.split("/")[-2])

    def _save_intermediate_image(self, result, image_name):
        output_file = os.path.join(self.output_dir, f"{image_name}_result.tif")
        self._save_geotiff(result, output_file)
        self.intermediate_images.append(output_file)
        self.intermediate_images_with_text.append(
            add_text_to_image(output_file, image_name, self.cmap)
        )

    def _aggregate_results(self):
        sorted_dates_and_results = sorted(
            zip(self.dates, self.result_list), key=lambda x: x[0]
        )
        sorted_dates, sorted_results = zip(*sorted_dates_and_results)
        max_shape = tuple(max(s) for s in zip(*[arr.shape for arr in sorted_results]))
        padded_result_list = [pad_array(arr, max_shape) for arr in sorted_results]
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

        return aggregated_result, sorted_dates, result_stack

    def compute(self):
        print("Engine starting...")
        os.makedirs(self.output_dir, exist_ok=True)

        if not self.band1:
            raise ValueError("Band1 is required")

        self._process_images()

        if self.result_list and self.operation:
            print("Aggregating results...")
            aggregated_result, sorted_dates, result_stack = self._aggregate_results()

            output_file = os.path.join(
                self.output_dir, "landsat_custom_band_output_aggregate.tif"
            )
            print("Saving aggregate TIFF and PNG...")
            self._save_geotiff(aggregated_result, output_file)
            self._plot_result(aggregated_result, output_file)

        if self.timeseries and self.intermediate_images:
            print("Creating GIF...")
            create_gif(
                self.intermediate_images_with_text,
                os.path.join(self.output_dir, "output.gif"),
            )
            zip_files(
                self.intermediate_images,
                os.path.join(self.output_dir, "tiff_files.zip"),
            )

    # def _save_geotiff(self, data, output_file):
    #     data = np.where(np.isnan(data), -9999, data)
    #     with rasterio.open(
    #         output_file,
    #         "w",
    #         driver="GTiff",
    #         height=data.shape[1],
    #         width=data.shape[2],
    #         count=data.shape[0],
    #         dtype=data.dtype,
    #         crs=self.crs,
    #         transform=self.transform,
    #         nodata=-9999,
    #     ) as dst:
    #         for band in range(1, data.shape[0] + 1):
    #             dst.write(data[band - 1], band)

    def _plot_result(self, result, output_file):
        if result.shape[0] == 1:
            normed = (result[0] - result[0].min()) / (result[0].max() - result[0].min())
            cmap = plt.get_cmap(self.cmap)
            colored = cmap(normed)
            image = (colored[:, :, :3] * 255).astype(np.uint8)
        else:
            image = np.transpose(result, (1, 2, 0))
            image = ((image - image.min()) / (image.max() - image.min()) * 255).astype(np.uint8)

        plt.figure(figsize=(10, 10))
        plt.imshow(image)
        plt.axis("off")
        plt.title("Landsat Band Aggregated Output")
        plt.savefig(output_file.replace(".tif", "_colormap.png"), bbox_inches="tight")
        plt.close()



if __name__ == "__main__":
    bbox = [83.84765625, 28.22697003891833, 83.935546875, 28.304380682962773]
    start_date = "2024-12-15"
    end_date = "2024-12-31"
    cloud_cover = 30
    formula = "(band2-band1)/(band2+band1)"  # e.g., NDVI
    band1 = "red"
    band2 = "nir"
    operation = "median"
    timeseries = True
    output_dir = "./output"
    workers = 1

    processor = LandsatProcessor(
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

