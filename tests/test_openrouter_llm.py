"""
Unit tests for the OpenRouter LLM adapter quality fixes.

Covers:
- Reasoning is disabled in the outbound payload (reasoning tokens were
  starving the visible answer budget on nvidia/nemotron-3-ultra).
- Transient provider errors (503 overloaded) are retried before failing.
- In-band provider errors inside HTTP 200 bodies are surfaced as LLMError.
- Empty visible content (reasoning exhausted the budget) raises LLMError.
"""

import json
from typing import Any
from unittest.mock import MagicMock

import pytest

import app.infrastructure.openrouter_llm as llm_module
from app.core.domain import Message
from app.core.exceptions import LLMError
from app.infrastructure.openrouter_llm import OpenRouterLLM


def _make_response(status_code: int, body: dict[str, Any]) -> MagicMock:
    response = MagicMock()
    response.status_code = status_code
    response.json.return_value = body
    response.text = json.dumps(body)
    if status_code >= 400:
        response.raise_for_status.side_effect = llm_module.httpx.HTTPStatusError(
            "error", request=MagicMock(), response=response
        )
    else:
        response.raise_for_status.return_value = None
    return response


def _ok_body(content: str) -> dict[str, Any]:
    return {
        "choices": [
            {"message": {"role": "assistant", "content": content}, "finish_reason": "stop"}
        ]
    }


@pytest.fixture()
def llm() -> OpenRouterLLM:
    return OpenRouterLLM(api_key="test-key", cache=None)


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    monkeypatch.setattr(llm_module.time, "sleep", lambda *_: None)


def _capture_posts(monkeypatch, responses: list[MagicMock]) -> list[dict]:
    """Patch httpx.post to return the given responses in order and capture payloads."""
    captured: list[dict] = []

    def fake_post(url: str, headers: dict | None = None, json: dict | None = None, timeout: Any = None):
        captured.append({"url": url, "json": json, "timeout": timeout})
        return responses.pop(0)

    monkeypatch.setattr(llm_module.httpx, "post", fake_post)
    return captured


def test_payload_disables_reasoning(llm: OpenRouterLLM, monkeypatch) -> None:
    """Reasoning must be explicitly disabled so the answer gets the full token budget."""
    captured = _capture_posts(monkeypatch, [_make_response(200, _ok_body("answer"))])

    result = llm.generate([Message(role="user", content="q")])

    assert result == "answer"
    assert captured[0]["json"]["reasoning"] == {"enabled": False, "exclude": True}


def test_transient_503_is_retried_then_succeeds(llm: OpenRouterLLM, monkeypatch) -> None:
    """The Nvidia free tier intermittently returns 503 — retry instead of failing."""
    responses = [
        _make_response(503, {"error": {"code": 503, "message": "overloaded"}}),
        _make_response(200, _ok_body("recovered")),
    ]
    captured = _capture_posts(monkeypatch, responses)

    result = llm.generate([Message(role="user", content="q")])

    assert result == "recovered"
    assert len(captured) == 2


def test_transient_503_exhausted_retries_raises(llm: OpenRouterLLM, monkeypatch) -> None:
    responses = [_make_response(503, {"error": {"code": 503, "message": "overloaded"}})] * 3
    _capture_posts(monkeypatch, responses)

    with pytest.raises(LLMError, match="503"):
        llm.generate([Message(role="user", content="q")])


def test_in_band_provider_error_inside_http_200_raises(llm: OpenRouterLLM, monkeypatch) -> None:
    """OpenRouter sometimes reports upstream provider failures inside a 200 body."""
    body = {
        "id": "gen-x",
        "error": {"message": "Upstream error from Nvidia: Service temporarily overloaded", "code": 503},
    }
    _capture_posts(monkeypatch, [_make_response(200, body)])

    with pytest.raises(LLMError, match="upstream provider error"):
        llm.generate([Message(role="user", content="q")])


def test_empty_visible_content_raises(llm: OpenRouterLLM, monkeypatch) -> None:
    """Reasoning models can consume the whole budget and return empty content."""
    body = {"choices": [{"message": {"role": "assistant", "content": None, "reasoning": "thinking..."}}]}
    _capture_posts(monkeypatch, [_make_response(200, body)])

    with pytest.raises(LLMError, match="empty answer"):
        llm.generate([Message(role="user", content="q")])


def test_reasoning_enabled_via_settings(llm: OpenRouterLLM, monkeypatch) -> None:
    """When llm_reasoning_enabled is true, no reasoning override is sent."""
    monkeypatch.setattr(llm_module.settings, "llm_reasoning_enabled", True)
    captured = _capture_posts(monkeypatch, [_make_response(200, _ok_body("answer"))])

    llm.generate([Message(role="user", content="q")])

    assert "reasoning" not in captured[0]["json"]
