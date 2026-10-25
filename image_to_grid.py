"""
Core image -> mosaic grid conversion for Mosaic Studio.

This is an original implementation written in Python (Pillow). It does not
reuse any code from the smach/crochet (R/Shiny, MIT-licensed) reference
project -- only the general concept of "reduce an image to a colored grid"
is shared, which is the standard approach for any graphgan/mosaic-style
crochet chart generator.

The algorithm:
1. Load the image and convert to RGB.
2. Quantize (reduce) the number of colors using Pillow's median-cut
   quantizer. This groups similar colors together, which keeps the
   resulting pattern from having too many near-duplicate shades (bad for
   crochet, since every extra color means a bobbin/yarn change).
3. Resize the quantized image down to the target grid width/height using
   NEAREST resampling so each output pixel maps cleanly to one grid cell
   (no blending of colors at cell boundaries).
4. Read off one hex color per cell, and build a palette (sorted by how
   often each color is used, most common first) so the frontend can offer
   it as a swatch picker for manual edits.
"""

from __future__ import annotations

from PIL import Image


def image_to_grid(
    image_path: str,
    grid_width: int,
    grid_height: int,
    max_colors: int = 8,
) -> dict:
    """Convert an image file into a mosaic crochet grid.

    Args:
        image_path: path to the source image on disk.
        grid_width: number of stitches/cells across.
        grid_height: number of rows.
        max_colors: max number of distinct yarn colors to reduce to.

    Returns:
        {
            "width": int,
            "height": int,
            "cells": [[hex, hex, ...], ...]   # grid_height rows of grid_width hex colors
            "palette": [hex, ...]              # distinct colors, most-used first
        }
    """
    if grid_width < 1 or grid_height < 1:
        raise ValueError("grid_width and grid_height must be >= 1")
    if max_colors < 1:
        raise ValueError("max_colors must be >= 1")

    img = Image.open(image_path).convert("RGB")

    # Reduce the palette first, on the full-resolution image, so the
    # downscale step picks the dominant color for each cell rather than an
    # arbitrary single pixel.
    quantized = img.quantize(colors=max_colors, method=Image.MEDIANCUT).convert("RGB")

    small = quantized.resize((grid_width, grid_height), Image.NEAREST)
    pixels = small.load()

    cells: list[list[str]] = []
    counts: dict[str, int] = {}

    for y in range(grid_height):
        row: list[str] = []
        for x in range(grid_width):
            r, g, b = pixels[x, y]
            hex_color = "#{:02x}{:02x}{:02x}".format(r, g, b)
            row.append(hex_color)
            counts[hex_color] = counts.get(hex_color, 0) + 1
        cells.append(row)

    palette = sorted(counts.keys(), key=lambda c: -counts[c])

    return {
        "width": grid_width,
        "height": grid_height,
        "cells": cells,
        "palette": palette,
    }
