import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

import numpy as np
import rasterio
from pyproj import Transformer
from rasterio.windows import from_bounds
from tqdm import tqdm

from .utils import (
    filter_intersected_features,
    remove_overlapping_sentinel2_tiles,
    search_stac_api,
    smart_filter_images,
    zip_files,
)

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


class ExtractProcessor:
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

    def _get_band_urls(self, features):
        band_urls = [
            [feature["assets"][band]["href"] for band in self.bands_list]
            for feature in features
        ]
        return band_urls

    def _fetch_and_save_bands(self, band_urls, feature_id):
        try:
            bands = []
            bands_meta = []
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
                    bands.append(band_data)
                    bands_meta.append(band_url.split("/")[-1].split(".")[0])
            stacked_bands = np.stack(bands)
            output_file = os.path.join(
                self.output_dir, f"{feature_id}_bands_export.tif"
            )
            self._save_geotiff(stacked_bands, output_file, bands_meta)
            return output_file
        except Exception as ex:
            print(f"Error fetching bands: {ex}")
            return None

    def _save_geotiff(self, bands, output_file, bands_meta=None):

        band_shape = bands.shape
        nodata_value = -9999
        bands = np.where(np.isnan(bands), nodata_value, bands)
        with rasterio.open(
            output_file,
            "w",
            driver="GTiff",
            height=bands.shape[1],
            width=bands.shape[2],
            count=len(bands),
            dtype=bands.dtype,
            crs=self.crs,
            transform=self.transform,
            nodata=nodata_value,
        ) as dst:
            for band in range(1, band_shape[0] + 1):
                dst.write(bands[band - 1], band)
                if bands_meta:
                    dst.set_band_description(band, bands_meta[band - 1])

    def extract(self):
        print("Extracting bands...")
        os.makedirs(self.output_dir, exist_ok=True)

        features = search_stac_api(
            self.bbox,
            self.start_date,
            self.end_date,
            self.cloud_cover,
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
            print(
                f"Scenes after applying smart filter: {len(overlapping_features_removed)}"
            )

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
                    result_lists.append(result)
        else:
            for band_urls, feature in tqdm(
                zip(band_urls_list, overlapping_features_removed),
                total=len(band_urls_list),
                desc="Extracting Bands",
                file=self.log_file,
            ):
                result = self._fetch_and_save_bands(band_urls, feature["id"])
                result_lists.append(result)
        if self.zip_output:
            zip_files(
                result_lists,
                os.path.join(self.output_dir, "tiff_files.zip"),
            )


if __name__ == "__main__":
    # Example usage
    bbox = [83.84765625, 28.22697003891833, 83.935546875, 28.304380682962773]
    start_date = "2024-12-15"
    end_date = "2024-12-31"
    cloud_cover = 30
    bands_list = ["red", "nir", "green"]
    output_dir = "./extracted_bands"
    workers = 1  # Number of parallel workers
    os.makedirs(output_dir, exist_ok=True)

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
