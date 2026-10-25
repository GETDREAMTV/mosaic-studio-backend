"""
Mosaic Studio backend - MVP API.

One endpoint for now: POST /api/convert
Takes an uploaded image + grid settings, returns a JSON mosaic grid.

Run locally:
    pip install -r requirements.txt
    python app.py

Then it listens on http://localhost:5000
"""

from __future__ import annotations

import base64
import os
import uuid
from dataclasses import asdict

from dotenv import load_dotenv
from flask import Flask, jsonify, request, send_file
from flask_cors import CORS

from cover_generator import (
    CoverGenerationError,
    build_cover_prompt,
    generate_cover_image,
    is_configured as cover_is_configured,
)
from image_to_grid import image_to_grid
from pattern_engine import generate_pattern
from pdf_export import PdfExportInput, build_pdf

load_dotenv()  # reads backend/.env if present (never committed -- see .gitignore)

app = Flask(__name__)

# In local dev, allow any origin (the Vite dev server on a random port).
# In production, set FRONTEND_ORIGIN to your real frontend URL(s), comma
# separated if there's more than one (e.g. your Hostinger domain with and
# without "www"). This keeps randos off your backend's API.
_frontend_origin = os.environ.get("FRONTEND_ORIGIN")
if _frontend_origin:
    _allowed_origins = [o.strip() for o in _frontend_origin.split(",") if o.strip()]
    CORS(app, origins=_allowed_origins)
else:
    CORS(app)

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}


@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


@app.route("/api/convert", methods=["POST"])
def convert():
    if "image" not in request.files:
        return jsonify({"error": "no image uploaded (expected form field 'image')"}), 400

    file = request.files["image"]
    if file.filename == "":
        return jsonify({"error": "empty filename"}), 400

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        return jsonify({"error": f"unsupported file type: {ext}"}), 400

    try:
        grid_width = int(request.form.get("grid_width", 40))
        grid_height = int(request.form.get("grid_height", 40))
        max_colors = int(request.form.get("max_colors", 8))
    except ValueError:
        return jsonify({"error": "grid_width, grid_height and max_colors must be integers"}), 400

    if not (1 <= grid_width <= 300 and 1 <= grid_height <= 300):
        return jsonify({"error": "grid_width and grid_height must be between 1 and 300"}), 400
    if not (1 <= max_colors <= 40):
        return jsonify({"error": "max_colors must be between 1 and 40"}), 400

    filename = f"{uuid.uuid4().hex}{ext}"
    path = os.path.join(UPLOAD_DIR, filename)
    file.save(path)

    try:
        result = image_to_grid(path, grid_width, grid_height, max_colors)
    except Exception as exc:  # noqa: BLE001 - return a clean error to the client
        return jsonify({"error": f"failed to convert image: {exc}"}), 500
    finally:
        if os.path.exists(path):
            os.remove(path)

    return jsonify(result)


@app.route("/api/instructions", methods=["POST"])
def instructions():
    """Generate written row-by-row overlay mosaic crochet instructions
    from a previously-converted grid (no re-upload needed)."""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "expected JSON body with 'cells' and 'palette'"}), 400

    cells = data.get("cells")
    palette = data.get("palette")
    starting_color = data.get("starting_color", "A")

    if not cells or not isinstance(cells, list):
        return jsonify({"error": "missing or invalid 'cells'"}), 400
    if not palette or not isinstance(palette, list):
        return jsonify({"error": "missing or invalid 'palette'"}), 400
    if starting_color not in ("A", "B"):
        return jsonify({"error": "starting_color must be 'A' or 'B'"}), 400

    try:
        result = generate_pattern(cells, palette, starting_color=starting_color)
    except Exception as exc:  # noqa: BLE001 - return a clean error to the client
        return jsonify({"error": f"failed to generate instructions: {exc}"}), 500

    return jsonify(asdict(result))


@app.route("/api/cover-status", methods=["GET"])
def cover_status():
    """Lets the frontend know whether the optional OpenRouter cover
    generator is configured, without ever exposing the key itself."""
    return jsonify({"configured": cover_is_configured()})


@app.route("/api/generate-cover", methods=["POST"])
def generate_cover():
    """Optional: generate an AI mockup/cover photo via OpenRouter.

    Costs real OpenRouter credit per call -- only ever triggered by an
    explicit click in the UI, never automatically.
    """
    if not cover_is_configured():
        return (
            jsonify(
                {
                    "error": (
                        "OPENROUTER_API_KEY مامضبوطش. شوف backend/.env.example "
                        "وملف README."
                    )
                }
            ),
            400,
        )

    data = request.get_json(silent=True) or {}
    custom_prompt = data.get("prompt")
    color_a_hex = data.get("color_a_hex")
    color_b_hex = data.get("color_b_hex")
    title = data.get("title", "")

    if custom_prompt:
        prompt = custom_prompt
    elif color_a_hex and color_b_hex:
        prompt = build_cover_prompt(color_a_hex, color_b_hex, title)
    else:
        return (
            jsonify({"error": "خاصك تبعت 'prompt' أو 'color_a_hex' و 'color_b_hex'"}),
            400,
        )

    try:
        image_bytes = generate_cover_image(prompt)
    except CoverGenerationError as exc:
        return jsonify({"error": str(exc)}), 502

    # Also save a copy to disk so it survives even if the browser tab closes.
    filename = f"cover_{uuid.uuid4().hex}.png"
    path = os.path.join(UPLOAD_DIR, filename)
    with open(path, "wb") as f:
        f.write(image_bytes)

    return jsonify(
        {
            "image_base64": base64.b64encode(image_bytes).decode("ascii"),
            "prompt_used": prompt,
            "saved_as": filename,
        }
    )


@app.route("/api/export-pdf", methods=["POST"])
def export_pdf():
    """Assemble the full sellable pattern PDF: cover, facts, abbreviations,
    chart pages, written instructions, and a final QA note.

    Expects JSON: cells, palette, foundation_chain_row, rows, warnings,
    color_a_hex, color_b_hex, title (optional), cover_image_base64
    (optional, from a prior /api/generate-cover call).
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "expected a JSON body"}), 400

    required = [
        "cells",
        "palette",
        "foundation_chain_row",
        "rows",
        "color_a_hex",
        "color_b_hex",
    ]
    missing = [k for k in required if not data.get(k)]
    if missing:
        return jsonify({"error": f"missing fields: {', '.join(missing)}"}), 400

    cover_bytes = None
    cover_b64 = data.get("cover_image_base64")
    if cover_b64:
        try:
            cover_bytes = base64.b64decode(cover_b64)
        except Exception:  # noqa: BLE001
            return jsonify({"error": "cover_image_base64 is not valid base64"}), 400

    try:
        pdf_input = PdfExportInput(
            width=len(data["cells"][0]) if data["cells"] else 0,
            height=len(data["cells"]),
            cells=data["cells"],
            color_a_hex=data["color_a_hex"],
            color_b_hex=data["color_b_hex"],
            foundation_chain_row=data["foundation_chain_row"],
            rows=data["rows"],
            warnings=data.get("warnings", []),
            title=data.get("title") or "Mosaic Studio Pattern",
            cover_image_bytes=cover_bytes,
        )
    except Exception as exc:  # noqa: BLE001
        return jsonify({"error": f"invalid pattern data: {exc}"}), 400

    filename = f"pattern_{uuid.uuid4().hex}.pdf"
    path = os.path.join(UPLOAD_DIR, filename)
    try:
        build_pdf(path, pdf_input)
    except Exception as exc:  # noqa: BLE001
        return jsonify({"error": f"failed to build PDF: {exc}"}), 500

    download_name = f"{pdf_input.title.replace(' ', '_')}.pdf"
    return send_file(
        path,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=download_name,
    )


if __name__ == "__main__":
    # Render (and most free Python hosts) inject the port to bind via the
    # PORT env var; fall back to 5000 for local dev.
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "true").lower() == "true"
    app.run(debug=debug, host="0.0.0.0", port=port)
