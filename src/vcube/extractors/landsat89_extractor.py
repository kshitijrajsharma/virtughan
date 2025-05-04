import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.warp import reproject
from tqdm import tqdm

from ..utils.common import (
    filter_intersected_features,
    search_stac_api,
    smart_filter_images,
    zip_files,
)
from ..utils.landsat89_utils import remove_overlapping_landsat_tiles
from .extractor_common import ExtractorCommon

# ✅ Landsat 8/9 supported bands
VALID_BANDS = {
    "coastal": "Coastal/Aerosol Band (Band 1)",
    "blue": "Blue Band (Band 2)",
    "green": "Green Band (Band 3)",
    "red": "Red Band (Band 4)",
    "nir": "Near Infrared Band (Band 5)",
    "swir1": "Shortwave Infrared Band 1 (Band 6)",
    "swir2": "Shortwave Infrared Band 2 (Band 7)",
    "pan": "Panchromatic Band (Band 8)",
    "cirrus": "Cirrus Band (Band 9)",
    "lwir1": "Thermal Infrared Band 10",
    "lwir2": "Thermal Infrared Band 11",
}
class ExtractProcessor(ExtractorCommon):
    def __init__(
        self,
        bbox,
        start_date,
        end_date,
        cloud_cover,
        bands_list,
        output_dir,
        log_file=sys.stdout,
        workers=1,
        zip_output=False,
        smart_filter=True,
    ):
        self.bbox = bbox
        self.start_date = start_date
        self.end_date = end_date
        self.cloud_cover = cloud_cover
        self.bands_list = bands_list
        self.output_dir = output_dir
        self.log_file = log_file
        self.workers = workers
        self.zip_output = zip_output
        self.crs = None
        self.transform = None
        self.use_smart_filter = smart_filter

        self._validate_bands_list()

    def _validate_bands_list(self):
        invalid_bands = [band for band in self.bands_list if band not in VALID_BANDS]
        if invalid_bands:
            raise ValueError(
                f"Invalid band names: {', '.join(invalid_bands)}. "
                f"Valid bands: {', '.join(VALID_BANDS.keys())}"
            )

    def _get_band_urls(self, features):
        return [
            [feature["assets"][band]["href"] for band in self.bands_list]
            for feature in features
        ]
    def _fetch_and_save_bands(self, band_urls, feature_id):
        try:
            bands = []
            bands_meta = []
            resolutions = []

            for band_url in band_urls:
                with rasterio.open(band_url) as band_cog:
                    resolutions.append(band_cog.res)

            lowest_resolution = max(resolutions, key=lambda res: res[0] * res[1])

            for band_url in band_urls:
                with rasterio.open(band_url) as band_cog:
                    min_x, min_y, max_x, max_y = self._transform_bbox(band_cog.crs)
                    band_window = self._calculate_window(
                        band_cog, min_x, min_y, max_x, max_y
                    )

                    if self._is_window_out_of_bounds(band_window):
                        return None

                    self.crs = band_cog.crs
                    self.transform = band_cog.transform

                    band_data = band_cog.read(1, window=band_window).astype(float)

                    if band_cog.res != lowest_resolution:
                        scale_x = band_cog.res[0] / lowest_resolution[0]
                        scale_y = band_cog.res[1] / lowest_resolution[1]
                        band_data = reproject(
                            source=band_data,
                            destination=np.empty(
                                (
                                    int(band_data.shape[0] * scale_y),
                                    int(band_data.shape[1] * scale_x),
                                ),
                                dtype=band_data.dtype,
                            ),
                            src_transform=band_cog.transform,
                            src_crs=band_cog.crs,
                            dst_transform=band_cog.transform
                            * band_cog.transform.scale(scale_x, scale_y),
                            dst_crs=band_cog.crs,
                            resampling=Resampling.average,
                        )[0]

                    bands.append(band_data)
                    bands_meta.append(band_url.split("/")[-1].split(".")[0])

            stacked_bands = np.stack(bands)
            output_file = os.path.join(
                self.output_dir, f"{feature_id}_landsat_bands.tif"
            )
            self._save_geotiff(stacked_bands, output_file, bands_meta)
            return output_file
        except Exception as ex:
            print(f"Error fetching bands: {ex}")
            return None

    def extract(self):
        print("Extracting bands...")
        os.makedirs(self.output_dir, exist_ok=True)

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
        print(f"After removing overlaps: {len(features)}")

        if self.use_smart_filter:
            features = smart_filter_images(features, self.start_date, self.end_date)
            print(f"After smart filter: {len(features)}")

        band_urls_list = self._get_band_urls(features)
        result_list = []

        if self.workers > 1:
            with ThreadPoolExecutor(max_workers=self.workers) as executor:
                futures = [
                    executor.submit(self._fetch_and_save_bands, band_urls, feature["id"])
                    for band_urls, feature in zip(band_urls_list, features)
                ]
                for future in tqdm(as_completed(futures), total=len(futures), desc="Extracting"):
                    result_list.append(future.result())
        else:
            for band_urls, feature in tqdm(
                zip(band_urls_list, features), total=len(band_urls_list), desc="Extracting"
            ):
                result_list.append(self._fetch_and_save_bands(band_urls, feature["id"]))

        if self.zip_output:
            zip_files(result_list, os.path.join(self.output_dir, "tiff_files.zip"))


if __name__ == "__main__":
    bbox = [83.84765625, 28.22697003891833, 83.935546875, 28.304380682962773]
    start_date = "2024-12-15"
    end_date = "2024-12-31"
    cloud_cover = 30
    bands_list = ["red", "nir", "green"]  # adjust as needed
    output_dir = "./output"
    workers = 1
    zip_output = True

    extractor = ExtractProcessor(
        bbox=bbox,
        start_date=start_date,
        end_date=end_date,
        cloud_cover=cloud_cover,
        bands_list=bands_list,
        output_dir=output_dir,
        workers=workers,
        zip_output=zip_output,
    )
    extractor.extract()
