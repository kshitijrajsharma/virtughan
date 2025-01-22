# VirtuGhan

<img src="./static/img/virtughan-logo.png" alt="VirtuGhan Logo" width="100" height="100"> 

![Tests Passing](https://img.shields.io/badge/tests-passing-brightgreen)
![Build Status](https://img.shields.io/github/actions/workflow/status/kshitijrajsharma/VirtuGhan/tests.yml?branch=master)
![Website Status](https://img.shields.io/website-up-down-green-red/https/virtughan.live)
![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=flat&logo=fastapi)
![PyPI Version](https://img.shields.io/pypi/v/virtughan)
![Python Version](https://img.shields.io/pypi/pyversions/virtughan)
![License](https://img.shields.io/github/license/kshitijrajsharma/VirtuGhan)
![Dependencies](https://img.shields.io/librariesio/release/pypi/virtughan)
![Last Commit](https://img.shields.io/github/last-commit/kshitijrajsharma/VirtuGhan)

 Name is combination of two words `virtual` & `cube` , where `cube` translated to Nepali word `घन`,  also known as virtual computation cube. You can test demo of this project for Sentinel2 data at : https://virtughan.live/ 


### Install 

As a python package : 

https://pypi.org/project/VirtuGhan/ 

```bash
pip install VirtuGhan
```

## Purpose

### 1. Efficient On-the-Fly Tile Computation

This research explores how to perform real-time calculations on satellite images at different zoom levels, similar to Google Earth Engine, but using open-source tools. By using Cloud Optimized GeoTIFFs (COGs) with Sentinel-2 imagery, large images can be analyzed without needing to pre-process or store them. The study highlights how this method can scale well and work efficiently, even with limited hardware. Our main focus is on how to scale the computation on different zoom-levels without introducing server overhead 

[Watch](https://krschap.nyc3.cdn.digitaloceanspaces.com/ontheflydemo.gif)

#### Example python usage

```python
import mercantile
from PIL import Image
from io import BytesIO
from vcube.tile import TileProcessor

lat, lon = 28.28139, 83.91866
zoom_level = 12
x, y, z = mercantile.tile(lon, lat, zoom_level)

tile_processor = TileProcessor()

image_bytes, feature = await tile_processor.cached_generate_tile(
    x=x,
    y=y,
    z=z,
    start_date="2020-01-01",
    end_date="2025-01-01",
    cloud_cover=30,
    band1="red",
    band2="nir",
    formula="(band2-band1)/(band2+band1)",
    colormap_str="RdYlGn",
)

image = Image.open(BytesIO(image_bytes))

print(f"Tile: {x}_{y}_{z}")
print(f"Date: {feature['properties']['datetime']}")
print(f"Cloud Cover: {feature['properties']['eo:cloud_cover']}%")

image.save(f'tile_{x}_{y}_{z}.png')
```


### 2. Virtual Computation Cubes: Focusing on Computation 

We believe that instead of focusing on storing large images, data cube systems should prioritize efficient computation. COGs make it possible to analyze images directly without storing the entire dataset. This introduces the idea of virtual computation cubes, where images are stacked and processed over time, allowing for analysis across different layers ( including semantic layers ) without needing to download or save everything. So original data is never replicated. In this setup, a data provider can store and convert images to COGs, while users or service providers focus on calculations. This approach reduces the need for terra-bytes of storage and makes it easier to process large datasets quickly.

#### Example python usage

Example NDVI calculation 

```python
from vcube.engine import VCubeProcessor

processor = VCubeProcessor(
    bbox=[83.84765625, 28.22697003891833, 83.935546875, 28.304380682962773],
    start_date="2023-01-01",
    end_date="2025-01-01",
    cloud_cover=30,
    formula="(band2-band1)/(band2+band1)",
    band1="red",
    band2="nir",
    operation="median",
    timeseries=True,
    output_dir="virtughan_output",
    workers=16
)

processor.compute()
```




### Summary 

This research introduces methods on how to use COGs, the SpatioTemporal Asset Catalog (STAC) API, and NumPy arrays to improve the way large Earth observation datasets are accessed and processed. The method allows users to focus on specific areas of interest, process data across different bands and layers over time, and maintain optimal resolution while ensuring fast performance. By using the STAC API, it becomes easier to search for and only process the necessary data without needing to download entire images ( not even the single scene , only accessing the parts ) The study shows how COGs can improve the handling of large datasets, not only making  the access faster but also making computation efficient, and scalable across different zoom levels . 
![image](https://github.com/user-attachments/assets/e5741f6b-d6c2-4e47-a794-21c2244a7476)



### Background

We started initially by looking at how Google Earth Engine (GEE) computes results on-the-fly at different zoom levels on large-scale Earth observation datasets. We were fascinated by the approach and felt an urge to replicate something similar on our own in an open-source manner. We knew Google uses their own kind of tiling, so we started from there.

Initially, we faced a challenge – how could we generate tiles and compute at the same time without pre-computing the whole dataset? Pre-computation would lead to larger processed data sizes, which we didn’t want. And so, the exploration began and the concept of on the fly tiling computation introduced 

At university, we were introduced to the concept of data cubes and the advantages of having a time dimension and semantic layers in the data. It seemed fascinating, despite the challenge of maintaining terabytes of satellite imagery. We thought – maybe we could achieve something similar by developing an approach where one doesn’t need to replicate data but can still build a data cube with semantic layers and computation. This raised another challenge – how to make it work? And hence come the virtual data cube

We started converting Sentinel-2 images to Cloud Optimized GeoTIFFs (COGs) and experimented with the time dimension using Python’s xarray to compute the data. We found that [earth-search](https://github.com/Element84/earth-search)’s effort to store Sentinel images as COGs made it easier for us to build virtual data cubes across the world without storing any data. This felt like an achievement and proof that modern data cubes should focus on improving computation rather than worrying about how to manage terabytes of data.

We wanted to build something to show that this approach actually works and is scalable. We deliberately chose to use only our laptops to run the prototype and process a year’s worth of data without expensive servers.



Learn about COG and how to generate one for this project [Here](./docs/cog.md)


### Sample case study : 
[Watch Video](https://krschap.nyc3.cdn.digitaloceanspaces.com/virtughan.MP4)
 

## Local Setup 

This project has FASTAPI and Plain JS Frontend.

Inorder to setup project , follow [here](./docs/install.md)

## Resources and Credits 

- https://registry.opendata.aws/sentinel-2-l2a-cogs/ COGS Stac API for sentinel-2


## Acknowledgment

This project was undertaken as part of the project work for our master's program , Coopernicus Masters in Digital Earth. 

<p align="left">
  <img src="https://github.com/user-attachments/assets/2f0555f8-67c3-49da-a0e8-037bdfd4ce10" alt="CMIDE-InLine-logoCMYK" style="width:200px;"/>
  <img src="https://github.com/user-attachments/assets/e553c675-f8e5-440a-b50f-625d0ce4f0c9" alt="EU_POS_transparent" style="width:200px;"/>
</p>

### Copyright 

© 2024 – Concept by Kshitij and Upen , Distributed under GNU General Public License v3.0 

