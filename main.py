import time
from io import BytesIO

import mercantile
import numpy as np
from fastapi import FastAPI, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from matplotlib import pyplot as plt
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


@app.get("/tile/{z}/{x}/{y}")
async def get_tile(
    z: int, x: int, y: int, band: str = Query("rgb", enum=["rgb", "ndvi"])
):
    start_time = time.time()

    cog_path = "sentinel_r10_cog.tif"

    with COGReader(cog_path) as cog:
        try:
            tile_data, mask = cog.tile(x, y, z)
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
            image = process_rgb(r, g, b)
        elif band == "ndvi":
            image = process_ndvi(r, nir)

    computation_time = time.time() - start_time

    buffered = BytesIO()
    image.save(buffered, format="PNG")
    image_bytes = buffered.getvalue()

    headers = {"X-Computation-Time": str(computation_time)}

    return Response(content=image_bytes, media_type="image/png", headers=headers)


def process_rgb(r, g, b):
    r_norm = (r - np.min(r)) / (np.max(r) - np.min(r))
    g_norm = (g - np.min(g)) / (np.max(g) - np.min(g))
    b_norm = (b - np.min(b)) / (np.max(b) - np.min(b))

    rgb = np.stack((r_norm, g_norm, b_norm), axis=-1)
    rgb_image = (rgb * 255).astype(np.uint8)
    image = Image.fromarray(rgb_image)

    return image


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
