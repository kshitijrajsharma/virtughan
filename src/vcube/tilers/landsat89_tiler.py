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
import planetary_computer

from ..utils.common import (
    aggregate_time_series,
    filter_intersected_features,
    filter_latest_image_per_grid,
    search_stac_api_async,    # picks endpoint by collection
    smart_filter_images,
)
from ..utils.landsat89_utils import remove_overlapping_landsat_tiles

matplotlib.use("Agg")


class TileProcessor:
    """
    Processor for generating and caching Landsat tiles via Microsoft Planetary Computer.
    """

    def __init__(self, cache_time=60):
        self.cache_time = cache_time

    @staticmethod
    def apply_colormap(result: np.ndarray, colormap_str: str) -> Image.Image:
        # Normalize and apply matplotlib colormap
        norm = (result - result.min()) / (result.max() - result.min())
        cmap = plt.get_cmap(colormap_str)
        colored = cmap(norm)
        img = (colored[:, :, :3] * 255).astype(np.uint8)
        return Image.fromarray(img)

    @staticmethod
    async def fetch_tile(url: str, x: int, y: int, z: int) -> np.ndarray:
        """
        Fetch a single x/y/z COG tile from a signed Planetary Computer URL.
        """
        signed = planetary_computer.sign(url)

        def read():
            with COGReader(signed) as cog:
                tile, _ = cog.tile(x, y, z)
                return tile

        return await asyncio.to_thread(read)

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
        band2: str = None,
        formula: str = "band1",
        colormap_str: str = "RdYlGn",
        latest: bool = True,
        operation: str = "median",
    ) -> bytes:
        """
        Search Landsat scenes, fetch COG tiles, compute (band math or TS), return PNG bytes.
        """
        # 1) Build tile bounds
        tile = mercantile.Tile(x, y, z)
        west, south, east, north = mercantile.bounds(tile)
        bbox_geojson = mapping(box(west, south, east, north))

        # 2) Search STAC (collection routed by common helper)
        features = await search_stac_api_async(
            bbox_geojson,
            start_date,
            end_date,
            cloud_cover,
            collection="landsat-c2-l2",
        )
        if not features:
            raise HTTPException(status_code=404, detail="No scenes found")

        # 3) Filter by intersection
        features = filter_intersected_features(features, [west, south, east, north])

        # 4) Latest vs time-series
        if latest:
            features = filter_latest_image_per_grid(features)
            if not features:
                raise HTTPException(status_code=404, detail="No overlapping image found")
            features = [features[0]]
        else:
            features = remove_overlapping_landsat_tiles(features)
            features = smart_filter_images(features, start_date, end_date)

        # 5) Prepare asset URLs
        band1_urls = [f["assets"][band1]["href"] for f in features]
        band2_urls = (
            [f["assets"][band2]["href"] for f in features] if band2 else [None] * len(features)
        )

        # 6) Fetch tiles
        tiles1, tiles2 = [], []
        tasks = []
        for b1, b2 in zip(band1_urls, band2_urls):
            tasks.append(self.fetch_tile(b1, x, y, z))
            if b2:
                tasks.append(self.fetch_tile(b2, x, y, z))

        try:
            fetched = await asyncio.gather(*tasks)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

        # Distribute fetched tiles into two lists
        idx = 0
        for _ in features:
            tiles1.append(fetched[idx]); idx += 1
            if band2:
                tiles2.append(fetched[idx]); idx += 1

        # 7) Convert first tiles to float arrays
        arr1 = tiles1[0][0].astype(float)
        arr2 = tiles2[0][0].astype(float) if band2 else None

        # 8) Compute result via eval with correct locals
        if latest:
            # single-scene compute
            if band2:
                result = eval(formula, {}, {"band1": arr1, "band2": arr2})
            else:
                # either single-band formula or RGB image
                if arr1.ndim == 2:
                    result = eval(formula, {}, {"band1": arr1})
                else:
                    # multi-band image → return directly
                    img = Image.fromarray(arr1.transpose(1, 2, 0).astype(np.uint8))
                    buf = BytesIO()
                    img.save(buf, format="PNG")
                    return buf.getvalue(), features[0]
        else:
            # time-series aggregation
            arrs1 = [t[0].astype(float) for t in tiles1]
            agg1  = aggregate_time_series(arrs1, operation)
            if band2:
                arrs2 = [t[0].astype(float) for t in tiles2]
                agg2  = aggregate_time_series(arrs2, operation)
                result = eval(formula, {}, {"band1": agg1, "band2": agg2})
            else:
                result = agg1

        # 9) Apply colormap and return PNG bytes
        img = self.apply_colormap(result, colormap_str)
        buf = BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue(), features[0]


if __name__ == "__main__":
    import os

    async def demo():
        proc = TileProcessor()
        png, feat = await proc.cached_generate_tile(
            x=270, y=163, z=9,
            start_date="2024-12-15",
            end_date="2024-12-31",
            cloud_cover=30,
            band1="red",
            band2="nir08",
            formula="(band2 - band1)/(band2 + band1)",
            colormap_str="RdYlGn",
            latest=True,
            operation="median",
        )
        os.makedirs("./output", exist_ok=True)
        with open("./output/landsat_pc_tile.png", "wb") as f:
            f.write(png)
        print("Saved:", feat["id"])

    asyncio.run(demo())
