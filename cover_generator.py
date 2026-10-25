"""
AI cover / mockup image generation via OpenRouter -- OPTIONAL feature.

This only runs if OPENROUTER_API_KEY is set in the environment (meant to
come from a local backend/.env file that is NEVER committed or shared --
see .gitignore and .env.example). It is never called automatically:
every call spends real OpenRouter account credit, so it only runs when
the person explicitly clicks "generate cover" in the UI.

API reference (confirmed Oct 2026):
https://openrouter.ai/blog/tutorials/image-generation-models/

    POST https://openrouter.ai/api/v1/images
    { "model": "google/gemini-2.5-flash-image", "prompt": "..." }
    -> response.data[0].b64_json   (base64-encoded image bytes)

Notes from that reference worth keeping in mind:
- No image model on OpenRouter is free; every call bills the account.
- A 402 response means the account balance is at/below $1.
- Model slugs change over time -- DEFAULT_MODEL below may need updating;
  check https://openrouter.ai/api/v1/images/models for the current list.
"""

from __future__ import annotations

import base64
import os

import requests

OPENROUTER_URL = "https://openrouter.ai/api/v1/images"
DEFAULT_MODEL = "google/gemini-2.5-flash-image"
REQUEST_TIMEOUT_SECONDS = 60


class CoverGenerationError(Exception):
    """Raised with a short, human-readable (Darija) message -- never
    includes the API key itself."""


def is_configured() -> bool:
    return bool(os.environ.get("OPENROUTER_API_KEY"))


def build_cover_prompt(color_a_hex: str, color_b_hex: str, title: str = "") -> str:
    """Build a generic, original mockup-photo prompt from the pattern's
    two colors. Deliberately generic/staged-product-photo in style --
    not a copy of any specific seller's cover design or layout, and the
    model is told explicitly not to add any text/logo/watermark."""
    subject = f'of a "{title}" design ' if title else ""
    return (
        f"Professional product photography {subject}of a handmade "
        f"two-color crochet mosaic blanket draped over a cozy armchair, "
        f"geometric mosaic pattern using colors {color_a_hex} and "
        f"{color_b_hex}, soft natural window light, warm neutral home "
        f"interior styling, shallow depth of field, visible yarn "
        f"texture, no text, no logo, no watermark"
    )


def generate_cover_image(prompt: str, model: str = DEFAULT_MODEL) -> bytes:
    """Call OpenRouter's image API and return raw image bytes.

    Raises CoverGenerationError with a short Darija message on any
    failure (missing key, bad key, no credit, bad response, network
    error). Never includes the API key in any message or log.
    """
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise CoverGenerationError(
            "ماكاينش OPENROUTER_API_KEY. زيد ملف backend/.env فيه السطر "
            "OPENROUTER_API_KEY=sk-... (شوف backend/.env.example) ثم عاود "
            "شغل الـ backend."
        )

    try:
        resp = requests.post(
            OPENROUTER_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={"model": model, "prompt": prompt},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
    except requests.RequestException as exc:
        raise CoverGenerationError(f"ماقدرناش نوصلو لـ OpenRouter: {exc}") from exc

    if resp.status_code == 402:
        raise CoverGenerationError(
            "الرصيد ديالك فـ OpenRouter ناقص (أقل من $1). زيد رصيد فـ "
            "openrouter.ai/credits ثم عاود جرب."
        )
    if resp.status_code == 401:
        raise CoverGenerationError(
            "الـ API key ديال OpenRouter ماشي صحيح أو ماشي مفعّل. تأكد منو "
            "فملف backend/.env."
        )
    if not resp.ok:
        raise CoverGenerationError(
            f"OpenRouter رجع خطأ ({resp.status_code}). عاود جرب من بعد شوية."
        )

    try:
        body = resp.json()
        b64_data = body["data"][0]["b64_json"]
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        raise CoverGenerationError(
            "OpenRouter مارجعش صورة صالحة فالجواب."
        ) from exc

    return base64.b64decode(b64_data)
