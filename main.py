import base64
import time
from io import BytesIO

import matplotlib.pyplot as plt
import mercantile
import numpy as np
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from PIL import Image
from rio_tiler.io import COGReader

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/image")
async def get_image(
    bbox: str, zoom: int, band: str = Query("rgb", enum=["rgb", "ndvi"])
):
    if zoom < 5:
        return JSONResponse(
            content={
                "error": "Zoom level must be greater than 10",
                "zoom": zoom,
            },
            status_code=400,
        )

    start_time = time.time()
    coords = list(map(float, bbox.split(",")))
    min_lon, min_lat, max_lon, max_lat = coords

    # Calculate the centroid of the bounding box
    center_lon = (min_lon + max_lon) / 2
    center_lat = (min_lat + max_lat) / 2

    # Get the center tile
    center_tile = mercantile.tile(center_lon, center_lat, zoom)

    cog_path = "sentinel_r10_cog.tif"
    images_base64 = []

    with COGReader(cog_path) as cog:
        try:
            tile_data, mask = cog.tile(center_tile.x, center_tile.y, zoom)
        except Exception as e:
            print(f"Error: {e}")
            return JSONResponse(
                content={"error": str(e)},
                status_code=500,
            )
        r = tile_data[1]
        g = tile_data[2]
        b = tile_data[3]
        nir = tile_data[4]

        if band == "rgb":
            tile_image_base64 = process_rgb(r, g, b)
        elif band == "ndvi":
            tile_image_base64 = process_ndvi(r, nir)

        images_base64.append(
            {"tile": (center_tile.x, center_tile.y, zoom), "image": tile_image_base64}
        )

    computation_time = time.time() - start_time

    return JSONResponse(
        content={
            "images": images_base64,
            "computation_time": computation_time,
            "coords": coords,
            "zoom": zoom,
        }
    )


def process_rgb(r, g, b):
    r_norm = (r - np.min(r)) / (np.max(r) - np.min(r))
    g_norm = (g - np.min(g)) / (np.max(g) - np.min(g))
    b_norm = (b - np.min(b)) / (np.max(b) - np.min(b))

    rgb = np.stack((r_norm, g_norm, b_norm), axis=-1)
    rgb_image = (rgb * 255).astype(np.uint8)
    image = Image.fromarray(rgb_image)

    buffered = BytesIO()
    image.save(buffered, format="PNG")
    image_base64 = base64.b64encode(buffered.getvalue()).decode("utf-8")

    return image_base64


def process_ndvi(r, nir):
    ndvi = (nir.astype(float) - r.astype(float)) / (nir + r)
    ndvi = np.ma.masked_invalid(ndvi)
    ndvi_normalized = (ndvi + 1) / 2

    colormap = plt.get_cmap("RdYlGn")
    ndvi_colored = colormap(ndvi_normalized)

    ndvi_image = (ndvi_colored[:, :, :3] * 255).astype(np.uint8)
    image = Image.fromarray(ndvi_image)

    buffered = BytesIO()
    image.save(buffered, format="PNG")
    image_base64 = base64.b64encode(buffered.getvalue()).decode("utf-8")

    return image_base64


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
