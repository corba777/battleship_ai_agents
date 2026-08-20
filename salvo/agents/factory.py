from __future__ import annotations

import queue
import random

from salvo.agents.bots import OccupancyBot, ParityBot, RandomBot
from salvo.agents.catalog import is_llm_name, ollama_model, parse_slot
from salvo.agents.human import HumanPlayer
from salvo.agents.player import LlmPlayer
from salvo.agents.speech import pick_speech
from salvo.referee.events import PlayerMeta

LLMS = ("gemini", "claude", "opus", "openai")
PERSONAS = ("methodical", "intuitive")


def make_player(
    name: str,
    rng: random.Random,
    *,
    persona: str | None = None,
    speech: str | None = None,
    model: str | None = None,
    provider: str | None = None,
    side: str = "left",
    inbox: queue.Queue[str | None] | None = None,
    stop: object | None = None,
) -> OccupancyBot | ParityBot | RandomBot | LlmPlayer | HumanPlayer:
    if name == "parity":
        return ParityBot(
            rng,
            PlayerMeta(name="methodical", kind="bot", model="parity", persona="methodical"),
        )
    if name == "occupancy":
        return OccupancyBot(
            rng,
            PlayerMeta(name="occupancy", kind="bot", model="occupancy", persona="methodical"),
        )
    if name == "random":
        return RandomBot(rng, PlayerMeta(name="random", kind="bot", model="random"))
    if name == "human":
        if inbox is None:
            raise ValueError("human player needs a live shot inbox")
        return HumanPlayer(side, inbox, stop)
    picked = persona or ("methodical" if side == "left" else "intuitive")
    if picked not in PERSONAS:
        raise ValueError(f"unknown persona: {picked}")
    if provider == "ollama" and not is_llm_name(name):
        resolved = model or (ollama_model() if name == "ollama" else name)
        return LlmPlayer(
            "ollama",
            picked,
            speech=pick_speech(speech),
            model=resolved,
            provider="ollama",
        )
    if is_llm_name(name):
        kind, resolved = parse_slot(name, model)
        return LlmPlayer(
            kind,
            picked,
            speech=pick_speech(speech),
            model=resolved,
            provider=provider,
        )
    raise ValueError(f"unknown player: {name}")
