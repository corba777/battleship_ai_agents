from __future__ import annotations

import hashlib
import logging
from collections.abc import Callable
from pathlib import Path

from salvo.agents.catalog import pick_adk, pick_provider, resolve_model
from salvo.agents.observe import Observation, render_observation
from salvo.agents.speech import SpeechProfile, compose_system, pick_speech
from salvo.referee.events import PlayerMeta

PROMPTS = Path(__file__).resolve().parent / "prompts"

CompleteFn = Callable[[str, str], str]
log = logging.getLogger(__name__)


def load_persona(name: str) -> str:
    path = PROMPTS / f"{name}.md"
    if not path.is_file():
        raise FileNotFoundError(f"unknown persona: {name}")
    return path.read_text(encoding="utf-8").strip()


class LlmPlayer:
    def __init__(
        self,
        kind: str,
        persona: str,
        complete: CompleteFn | None = None,
        speech: str | None = None,
        model: str | None = None,
        provider: str | None = None,
        adk: bool | None = None,
    ) -> None:
        self.kind = kind
        self.persona = persona
        self.model = resolve_model(kind, model)
        self.provider = pick_provider(kind, provider, model=self.model)
        self.adk = pick_adk(self.provider, adk)
        self.speech: SpeechProfile = pick_speech(speech)
        self.system = compose_system(load_persona(persona), self.speech)
        self.prompt_hash = hashlib.sha256(self.system.encode()).hexdigest()[:16]
        self._complete = complete
        self.meta = PlayerMeta(
            name=persona,
            kind="llm",
            model=self.model,
            persona=persona,
            speech=self.speech,
            provider=self.provider,
            adk=self.adk or None,
        )

    def act(self, obs: Observation, error: str | None = None) -> str:
        user = render_observation(obs, error=error)
        try:
            if self._complete is not None:
                return self._complete(self.system, user)
            from salvo.agents.providers import complete

            return complete(
                self.kind,
                self.system,
                user,
                model=self.model,
                provider=self.provider,
                adk=self.adk,
            )
        except Exception as exc:
            log.exception(
                "provider error kind=%s model=%s provider=%s",
                self.kind,
                self.model,
                self.provider,
            )
            return f"(provider error) {exc}"
