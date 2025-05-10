import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.warp import reproject
from tqdm import tqdm
import json

from ..utils.common import (
    filter_intersected_features,
    search_stac_api,
    smart_filter_images,
    zip_files,
)
from ..utils.sentinel2_utils import remove_overlapping_sentinel2_tiles
from .extractor_common import ExtractorCommon

VALID_BANDS = {
    "red": "Red - 10m",
    "green": "Green - 10m",
    "blue": "Blue - 10m",
    "nir": "NIR 1 - 10m",
    "swir22": "SWIR 2.2μm - 20m",
    "rededge2": "Red Edge 2 - 20m",
    "rededge3": "Red Edge 3 - 20m",
    "rededge1": "Red Edge 1 - 20m",
    "swir16": "SWIR 1.6μm - 20m",
    "wvp": "Water Vapour (WVP)",
    "nir08": "NIR 2 - 20m",
    "aot": "Aerosol optical thickness (AOT)",
    "coastal": "Coastal - 60m",
    "nir09": "NIR 3 - 60m",
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
                f"Band names should be one of: {', '.join(VALID_BANDS.keys())}"
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
            dst_transform = None

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

                    band_data = band_cog.read(1, window=band_window).astype(float)
                    transform = band_cog.window_transform(band_window)

                    if band_cog.res != lowest_resolution:
                        scale_x = band_cog.res[0] / lowest_resolution[0]
                        scale_y = band_cog.res[1] / lowest_resolution[1]
                        transform *= rasterio.Affine.scale(scale_x, scale_y)
                        band_data, _ = reproject(
                            source=band_data,
                            destination=np.empty(
                                (
                                    int(band_data.shape[0] * scale_y),
                                    int(band_data.shape[1] * scale_x),
                                ),
                                dtype=band_data.dtype,
                            ),
                            src_transform=band_cog.window_transform(band_window),
                            src_crs=band_cog.crs,
                            dst_transform=transform,
                            dst_crs=band_cog.crs,
                            resampling=Resampling.average,
                        )

                    bands.append(band_data)
                    bands_meta.append(band_url.split("/")[-1].split(".")[0])
                    self.crs = band_cog.crs
                    dst_transform = transform

            self.transform = dst_transform
            stacked_bands = np.stack(bands)
            output_file = os.path.join(
                self.output_dir, f"{feature_id}_bands_export.tif"
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
            collection="sentinel-2-l2a"
        )
        print(f"Total scenes found: {len(features)}")
        filtered_features = filter_intersected_features(features, self.bbox)
        print(f"Scenes covering input area: {len(filtered_features)}")
        overlapping_features_removed = remove_overlapping_sentinel2_tiles(filtered_features)
        print(f"Scenes after removing overlaps: {len(overlapping_features_removed)}")

        if self.use_smart_filter:
            overlapping_features_removed = smart_filter_images(
                overlapping_features_removed, self.start_date, self.end_date
            )
            print(f"Scenes after applying smart filter: {len(overlapping_features_removed)}")

        band_urls_list = self._get_band_urls(overlapping_features_removed)
        result_lists = []

        if self.workers > 1:
            print("Using Parallel Processing...")
            with ThreadPoolExecutor(max_workers=self.workers) as executor:
                futures = [
                    executor.submit(
                        self._fetch_and_save_bands, band_urls, feature["id"]
                    )
                    for band_urls, feature in zip(
                        band_urls_list, overlapping_features_removed
                    )
                ]
                for future in tqdm(
                    as_completed(futures),
                    total=len(futures),
                    desc="Extracting Bands",
                    file=self.log_file,
                ):
                    result = future.result()
                    if result:
                        result_lists.append(result)
        else:
            for band_urls, feature in tqdm(
                zip(band_urls_list, overlapping_features_removed),
                total=len(band_urls_list),
                desc="Extracting Bands",
                file=self.log_file,
            ):
                result = self._fetch_and_save_bands(band_urls, feature["id"])
                if result:
                    result_lists.append(result)

        if self.zip_output:
            zip_files(
                result_lists,
                os.path.join(self.output_dir, "tiff_files.zip"),
            )


if __name__ == "__main__":
    bbox = [83.84765625, 28.22697003891833, 83.935546875, 28.304380682962773]
    start_date = "2024-12-15"
    end_date = "2024-12-31"
    cloud_cover = 30
    bands_list = ["red", "nir", "green"]
    output_dir = "./extracted_bands"
    workers = 1

    extractor = ExtractProcessor(
        bbox,
        start_date,
        end_date,
        cloud_cover,
        bands_list,
        output_dir,
        workers=workers,
    )
    extractor.extract()
