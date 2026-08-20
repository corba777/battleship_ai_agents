from __future__ import annotations

import pytest

from salvo.agents.catalog import (
    catalog_payload,
    kind_of,
    parse_slot,
    pick_provider,
)
from salvo.agents.factory import make_player
from salvo.agents.providers import ollama_chat_body, ollama_content


def test_ollama_catalog_and_slots(monkeypatch) -> None:
    monkeypatch.delenv("OLLAMA_URL", raising=False)
    monkeypatch.delenv("OLLAMA_MODEL", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)
    monkeypatch.setenv("OLLAMA_MODELS", "qwen3.6:35b, llama3.1")
    monkeypatch.setenv("OLLAMA_MODEL", "qwen3.6:35b")
    payload = catalog_payload()["providers"]["ollama"]
    assert payload["ok"] is True
    assert payload["default"] == "qwen3.6:35b"
    assert payload["models"][0] == "qwen3.6:35b"
    assert "llama3.1" in payload["models"]
    assert payload["hint"] == "http://localhost:11434"
    assert parse_slot("ollama") == ("ollama", "qwen3.6:35b")
    assert parse_slot("qwen3.6:35b") == ("ollama", "qwen3.6:35b")
    assert kind_of("llama3.1") == "ollama"
    assert pick_provider("ollama", None) == "ollama"


def test_ollama_chat_body_think_off_by_default(monkeypatch) -> None:
    monkeypatch.delenv("OLLAMA_THINK", raising=False)
    body = ollama_chat_body("qwen3.6:35b", "sys", "user")
    assert body["stream"] is False
    assert body["format"] == "json"
    assert body["think"] is False
    assert body["options"] == {"temperature": 0.9, "num_predict": 400}
    assert body["messages"] == [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "user"},
    ]
    on = ollama_chat_body("qwen3.6:35b", "sys", "user", think=True)
    assert on["think"] is True
    assert on["options"]["num_predict"] == 1600


def test_ollama_content_does_not_use_thinking_as_json() -> None:
    text = ollama_content(
        {"message": {"content": '{"shot":"E5"}', "thinking": "maybe D4"}}
    )
    assert text == '{"shot":"E5"}'
    with pytest.raises(RuntimeError, match="spent tokens on think"):
        ollama_content({"message": {"content": "", "thinking": "I like C3"}})


def test_ollama_player_meta(monkeypatch) -> None:
    import random

    monkeypatch.setenv("OLLAMA_MODEL", "qwen3.6:35b")
    player = make_player("qwen3.6:35b", random.Random(0), side="left", provider="ollama")
    assert player.kind == "ollama"
    assert player.provider == "ollama"
    assert player.meta.model == "qwen3.6:35b"


def test_ollama_rejects_cross_family() -> None:
    with pytest.raises(ValueError, match="only for Ollama"):
        pick_provider("gemini", "ollama")
    with pytest.raises(ValueError, match="not on Vertex"):
        pick_provider("ollama", "vertex")
