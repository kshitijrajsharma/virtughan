import asyncio
from io import BytesIO

import httpx
import matplotlib
import mercantile
import numpy as np
from aiocache import cached
from fastapi import HTTPException
from matplotlib import pyplot as plt
from PIL import Image
from rio_tiler.io import COGReader
from shapely.geometry import box, mapping

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
    ) -> bytes:
        tile = mercantile.Tile(x, y, z)
        bbox = mercantile.bounds(tile)
        bbox_polygon = box(bbox.west, bbox.south, bbox.east, bbox.north)
        bbox_geojson = mapping(bbox_polygon)
        STAC_API_URL = "https://earth-search.aws.element84.com/v1/search"
        search_params = {
            "collections": ["sentinel-2-l2a"],
            "datetime": f"{start_date}T00:00:00Z/{end_date}T23:59:59Z",
            "query": {"eo:cloud_cover": {"lt": cloud_cover}},
            "intersects": bbox_geojson,
            "limit": 1,
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(STAC_API_URL, json=search_params)
        if response.status_code != 200:
            raise HTTPException(status_code=404, detail="Error searching STAC API")

        results = response.json()
        if not results["features"]:
            raise HTTPException(
                status_code=404, detail="No images found for the given parameters"
            )

        feature = results["features"][0]
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

        buffered = BytesIO()
        image.save(buffered, format="PNG")
        image_bytes = buffered.getvalue()

        return image_bytes, feature
