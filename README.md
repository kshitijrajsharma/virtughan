# scog-compute

## Purpose

### 1. Efficient On-the-Fly Tile Processing 

The project demonstrates the capability to perform on-the-fly computation at various zoom levels, similar to Google Earth Engine, but using an open-source approach with Cloud Optimized GeoTIFFs (COGs) for Sentinel-2 imagery. This means that users can zoom in and out of large images and perform computations in real-time, without the need for pre-processing or storing the entire image. The project showcases the efficiency and scalability of this approach, which can be achieved with minimal hardware resources.

### 2. Virtual Data Cubes: Shifting from Storage to Computation 

The focus of data cubes should shift from storing huge images to optimizing computation, as COGs enable efficient computation without the need for storing the entire image. This approach introduces the concept of a virtual data cube, where images are stacked and computed over time, allowing for semantic layers and time dimensions to be processed without requiring storage of the entire dataset. In this approach, one provider can store the data, convert it to COG, and save it, while other users can focus on optimizing the computation without needing to store the image. This enables a more efficient use of resources and allows for the creation of virtual data cubes that can be processed and analyzed in reasonable-time.

### 3. Cloud Optiized Geotiff & STAC API for Earth Observation data and Computation
The project presnets the methods using COG , STAC API and numpy array , not only in terms of data access but also the efficient computation, enabling users to focus on areas of interest and process data accross different bands and semantic layers along time dimention maintaining resolution in optimal speed . The use of STAC API simplifies search and computation, allowing for the creation of virtual data cubes in any part of the world, without the need for downloading or storing entire images. This approach enables users to access and process only the parts of the image that are required, reducing the computational resources needed and increasing the speed of processing. The project demonstrates the potential of COGs to mxernize the way we work with large large earth observation datasets, enabling faster, efficient, maintainable and more scalable computation and analysis.

![image](https://github.com/user-attachments/assets/e5741f6b-d6c2-4e47-a794-21c2244a7476)


Learn about COG and how to generate one for this project [Here](./cog.md)

## Installation and Setup

### Prerequisites

- Python 3.10 or higher
- [poetry](https://python-poetry.org/) 

### Install PDM

If you don't have poetry installed, you can install it using the following command:

```bash
pip install poetry
```


#### Install 
```bash
poetry install
```

#### Activate virtualenv 
```bash
poetry shell
```

#### Run 

```bash
poetry run uvicorn main:app --reload
```


## Resources and Credits 

- https://registry.opendata.aws/sentinel-2-l2a-cogs/ COGS Stac API for sentinel-2
