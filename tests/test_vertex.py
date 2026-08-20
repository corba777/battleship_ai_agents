from __future__ import annotations

import os

import pytest

from salvo.agents.adk import extract_contract_text
from salvo.agents.factory import make_player
from salvo.agents.vertex import generate, is_claude_model, project_id, vertex_location


def test_defaults_match_project_models(monkeypatch) -> None:
    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
    monkeypatch.delenv("GCLOUD_PROJECT", raising=False)
    monkeypatch.delenv("SALVO_GEMINI_MODEL", raising=False)
    monkeypatch.delenv("SALVO_CLAUDE_MODEL", raising=False)
    assert project_id() == ""
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "example-project")
    assert project_id() == "example-project"
    from salvo.agents.vertex import claude_model, gemini_model, model_id

    assert gemini_model() == "gemini-3.5-flash-lite"
    assert claude_model() == "claude-opus-4-6"
    assert model_id("gemini") == "gemini-3.5-flash-lite"
    assert model_id("opus") == "claude-opus-4-6"


def test_opus_player_uses_claude_kind(monkeypatch) -> None:
    import random

    monkeypatch.delenv("SALVO_CLAUDE_MODEL", raising=False)
    player = make_player("opus", random.Random(0), persona="intuitive", side="right")
    assert player.kind == "claude"
    assert player.meta.model == "claude-opus-4-6"


def test_vertex_claude_uses_anthropic_raw_predict() -> None:
    from salvo.agents.vertex import vertex_anthropic_body, vertex_anthropic_text, vertex_anthropic_url

    url = vertex_anthropic_url("example-project", "global", "claude-opus-4-6")
    assert url == (
        "https://aiplatform.googleapis.com/v1/projects/example-project"
        "/locations/global/publishers/anthropic/models/claude-opus-4-6:rawPredict"
    )
    body = vertex_anthropic_body("sys", "usr")
    assert body["messages"] == [{"role": "user", "content": "usr"}]
    text = vertex_anthropic_text(
        {"content": [{"type": "text", "text": "hello"}, {"type": "thinking"}]}
    )
    assert text == "hello"


def test_player_adk_is_opt_in(monkeypatch) -> None:
    import random

    monkeypatch.delenv("SALVO_ADK", raising=False)
    direct = make_player("gemini", random.Random(0), side="left")
    assert direct.adk is False
    assert "adk" not in direct.meta.as_dict()
    wrapped = make_player("gemini", random.Random(0), side="left", adk=True)
    assert wrapped.adk is True
    assert wrapped.meta.as_dict()["adk"] is True
    api = make_player("gemini", random.Random(0), side="left", provider="gemini", adk=True)
    assert api.adk is True
    openai = make_player("gpt-5.4-nano", random.Random(0), side="left", adk=True)
    assert openai.adk is True
    anthropic = make_player(
        "claude-sonnet-5", random.Random(0), side="left", provider="anthropic", adk=True
    )
    assert anthropic.adk is True
    ollama = make_player("llama3.1", random.Random(0), side="left", provider="ollama", adk=True)
    assert ollama.adk is False


def test_extract_keeps_final_answer_json_only() -> None:
    tagged = (
        "/*PLANNING*/parity hunt\n"
        "/*REASONING*/E5 is even\n"
        '/*FINAL_ANSWER*/\n{"shot":"E5","belief":[{"cell":"E5","p":0.9}],"say":"Opening."}'
    )
    out = extract_contract_text(tagged)
    assert out.startswith("{")
    assert "PLANNING" not in out
    assert '"shot":"E5"' in out
    plain = '{"shot":"D2","belief":[{"cell":"D2","p":0.8}],"say":"D2."}'
    assert extract_contract_text(plain) == plain


def test_vertex_generate_direct_by_default(monkeypatch) -> None:
    monkeypatch.setattr(
        "salvo.agents.vertex.generate_vertex_gemini",
        lambda model, system, user, location: f"direct:{model}",
    )
    text = generate("gemini-3.5-flash-lite", "sys", "usr", "global")
    assert text == "direct:gemini-3.5-flash-lite"


def test_vertex_generate_adk_when_requested(monkeypatch) -> None:
    seen: dict[str, str] = {}

    def fake(model: str, system: str, user: str, location: str) -> str:
        seen["model"] = model
        seen["location"] = location
        return '{"shot":"E5","belief":[{"cell":"E5","p":0.9}],"say":"Opening."}'

    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "example-project")
    monkeypatch.setattr("salvo.agents.adk.complete", fake)
    text = generate("gemini-3.5-flash-lite", "sys", "usr", "global", adk=True)
    assert seen["model"] == "gemini-3.5-flash-lite"
    assert seen["location"] == "global"
    assert "shot" in text


def test_vertex_claude_location_prefers_claude_env(monkeypatch) -> None:
    monkeypatch.setenv("VERTEX_LOCATION", "global")
    monkeypatch.setenv("VERTEX_CLAUDE_LOCATION", "us-east5")
    assert vertex_location("gemini") == "global"
    assert vertex_location("claude") == "us-east5"


def test_adk_model_uses_api_classes_not_vertex_claude() -> None:
    from google.adk.labs.openai import OpenAILlm
    from google.adk.models.anthropic_llm import AnthropicLlm, Claude

    from salvo.agents.adk import adk_model

    openai = adk_model("gpt-5.4-nano", "openai")
    anthropic = adk_model("claude-sonnet-5", "anthropic")
    assert isinstance(openai, OpenAILlm)
    assert isinstance(anthropic, AnthropicLlm)
    assert not isinstance(anthropic, Claude)
    assert adk_model("gemini-3.5-flash-lite", "vertex") == "gemini-3.5-flash-lite"
    assert adk_model("gemini-3.5-flash-lite", "gemini") == "gemini-3.5-flash-lite"


def test_adk_registry_routes_vertex_claude() -> None:
    from google.adk.models.anthropic_llm import Claude
    from google.adk.models.registry import LLMRegistry

    LLMRegistry.register(Claude)
    assert LLMRegistry.resolve("claude-opus-4-6") is Claude
    assert LLMRegistry.resolve("gemini-3.5-flash-lite").__name__ == "Gemini"


def test_openai_adk_routes_to_adk_complete(monkeypatch) -> None:
    seen: dict[str, str] = {}

    def fake(model: str, system: str, user: str, location: str = "global", *, provider: str = "vertex") -> str:
        seen["model"] = model
        seen["provider"] = provider
        seen["location"] = location
        return '{"shot":"E5","belief":[{"cell":"E5","p":0.9}],"say":"Opening."}'

    monkeypatch.setattr("salvo.agents.adk.complete", fake)
    from salvo.agents.providers import complete

    text = complete("openai", "sys", "usr", model="gpt-5.4-nano", adk=True)
    assert seen["provider"] == "openai"
    assert seen["model"] == "gpt-5.4-nano"
    assert "shot" in text


def test_vertex_env_sets_adk_location(monkeypatch) -> None:
    from salvo.agents.adk import _vertex_env

    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "example-project")
    monkeypatch.delenv("GOOGLE_CLOUD_LOCATION", raising=False)
    monkeypatch.delenv("GOOGLE_GENAI_USE_VERTEXAI", raising=False)
    with _vertex_env("us-east5"):
        assert os.environ["GOOGLE_CLOUD_LOCATION"] == "us-east5"
        assert os.environ["GOOGLE_GENAI_USE_VERTEXAI"] == "TRUE"
        assert os.environ["GOOGLE_CLOUD_PROJECT"] == "example-project"
    assert "GOOGLE_CLOUD_LOCATION" not in os.environ


def test_gemini_api_env_forces_non_vertex(monkeypatch) -> None:
    from salvo.agents.adk import _gemini_api_env

    monkeypatch.setenv("GOOGLE_GENAI_USE_VERTEXAI", "true")
    monkeypatch.setenv("GEMINI_API_KEY", "studio-key")
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    with _gemini_api_env():
        assert os.environ["GOOGLE_GENAI_USE_VERTEXAI"] == "FALSE"
        assert os.environ["GOOGLE_API_KEY"] == "studio-key"
        assert os.environ["GEMINI_API_KEY"] == "studio-key"
    assert os.environ["GOOGLE_GENAI_USE_VERTEXAI"] == "true"
    assert "GOOGLE_API_KEY" not in os.environ


def test_gemini_api_env_requires_key(monkeypatch) -> None:
    from salvo.agents.adk import _gemini_api_env

    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="GEMINI_API_KEY"):
        with _gemini_api_env():
            pass


def test_gemini_api_adk_routes_to_adk_complete(monkeypatch) -> None:
    seen: dict[str, str] = {}

    def fake(
        model: str,
        system: str,
        user: str,
        location: str = "global",
        *,
        provider: str = "vertex",
    ) -> str:
        seen["model"] = model
        seen["provider"] = provider
        seen["location"] = location
        return '{"shot":"E5","belief":[{"cell":"E5","p":0.9}],"say":"Opening."}'

    monkeypatch.setattr("salvo.agents.adk.complete", fake)
    from salvo.agents.providers import complete

    text = complete(
        "gemini",
        "sys",
        "usr",
        model="gemini-3.5-flash-lite",
        provider="gemini",
        adk=True,
    )
    assert seen["provider"] == "gemini"
    assert seen["model"] == "gemini-3.5-flash-lite"
    assert "shot" in text
