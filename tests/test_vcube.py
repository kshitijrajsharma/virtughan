import os
import shutil
from io import BytesIO

import mercantile
import pytest
from PIL import Image

from vcube.engine import VCubeProcessor
from vcube.extract import ExtractProcessor
from vcube.tile import TileProcessor


@pytest.fixture(scope="module")
def setup_vcube_processor():
    bbox = [83.84765625, 28.22697003891833, 83.935546875, 28.304380682962773]
    start_date = "2024-12-01"
    end_date = "2025-01-01"
    cloud_cover = 30
    formula = "(band2-band1)/(band2+band1)"
    band1 = "red"
    band2 = "nir"
    operation = "median"
    output_dir = "virtughan_output"
    timeseries = True
    workers = 2

    # Cleanup before running tests
    if os.path.exists(output_dir):
        shutil.rmtree(output_dir)

    processor = VCubeProcessor(
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
        workers=workers,
    )
    return processor


def test_compute(setup_vcube_processor):
    processor = setup_vcube_processor
    processor.compute()
    # Check if output directory is created
    assert os.path.exists(processor.output_dir)
    # Check if some output files are created
    assert len(os.listdir(processor.output_dir)) > 0


@pytest.fixture(scope="module")
def setup_tile_processor():
    lat = 28.28139
    lon = 83.91866
    zoom_level = 12
    x, y, z = mercantile.tile(lon, lat, zoom_level)
    tile_processor = TileProcessor()
    return tile_processor, x, y, z


@pytest.mark.asyncio
async def test_generate_tile(setup_tile_processor):
    tile_processor, x, y, z = setup_tile_processor
    image_bytes, feature = await tile_processor.cached_generate_tile(
        x=x,
        y=y,
        z=z,
        start_date="2024-01-01",
        end_date="2025-01-01",
        cloud_cover=30,
        band1="red",
        band2="nir",
        formula="(band2-band1)/(band2+band1)",
        colormap_str="RdYlGn",
    )

    image = Image.open(BytesIO(image_bytes))
    image_path = f"tile_{x}_{y}_{z}.png"
    image.save(image_path)

    # Check if the image is saved
    assert os.path.exists(image_path)
    # Check if the feature properties are correct
    assert "datetime" in feature["properties"]
    assert "eo:cloud_cover" in feature["properties"]

    # Cleanup
    os.remove(image_path)


@pytest.fixture(scope="module")
def setup_extract_processor():
    bbox = [83.84765625, 28.22697003891833, 83.935546875, 28.304380682962773]
    start_date = "2024-12-15"
    end_date = "2024-12-31"
    cloud_cover = 30
    bands_list = ["red", "green", "blue"]
    output_dir = "./sentinel_images"
    workers = 1

    # Cleanup before running tests
    if os.path.exists(output_dir):
        shutil.rmtree(output_dir)

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
    return extractor


def test_extract(setup_extract_processor):
    extractor = setup_extract_processor
    extractor.extract()
    # Check if output directory is created
    assert os.path.exists(extractor.output_dir)
    # Check if some output files are created
    assert len(os.listdir(extractor.output_dir)) > 0
