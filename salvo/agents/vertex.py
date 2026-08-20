from __future__ import annotations

import logging
import os
from typing import Any
from urllib.parse import quote

from salvo.agents.catalog import (
    DEFAULT_CLAUDE_MODEL,
    DEFAULT_GEMINI_MODEL,
    claude_model,
    gemini_model,
    model_id,
    project_id,
    require_project_id,
)

__all__ = [
    "DEFAULT_CLAUDE_MODEL",
    "DEFAULT_GEMINI_MODEL",
    "claude_model",
    "complete",
    "gemini_model",
    "generate",
    "is_claude_model",
    "model_id",
    "project_id",
    "require_project_id",
    "vertex_anthropic_body",
    "vertex_anthropic_text",
    "vertex_anthropic_url",
    "vertex_location",
]

log = logging.getLogger(__name__)

_CLOUD_SCOPE = "https://www.googleapis.com/auth/cloud-platform"


def vertex_location(kind: str) -> str:
    default = os.environ.get("VERTEX_LOCATION", "global")
    if kind in ("claude", "opus"):
        return os.environ.get("VERTEX_CLAUDE_LOCATION", default)
    return default


def quota_project() -> str:
    return (
        os.environ.get("GOOGLE_CLOUD_QUOTA_PROJECT")
        or os.environ.get("GOOGLE_CLOUD_PROJECT")
        or project_id()
    )


def is_claude_model(model: str) -> bool:
    name = model.strip().lower()
    return name.startswith("claude-") or name.startswith("anthropic/")


def vertex_anthropic_model_id(model: str) -> str:
    name = model.strip()
    if name.lower().startswith("anthropic/"):
        return name.split("/", 1)[1]
    return name


def vertex_anthropic_url(project: str, location: str, model: str) -> str:
    loc = (location or "global").strip() or "global"
    host = (
        "https://aiplatform.googleapis.com"
        if loc == "global"
        else f"https://{loc}-aiplatform.googleapis.com"
    )
    model_id_ = quote(vertex_anthropic_model_id(model), safe="-._~")
    return (
        f"{host}/v1/projects/{project}/locations/{loc}"
        f"/publishers/anthropic/models/{model_id_}:rawPredict"
    )


def vertex_anthropic_body(system: str, user: str) -> dict[str, Any]:
    return {
        "anthropic_version": "vertex-2023-10-16",
        "max_tokens": 400,
        "temperature": 0.9,
        "system": system,
        "messages": [{"role": "user", "content": user}],
    }


def vertex_anthropic_text(data: dict[str, Any]) -> str:
    parts = [
        block.get("text") or ""
        for block in data.get("content") or []
        if isinstance(block, dict) and block.get("type") == "text"
    ]
    return "".join(parts).strip()


def complete(kind: str, system: str, user: str) -> str:
    from salvo.agents.providers import complete as routed

    return routed(kind, system, user)


def generate(model: str, system: str, user: str, location: str) -> str:
    if is_claude_model(model):
        return generate_vertex_claude(model, system, user, location)
    return generate_vertex_gemini(model, system, user, location)


def generate_vertex_gemini(model: str, system: str, user: str, location: str) -> str:
    from google import genai
    from google.genai import types

    client = genai.Client(vertexai=True, project=require_project_id(), location=location)
    response = client.models.generate_content(
        model=model,
        contents=user,
        config=types.GenerateContentConfig(
            system_instruction=system,
            temperature=0.9,
            max_output_tokens=400,
            http_options=types.HttpOptions(timeout=60_000),
        ),
    )
    text = response.text
    if not text:
        raise RuntimeError("empty model response")
    return text


def generate_vertex_claude(model: str, system: str, user: str, location: str) -> str:
    import httpx

    url = vertex_anthropic_url(require_project_id(), location, model)
    log.info("vertex claude rawPredict %s", url)
    response = httpx.post(
        url,
        headers=_vertex_headers(),
        json=vertex_anthropic_body(system, user),
        timeout=60.0,
    )
    if response.status_code >= 400:
        raise RuntimeError(
            f"vertex claude {response.status_code}: {response.text[:800]}"
        )
    text = vertex_anthropic_text(response.json())
    if not text:
        raise RuntimeError("empty model response")
    return text


def _vertex_headers() -> dict[str, str]:
    import google.auth
    import google.auth.transport.requests

    creds, _ = google.auth.default(scopes=[_CLOUD_SCOPE])
    creds.refresh(google.auth.transport.requests.Request())
    if not creds.token:
        raise RuntimeError("Vertex ADC returned no access token")
    return {
        "Authorization": f"Bearer {creds.token}",
        "Content-Type": "application/json",
        "x-goog-user-project": quota_project(),
    }
