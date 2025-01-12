import asyncio
from io import BytesIO

import matplotlib
import mercantile
import numpy as np
from aiocache import cached
from fastapi import HTTPException
from matplotlib import pyplot as plt
from PIL import Image
from rio_tiler.io import COGReader
from shapely.geometry import box, mapping

from .utils import (
    aggregate_time_series,
    filter_intersected_features,
    filter_latest_image_per_grid,
    remove_overlapping_sentinel2_tiles,
    search_stac_api_async,
    smart_filter_images,
)

matplotlib.use("Agg")


class TileProcessor:
    def __init__(self, cache_time=60):
        self.cache_time = cache_time

    @staticmethod
    def apply_colormap(result, colormap_str):
        result_normalized = (result - result.min()) / (result.max() - result.min())
        colormap = plt.get_cmap(colormap_str)
        result_colored = colormap(result_normalized)
        result_image = (result_colored[:, :, :3] * 255).astype(np.uint8)
        return Image.fromarray(result_image)

    @staticmethod
    async def fetch_tile(url, x, y, z):
        def read_tile():
            with COGReader(url) as cog:
                tile, _ = cog.tile(x, y, z)
                return tile

        return await asyncio.to_thread(read_tile)

    @cached(ttl=60 * 1)
    async def cached_generate_tile(
        self,
        x: int,
        y: int,
        z: int,
        start_date: str,
        end_date: str,
        cloud_cover: int,
        band1: str,
        band2: str,
        formula: str,
        colormap_str: str = "RdYlGn",
        latest: bool = True,
        operation: str = "median",
    ) -> bytes:
        tile = mercantile.Tile(x, y, z)
        bbox = mercantile.bounds(tile)
        bbox_geojson = mapping(box(bbox.west, bbox.south, bbox.east, bbox.north))
        results = await search_stac_api_async(
            bbox_geojson, start_date, end_date, cloud_cover
        )

        if not results:
            raise HTTPException(
                status_code=404, detail="No images found for the given parameters"
            )

        results = filter_intersected_features(
            results, [bbox.west, bbox.south, bbox.east, bbox.north]
        )
        if latest:
            if len(results) > 0:
                results = filter_latest_image_per_grid(results)
                feature = results[0]
                band1_url = feature["assets"][band1]["href"]
                band2_url = feature["assets"][band2]["href"] if band2 else None

                try:
                    tasks = [self.fetch_tile(band1_url, x, y, z)]
                    if band2_url:
                        tasks.append(self.fetch_tile(band2_url, x, y, z))

                    tiles = await asyncio.gather(*tasks)
                    band1 = tiles[0]
                    band2 = tiles[1] if band2_url else None
                except Exception as e:
                    raise HTTPException(status_code=500, detail=str(e))

                if band2 is not None:
                    band1 = band1[0].astype(float)
                    band2 = band2[0].astype(float)
                    result = eval(formula)
                    image = self.apply_colormap(result, colormap_str)
                else:
                    inner_bands = band1.shape[0]
                    if inner_bands == 1:
                        band1 = band1[0].astype(float)
                        result = eval(formula)
                        image = self.apply_colormap(result, colormap_str)
                    else:
                        band1 = band1.transpose(1, 2, 0)
                        image = Image.fromarray(band1)
            else:

                raise HTTPException(
                    status_code=404, detail="No images found for the given parameters"
                )
        else:

            results = remove_overlapping_sentinel2_tiles(results)
            results = smart_filter_images(results, start_date, end_date)
            band1_tiles = []
            band2_tiles = []

            tasks = []
            for feature in results:
                band1_url = feature["assets"][band1]["href"]
                band2_url = feature["assets"][band2]["href"] if band2 else None
                tasks.append(self.fetch_tile(band1_url, x, y, z))
                if band2_url:
                    tasks.append(self.fetch_tile(band2_url, x, y, z))

            try:
                tiles = await asyncio.gather(*tasks)
                for i in range(0, len(tiles), 2 if band2 else 1):
                    band1_tiles.append(tiles[i])
                    if band2:
                        band2_tiles.append(tiles[i + 1])
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))

            band1 = aggregate_time_series(
                [tile[0].astype(float) for tile in band1_tiles], operation
            )
            if band2_tiles:
                band2 = aggregate_time_series(
                    [tile[0].astype(float) for tile in band2_tiles], operation
                )
                result = eval(formula)
            else:
                result = eval(formula)

            image = self.apply_colormap(result, colormap_str)

        buffered = BytesIO()
        image.save(buffered, format="PNG")
        image_bytes = buffered.getvalue()

        return image_bytes, feature
