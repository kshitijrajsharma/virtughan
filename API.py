import asyncio
import gc
import json
import os
import shutil
import sys
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta

import matplotlib
from fastapi import BackgroundTasks, FastAPI, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from shapely.geometry import box, mapping
from starlette.requests import Request
from starlette.status import HTTP_504_GATEWAY_TIMEOUT

from src.vcube.engine import VCubeProcessor
from src.vcube.extract import ExtractProcessor
from src.vcube.tile import TileProcessor
from src.vcube.utils import search_stac_api_async

app = FastAPI()

matplotlib.use("Agg")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

EXPIRY_DURATION_HOURS = int(os.getenv("EXPIRY_DURATION_HOURS", 1))
EXPIRY_DURATION = timedelta(hours=EXPIRY_DURATION_HOURS)
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", 120))
STATIC_EXPORT_DIR = os.getenv("STATIC_EXPORT_DIR", "static/export")
STATIC_DIR = os.getenv("STATIC_DIR", "static")


@asynccontextmanager
async def lifespan(app: FastAPI):
    asyncio.create_task(cleanup_expired_folders())
    yield


@app.middleware("http")
async def timeout_middleware(request: Request, call_next):
    try:
        return await asyncio.wait_for(call_next(request), timeout=REQUEST_TIMEOUT)
    except asyncio.TimeoutError:
        return JSONResponse(
            {"detail": "Request processing exceeded the time limit."},
            status_code=HTTP_504_GATEWAY_TIMEOUT,
        )


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

templates = Jinja2Templates(directory="templates")


@app.get("/", response_class=HTMLResponse)
async def read_index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/about", response_class=HTMLResponse)
async def read_about(request: Request):
    return templates.TemplateResponse("about.html", {"request": request})


with open("data/sentinel-2-bands.json") as f:
    sentinel2_assets = json.load(f)


@app.get("/list-files")
async def list_files(uid: str):
    directory = f"{STATIC_EXPORT_DIR}/{uid}"
    if not os.path.exists(directory):
        raise HTTPException(status_code=404, detail="Directory not found")

    files = {}
    for filename in os.listdir(directory):
        filepath = os.path.join(directory, filename)
        if os.path.isfile(filepath):
            files[filename] = os.path.getsize(filepath)

    return JSONResponse(content=files)


@app.get("/logs")
async def get_logs(uid: str):
    log_file = f"{STATIC_EXPORT_DIR}/{uid}/runtime.log"
    if os.path.exists(log_file):
        with open(log_file, "r") as file:
            logs = file.readlines()[-30:]
        return Response("\n".join(logs), media_type="text/plain")
    else:
        return JSONResponse(content={"error": "Log file not found"}, status_code=404)


@app.get("/sentinel2-bands")
async def get_sentinel2_bands(
    band: str = Query(None, description="Band name to filter"),
):
    if band:
        if band in sentinel2_assets:
            band_data = sentinel2_assets[band]
            filtered_data = {
                "type": band_data.get("type"),
                "title": band_data.get("title"),
                "eo:bands": band_data.get("eo:bands"),
                "gsd": band_data.get("gsd"),
                "raster:bands": band_data.get("raster:bands"),
            }
            return filtered_data
        else:
            raise HTTPException(status_code=404, detail="Band not found")
    else:
        return {key: value["title"] for key, value in sentinel2_assets.items()}


@app.get("/export")
async def compute_aoi_over_time(
    background_tasks: BackgroundTasks,
    bbox: str = Query(
        ..., description="Bounding box in the format 'west,south,east,north'"
    ),
    start_date: str = Query(
        (datetime.now() - timedelta(days=365 * 1)).strftime("%Y-%m-%d"),
        description="Start date in YYYY-MM-DD format (default: 1 years ago)",
    ),
    end_date: str = Query(
        datetime.now().strftime("%Y-%m-%d"),
        description="End date in YYYY-MM-DD format (default: today)",
    ),
    cloud_cover: int = Query(30, description="Cloud cover percentage (default: 30)"),
    formula: str = Query(
        "(band2 - band1) / (band2 + band1)",
        description="Formula for custom band calculation (default: NDVI)",
    ),
    band1: str = Query(
        "red", description="First band for custom calculation (default: red)"
    ),
    band2: str = Query(
        "nir", description="Second band for custom calculation (default: nir)"
    ),
    operation: str = Query(
        None, description="Operation for aggregating results (default: None)"
    ),
    timeseries: bool = Query(
        True, description="Should timeseries be generated (default: True)"
    ),
    smart_filter: bool = Query(
        False, description="Should smart filter be applied ? (default: False)"
    ),
):
    if timeseries is False and operation is None:
        return JSONResponse(
            content={"error": "Operation is required if timeseries is disabled"},
            status_code=400,
        )
    if band1 is None:
        return JSONResponse(
            content={"error": "Band1 is required"},
            status_code=400,
        )

    valid_operations = ["mean", "median", "max", "min", "std", "sum", "var"]
    if operation and operation not in valid_operations:
        return JSONResponse(
            content={
                "error": f"Invalid operation {operation}. Choose from 'mean', 'median', 'max', 'min', 'std', 'sum', 'var'"
            },
            status_code=400,
        )
    bbox = list(map(float, bbox.split(",")))

    uid = datetime.now().strftime("%Y%m%d%H%M%S") + "_" + str(uuid.uuid4())[:6]

    output_dir = f"{STATIC_EXPORT_DIR}/{uid}"
    if os.path.exists(output_dir):
        shutil.rmtree(output_dir)
    os.makedirs(output_dir, exist_ok=True)

    background_tasks.add_task(
        run_computation,
        bbox,
        start_date,
        end_date,
        cloud_cover,
        formula,
        band1,
        band2,
        operation,
        timeseries,
        output_dir,
        smart_filter,
    )
    return {"message": f"Processing started in background: {output_dir}", "uid": uid}


async def run_computation(
    bbox,
    start_date,
    end_date,
    cloud_cover,
    formula,
    band1,
    band2,
    operation,
    timeseries,
    output_dir,
    smart_filter,
):
    log_file = f"{output_dir}/runtime.log"
    if os.path.exists(log_file):
        os.remove(log_file)
    with open(log_file, "a") as f:
        sys.stdout = f

        print("Starting processing...")
        try:
            processor = VCubeProcessor(
                bbox=bbox,
                start_date=start_date,
                end_date=end_date,
                cloud_cover=cloud_cover,
                formula=formula,
                band1=band1,
                band2=band2,
                operation=operation,
                timeseries=timeseries,
                output_dir=output_dir,
                log_file=f,
                smart_filter=smart_filter,
            )
            processor.compute()
            print(f"Processing completed. Results saved in {output_dir}")

        except Exception as e:
            print(f"Error processing : {e}")

        finally:
            gc.collect()


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

    response = await search_stac_api_async(
        bbox_geojson, start_date, end_date, cloud_cover
    )

    feature_collection = {"type": "FeatureCollection", "features": response}
    return JSONResponse(content=feature_collection)


@app.get("/tile/{z}/{x}/{y}")
async def get_tile(
    z: int,
    x: int,
    y: int,
    start_date: str = Query(None),
    end_date: str = Query(None),
    cloud_cover: int = Query(30),
    band1: str = Query(
        "visual", description="First band for custom calculation (default: red)"
    ),
    band2: str = Query(
        None, description="Second band for custom calculation (default: nir)"
    ),
    formula: str = Query(
        "band1",
        description="Formula for custom band calculation (example: (band2 - band1) / (band2 + band1) for NDVI)",
    ),
    colormap_str: str = Query("RdYlGn", description="Colormap for the output image"),
    operation: str = Query(
        "median",
        description="Operation for aggregating results (default: mean), Only applicable if timeseries is true",
    ),
    timeseries: bool = Query(
        False, description="Should timeseries be analyzed (default: False)"
    ),
):
    if z < 10 or z > 23:
        return JSONResponse(
            content={"error": "Zoom level must be between 10 and 23"},
            status_code=400,
        )
    if band1 is None:
        return JSONResponse(
            content={"error": "Band1 is required"},
            status_code=400,
        )
    if not start_date:
        start_date = (datetime.now() - timedelta(days=30 * 12)).strftime("%Y-%m-%d")
    if not end_date:
        end_date = datetime.now().strftime("%Y-%m-%d")

    try:
        start_time = time.time()
        tile_processor = TileProcessor()
        image_bytes, feature = await tile_processor.cached_generate_tile(
            x,
            y,
            z,
            start_date,
            end_date,
            cloud_cover,
            band1,
            band2,
            formula,
            colormap_str,
            operation=operation,
            latest=(timeseries is False),
        )
        computation_time = time.time() - start_time

        headers = {
            "X-Computation-Time": str(computation_time),
            "X-Image-Date": feature["properties"]["datetime"],
            "X-Cloud-Cover": str(feature["properties"]["eo:cloud_cover"]),
        }

        return Response(content=image_bytes, media_type="image/png", headers=headers)
    except Exception as ex:
        # raise ex
        return JSONResponse(
            content={"error": f"Computation Error:  {str(ex)}"}, status_code=504
        )


@app.get("/image-download")
async def extract_raw_bands_as_image(
    background_tasks: BackgroundTasks,
    bbox: str = Query(
        ..., description="Bounding box in the format 'west,south,east,north'"
    ),
    start_date: str = Query(
        (datetime.now() - timedelta(days=30 * 1)).strftime("%Y-%m-%d"),
        description="Start date in YYYY-MM-DD format (default: 1 year ago)",
    ),
    end_date: str = Query(
        datetime.now().strftime("%Y-%m-%d"),
        description="End date in YYYY-MM-DD format (default: today)",
    ),
    cloud_cover: int = Query(30, description="Cloud cover percentage (default: 30)"),
    bands_list: str = Query(
        "red,green,blue",
        description="Comma-separated list of bands to extract (default: red,green,blue)",
    ),
    smart_filter: bool = Query(
        False, description="Should smart filter be applied ? (default: False)"
    ),
):
    uid = datetime.now().strftime("%Y%m%d%H%M%S") + "_" + str(uuid.uuid4())[:8]

    output_dir = f"{STATIC_EXPORT_DIR}/{uid}"
    bbox = list(map(float, bbox.split(",")))

    if os.path.exists(output_dir):
        shutil.rmtree(output_dir)
    os.makedirs(output_dir, exist_ok=True)

    background_tasks.add_task(
        run_image_download,
        bbox,
        start_date,
        end_date,
        cloud_cover,
        bands_list.split(","),
        output_dir,
        smart_filter,
    )
    return {
        "message": f"Raw band extraction started in background: {output_dir}",
        "uid": uid,
    }


async def run_image_download(
    bbox, start_date, end_date, cloud_cover, bands_list, output_dir, smart_filter
):
    log_file = f"{output_dir}/runtime.log"
    if os.path.exists(log_file):
        os.remove(log_file)
    with open(log_file, "a") as f:
        sys.stdout = f

        print("Starting raw band extraction...")
        try:
            processor = ExtractProcessor(
                bbox=bbox,
                start_date=start_date,
                end_date=end_date,
                cloud_cover=cloud_cover,
                bands_list=bands_list,
                output_dir=output_dir,
                log_file=f,
                zip_output=True,
                smart_filter=smart_filter,
            )
            processor.extract()
            print(f"Raw band extraction completed. Results saved in {output_dir}")

        except Exception as e:
            print(f"Error during raw band extraction: {e}")

        finally:
            gc.collect()


async def cleanup_expired_folders():
    while True:
        now = datetime.now()
        os.makedirs(STATIC_EXPORT_DIR, exist_ok=True)
        for folder_name in os.listdir(STATIC_EXPORT_DIR):
            folder_path = os.path.join(STATIC_EXPORT_DIR, folder_name)
            if os.path.isdir(folder_path):
                folder_creation_time = datetime.strptime(
                    folder_name.split("_")[0], "%Y%m%d%H%M%S"
                )
                if now - folder_creation_time > EXPIRY_DURATION:
                    shutil.rmtree(folder_path)
                    print(f"Deleted expired folder: {folder_path}")
        await asyncio.sleep(1 * 60 * 60)  # Run the cleanup task every 1 hours
