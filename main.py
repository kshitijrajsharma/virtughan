import asyncio
import os
import time
from datetime import datetime, timedelta
from io import BytesIO
from typing import List

import httpx
import mercantile
import numpy as np
from aiocache import cached
from fastapi import (
    BackgroundTasks,
    FastAPI,
    HTTPException,
    Query,
    Response,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from matplotlib import pyplot as plt
from PIL import Image
from rio_tiler.io import COGReader
from shapely.geometry import box, mapping
from starlette.requests import Request

from src.scog_compute.process_ndvi_cog_tiles import main as calculate_ndvi_over_time

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.mount("/static", StaticFiles(directory="static"), name="static")

templates = Jinja2Templates(directory="templates")
# store websocket connections
connections: List[WebSocket] = []


@app.get("/", response_class=HTMLResponse)
async def read_index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


async def fetch_tile(url, x, y, z):
    def read_tile():
        with COGReader(url) as cog:
            tile, _ = cog.tile(x, y, z)
            return tile[0]

    return await asyncio.to_thread(read_tile)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    connections.append(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        connections.remove(websocket)


async def notify_progress(message: str):
    for connection in connections:
        await connection.send_text(message)


@app.post("/process_ndvi")
async def process_ndvi_endpoint(
    background_tasks: BackgroundTasks,
    lat: float = Query(28.202082, description="Latitude (default: 28.202082)"),
    lon: float = Query(83.987222, description="Longitude (default: 83.987222)"),
    z: int = Query(10, description="Zoom level (default: 10)"),
    cc: int = Query(30, description="Cloud cover percentage (default: 30)"),
    sd: str = Query(
        (datetime.now() - timedelta(days=30 * 2)).strftime("%Y-%m-01"),
        description="Start date in YYYY-MM-DD format (default: first day of last 2 months)",
    ),
    ed: str = Query(
        datetime.now().strftime("%Y-%m-%d"),
        description="End date in YYYY-MM-DD format (default: today)",
    ),
):
    background_tasks.add_task(run_ndvi_script, lat, lon, z, cc, sd, ed)
    return {"message": "NDVI processing started"}


async def run_ndvi_script(lat, lon, z, cc, sd, ed):
    await notify_progress("Starting NDVI processing...")
    image_url = "static/ndvi_result.png"
    if os.path.exists("static/ndvi_result.png"):
        os.remove("static/ndvi_result.png")
    await calculate_ndvi_over_time(lat, lon, z, cc, sd, ed, image_url, notify_progress)

    await notify_progress(f"Result available at {image_url}")


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

    async with httpx.AsyncClient() as client:
        response = await client.post(STAC_API_URL, json=search_params)
    if response.status_code != 200:
        return JSONResponse(
            content={"error": "Error searching STAC API"},
            status_code=500,
        )

    results = response.json()
    return results


@cached(ttl=3600)
async def cached_generate_tile(
    x: int, y: int, z: int, start_date: str, end_date: str, cloud_cover: int
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
    red_band_url = feature["assets"]["red"]["href"]
    nir_band_url = feature["assets"]["nir"]["href"]

    try:
        red_tile, nir_tile = await asyncio.gather(
            fetch_tile(red_band_url, x, y, z), fetch_tile(nir_band_url, x, y, z)
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    r = red_tile
    nir = nir_tile
    image = process_ndvi(r, nir)

    buffered = BytesIO()
    image.save(buffered, format="PNG")
    image_bytes = buffered.getvalue()

    return image_bytes, feature


@app.get("/tile/{z}/{x}/{y}")
async def get_tile(
    z: int,
    x: int,
    y: int,
    start_date: str = Query(None),
    end_date: str = Query(None),
    cloud_cover: int = Query(30),
):
    if z < 10 or z > 16:
        return JSONResponse(
            content={"error": "Zoom level must be between 8 and 17"},
            status_code=400,
        )

    if not start_date:
        start_date = (datetime.now() - timedelta(days=30 * 12)).strftime("%Y-%m-%d")
    if not end_date:
        end_date = datetime.now().strftime("%Y-%m-%d")

    try:
        start_time = time.time()
        image_bytes, feature = await cached_generate_tile(
            x, y, z, start_date, end_date, cloud_cover
        )
        computation_time = time.time() - start_time

        headers = {
            "X-Computation-Time": str(computation_time),
            "X-Image-Date": feature["properties"]["datetime"],
            "X-Cloud-Cover": str(feature["properties"]["eo:cloud_cover"]),
        }

        return Response(content=image_bytes, media_type="image/png", headers=headers)
    except HTTPException as e:
        return JSONResponse(content={"error": e.detail}, status_code=e.status_code)


def process_ndvi(r, nir):
    ndvi = (nir.astype(float) - r.astype(float)) / (nir + r)
    ndvi = np.ma.masked_invalid(ndvi)

    ndvi_normalized = (ndvi - ndvi.min()) / (ndvi.max() - ndvi.min())

    colormap = plt.get_cmap("RdYlGn")
    ndvi_colored = colormap(ndvi_normalized)

    ndvi_image = (ndvi_colored[:, :, :3] * 255).astype(np.uint8)
    image = Image.fromarray(ndvi_image)

    return image
