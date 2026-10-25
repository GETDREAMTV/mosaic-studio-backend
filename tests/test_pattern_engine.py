import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pattern_engine import _rle, generate_pattern, reduce_to_two_colors


# ---------------------------------------------------------------------
# RLE helper
# ---------------------------------------------------------------------


def test_rle_basic():
    assert _rle(["sc", "sc", "sc"]) == "3sc"
    assert _rle(["sc", "sc", "dc", "dc", "dc"]) == "2sc, 3dc"
    assert _rle(["dc", "sc", "dc"]) == "1dc, 1sc, 1dc"


def test_rle_empty():
    assert _rle([]) == ""


# ---------------------------------------------------------------------
# reduce_to_two_colors
# ---------------------------------------------------------------------


def test_reduce_to_two_colors_keeps_binary_grid_unchanged():
    cells = [["#ff0000", "#0000ff"], ["#0000ff", "#ff0000"]]
    palette = ["#ff0000", "#0000ff"]
    binary, a, b = reduce_to_two_colors(cells, palette)
    assert a == "#ff0000"
    assert b == "#0000ff"
    assert binary == cells


def test_reduce_to_two_colors_collapses_extra_colors():
    # third color (#ff0101) is almost red -> should map to color A
    cells = [["#ff0000", "#0000ff", "#ff0101"]]
    palette = ["#ff0000", "#0000ff", "#ff0101"]
    binary, a, b = reduce_to_two_colors(cells, palette)
    assert binary == [["#ff0000", "#0000ff", "#ff0000"]]
    assert a == "#ff0000"
    assert b == "#0000ff"


# ---------------------------------------------------------------------
# generate_pattern
# ---------------------------------------------------------------------


def _solid_row(color, width):
    return [color] * width


def test_foundation_chain_counts_border_stitches():
    A, B = "#aa0000", "#eeeeee"
    # 3 solid rows (bottom-up safe), width 4 -> chain = 4 + 2 border = 6
    cells = [_solid_row(A, 4), _solid_row(B, 4), _solid_row(A, 4)]
    result = generate_pattern(cells, [A, B], starting_color="A")
    assert result.foundation_chain_row == "Row 0: Use color A, 6ch"


def test_first_two_rows_are_forced_solid_sc():
    A, B = "#aa0000", "#eeeeee"
    cells = [_solid_row(A, 5), _solid_row(B, 5), _solid_row(A, 5)]
    result = generate_pattern(cells, [A, B], starting_color="A")
    # pattern Row 1 = last grid row (bottom of image) = cells[2] = A
    assert result.rows[0] == "Row 1: Use color A, bs, 5sc, bs"
    # pattern Row 2 = cells[1] = B
    assert result.rows[1] == "Row 2: Use color B, bs, 5sc, bs"


def test_overlay_row_produces_dc_where_opposite_color_requested():
    A, B = "#aa0000", "#eeeeee"
    # Row3 (pattern) = grid row 0 (top): mostly A with 1 B cell in the middle
    # -> that B cell should become a 'dc' (color B lifted through a color-A row)
    row_top = [A, A, B, A, A]
    cells = [row_top, _solid_row(B, 5), _solid_row(A, 5)]
    result = generate_pattern(cells, [A, B], starting_color="A")
    assert result.rows[2] == "Row 3: Use color A, bs, 2sc, 1dc, 2sc, bs"


def test_warns_when_base_rows_are_not_solid():
    A, B = "#aa0000", "#eeeeee"
    # bottom row (-> pattern Row 1) has a stray B cell -- not physically
    # possible on the very first row, should be flagged.
    bad_bottom_row = [A, B, A]
    cells = [_solid_row(A, 3), _solid_row(B, 3), bad_bottom_row]
    result = generate_pattern(cells, [A, B], starting_color="A")
    assert any("Row 1" in w or "1" in w for w in result.warnings)


def test_warns_when_more_than_two_colors_present():
    A, B, C = "#aa0000", "#eeeeee", "#00ff00"
    cells = [_solid_row(A, 3), _solid_row(B, 3), [A, C, A]]
    result = generate_pattern(cells, [A, B, C], starting_color="A")
    assert any("overlay" in w.lower() or "ألوان" in w for w in result.warnings)


def test_always_includes_swatch_test_warning():
    A, B = "#aa0000", "#eeeeee"
    cells = [_solid_row(A, 3), _solid_row(B, 3), _solid_row(A, 3)]
    result = generate_pattern(cells, [A, B])
    assert any("Swatch" in w or "جرب" in w for w in result.warnings)
