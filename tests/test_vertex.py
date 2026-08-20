from __future__ import annotations

from salvo.agents.factory import make_player
from salvo.agents.vertex import (
    claude_model,
    gemini_model,
    is_claude_model,
    model_id,
    project_id,
    vertex_anthropic_body,
    vertex_anthropic_text,
    vertex_anthropic_url,
)


def test_defaults_match_project_models(monkeypatch) -> None:
    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
    monkeypatch.delenv("GCLOUD_PROJECT", raising=False)
    monkeypatch.delenv("SALVO_GEMINI_MODEL", raising=False)
    monkeypatch.delenv("SALVO_CLAUDE_MODEL", raising=False)
    assert project_id() == ""
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "example-project")
    assert project_id() == "example-project"
    assert gemini_model() == "gemini-3.5-flash-lite"
    assert claude_model() == "claude-opus-4-6"
    assert model_id("gemini") == "gemini-3.5-flash-lite"
    assert model_id("opus") == "claude-opus-4-6"


def test_aliases_and_env_override(monkeypatch) -> None:
    monkeypatch.setenv("SALVO_GEMINI_MODEL", "gemini-3.5-flash")
    monkeypatch.setenv("SALVO_CLAUDE_MODEL", "opus-4.6")
    assert gemini_model() == "gemini-3.5-flash"
    assert claude_model() == "claude-opus-4-6"


def test_opus_player_uses_claude_kind(monkeypatch) -> None:
    import random

    monkeypatch.delenv("SALVO_CLAUDE_MODEL", raising=False)
    player = make_player("opus", random.Random(0), persona="intuitive", side="right")
    assert player.kind == "claude"
    assert player.meta.model == "claude-opus-4-6"


def test_vertex_claude_uses_anthropic_raw_predict() -> None:
    assert is_claude_model("claude-opus-4-6")
    assert is_claude_model("anthropic/claude-opus-4-6")
    assert not is_claude_model("gemini-3.5-flash-lite")
    url = vertex_anthropic_url(
        "example-project", "global", "claude-opus-4-6"
    )
    assert url == (
        "https://aiplatform.googleapis.com/v1/projects/example-project"
        "/locations/global/publishers/anthropic/models/claude-opus-4-6:rawPredict"
    )
    regional = vertex_anthropic_url(
        "example-project", "us-east5", "anthropic/claude-opus-4-6"
    )
    assert regional.startswith("https://us-east5-aiplatform.googleapis.com/")
    body = vertex_anthropic_body("sys", "usr")
    assert body["anthropic_version"] == "vertex-2023-10-16"
    assert body["messages"] == [{"role": "user", "content": "usr"}]
    text = vertex_anthropic_text(
        {"content": [{"type": "text", "text": "hello"}, {"type": "thinking"}]}
    )
    assert text == "hello"
