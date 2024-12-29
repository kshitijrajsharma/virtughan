
## Understand COG 

### Cloud Optimized GeoTIFF (COG)

A Cloud Optimized GeoTIFF (COG) is a GeoTIFF file that has been optimized for efficient access and processing in cloud environments. It allows for efficient reading of small portions of the file without requiring the entire file to be downloaded, making it ideal for use in web applications and cloud-based geographic information systems (GIS).

#### Key Features of COG

1. **Internal Tiling**: The image data is divided into regular tiles, typically 256x256 pixels. This tiling allows for efficient access to small parts of the image, which is particularly useful for operations like map tiling and zooming.

2. **Overviews (Pyramids)**: These are reduced resolution versions of the image that allow for faster access at different zoom levels. Overviews are stored within the same file and can be accessed quickly to display lower resolution images when high resolution is not necessary.

3. **Efficient Data Access**: COGs are structured to allow HTTP range requests, enabling clients to request just the portions of the file they need. This makes it possible to read a small part of the image without downloading the entire file.

4. **Metadata**: COGs include metadata that describes the internal tiling and overviews, enabling clients to efficiently locate and access the required data.

### How COG Works Internally

#### 1. Internal Tiling

- **Tiles**: The image is divided into regular, non-overlapping tiles (e.g., 256x256 pixels). Each tile can be accessed independently, allowing for efficient read operations on small portions of the image.
  
- **Tile Indexing**: The tiles are indexed within the file, allowing for quick location and retrieval of specific tiles.

#### 2. Overviews (Pyramids)

- **Purpose**: Overviews provide lower resolution versions of the image. They are used to quickly access and display the image at different zoom levels without processing the full-resolution data.

- **Levels**: Overviews are created at multiple levels of reduced resolution. For example, a 1:4 overview would represent the image at one-fourth the resolution of the original.

- **Storage**: Overviews are stored within the same GeoTIFF file and can be accessed through the same indexing mechanism as the full-resolution tiles.

#### 3. Efficient Data Access

- **HTTP Range Requests**: COGs support HTTP range requests, which allow clients to request specific byte ranges from the file. This is particularly useful for accessing individual tiles or overviews without downloading the entire file.

- **Indexing Metadata**: Metadata within the COG provides information about the structure of the file, including the location of tiles and overviews. This metadata is used by clients to efficiently locate and read the required data.

### Tiling and Overview Example

Consider an example where we have a high-resolution satellite image stored as a COG:

- **High-Resolution Image**: The original image is 10,000 x 10,000 pixels.
- **Tiles**: The image is divided into 256x256 pixel tiles.
- **Overviews**: Overviews are created at multiple levels (e.g., 1:2, 1:4, 1:8).

When a client requests a view of the image at a low zoom level, the client can:
1. **Access Overviews**: Fetch the appropriate overview level (e.g., 1:8) to quickly display a low-resolution version of the image.
2. **Access Tiles**: Request specific tiles from the full-resolution image as needed for detailed views.

### Benefits of COG

- **Performance**: Faster data access and reduced bandwidth usage due to efficient tile and overview retrieval.
- **Scalability**: Ideal for cloud environments where data is accessed over the network.
- **Flexibility**: Supports a wide range of applications, from web mapping to scientific analysis.



## How to Generate  COG for this project ?

Sentinel 2 Raw Image 
![image](https://github.com/user-attachments/assets/a8d724d5-8cf9-423b-bde9-5b45ce517b0d)

Work on 10m resolution 

Get all the jp2 images 

```bash
ls -1 *.jp2 > jp2_list.txt
```

Merge

```bash
gdal_merge.py -separate --optfile jp2_list.txt -o sentinel_r10.tif 
```

Or

```bash
gdal_merge.py -separate T45RTM_20241225T050129_B02_10m.jp2 T45RTM_20241225T050129_B03_10m.jp2 T45RTM_20241225T050129_B04_10m.jp2 T45RTM_20241225T050129_B08_10m.jp2 -o sentinel210m.tif -a_nodata 0
```


Check : 
```bash
gdalinfo sentinel_r10.tif
```

![image](https://github.com/user-attachments/assets/e38aaf11-b2c7-466d-909e-b20fa348be8d)


Size : 

2.1 GB for the merged file 



Conversion to COG : 

```bash
gdal_translate -of COG sentinel_r10.tif sentinel_r10_cog.tif  -co NUM_THREADS=32 -co COMPRESS=DEFLATE -co BIGTIFF=YES -co TILING_SCHEME=GoogleMapsCompatible -co LEVEL=9
```

GDAL info

```bash
 gdalinfo sentinel_r10_cog.tif
```
![image](https://github.com/user-attachments/assets/19283513-41f5-4d1e-a4b7-20c212c43625)

