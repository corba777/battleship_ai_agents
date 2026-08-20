from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

Side = Literal["left", "right"]
ShotKind = Literal["hit", "miss", "repeat"]
PlayerKind = Literal["llm", "bot", "human"]


@dataclass(slots=True)
class PlayerMeta:
    name: str
    kind: PlayerKind
    model: str
    persona: str | None = None
    speech: str | None = None
    provider: str | None = None
    adk: bool | None = None

    def as_dict(self) -> dict[str, Any]:
        data = {"name": self.name, "kind": self.kind, "model": self.model}
        if self.persona is not None:
            data["persona"] = self.persona
        if self.speech is not None:
            data["speech"] = self.speech
        if self.provider is not None:
            data["provider"] = self.provider
        if self.adk:
            data["adk"] = True
        return data


@dataclass(slots=True)
class Belief:
    cell: str
    p: float


@dataclass(slots=True)
class SideStats:
    shots: int = 0
    hits: int = 0
    misses: int = 0
    repeats: int = 0
    illegals: int = 0
    schema: int = 0
    coerced: int = 0

    def as_dict(self) -> dict[str, int]:
        return asdict(self)


@dataclass(slots=True)
class MatchStart:
    seed: int
    players: dict[Side, PlayerMeta]
    placements: dict[Side, list[dict[str, Any]]]
    prompt_hashes: dict[str, str] = field(default_factory=dict)
    type: Literal["match_start"] = "match_start"

    def as_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "type": self.type,
            "seed": self.seed,
            "players": {side: meta.as_dict() for side, meta in self.players.items()},
            "placements": self.placements,
        }
        if self.prompt_hashes:
            payload["prompt_hashes"] = self.prompt_hashes
        return payload


@dataclass(slots=True)
class Turn:
    side: Side
    index: int
    type: Literal["turn"] = "turn"

    def as_dict(self) -> dict[str, Any]:
        return {"type": self.type, "side": self.side, "index": self.index}


@dataclass(slots=True)
class Thinking:
    side: Side
    say: str
    belief: list[Belief]
    type: Literal["thinking"] = "thinking"

    def as_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "side": self.side,
            "say": self.say,
            "belief": [{"cell": b.cell, "p": b.p} for b in self.belief],
        }


@dataclass(slots=True)
class ShotResult:
    side: Side
    cell: str
    result: ShotKind
    coerced: bool
    type: Literal["shot_result"] = "shot_result"

    def as_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "side": self.side,
            "cell": self.cell,
            "result": self.result,
            "coerced": self.coerced,
        }


@dataclass(slots=True)
class Sunk:
    side: Side
    ship: str
    cells: list[str]
    type: Literal["sunk"] = "sunk"

    def as_dict(self) -> dict[str, Any]:
        return {"type": self.type, "side": self.side, "ship": self.ship, "cells": self.cells}


@dataclass(slots=True)
class Illegal:
    side: Side
    raw: str
    reason: str
    attempt: int
    kind: Literal["rules", "schema"] = "rules"
    type: Literal["illegal"] = "illegal"

    def as_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "side": self.side,
            "raw": self.raw,
            "reason": self.reason,
            "kind": self.kind,
            "attempt": self.attempt,
        }


@dataclass(slots=True)
class MatchAbort:
    turns: int
    stats: dict[Side, SideStats]
    reason: str = "stopped"
    type: Literal["match_abort"] = "match_abort"

    def as_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "turns": self.turns,
            "reason": self.reason,
            "stats": {side: s.as_dict() for side, s in self.stats.items()},
        }


@dataclass(slots=True)
class MatchEnd:
    winner: Side
    turns: int
    stats: dict[Side, SideStats]
    type: Literal["match_end"] = "match_end"

    def as_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "winner": self.winner,
            "turns": self.turns,
            "stats": {side: s.as_dict() for side, s in self.stats.items()},
        }


MatchEvent = MatchStart | Turn | Thinking | ShotResult | Sunk | Illegal | MatchAbort | MatchEnd


def opponent(side: Side) -> Side:
    return "right" if side == "left" else "left"
