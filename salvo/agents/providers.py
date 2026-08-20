from __future__ import annotations

import logging
import re

from salvo.agents.catalog import pick_adk, pick_provider, resolve_model
from salvo.agents.vertex import generate, vertex_location

log = logging.getLogger(__name__)


def complete(
    kind: str,
    system: str,
    user: str,
    *,
    model: str | None = None,
    provider: str | None = None,
    adk: bool | None = None,
) -> str:
    resolved = resolve_model(kind, model)
    route = pick_provider(kind, provider, model=resolved)
    use_adk = pick_adk(route, adk)
    if use_adk:
        from salvo.agents.adk import complete as adk_complete

        location = vertex_location(kind) if route == "vertex" else "global"
        return adk_complete(
            resolved, system, user, location, provider=route
        )
    if route == "vertex":
        return generate(resolved, system, user, vertex_location(kind), adk=False)
    if route == "gemini":
        return generate_gemini_api(resolved, system, user)
    if route == "openai":
        return generate_openai(resolved, system, user)
    if route == "ollama":
        return generate_ollama(resolved, system, user)
    return generate_anthropic(resolved, system, user)


def generate_gemini_api(model: str, system: str, user: str) -> str:
    from google import genai
    from google.genai import types

    from salvo.agents.catalog import gemini_api_key

    key = gemini_api_key()
    if not key:
        raise RuntimeError("GEMINI_API_KEY / GOOGLE_API_KEY is not set")
    client = genai.Client(api_key=key)
    response = client.models.generate_content(
        model=model,
        contents=user,
        config=types.GenerateContentConfig(
            system_instruction=system,
            temperature=0.9,
            max_output_tokens=400,
        ),
    )
    text = response.text
    if not text:
        raise RuntimeError("empty model response")
    return text


def generate_anthropic(model: str, system: str, user: str) -> str:
    import anthropic

    from salvo.agents.catalog import anthropic_api_key

    key = anthropic_api_key()
    if not key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set")
    client = anthropic.Anthropic(api_key=key)
    kwargs: dict[str, object] = {
        "model": model,
        "max_tokens": 800 if _anthropic_always_on_thinking(model) else 400,
        "system": system,
        "messages": [{"role": "user", "content": user}],
    }
    if _anthropic_always_on_thinking(model):
        kwargs["output_config"] = {"effort": "low"}
    elif _anthropic_restricted(model):
        kwargs["thinking"] = {"type": "disabled"}
    else:
        kwargs["temperature"] = 0.9
    message = client.messages.create(**kwargs)
    parts = [block.text for block in message.content if getattr(block, "text", None)]
    text = "".join(parts).strip()
    if not text:
        raise RuntimeError("empty model response")
    return text


def generate_openai(model: str, system: str, user: str) -> str:
    import httpx

    from salvo.agents.catalog import openai_api_key

    key = openai_api_key()
    if not key:
        raise RuntimeError("OPENAI_API_KEY is not set")
    body: dict[str, object] = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    if _openai_restricted(model):
        body["max_completion_tokens"] = 800
    else:
        body["max_tokens"] = 400
        body["temperature"] = 0.9
    response = httpx.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {key}"},
        json=body,
        timeout=60.0,
    )
    response.raise_for_status()
    text = (
        response.json()
        .get("choices", [{}])[0]
        .get("message", {})
        .get("content")
        or ""
    )
    if not str(text).strip():
        raise RuntimeError("empty model response")
    return str(text)


def ollama_chat_body(
    model: str,
    system: str,
    user: str,
    *,
    think: bool | None = None,
) -> dict[str, object]:
    from salvo.agents.catalog import ollama_think

    enabled = ollama_think() if think is None else think
    return {
        "model": model,
        "stream": False,
        "format": "json",
        "think": enabled,
        "options": {
            "temperature": 0.9,
            "num_predict": 1600 if enabled else 400,
        },
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }


def ollama_content(data: dict[str, object]) -> str:
    message = data.get("message")
    if not isinstance(message, dict):
        raise RuntimeError("empty model response")
    text = str(message.get("content") or "").strip()
    thinking = str(message.get("thinking") or "").strip()
    if thinking:
        log.info("ollama think (%s chars)", len(thinking))
    if text:
        return text
    if thinking:
        raise RuntimeError("empty content (model spent tokens on think)")
    raise RuntimeError("empty model response")


def generate_ollama(model: str, system: str, user: str) -> str:
    import httpx

    from salvo.agents.catalog import ollama_think, ollama_url

    think = ollama_think()
    response = httpx.post(
        f"{ollama_url()}/api/chat",
        json=ollama_chat_body(model, system, user, think=think),
        timeout=180.0 if think else 120.0,
    )
    if response.status_code >= 400:
        raise RuntimeError(f"ollama {response.status_code}: {response.text[:800]}")
    return ollama_content(response.json())


def _openai_restricted(model: str) -> bool:
    return bool(re.match(r"^(o[0-9]|gpt-5|gpt-6)", model, re.I))


def _anthropic_restricted(model: str) -> bool:
    return bool(
        re.search(
            r"claude-(sonnet-5|opus-5|opus-4-[7-9]|fable-5|mythos-5)\b",
            model,
            re.I,
        )
    )


def _anthropic_always_on_thinking(model: str) -> bool:
    return bool(re.search(r"claude-(fable-5|mythos-5)\b", model, re.I))
