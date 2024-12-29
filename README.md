# scog-compute

## Purpose

The goal of this project is to efficiently do raster computation  on different zoom levels, similar to Google Earth Engine, but using Cloud Optimized GeoTIFFs (COGs) for Sentinel-2 imagery. When you zoom in and out on Google Earth Engine, it efficiently processes large images on the fly. We aim to replicate this capability in an open-source and scalable manner using COGs. This experiment demonstrates that on-the-fly computation at various zoom levels can be achieved with minimal and scalable hardware. Additionally, by leveraging a data cube, this approach can be expanded to include temporal dimensions.


![image](https://github.com/user-attachments/assets/4ef38608-bf96-474a-8f7e-2890b5677cf5)

Learn about COG and how to generate one for this project [Here](./cog.md)

## Installation and Setup

### Prerequisites

- Python 3.10 or higher
- [PDM](https://pdm-project.org/en/latest/) 

### Install PDM

If you don't have PDM installed, you can install it using the following command:

```bash
pip install pdm
```

#### Activate your venv with pdm 

``` bash 
pdm venv activate
```

#### Install 
```bash
pdm install
```

#### Run 

```bash
pdm run uvicorn main:app --reload
```


## Resources and Credits 

- https://registry.opendata.aws/sentinel-2-l2a-cogs/ COGS Stac API for sentinel-2