"""
Pattern Engine — Stage 2 of Mosaic Studio.

Converts a 2-color mosaic grid into written row-by-row Overlay Mosaic
Crochet instructions, in the same textual convention used across
commercial overlay-mosaic pattern PDFs:

    Row 0: Use color A, 190ch
    Row 1: Use color A, bs, 188sc, bs
    Row 2: Use color B, bs, 188sc, bs
    Row 3: Use color A, bs, 2dc, 184sc, 2dc, bs
    ...

That text format itself (row number, color, run-length stitch counts,
border stitch markers) is a generic, functional notation used across the
overlay-mosaic pattern industry -- it is not copied from any specific
pattern. The stitch-generation RULE below is this project's own
implementation of the publicly documented "Overlay Mosaic Crochet"
technique (color changes every row; a double crochet worked around the
post of / into the stitch 2 rows below carries that row's color up and
over the current row to create the mosaic effect).

IMPORTANT / HONEST LIMITATION
------------------------------
Overlay mosaic crochet has a few competing conventions in the community
(which loop you insert into, back-post vs front-loop, which color's yarn
the "lifted" stitch actually uses). This module encodes one consistent,
defensible version of the technique, but it has NOT been physically
crocheted and verified. Exactly like the project plan says: swatch-test
any generated pattern on a small sample before trusting it for a sellable
PDF. `generate_pattern()` always returns a `warnings` list -- surface it
to the person, don't hide it.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class PatternResult:
    color_a_hex: str
    color_b_hex: str
    foundation_chain_row: str
    rows: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    h = hex_color.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _color_distance(c1: tuple[int, int, int], c2: tuple[int, int, int]) -> float:
    return sum((a - b) ** 2 for a, b in zip(c1, c2))


def reduce_to_two_colors(
    cells: list[list[str]], palette: list[str]
) -> tuple[list[list[str]], str, str]:
    """Overlay mosaic crochet is fundamentally a 2-color technique.

    If the source grid has more than 2 colors (e.g. because the image
    preview step used a higher max_colors for a nicer-looking proxy),
    collapse it down to the 2 most common colors, remapping every other
    cell to whichever of the two it's closer to.

    Returns (binary_cells, color_a_hex, color_b_hex) where color_a is the
    most frequent color in the original grid.
    """
    if not palette:
        raise ValueError("palette is empty")
    if len(palette) == 1:
        # Degenerate (flat color) image -- duplicate so the algorithm
        # still has two distinct labels to work with.
        a = b = palette[0]
    else:
        a, b = palette[0], palette[1]

    rgb_a, rgb_b = _hex_to_rgb(a), _hex_to_rgb(b)

    binary_cells: list[list[str]] = []
    for row in cells:
        new_row = []
        for cell in row:
            if cell == a:
                new_row.append(a)
            elif cell == b:
                new_row.append(b)
            else:
                rgb = _hex_to_rgb(cell)
                new_row.append(
                    a if _color_distance(rgb, rgb_a) <= _color_distance(rgb, rgb_b) else b
                )
        binary_cells.append(new_row)

    return binary_cells, a, b


def _rle(stitch_types: list[str]) -> str:
    """Run-length encode a list like ['sc','sc','dc','dc','dc'] into
    '2sc, 3dc'."""
    if not stitch_types:
        return ""
    parts = []
    current = stitch_types[0]
    count = 1
    for t in stitch_types[1:]:
        if t == current:
            count += 1
        else:
            parts.append(f"{count}{current}")
            current = t
            count = 1
    parts.append(f"{count}{current}")
    return ", ".join(parts)


def generate_pattern(
    cells: list[list[str]],
    palette: list[str],
    starting_color: str = "A",
    border_stitch: bool = True,
) -> PatternResult:
    """Generate written overlay mosaic crochet instructions from a grid.

    Args:
        cells: grid_height rows of grid_width hex colors, row 0 = TOP of
            the source image (matches image_to_grid.py's output).
        palette: distinct hex colors, most-used first (from image_to_grid).
        starting_color: 'A' or 'B' -- which label is used for the bottom
            (first-worked) row.
        border_stitch: whether to wrap every row with a border stitch
            (bs) at each end, matching the reference pattern convention.

    Returns:
        PatternResult with the foundation chain line, one text line per
        row (bottom row first, matching how the piece is actually
        crocheted), and a warnings list that should always be shown to
        the user.
    """
    if not cells or not cells[0]:
        raise ValueError("cells must be a non-empty grid")

    warnings: list[str] = []

    binary_cells, color_a_hex, color_b_hex = reduce_to_two_colors(cells, palette)
    if len(palette) > 2:
        warnings.append(
            f"الصورة فيها {len(palette)} ألوان؛ تقلصات تلقائياً لـ 2 (overlay "
            "mosaic كتقنية ديال لونين). راجع الـ Pattern Editor إلا بغيتي تبدل "
            "شكون اللون A وشكون B."
        )

    height = len(binary_cells)
    width = len(binary_cells[0])

    # Crochet rows are numbered bottom-to-top; our grid's row 0 is the TOP
    # of the source image, so row 1 of the pattern = the LAST row of cells.
    crochet_rows = list(reversed(binary_cells))  # index 0 -> pattern Row 1

    def color_label(row_num: int) -> str:
        is_start_parity = row_num % 2 == 1
        if starting_color.upper() == "A":
            return "A" if is_start_parity else "B"
        return "B" if is_start_parity else "A"

    def hex_for_label(label: str) -> str:
        return color_a_hex if label == "A" else color_b_hex

    chain_count = width + (2 if border_stitch else 0)
    foundation = f"Row 0: Use color {color_label(1)}, {chain_count}ch"

    rows_text: list[str] = []
    bad_base_rows: list[int] = []

    for i, row_cells in enumerate(crochet_rows):
        row_num = i + 1
        label = color_label(row_num)
        row_hex = hex_for_label(label)

        if row_num <= 2:
            # No row 2-below exists yet to overlay into -- these rows
            # must be a solid base color by construction.
            if any(c != row_hex for c in row_cells):
                bad_base_rows.append(row_num)
            stitch_types = ["sc"] * width
        else:
            stitch_types = [
                "sc" if cell == row_hex else "dc" for cell in row_cells
            ]

        body = _rle(stitch_types)
        if border_stitch:
            line = f"Row {row_num}: Use color {label}, bs, {body}, bs"
        else:
            line = f"Row {row_num}: Use color {label}, {body}"
        rows_text.append(line)

    if bad_base_rows:
        warnings.append(
            "الصفوف ديال الأساس (Row 1 وRow 2) خاصهم يكونوا بلون واحد صافي "
            "باش تخدم تقنية Overlay Mosaic -- الصورة ديالك فيها تفاصيل فهاد "
            f"الصفوف ({', '.join(map(str, bad_base_rows))}) اللي تهملات "
            "أوتوماتيكياً. زيد 2-3 صفوف فارغين (بلون صافي) فوق وتحت الصورة "
            "قبل التحويل باش تتفادى هاد المشكل."
        )

    warnings.append(
        "هاد التعليمات مصايبة أوتوماتيكياً ومابعدش تجربات يدوياً -- جرب "
        "عينة صغيرة (Swatch) قبل ما تعتبرها جاهزة للبيع، بحال ما هو مخطط "
        "فالمرحلة الرابعة (QA)."
    )

    return PatternResult(
        color_a_hex=color_a_hex,
        color_b_hex=color_b_hex,
        foundation_chain_row=foundation,
        rows=rows_text,
        warnings=warnings,
    )
