# **VirtuGhan: A Virtual Computation Cube for On-the-Fly Geospatial Computations and Tiling**

## **Authors**

*Kshitij Raj Sharma , Upendra Oli*

## **Abstract**

We introduce virtughan, a Python-based geospatial data pipeline designed for dynamic, on-the-fly computations on raster tiles. This system provides money-efficient and scalable tile processing by leveraging Cloud-Optimized GeoTIFFs (COGs) and SpatioTemporal Asset Catalog (STAC) endpoints, and delivering immediate results at varying zoom levels and time dimensions. Specifically, the pipeline can dynamically scale from single pixels to multiple zoom levels, applying user-defined computations or filtering steps while creating each tile. By focusing on tile-based requests, virtughan minimizes data transfer, ensures computational efficiency, and supports near-real-time data exploration to cloud-based geospatial engines, but on minimal hardware.

## **1\. Introduction**

Traditionally, geospatial pipelines store pre-processed raster files, which can limit flexibility when new analyses are required. virtughan breaks this limitation by computing results on the fly during tile requests. Its design is influenced by “virtual data cube” concepts and aims to provide capabilities similar to platforms like Google Earth Engine while keeping costs manageable. The system:

1. Fetches only the required data for (x, y, zoom) tiles across time.  
2. Scales single pixels to multiple zoom levels, ensuring consistent spatial footprints for advanced analyses.  
3. Integrates with Sentinel-2 STAC catalogs and COGs for partial reads, thus reducing overall I/O.  
4. Applies real-time filtering and computation formulas to select only those tiles that fully cover the area of interest.

## **2\. Background**

* **Tile-Based Delivery**: Common for web mapping platforms, tiling offers a straightforward approach to request a small portion of data for a given bounding box at a particular zoom.  
* **Data Cubes**: Provide a conceptual framework to store spatiotemporal data, but can be large. virtughan uses a “virtual” approach, reading only the data it needs without storing.  
* **STAC and COGs**: Allow the system to quickly discover relevant imagery and perform efficient windowed reads on cloud-hosted GeoTIFFs.  
* **FastAPI**: Powers asynchronous requests, making it a suitable technology for scalable microservices serving tiles.

## **3\. System Overview and Methodology**

### **3.1 Virtual Data Cube Concept**

At the core is a **virtual data cube**:

* **No massive pre-stacked arrays**: Instead, STAC items indicate where each requested tile’s data can be fetched.  
* **Band Math & Corrections**: The system can apply formulas or filtering steps (e.g., remove cloud-covered or incomplete scenes) at tile creation time.  
* **Temporal Dimension**: Maintains the same (x, y) footprint across time, letting users visualize changes or compute multi-temporal metrics without re-downloading entire scenes.

### **3.2 Data Flow**

1. **Tile Request**: Front-end or an API user requests `(z, x, y)`—plus time, formula, or filter criteria.  
2. **Bounding Box Calculation**: **mercantile** determines the bounding box for the tile.  
3. **STAC Query & Filtering**: The pipeline searches STAC for relevant Sentinel-2 scenes that **fully cover** the bounding box and time range.  
4. **Windowed Read & Original Resolution**: Partial reads from COGs at the original or resampled resolution.  
5. **On-the-Fly Computation**: Pixel-level transformations (e.g., NDVI, custom ratio computations, band filtering) on different scales are applied.  
6. **Response & Caching**: The finished tile is encoded as a PNG (or another format) and cached for subsequent requests.

---

## **4\. Implementation Details**

### **4.1 Project Structure**

* **`src/vcube/`**:  
  * **Core Classes** for the virtual data cube (coordinates, STAC references, band configuration).  
  * **Computation Methods** that implement tile-based processing and filtering/correction.  
  * **Async Caching** utilities for scalable tile servicing.  
* **FastAPI Endpoints**:  
  * Provide routes for requesting tiles (`/tiles/{z}/{x}/{y}`), time slices (`/tiles/{time}/{z}/{x}/{y}`), or specific computations (`/compute/{formula}/{z}/{x}/{y}`).  
* **`virtughan` Package**:  
  * A cohesive library that wraps these functionalities, enabling easy import and usage in external projects.

### **4.2 Tile-Based Computations and Scaling**

A primary feature of virtughan is its tile-based approach:

* During the tile creation process, the system directly computes any required transformations (e.g., spectral indices).  
* The same single pixel can be “scaled” to various zoom levels by adjusting how data is resampled. This means a user can quickly see broad overviews (low zoom) or fine-detail tiles (high zoom) with consistent computations.  
* By only fetching the tile’s bounding box from COGs, data transfer and storage costs are minimized. This makes the approach money efficient and practical even on moderate hardware.

### **4.3 Sentinel-2 and AWS STAC Integration**

Currently, the system primarily uses **Sentinel-2** data from AWS:

* **Filtering**: Scenes that do not fully cover the tile’s bounding box can be discarded, ensuring uniform coverage.  
* **Data Corrections**: On-the-fly correction (e.g., excluding cloud pixels if flagged, or ignoring incomplete scenes).  
* **Spectral Computations**: Quick formulas like NDVI or custom band ratios are computed while generating tiles.

## **5\. Advantages of tile-based computation** 

**Integration in Data Explorers and Data Cubes**: By fetching only the needed tiles rather than entire scenes, analysts can efficiently browse and manipulate geospatial data, reducing both storage requirements and processing overhead.

**Multi-Scale Computations**: Tiles are inherently designed for flexible zoom levels, allowing workflows to seamlessly transition between coarse overview analyses and fine-grained inspections without re-downloading massive imagery.

**Cost and Memory Efficiency**: Focusing on partial reads (tiles) at the time of computation avoids large up-front investments in data storage and processing, making scalable geospatial analysis more affordable and accessible.

**STAC Filtering and Metadata Utilization**: The ability to filter and retrieve specific scenes based on STAC metadata streamlines data discovery and ensures that only relevant scenes can be fetched, & high-quality tiles are processed.

**Ideal for ML Pipelines**: By extracting precisely the required tiles—and appending any necessary metadata or on-the-fly computations—this approach can feed large-scale or foundation models without overwhelming resources, enabling more targeted and efficient training.

**Versatile Frontend and Backend Applications**: Whether powering interactive web maps or supporting heavy analytical jobs, the tile-based approach provides a unified way to request, process, and deliver geospatial data in near real-time.

## **6\. Future Directions**

* **Mosaicking**: Extending the pipeline to merge multiple scenes seamlessly for large-scale coverage.  
* **Expanded Sensor Support**: Adding Landsat, MODIS, and commercial satellites.  
* **User-Customizable Formulas**: A plugin system for advanced band math or machine learning inference.  
* **Distributed Caching**: Scaling to higher workloads or multi-server environments.

## **7\. Conclusion**

virtughan demonstrates how a virtual data cube architecture coupled with a tile-based approach enables real-time raster computations at varying scales and time slices. By fetching only the necessary pixels, applying on-the-fly calculations, and leveraging STAC and COG protocols, it delivers a cost-effective, scalable, and flexible solution for modern geospatial applications. Whether one needs a broad overview or a pixel-level deep dive, virtughan’s tile-based computations offer a blueprint for minimal-hardware, high-impact geospatial data processing.

---

## **References**

1. [rio-tiler Repository](https://github.com/cogeotiff/rio-tiler)  
2. [mercantile Repository](https://github.com/mapbox/mercantile)  
3. STAC: SpatioTemporal Asset Catalog. [https://stacspec.org](https://stacspec.org)  
4. FastAPI: [https://fastapi.tiangolo.com](https://fastapi.tiangolo.com)   
5. Rasterio Documentation: [https://rasterio.readthedocs.io](https://rasterio.readthedocs.io)  
6. [https://registry.opendata.aws/sentinel-2-l2a-cogs/](https://registry.opendata.aws/sentinel-2-l2a-cogs/)


### **Acknowledgments**

We thank the open-source community for creating and maintaining the foundational GIS libraries leveraged in this project, as well as our professors and fellow colleagues that helped us shape the idea and provide the opportunity to our master's program , Coopernicus Masters in Digital Earth , Co funded by European Union. 
