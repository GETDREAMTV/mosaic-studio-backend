import base64
import os
import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
import requests

import cover_generator as cg


# ---------------------------------------------------------------------
# is_configured
# ---------------------------------------------------------------------


def test_is_configured_false_when_env_missing(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    assert cg.is_configured() is False


def test_is_configured_true_when_env_set(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-fake-test-key")
    assert cg.is_configured() is True


# ---------------------------------------------------------------------
# build_cover_prompt
# ---------------------------------------------------------------------


def test_build_cover_prompt_includes_colors_and_no_watermark_instruction():
    prompt = cg.build_cover_prompt("#aa0000", "#eeeeee", title="Owl Blanket")
    assert "#aa0000" in prompt
    assert "#eeeeee" in prompt
    assert "Owl Blanket" in prompt
    assert "no text" in prompt
    assert "no watermark" in prompt


def test_build_cover_prompt_works_without_title():
    prompt = cg.build_cover_prompt("#111111", "#222222")
    assert "#111111" in prompt and "#222222" in prompt


# ---------------------------------------------------------------------
# generate_cover_image
# ---------------------------------------------------------------------


def test_generate_cover_image_raises_without_key(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    with pytest.raises(cg.CoverGenerationError, match="OPENROUTER_API_KEY"):
        cg.generate_cover_image("a prompt")


def test_generate_cover_image_success(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-fake-test-key")

    fake_bytes = b"\x89PNG-fake-image-bytes"
    b64 = base64.b64encode(fake_bytes).decode("ascii")

    mock_resp = MagicMock()
    mock_resp.ok = True
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"data": [{"b64_json": b64}]}

    with patch("cover_generator.requests.post", return_value=mock_resp) as mock_post:
        result = cg.generate_cover_image("a cozy blanket photo")

    assert result == fake_bytes
    # make sure the key was sent as a Bearer header, and never anywhere else
    _, kwargs = mock_post.call_args
    assert kwargs["headers"]["Authorization"] == "Bearer sk-fake-test-key"


def test_generate_cover_image_402_raises_friendly_message(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-fake-test-key")
    mock_resp = MagicMock()
    mock_resp.ok = False
    mock_resp.status_code = 402

    with patch("cover_generator.requests.post", return_value=mock_resp):
        with pytest.raises(cg.CoverGenerationError, match="الرصيد"):
            cg.generate_cover_image("a prompt")


def test_generate_cover_image_401_raises_friendly_message(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-wrong-key")
    mock_resp = MagicMock()
    mock_resp.ok = False
    mock_resp.status_code = 401

    with patch("cover_generator.requests.post", return_value=mock_resp):
        with pytest.raises(cg.CoverGenerationError, match="API key"):
            cg.generate_cover_image("a prompt")


def test_generate_cover_image_network_error_raises(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-fake-test-key")
    with patch(
        "cover_generator.requests.post",
        side_effect=requests.ConnectionError("boom"),
    ):
        with pytest.raises(cg.CoverGenerationError, match="OpenRouter"):
            cg.generate_cover_image("a prompt")


def test_generate_cover_image_bad_response_shape_raises(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-fake-test-key")
    mock_resp = MagicMock()
    mock_resp.ok = True
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"data": []}  # missing b64_json

    with patch("cover_generator.requests.post", return_value=mock_resp):
        with pytest.raises(cg.CoverGenerationError):
            cg.generate_cover_image("a prompt")


def test_generate_cover_image_never_leaks_key_in_error(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-super-secret-value")
    mock_resp = MagicMock()
    mock_resp.ok = False
    mock_resp.status_code = 500
    mock_resp.text = "internal error"

    with patch("cover_generator.requests.post", return_value=mock_resp):
        with pytest.raises(cg.CoverGenerationError) as exc_info:
            cg.generate_cover_image("a prompt")

    assert "sk-super-secret-value" not in str(exc_info.value)
