import os
from io import BytesIO

import matplotlib.pyplot as plt
import numpy as np
import rasterio
from PIL import Image
from pyproj import Transformer
from rasterio.windows import from_bounds


class EngineCommon:
    """
    Base class containing common utilities for Engine processing.
    """

    def _transform_bbox(self, crs):
        transformer = Transformer.from_crs("epsg:4326", crs, always_xy=True)
        min_x, min_y = transformer.transform(self.bbox[0], self.bbox[1])
        max_x, max_y = transformer.transform(self.bbox[2], self.bbox[3])
        return min_x, min_y, max_x, max_y

    def _calculate_window(self, cog, min_x, min_y, max_x, max_y):
        return from_bounds(min_x, min_y, max_x, max_y, cog.transform)

    def _is_window_out_of_bounds(self, window):
        return (
            window.col_off < 0
            or window.row_off < 0
            or window.width <= 0
            or window.height <= 0
        )
    def _pad_array(self, array, target_shape, fill_value=np.nan):
        """
        Pad the array to the target shape.

        Parameters:
        array (numpy.ndarray): Array to pad.
        target_shape (tuple): Target shape to pad to.
        fill_value (float): Value to use for padding.

        Returns:
        numpy.ndarray: Padded array.
        """
        pad_width = [
            (0, max(0, target - current))
            for current, target in zip(array.shape, target_shape)
        ]
        return np.pad(array, pad_width, mode="constant", constant_values=fill_value)

    def _save_geotiff(self, data, output_file):
        """
        Save array data as a GeoTIFF.

        Parameters:
        data (numpy.ndarray): Array to save.
        output_file (str): Output file path.
        """
        nodata_value = -9999
        data = np.where(np.isnan(data), nodata_value, data)
        with rasterio.open(
            output_file,
            "w",
            driver="GTiff",
            height=data.shape[1],
            width=data.shape[2],
            count=data.shape[0],
            dtype=data.dtype,
            crs=self.crs,
            transform=self.transform,
            nodata=nodata_value,
        ) as dst:
            for band in range(1, data.shape[0] + 1):
                dst.write(data[band - 1], band)
    def add_text_to_image(self, image_path, text):
        """
        Add a title text to an image and save.

        Parameters:
        image_path (str): Path to the input image.
        text (str): Title to add.

        Returns:
        str: Path to saved image with text.
        """
        with rasterio.open(image_path) as src:
            image_array = (
                src.read(1)
                if src.count == 1
                else np.dstack([src.read(i) for i in range(1, 4)])
            )
            image_array = (
                (image_array - image_array.min())
                / (image_array.max() - image_array.min())
                * 255
            )
            image = Image.fromarray(image_array.astype(np.uint8))

        plt.figure(figsize=(10, 10))
        plt.imshow(image, cmap=self.cmap if src.count == 1 else None)
        plt.axis("off")
        plt.title(text)
        temp_image_path = os.path.splitext(image_path)[0] + "_text.png"
        plt.savefig(temp_image_path, bbox_inches="tight", pad_inches=0.1)
        plt.close()
        return temp_image_path

    @staticmethod
    def create_gif(image_list, output_path, duration_per_image=1):
        """
        Create a GIF from a list of images.

        Parameters:
        image_list (list): List of image file paths.
        output_path (str): Output GIF path.
        duration_per_image (int): Duration per frame (seconds).
        """
        sorted_image_list = sorted(image_list)
        images = [Image.open(image_path) for image_path in sorted_image_list]
        max_width = max(image.width for image in images)
        max_height = max(image.height for image in images)
        resized_images = [
            image.resize((max_width, max_height), Image.LANCZOS) for image in images
        ]

        frame_duration = duration_per_image * 1000  # ms
        resized_images[0].save(
            output_path,
            save_all=True,
            append_images=resized_images[1:],
            duration=frame_duration,
            loop=0,
        )
        print(f"Saved timeseries GIF to {output_path}")
    def _create_image(self, data):
        """
        Normalize and create an RGB image from data.

        Parameters:
        data (numpy.ndarray): Data array.

        Returns:
        numpy.ndarray: RGB image array.
        """
        if data.shape[0] == 1:
            result_normalized = (data[0] - data[0].min()) / (data[0].max() - data[0].min())
            colormap = plt.get_cmap(self.cmap)
            result_colored = colormap(result_normalized)
            return (result_colored[:, :, :3] * 255).astype(np.uint8)
        else:
            image_array = np.transpose(data, (1, 2, 0))
            image_array = (
                (image_array - image_array.min())
                / (image_array.max() - image_array.min())
                * 255
            )
            return image_array.astype(np.uint8)

    def _plot_result(self, image, output_file):
        """
        Plot and save an aggregated result image.

        Parameters:
        image (numpy.ndarray): Image to plot.
        output_file (str): Output file path.
        """
        plt.figure(figsize=(10, 10))
        plt.imshow(image)
        plt.title(f"Aggregated {self.operation} Calculation")
        plt.xlabel(
            f"From {self.start_date} to {self.end_date}\nCloud Cover < {self.cloud_cover}%\nBBox: {self.bbox}\nTotal Scenes Processed: {len(self.result_list)}"
        )
        plt.colorbar(
            plt.cm.ScalarMappable(cmap=plt.get_cmap(self.cmap)),
            ax=plt.gca(),
            shrink=0.5,
        )
        plt.savefig(
            output_file.replace(".tif", "_colormap.png"),
            bbox_inches="tight",
            pad_inches=0.1,
        )
        plt.close()
