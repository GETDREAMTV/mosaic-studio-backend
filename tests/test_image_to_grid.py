import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from PIL import Image

from image_to_grid import image_to_grid


def _make_image(path, size=(100, 100), color="red"):
    img = Image.new("RGB", size, color=color)
    img.save(path)
    return path


def test_grid_has_requested_dimensions(tmp_path):
    img_path = _make_image(tmp_path / "solid.png")
    result = image_to_grid(str(img_path), grid_width=12, grid_height=8, max_colors=4)

    assert result["width"] == 12
    assert result["height"] == 8
    assert len(result["cells"]) == 8
    assert all(len(row) == 12 for row in result["cells"])


def test_solid_color_image_produces_single_palette_color(tmp_path):
    img_path = _make_image(tmp_path / "blue.png", color=(10, 20, 230))
    result = image_to_grid(str(img_path), grid_width=5, grid_height=5, max_colors=2)

    # A flat-color image should quantize down to one dominant hex color.
    assert len(result["palette"]) == 1
    assert all(cell == result["palette"][0] for row in result["cells"] for cell in row)


def test_palette_is_sorted_most_used_first(tmp_path):
    # Half red, half green -> both colors should appear, red should dominate.
    img = Image.new("RGB", (100, 100), color=(255, 0, 0))
    for x in range(100):
        for y in range(80, 100):
            img.putpixel((x, y), (0, 255, 0))
    path = tmp_path / "split.png"
    img.save(path)

    result = image_to_grid(str(path), grid_width=10, grid_height=10, max_colors=2)
    assert len(result["palette"]) == 2

    flat = [cell for row in result["cells"] for cell in row]
    counts = {c: flat.count(c) for c in result["palette"]}
    most_common = max(counts, key=counts.get)
    assert result["palette"][0] == most_common


def test_invalid_dimensions_raise(tmp_path):
    img_path = _make_image(tmp_path / "x.png")
    with pytest.raises(ValueError):
        image_to_grid(str(img_path), grid_width=0, grid_height=10)
    with pytest.raises(ValueError):
        image_to_grid(str(img_path), grid_width=10, grid_height=10, max_colors=0)
