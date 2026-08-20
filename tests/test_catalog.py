from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from salvo.agents.catalog import (
    anthropic_models,
    catalog_payload,
    parse_slot,
    pick_provider,
    resolve_model,
    vertex_models,
)
from salvo.agents.factory import make_player
from salvo.server import app as app_mod


def test_catalog_separates_vertex_from_anthropic_and_has_openai(monkeypatch) -> None:
    for key in (
        "SALVO_GEMINI_MODEL",
        "SALVO_CLAUDE_MODEL",
        "SALVO_GEMINI_MODELS",
        "SALVO_CLAUDE_MODELS",
        "SALVO_VERTEX_CLAUDE_MODELS",
        "ANTHROPIC_MODEL",
        "ANTHROPIC_MODELS",
        "OPENAI_MODEL",
        "OPENAI_MODELS",
    ):
        monkeypatch.delenv(key, raising=False)
    payload = catalog_payload()["providers"]
    assert payload["vertex"]["default"] == "gemini-3.5-flash-lite"
    assert "gemini-3.5-flash" in payload["vertex"]["models"]
    assert "claude-opus-4-6" in payload["vertex"]["models"]
    assert "claude-sonnet-5" not in payload["vertex"]["models"]
    assert payload["anthropic"]["default"] == "claude-sonnet-5"
    assert "claude-opus-5" in payload["anthropic"]["models"]
    assert "gemini-3.5-flash-lite" not in payload["anthropic"]["models"]
    assert payload["openai"]["default"] == "gpt-5.4-nano"
    assert "gpt-5.4-nano" in payload["openai"]["models"]
    assert set(vertex_models()) & set(anthropic_models()) == set()


def test_parse_slot_accepts_model_ids() -> None:
    assert parse_slot("gemini") == ("gemini", "gemini-3.5-flash-lite")
    assert parse_slot("gemini-3.5-flash") == ("gemini", "gemini-3.5-flash")
    assert parse_slot("opus") == ("claude", "claude-opus-4-6")
    assert parse_slot("claude-sonnet-5") == ("claude", "claude-sonnet-5")
    assert parse_slot("gpt-5.4-nano") == ("openai", "gpt-5.4-nano")
    assert parse_slot("openai") == ("openai", "gpt-5.4-nano")
    assert parse_slot("ollama")[0] == "ollama"


def test_two_gemini_models_independent() -> None:
    import random

    left = make_player("gemini-3.5-flash", random.Random(0), side="left")
    right = make_player("gemini-2.5-pro", random.Random(1), side="right")
    assert left.kind == "gemini" and right.kind == "gemini"
    assert left.model == "gemini-3.5-flash"
    assert right.model == "gemini-2.5-pro"
    assert left.provider == "vertex"


def test_provider_defaults_follow_family(monkeypatch) -> None:
    monkeypatch.delenv("SALVO_PROVIDER", raising=False)
    assert pick_provider("gemini", None) == "vertex"
    assert pick_provider("gemini", "api") == "gemini"
    assert pick_provider("claude", "api") == "anthropic"
    assert pick_provider("claude", None, model="claude-opus-4-6") == "vertex"
    assert pick_provider("claude", None, model="claude-sonnet-5") == "anthropic"
    assert pick_provider("openai", None) == "openai"
    assert pick_provider("ollama", None) == "ollama"
    with pytest.raises(ValueError, match="only for Gemini"):
        pick_provider("claude", "gemini")
    with pytest.raises(ValueError, match="only for Claude"):
        pick_provider("gemini", "anthropic")
    with pytest.raises(ValueError, match="not on Vertex"):
        pick_provider("openai", "vertex")


def test_resolve_rejects_cross_family() -> None:
    with pytest.raises(ValueError, match="unknown gemini"):
        resolve_model("gemini", "claude-opus-4-6")


def test_openai_player_meta() -> None:
    import random

    player = make_player("gpt-5.4-nano", random.Random(0), side="left")
    assert player.kind == "openai"
    assert player.provider == "openai"
    assert player.meta.model == "gpt-5.4-nano"


def test_catalog_endpoint() -> None:
    client = TestClient(app_mod.app)
    body = client.get("/catalog").json()
    assert "vertex" in body["providers"]
    assert "openai" in body["providers"]
    assert "ollama" in body["providers"]
    assert body["providers"]["openai"]["default"] == "gpt-5.4-nano"
