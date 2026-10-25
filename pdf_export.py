"""
PDF Ebook Maker -- Stage 3 of Mosaic Studio.

Combines the grid (chart), the written row instructions from
pattern_engine, and an optional AI cover photo into one PDF, laid out in
the same general shape as the commercial pattern PDFs this project
studied: cover -> pattern facts -> abbreviations -> chart -> written
instructions -> a final QA note.

This module only arranges ORIGINAL content supplied by the caller (the
person's own image-derived grid and generated instructions) into a PDF.
It does not embed, trace, or reproduce any third-party pattern design.

Built with ReportLab (as planned in the project's own tech-stack table).
"""

from __future__ import annotations

import io
from dataclasses import dataclass

from PIL import Image as PILImage
from PIL import ImageDraw, ImageFont
from reportlab.lib import colors
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Image as RLImage,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

PAGE_SIZE = LETTER
PAGE_WIDTH, PAGE_HEIGHT = PAGE_SIZE
MARGIN = 0.6 * inch
CONTENT_WIDTH = PAGE_WIDTH - 2 * MARGIN

CELL_PX = 18  # pixels per chart cell in the rendered raster
MAX_COLS_PER_PAGE = 60  # roughly matches the reference patterns' column split


@dataclass
class PdfExportInput:
    width: int
    height: int
    cells: list[list[str]]  # binary (2-color) grid, row 0 = top of image
    color_a_hex: str
    color_b_hex: str
    foundation_chain_row: str
    rows: list[str]
    warnings: list[str]
    title: str = "Mosaic Studio Pattern"
    cover_image_bytes: bytes | None = None


# ---------------------------------------------------------------------
# Chart rendering (grid -> PNG, sliced into page-sized column chunks)
# ---------------------------------------------------------------------


def _load_font(size: int) -> ImageFont.ImageFont:
    try:
        return ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", size
        )
    except OSError:
        return ImageFont.load_default()


def render_chart_slices(
    cells: list[list[str]], max_cols_per_page: int = MAX_COLS_PER_PAGE
) -> list[bytes]:
    """Render the grid as one or more PNG chart images, split by column
    ranges so each slice fits comfortably on a page -- the same approach
    the reference pattern PDFs use for wide charts."""
    height = len(cells)
    width = len(cells[0]) if height else 0
    if width == 0 or height == 0:
        return []

    label_gutter = 28
    font = _load_font(10)

    slices: list[bytes] = []
    col_start = 0
    while col_start < width:
        col_end = min(col_start + max_cols_per_page, width)
        cols_in_slice = col_end - col_start

        img_w = label_gutter + cols_in_slice * CELL_PX + label_gutter
        img_h = label_gutter + height * CELL_PX + label_gutter
        img = PILImage.new("RGB", (img_w, img_h), "white")
        draw = ImageDraw.Draw(img)

        for grid_row in range(height):
            # crochet Row 1 = bottom of image = last cells row; draw top-down
            # so Row (height) is at the TOP of the chart, Row 1 at the BOTTOM.
            y0 = label_gutter + grid_row * CELL_PX
            crochet_row_num = height - grid_row
            for col in range(col_start, col_end):
                x0 = label_gutter + (col - col_start) * CELL_PX
                color = cells[grid_row][col]
                draw.rectangle(
                    [x0, y0, x0 + CELL_PX, y0 + CELL_PX],
                    fill=color,
                    outline="#999999",
                )
            draw.text(
                (2, y0 + CELL_PX / 2 - 5),
                str(crochet_row_num),
                fill="black",
                font=font,
            )
            draw.text(
                (img_w - label_gutter + 4, y0 + CELL_PX / 2 - 5),
                str(crochet_row_num),
                fill="black",
                font=font,
            )

        for col in range(col_start, col_end):
            x0 = label_gutter + (col - col_start) * CELL_PX
            label = str(col + 1)
            draw.text((x0 + 2, 4), label, fill="black", font=font)
            draw.text(
                (x0 + 2, img_h - label_gutter + 4), label, fill="black", font=font
            )

        buf = io.BytesIO()
        img.save(buf, format="PNG")
        slices.append(buf.getvalue())

        col_start = col_end

    return slices


# ---------------------------------------------------------------------
# PDF assembly
# ---------------------------------------------------------------------


def _styles():
    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="CoverTitle",
            fontSize=28,
            leading=34,
            alignment=1,
            spaceAfter=10,
        )
    )
    styles.add(
        ParagraphStyle(
            name="CoverSubtitle",
            fontSize=13,
            leading=18,
            alignment=1,
            textColor=colors.HexColor("#6b5f58"),
        )
    )
    styles.add(
        ParagraphStyle(
            name="SectionHeading",
            fontSize=18,
            leading=22,
            spaceAfter=12,
            textColor=colors.HexColor("#8f3f46"),
        )
    )
    styles.add(
        ParagraphStyle(
            name="RowLine",
            fontName="Courier",
            fontSize=9,
            leading=13,
        )
    )
    styles.add(
        ParagraphStyle(
            name="WarningLine",
            fontSize=9,
            leading=13,
            textColor=colors.HexColor("#7a5c00"),
        )
    )
    return styles


def _cover_page(data: PdfExportInput, styles) -> list:
    flow = [Spacer(1, 0.6 * inch), Paragraph(data.title, styles["CoverTitle"])]
    flow.append(Paragraph("Overlay Mosaic Crochet Pattern", styles["CoverSubtitle"]))
    flow.append(Spacer(1, 0.3 * inch))

    if data.cover_image_bytes:
        img_buf = io.BytesIO(data.cover_image_bytes)
        pil_img = PILImage.open(img_buf)
        aspect = pil_img.height / pil_img.width
        display_w = CONTENT_WIDTH * 0.85
        display_h = display_w * aspect
        max_h = 5.5 * inch
        if display_h > max_h:
            display_h = max_h
            display_w = display_h / aspect
        img_buf.seek(0)
        flow.append(RLImage(img_buf, width=display_w, height=display_h))
    else:
        # No AI cover generated -- show a plain two-color swatch banner
        # instead of leaving an empty page.
        banner = PILImage.new("RGB", (800, 240))
        draw = ImageDraw.Draw(banner)
        draw.rectangle([0, 0, 400, 240], fill=data.color_a_hex)
        draw.rectangle([400, 0, 800, 240], fill=data.color_b_hex)
        buf = io.BytesIO()
        banner.save(buf, format="PNG")
        buf.seek(0)
        flow.append(RLImage(buf, width=CONTENT_WIDTH * 0.85, height=2.5 * inch))

    flow.append(Spacer(1, 0.3 * inch))
    flow.append(
        Paragraph(
            f"Grid: {data.width} x {data.height} stitches &nbsp;&nbsp;|&nbsp;&nbsp; "
            f"2 colors &nbsp;&nbsp;|&nbsp;&nbsp; Made with Mosaic Studio",
            styles["CoverSubtitle"],
        )
    )
    flow.append(PageBreak())
    return flow


def _facts_page(data: PdfExportInput, styles) -> list:
    flow = [Paragraph("Pattern Facts", styles["SectionHeading"])]

    def swatch(hex_color: str) -> RLImage:
        sw = PILImage.new("RGB", (40, 40), hex_color)
        buf = io.BytesIO()
        sw.save(buf, format="PNG")
        buf.seek(0)
        return RLImage(buf, width=0.3 * inch, height=0.3 * inch)

    rows_count = len(data.rows)
    table_data = [
        ["Technique", "Overlay Mosaic Crochet"],
        ["Chart width (stitches)", str(data.width)],
        ["Chart height (rows)", str(rows_count)],
        ["Color A", swatch(data.color_a_hex)],
        ["Color B", swatch(data.color_b_hex)],
        [
            "Yarn weight / hook size / finished size",
            "Not calculated automatically -- decide based on your own "
            "gauge swatch. Do not guess a number here without testing.",
        ],
    ]
    t = Table(table_data, colWidths=[2.2 * inch, CONTENT_WIDTH - 2.2 * inch])
    t.setStyle(
        TableStyle(
            [
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e4dcd6")),
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#fbf6f3")),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    flow.append(t)
    flow.append(PageBreak())
    return flow


def _abbreviations_page(styles) -> list:
    flow = [Paragraph("Abbreviations", styles["SectionHeading"])]
    table_data = [
        ["Abbreviation", "Meaning"],
        ["ch", "Chain"],
        ["sc", "Single Crochet"],
        ["dc", "Double Crochet (overlay / dropped stitch)"],
        ["bs", "Border Stitch (worked at start and end of every row)"],
        ["A / B", "Color A / Color B (alternate every row)"],
    ]
    t = Table(table_data, colWidths=[1.6 * inch, CONTENT_WIDTH - 1.6 * inch])
    t.setStyle(
        TableStyle(
            [
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#8f3f46")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e4dcd6")),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    flow.append(t)
    flow.append(Spacer(1, 0.2 * inch))
    flow.append(
        Paragraph(
            "Work each row from right to left, cutting the yarn at the "
            "end of each row per the written instructions. Each row "
            "starts and ends with one Border Stitch (bs).",
            getSampleStyleSheet()["BodyText"],
        )
    )
    flow.append(PageBreak())
    return flow


def _chart_pages(data: PdfExportInput, styles) -> list:
    flow = [Paragraph("Chart", styles["SectionHeading"])]
    slices = render_chart_slices(data.cells)
    for i, png_bytes in enumerate(slices):
        buf = io.BytesIO(png_bytes)
        pil_img = PILImage.open(buf)
        aspect = pil_img.height / pil_img.width
        display_w = CONTENT_WIDTH
        display_h = display_w * aspect
        max_h = PAGE_HEIGHT - 2 * MARGIN - 0.5 * inch
        if display_h > max_h:
            display_h = max_h
            display_w = display_h / aspect
        buf.seek(0)
        if i > 0:
            flow.append(Paragraph("Chart (continued)", styles["SectionHeading"]))
        flow.append(RLImage(buf, width=display_w, height=display_h))
        flow.append(PageBreak())
    return flow


def _instructions_pages(data: PdfExportInput, styles) -> list:
    flow = [Paragraph("Written Instructions", styles["SectionHeading"])]
    flow.append(Paragraph(data.foundation_chain_row, styles["RowLine"]))
    flow.append(Spacer(1, 4))
    for line in data.rows:
        flow.append(Paragraph(line, styles["RowLine"]))
    flow.append(PageBreak())
    return flow


def _final_notes_page(data: PdfExportInput, styles) -> list:
    flow = [Paragraph("Before You Sell This Pattern", styles["SectionHeading"])]
    flow.append(
        Paragraph(
            "This PDF was generated automatically by Mosaic Studio. The "
            "stitch-by-stitch instructions were produced by an "
            "algorithmic implementation of the Overlay Mosaic Crochet "
            "technique and have not been physically crocheted or "
            "verified.",
            getSampleStyleSheet()["BodyText"],
        )
    )
    flow.append(Spacer(1, 8))
    for w in data.warnings:
        flow.append(Paragraph(f"⚠ {w}", styles["WarningLine"]))
    flow.append(Spacer(1, 12))
    flow.append(
        Paragraph(
            "<b>Before listing this pattern for sale:</b> crochet a full "
            "swatch yourself, confirm stitch and row counts match the "
            "chart, and check the finished look against the intended "
            "design.",
            getSampleStyleSheet()["BodyText"],
        )
    )
    return flow


def build_pdf(output_path: str, data: PdfExportInput) -> None:
    """Build the full pattern PDF and write it to output_path."""
    styles = _styles()
    doc = SimpleDocTemplate(
        output_path,
        pagesize=PAGE_SIZE,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=MARGIN,
        bottomMargin=MARGIN,
        title=data.title,
    )

    story: list = []
    story += _cover_page(data, styles)
    story += _facts_page(data, styles)
    story += _abbreviations_page(styles)
    story += _chart_pages(data, styles)
    story += _instructions_pages(data, styles)
    story += _final_notes_page(data, styles)

    doc.build(story)
