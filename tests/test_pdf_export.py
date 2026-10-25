import io
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from PIL import Image
from pypdf import PdfReader

from pdf_export import PdfExportInput, build_pdf, render_chart_slices


def _sample_grid(width=20, height=10, color_a="#aa0000", color_b="#eeeeee"):
    cells = []
    for r in range(height):
        row = [color_a if (r + c) % 4 == 0 else color_b for c in range(width)]
        cells.append(row)
    return cells


def _sample_input(**overrides) -> PdfExportInput:
    width, height = 20, 10
    cells = _sample_grid(width, height)
    rows = [f"Row {i}: Use color A, bs, {width}sc, bs" for i in range(1, height + 1)]
    defaults = dict(
        width=width,
        height=height,
        cells=cells,
        color_a_hex="#aa0000",
        color_b_hex="#eeeeee",
        foundation_chain_row=f"Row 0: Use color A, {width + 2}ch",
        rows=rows,
        warnings=["test warning -- swatch before selling"],
        title="Test Pattern",
        cover_image_bytes=None,
    )
    defaults.update(overrides)
    return PdfExportInput(**defaults)


# ---------------------------------------------------------------------
# render_chart_slices
# ---------------------------------------------------------------------


def test_render_chart_slices_returns_one_png_for_narrow_grid():
    cells = _sample_grid(width=20, height=10)
    slices = render_chart_slices(cells, max_cols_per_page=60)
    assert len(slices) == 1
    img = Image.open(io.BytesIO(slices[0]))
    assert img.format == "PNG"


def test_render_chart_slices_splits_wide_grid_into_multiple_pages():
    cells = _sample_grid(width=150, height=10)
    slices = render_chart_slices(cells, max_cols_per_page=60)
    # 150 cols / 60 per page -> 3 slices
    assert len(slices) == 3


def test_render_chart_slices_empty_grid_returns_empty_list():
    assert render_chart_slices([]) == []


# ---------------------------------------------------------------------
# build_pdf
# ---------------------------------------------------------------------


def test_build_pdf_creates_a_valid_multi_page_pdf(tmp_path):
    out_path = tmp_path / "pattern.pdf"
    data = _sample_input()
    build_pdf(str(out_path), data)

    assert out_path.exists()
    assert out_path.stat().st_size > 1000  # not an empty/broken file

    reader = PdfReader(str(out_path))
    # cover + facts + abbreviations + >=1 chart page + instructions + notes
    assert len(reader.pages) >= 6


def test_build_pdf_with_cover_image_bytes(tmp_path):
    cover_img = Image.new("RGB", (400, 300), "#336699")
    buf = io.BytesIO()
    cover_img.save(buf, format="PNG")

    out_path = tmp_path / "pattern_with_cover.pdf"
    data = _sample_input(cover_image_bytes=buf.getvalue())
    build_pdf(str(out_path), data)

    reader = PdfReader(str(out_path))
    assert len(reader.pages) >= 6


def test_build_pdf_wide_grid_adds_extra_chart_pages(tmp_path):
    wide_cells = _sample_grid(width=150, height=10)
    rows = [f"Row {i}: Use color A, bs, 150sc, bs" for i in range(1, 11)]

    out_narrow = tmp_path / "narrow.pdf"
    build_pdf(str(out_narrow), _sample_input())

    out_wide = tmp_path / "wide.pdf"
    build_pdf(
        str(out_wide),
        _sample_input(width=150, cells=wide_cells, rows=rows),
    )

    narrow_pages = len(PdfReader(str(out_narrow)).pages)
    wide_pages = len(PdfReader(str(out_wide)).pages)
    assert wide_pages > narrow_pages


def test_build_pdf_extracted_text_contains_row_instructions(tmp_path):
    out_path = tmp_path / "pattern.pdf"
    data = _sample_input()
    build_pdf(str(out_path), data)

    reader = PdfReader(str(out_path))
    all_text = "\n".join(page.extract_text() or "" for page in reader.pages)
    assert "Row 1:" in all_text
    assert "Overlay Mosaic Crochet" in all_text
