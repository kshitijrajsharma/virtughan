import asyncio
from io import BytesIO

import numpy as np
from PIL import Image
from matplotlib import pyplot as plt
from rio_tiler.io import COGReader


class TileCommon:
    """
    Base class containing shared tile processing functions.
    """

    @staticmethod
    def apply_colormap(result, colormap_str):
        """
        Apply a matplotlib colormap to a normalized array and return an image.

        Parameters:
        result (numpy.ndarray): Array of values.
        colormap_str (str): Name of the matplotlib colormap.

        Returns:
        PIL.Image.Image: RGB image with applied colormap.
        """
        result_normalized = (result - result.min()) / (result.max() - result.min())
        colormap = plt.get_cmap(colormap_str)
        result_colored = colormap(result_normalized)
        result_image = (result_colored[:, :, :3] * 255).astype(np.uint8)
        return Image.fromarray(result_image)

    @staticmethod
    async def fetch_tile(url, x, y, z):
        """
        Fetch a tile from a COG URL at a specific x, y, z coordinate.

        Parameters:
        url (str): Cloud-Optimized GeoTIFF URL.
        x (int): Tile x index.
        y (int): Tile y index.
        z (int): Zoom level.

        Returns:
        numpy.ndarray: The tile as a NumPy array.
        """

        def read_tile():
            with COGReader(url) as cog:
                tile, _ = cog.tile(x, y, z)
                return tile

        return await asyncio.to_thread(read_tile)
