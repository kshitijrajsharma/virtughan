import time
from datetime import datetime, timedelta
from io import BytesIO

import mercantile
import numpy as np
import requests
from fastapi import FastAPI, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from matplotlib import pyplot as plt
from PIL import Image
from rio_tiler.io import COGReader
from shapely.geometry import box, mapping

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/search")
async def search_images(
    bbox: str = Query(
        ..., description="Bounding box in the format 'west,south,east,north'"
    ),
    cloud_cover: int = Query(30, description="Maximum cloud cover percentage"),
    start_date: str = Query(None, description="Start date in YYYY-MM-DD format"),
    end_date: str = Query(None, description="End date in YYYY-MM-DD format"),
):
    if not start_date:
        start_date = (datetime.now() - timedelta(days=60)).strftime("%Y-%m-%d")
    if not end_date:
        end_date = datetime.now().strftime("%Y-%m-%d")

    west, south, east, north = map(float, bbox.split(","))
    bbox_polygon = box(west, south, east, north)
    bbox_geojson = mapping(bbox_polygon)

    STAC_API_URL = "https://earth-search.aws.element84.com/v1/search"
    search_params = {
        "collections": ["sentinel-2-l2a"],
        "datetime": f"{start_date}T00:00:00Z/{end_date}T23:59:59Z",
        "query": {"eo:cloud_cover": {"lt": cloud_cover}},
        "intersects": bbox_geojson,
        "limit": 100,
    }

    response = requests.post(STAC_API_URL, json=search_params)
    if response.status_code != 200:
        return JSONResponse(
            content={"error": "Error searching STAC API"},
            status_code=500,
        )

    results = response.json()
    return results


@app.get("/tile/{z}/{x}/{y}")
async def get_tile(
    z: int,
    x: int,
    y: int,
    band: str = Query("rgb", enum=["rgb", "ndvi"]),
    start_date: str = Query(None),
    end_date: str = Query(None),
    cloud_cover: int = Query(30),
):
    if z < 10 or z > 16:
        return JSONResponse(
            content={"error": "Zoom level must be between 8 and 17"},
            status_code=400,
        )
    start_time = time.time()

    if not start_date:
        start_date = (datetime.now() - timedelta(days=30 * 12)).strftime("%Y-%m-%d")
    if not end_date:
        end_date = datetime.now().strftime("%Y-%m-%d")

    # cog_path = "sentinel_r10_cog.tif"
    tile = mercantile.Tile(x, y, z)
    bbox = mercantile.bounds(tile)
    bbox_polygon = box(bbox.west, bbox.south, bbox.east, bbox.north)

    # Convert the polygon to GeoJSON format
    bbox_geojson = mapping(bbox_polygon)
    STAC_API_URL = "https://earth-search.aws.element84.com/v1/search"
    search_params = {
        "collections": ["sentinel-2-l2a"],
        "datetime": f"{start_date}T00:00:00Z/{end_date}T23:59:59Z",
        "query": {"eo:cloud_cover": {"lt": cloud_cover}},
        "intersects": bbox_geojson,
        "limit": 1,
    }
    response = requests.post(STAC_API_URL, json=search_params)
    if response.status_code != 200:

        return JSONResponse(
            content={"error": "Error searching STAC API"},
            status_code=404,
        )

    results = response.json()
    if not results["features"]:
        return JSONResponse(
            content={"error": "No images found for the given parameters"},
            status_code=404,
        )

    feature = results["features"][0]
    red_band_url = feature["assets"]["red"]["href"]
    nir_band_url = feature["assets"]["nir"]["href"]

    try:
        with COGReader(red_band_url) as red_cog, COGReader(nir_band_url) as nir_cog:
            red_tile, _ = red_cog.tile(x, y, z)
            nir_tile, _ = nir_cog.tile(x, y, z)
    except Exception as e:
        print(f"Error: {e}")
        return JSONResponse(
            content={"error": str(e)},
            status_code=500,
        )
    r = red_tile[0]
    nir = nir_tile[0]
    image = process_ndvi(r, nir)
    computation_time = time.time() - start_time

    buffered = BytesIO()
    image.save(buffered, format="PNG")
    image_bytes = buffered.getvalue()

    headers = {
        "X-Computation-Time": str(computation_time),
        "X-Image-Date": feature["properties"]["datetime"],
        "X-Cloud-Cover": str(feature["properties"]["eo:cloud_cover"]),
    }
    return Response(content=image_bytes, media_type="image/png", headers=headers)


def process_ndvi(r, nir):
    ndvi = (nir.astype(float) - r.astype(float)) / (nir + r)
    ndvi = np.ma.masked_invalid(ndvi)
    ndvi_normalized = (ndvi + 1) / 2

    colormap = plt.get_cmap("RdYlGn")
    ndvi_colored = colormap(ndvi_normalized)

    ndvi_image = (ndvi_colored[:, :, :3] * 255).astype(np.uint8)
    image = Image.fromarray(ndvi_image)

    return image


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
