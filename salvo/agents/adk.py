from __future__ import annotations

import asyncio
import logging
import os
from contextlib import contextmanager, nullcontext
from typing import Iterator
from uuid import uuid4

from salvo.agents.catalog import require_project_id
from salvo.agents.vertex import is_claude_model

log = logging.getLogger(__name__)

APP_NAME = "salvo"
FINAL_ANSWER_TAG = "/*FINAL_ANSWER*/"
PLANNING_TAG = "/*PLANNING*/"
REASONING_TAG = "/*REASONING*/"

REACT_OVERLAY = (
    "You have no tools. Do not invent function calls.\n"
    f"Use {PLANNING_TAG} then {REASONING_TAG} then {FINAL_ANSWER_TAG}.\n"
    f"{FINAL_ANSWER_TAG} must be the JSON object from the contract "
    "(shot, belief 1-3, say). No fences. The referee parses only that JSON."
)

_claude_registered = False


def extract_contract_text(text: str) -> str:
    """Keep /*FINAL_ANSWER*/ JSON. Planning tags are ADK-only, not the contract."""
    raw = text.strip()
    if FINAL_ANSWER_TAG in raw:
        raw = raw.split(FINAL_ANSWER_TAG)[-1].strip()
    return raw


def adk_model(model: str, provider: str):
    """Backend instance or Vertex model string. Anthropic API must not be a bare claude-*."""
    if provider == "openai":
        from google.adk.labs.openai import OpenAILlm

        return OpenAILlm(model=model)
    if provider == "anthropic":
        from google.adk.models.anthropic_llm import AnthropicLlm

        return AnthropicLlm(model=model)
    _ensure_claude_registered(model)
    return model


def complete(
    model: str,
    system: str,
    user: str,
    location: str = "global",
    *,
    provider: str = "vertex",
) -> str:
    """One-shot ADK LlmAgent. Fresh session each call; no board tools."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(_complete_async(model, system, user, location, provider))
    raise RuntimeError("salvo ADK complete() must run off the event loop")


async def _complete_async(
    model: str, system: str, user: str, location: str, provider: str
) -> str:
    from google.adk.agents import LlmAgent
    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService
    from google.genai import types

    instruction = f"{system}\n\n{REACT_OVERLAY}"
    backend = adk_model(model, provider)
    agent = LlmAgent(
        name="salvo_llm",
        model=backend,
        instruction=instruction,
        planner=_contract_planner(),
        generate_content_config=_content_config(model, provider, types),
    )
    sessions = InMemorySessionService()
    session_id = uuid4().hex
    env = _vertex_env(location) if provider == "vertex" else nullcontext()
    with env:
        await sessions.create_session(
            app_name=APP_NAME, user_id="player", session_id=session_id
        )
        runner = Runner(
            app_name=APP_NAME, agent=agent, session_service=sessions
        )
        message = types.Content(role="user", parts=[types.Part(text=user)])
        chunks: list[str] = []
        async for event in runner.run_async(
            user_id="player", session_id=session_id, new_message=message
        ):
            if not event.is_final_response():
                continue
            piece = _event_text(event)
            if piece:
                chunks.append(piece)
    if not chunks:
        raise RuntimeError("empty model response")
    text = extract_contract_text(chunks[-1])
    if not text:
        raise RuntimeError("empty model response")
    log.debug("adk final %s chars model=%s provider=%s", len(text), model, provider)
    return text


def _content_config(model: str, provider: str, types: object):
    from salvo.agents.providers import _anthropic_restricted, _openai_restricted

    GenerateContentConfig = types.GenerateContentConfig  # type: ignore[attr-defined]
    kwargs: dict[str, object] = {"max_output_tokens": 1200}
    skip_temp = (provider == "openai" and _openai_restricted(model)) or (
        provider == "anthropic" and _anthropic_restricted(model)
    )
    if not skip_temp:
        kwargs["temperature"] = 0.9
    return GenerateContentConfig(**kwargs)


def _event_text(event: object) -> str:
    content = getattr(event, "content", None)
    parts = getattr(content, "parts", None) if content is not None else None
    if not parts:
        return ""
    bits: list[str] = []
    for part in parts:
        if getattr(part, "thought", False):
            continue
        text = getattr(part, "text", None)
        if text:
            bits.append(text)
    return "".join(bits).strip()


def _contract_planner():
    from google.adk.planners.plan_re_act_planner import PlanReActPlanner
    from typing_extensions import override

    class ContractReActPlanner(PlanReActPlanner):
        @override
        def build_planning_instruction(self, readonly_context, llm_request) -> str:
            del readonly_context, llm_request
            return (
                "You have no tools. Never emit function calls.\n"
                f"Format: {PLANNING_TAG} a short hunt plan. "
                f"{REASONING_TAG} why this cell. "
                f"{FINAL_ANSWER_TAG} the JSON object only.\n"
                "The JSON must match the user contract (shot, belief 1-3, say)."
            )

    return ContractReActPlanner()


def _ensure_claude_registered(model: str) -> None:
    global _claude_registered
    if not is_claude_model(model) or _claude_registered:
        return
    from google.adk.models.anthropic_llm import Claude
    from google.adk.models.registry import LLMRegistry

    LLMRegistry.register(Claude)
    _claude_registered = True


@contextmanager
def _vertex_env(location: str) -> Iterator[None]:
    loc = (location or "global").strip() or "global"
    updates = {
        "GOOGLE_GENAI_USE_VERTEXAI": "TRUE",
        "GOOGLE_CLOUD_PROJECT": require_project_id(),
        "GOOGLE_CLOUD_LOCATION": loc,
    }
    previous = {key: os.environ.get(key) for key in updates}
    os.environ.update(updates)
    try:
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
