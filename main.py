import base64
import time
from io import BytesIO

import matplotlib.pyplot as plt
import numpy as np
import rasterio
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from PIL import Image
from pyproj import Transformer
from rasterio.windows import from_bounds

app = FastAPI()


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/ndvi")
async def get_ndvi(bbox: str, zoom: int):
    if zoom < 2:
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

    transformer = Transformer.from_crs("epsg:4326", "epsg:3857", always_xy=True)

    # Transform to EPSG:3857
    min_x, min_y = transformer.transform(min_lon, min_lat)
    max_x, max_y = transformer.transform(max_lon, max_lat)

    with rasterio.open("sentinel_r10_cog.tif") as src:
        window = from_bounds(min_x, min_y, max_x, max_y, src.transform)
        red = src.read(4, window=window)
        nir = src.read(5, window=window)

        ndvi = (nir.astype(float) - red.astype(float)) / (nir + red)
        ndvi = np.ma.masked_invalid(ndvi)

    computation_time = time.time() - start_time

    # Normalize NDVI values to 0-1 for color mapping
    ndvi_normalized = (ndvi + 1) / 2
    colormap = plt.get_cmap("RdYlGn")
    ndvi_colored = colormap(ndvi_normalized)

    ndvi_image = (ndvi_colored[:, :, :3] * 255).astype(np.uint8)
    image = Image.fromarray(ndvi_image)

    buffered = BytesIO()
    image.save(buffered, format="PNG")
    image_base64 = base64.b64encode(buffered.getvalue()).decode("utf-8")

    return JSONResponse(
        content={
            "ndvi_image": image_base64,
            "computation_time": computation_time,
            "coords": coords,
            "zoom": zoom,
        }
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
