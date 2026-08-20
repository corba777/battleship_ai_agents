from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parents[2] / ".env")
except ImportError:
    pass

DEFAULT_GEMINI_MODEL = "gemini-3.5-flash-lite"
DEFAULT_CLAUDE_MODEL = "claude-opus-4-6"
DEFAULT_ANTHROPIC_MODEL = "claude-sonnet-5"
DEFAULT_OPENAI_MODEL = "gpt-5.4-nano"
DEFAULT_OLLAMA_MODEL = "llama3.1"
DEFAULT_OLLAMA_URL = "http://localhost:11434"
DEFAULT_PROVIDER = "vertex"

DEFAULT_GEMINI_MODELS = (
    "gemini-3.5-flash-lite,"
    "gemini-3.5-flash,"
    "gemini-3.6-flash,"
    "gemini-3.7-flash,"
    "gemini-3.1-pro-preview,"
    "gemini-2.5-flash,"
    "gemini-2.5-pro"
)
DEFAULT_VERTEX_CLAUDE_MODELS = "claude-opus-4-6"
DEFAULT_ANTHROPIC_MODELS = "claude-sonnet-5,claude-opus-5"
DEFAULT_OPENAI_MODELS = "gpt-5.4-nano,gpt-5.6-luna,gpt-5.6-sol"

BOTS = ("parity", "random", "occupancy")
KIND_ALIASES = {
    "gemini": "gemini",
    "flash-lite": "gemini",
    "claude": "claude",
    "opus": "claude",
    "openai": "openai",
    "gpt": "openai",
    "nano": "openai",
    "ollama": "ollama",
}
PROVIDERS = ("vertex", "gemini", "anthropic", "openai", "ollama")
ADK_PROVIDERS = ("vertex", "gemini", "openai", "anthropic")

_GEMINI_ALIASES = {
    "gemini": DEFAULT_GEMINI_MODEL,
    "flash-lite": DEFAULT_GEMINI_MODEL,
}
_CLAUDE_ALIASES = {
    "claude": DEFAULT_CLAUDE_MODEL,
    "opus": DEFAULT_CLAUDE_MODEL,
    "opus-4.6": DEFAULT_CLAUDE_MODEL,
}
_OPENAI_ALIASES = {
    "openai": DEFAULT_OPENAI_MODEL,
    "gpt": DEFAULT_OPENAI_MODEL,
    "nano": DEFAULT_OPENAI_MODEL,
}
_OLLAMA_ALIASES = {
    "ollama": DEFAULT_OLLAMA_MODEL,
}


def project_id() -> str:
    return (
        os.environ.get("GOOGLE_CLOUD_PROJECT") or os.environ.get("GCLOUD_PROJECT") or ""
    ).strip()


def require_project_id() -> str:
    pid = project_id()
    if not pid:
        raise RuntimeError("GOOGLE_CLOUD_PROJECT is not set")
    return pid


def parse_model_list(list_env: str | None, default: str) -> list[str]:
    parts = [p.strip() for p in (list_env or "").split(",") if p.strip()]
    fallback = default.strip() or DEFAULT_GEMINI_MODEL
    if not parts:
        return [fallback]
    uniq: list[str] = []
    for part in parts:
        if part not in uniq:
            uniq.append(part)
    if fallback not in uniq:
        return [fallback, *uniq]
    if uniq[0] == fallback:
        return uniq
    return [fallback, *[m for m in uniq if m != fallback]]


def gemini_model() -> str:
    raw = os.environ.get("SALVO_GEMINI_MODEL", DEFAULT_GEMINI_MODEL)
    return _GEMINI_ALIASES.get(raw, raw)


def claude_model() -> str:
    raw = os.environ.get("SALVO_CLAUDE_MODEL", DEFAULT_CLAUDE_MODEL)
    return _CLAUDE_ALIASES.get(raw, raw)


def anthropic_model() -> str:
    return (
        os.environ.get("ANTHROPIC_MODEL")
        or os.environ.get("SALVO_ANTHROPIC_MODEL")
        or DEFAULT_ANTHROPIC_MODEL
    )


def openai_model() -> str:
    raw = os.environ.get("OPENAI_MODEL") or os.environ.get(
        "SALVO_OPENAI_MODEL", DEFAULT_OPENAI_MODEL
    )
    return _OPENAI_ALIASES.get(raw, raw)


def gemini_models() -> list[str]:
    return parse_model_list(
        os.environ.get("SALVO_GEMINI_MODELS") or DEFAULT_GEMINI_MODELS,
        gemini_model(),
    )


def vertex_claude_models() -> list[str]:
    raw = (
        os.environ.get("SALVO_VERTEX_CLAUDE_MODELS")
        or os.environ.get("SALVO_CLAUDE_MODELS")
        or DEFAULT_VERTEX_CLAUDE_MODELS
    )
    return parse_model_list(raw, claude_model())


def vertex_models() -> list[str]:
    models = list(gemini_models())
    for item in vertex_claude_models():
        if item not in models:
            models.append(item)
    return models


def anthropic_models() -> list[str]:
    return parse_model_list(
        os.environ.get("ANTHROPIC_MODELS")
        or os.environ.get("SALVO_ANTHROPIC_MODELS")
        or DEFAULT_ANTHROPIC_MODELS,
        anthropic_model(),
    )


def openai_models() -> list[str]:
    return parse_model_list(
        os.environ.get("OPENAI_MODELS")
        or os.environ.get("SALVO_OPENAI_MODELS")
        or DEFAULT_OPENAI_MODELS,
        openai_model(),
    )


def ollama_model() -> str:
    raw = os.environ.get("OLLAMA_MODEL") or os.environ.get("LLM_MODEL") or DEFAULT_OLLAMA_MODEL
    return _OLLAMA_ALIASES.get(raw, raw)


def ollama_models() -> list[str]:
    return parse_model_list(
        os.environ.get("OLLAMA_MODELS") or os.environ.get("SALVO_OLLAMA_MODELS"),
        ollama_model(),
    )


def ollama_url() -> str:
    raw = (os.environ.get("OLLAMA_URL") or DEFAULT_OLLAMA_URL).strip().rstrip("/")
    if Path("/.dockerenv").is_file():
        for host in ("localhost", "127.0.0.1"):
            raw = raw.replace(f"http://{host}", "http://host.docker.internal")
            raw = raw.replace(f"https://{host}", "https://host.docker.internal")
    return raw


def ollama_think() -> bool:
    raw = (os.environ.get("OLLAMA_THINK") or "0").strip().lower()
    return raw in ("1", "true", "on", "yes")


def model_id(kind: str) -> str:
    if kind in ("gemini", "flash-lite"):
        return gemini_model()
    if kind in ("claude", "opus"):
        return claude_model()
    if kind == "openai":
        return openai_model()
    if kind == "ollama":
        return ollama_model()
    raise ValueError(f"unknown model kind: {kind}")


def kind_of(name: str) -> str:
    if name in KIND_ALIASES:
        return KIND_ALIASES[name]
    if name.startswith("gemini"):
        return "gemini"
    if name.startswith("claude") or name in _CLAUDE_ALIASES:
        return "claude"
    if name.startswith("gpt-") or re.match(r"^o[0-9]", name):
        return "openai"
    if name in ollama_models() or ":" in name:
        return "ollama"
    raise ValueError(f"unknown player: {name}")


def resolve_model(kind: str, name: str | None) -> str:
    if not name:
        return model_id(kind)
    if kind == "gemini":
        mapped = _GEMINI_ALIASES.get(name, name)
        if mapped.startswith("gemini"):
            return mapped
        raise ValueError(f"unknown gemini model: {name}")
    if kind == "openai":
        mapped = _OPENAI_ALIASES.get(name, name)
        if mapped.startswith("gpt-") or re.match(r"^o[0-9]", mapped) or mapped in _OPENAI_ALIASES:
            return mapped if mapped.startswith(("gpt-", "o")) else openai_model()
        raise ValueError(f"unknown openai model: {name}")
    if kind == "ollama":
        return _OLLAMA_ALIASES.get(name, name)
    mapped = _CLAUDE_ALIASES.get(name, name)
    if mapped.startswith("claude"):
        return mapped
    raise ValueError(f"unknown claude model: {name}")


def parse_slot(name: str, model: str | None = None) -> tuple[str, str]:
    if name in BOTS:
        raise ValueError(f"not an llm: {name}")
    kind = kind_of(name)
    chosen = model if model else (None if name in KIND_ALIASES else name)
    return kind, resolve_model(kind, chosen)


def is_llm_name(name: str) -> bool:
    try:
        kind_of(name)
        return True
    except ValueError:
        return False


def gemini_api_key() -> str:
    return os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or ""


def anthropic_api_key() -> str:
    return os.environ.get("ANTHROPIC_API_KEY") or ""


def openai_api_key() -> str:
    return os.environ.get("OPENAI_API_KEY") or ""


def anthropic_only_models() -> set[str]:
    vertex = set(vertex_claude_models())
    return {m for m in anthropic_models() if m not in vertex}


def pick_provider(kind: str, provider: str | None = None, model: str | None = None) -> str:
    raw = (provider or "").strip().lower()
    if not raw:
        if kind == "openai":
            return "openai"
        if kind == "ollama":
            return "ollama"
        if kind == "claude" and model and model in anthropic_only_models():
            return "anthropic"
        return (os.environ.get("SALVO_PROVIDER") or DEFAULT_PROVIDER).strip().lower()
    if raw in ("api", "gemini-api"):
        raw = "gemini" if kind == "gemini" else "anthropic"
    if raw not in PROVIDERS:
        raise ValueError(f"unknown provider: {provider}")
    if raw == "gemini" and kind != "gemini":
        raise ValueError("gemini API is only for Gemini models")
    if raw == "anthropic" and kind != "claude":
        raise ValueError("anthropic API is only for Claude models")
    if raw == "openai" and kind != "openai":
        raise ValueError("openai API is only for GPT models")
    if raw == "ollama" and kind != "ollama":
        raise ValueError("ollama is only for Ollama models")
    if raw == "vertex" and kind in ("openai", "ollama"):
        raise ValueError(f"{kind} models are not on Vertex in this project")
    return raw


def parse_adk(value: object) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    raw = str(value).strip().lower()
    if not raw:
        return None
    if raw in ("1", "true", "on", "yes", "adk"):
        return True
    if raw in ("0", "false", "off", "no", "direct"):
        return False
    raise ValueError(f"unknown adk: {value}")


def pick_adk(provider: str, requested: bool | None = None) -> bool:
    if provider not in ADK_PROVIDERS:
        return False
    if requested is not None:
        return requested
    raw = (os.environ.get("SALVO_ADK") or "0").strip().lower()
    return raw in ("1", "true", "on", "yes", "adk")


def provider_status() -> dict[str, dict[str, Any]]:
    location = os.environ.get("VERTEX_LOCATION", "global")
    gemini_key = bool(gemini_api_key())
    anthropic_key = bool(anthropic_api_key())
    openai_key = bool(openai_api_key())
    return {
        "vertex": {
            "ok": True,
            "label": "Vertex AI",
            "hint": f"{project_id() or 'GOOGLE_CLOUD_PROJECT'} · {location}",
            "default": gemini_model(),
            "models": vertex_models(),
        },
        "anthropic": {
            "ok": anthropic_key,
            "label": "Anthropic",
            "hint": "key loaded" if anthropic_key else "no ANTHROPIC_API_KEY",
            "default": anthropic_model(),
            "models": anthropic_models(),
        },
        "openai": {
            "ok": openai_key,
            "label": "OpenAI",
            "hint": "key loaded" if openai_key else "no OPENAI_API_KEY",
            "default": openai_model(),
            "models": openai_models(),
        },
        "gemini": {
            "ok": gemini_key,
            "label": "Gemini API",
            "hint": "key loaded" if gemini_key else "no GEMINI_API_KEY",
            "default": gemini_model(),
            "models": gemini_models(),
        },
        "ollama": {
            "ok": True,
            "label": "Ollama",
            "hint": ollama_url(),
            "default": ollama_model(),
            "models": ollama_models(),
        },
    }


def catalog_payload() -> dict[str, Any]:
    return {"providers": provider_status()}
