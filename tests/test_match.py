from __future__ import annotations

import random

from salvo.agents.bots import ParityBot, RandomBot
from salvo.referee.events import MatchAbort, MatchEnd, MatchStart, PlayerMeta, ShotResult
from salvo.referee.match import play_match


def test_bot_match_finishes() -> None:
    left = ParityBot(random.Random(1), PlayerMeta(name="methodical", kind="bot", model="parity"))
    right = RandomBot(random.Random(2), PlayerMeta(name="random", kind="bot", model="random"))
    events = list(play_match(left, right, seed=42))
    assert isinstance(events[0], MatchStart)
    assert isinstance(events[-1], MatchEnd)
    assert events[0].placements["left"]
    assert events[0].placements["right"]
    shots = [e for e in events if isinstance(e, ShotResult)]
    assert shots
    assert events[-1].winner in ("left", "right")


def test_same_seed_same_placements() -> None:
    def start(seed: int) -> MatchStart:
        left = ParityBot(random.Random(0), PlayerMeta(name="a", kind="bot", model="parity"))
        right = RandomBot(random.Random(0), PlayerMeta(name="b", kind="bot", model="random"))
        first = next(iter(play_match(left, right, seed=seed)))
        assert isinstance(first, MatchStart)
        return first

    a = start(7)
    b = start(7)
    assert a.placements == b.placements


class _AlwaysIllegal:
    meta = PlayerMeta(name="bad", kind="bot", model="bad")

    def act(self, obs: object, error: str | None = None) -> str:
        del obs, error
        return "5E"


def test_illegal_then_coerce() -> None:
    left = _AlwaysIllegal()
    right = RandomBot(random.Random(1), PlayerMeta(name="random", kind="bot", model="random"))
    events = []
    for event in play_match(left, right, seed=3):  # type: ignore[arg-type]
        events.append(event)
        if len(events) > 12:
            break
    kinds = [e.type for e in events]
    assert kinds.count("illegal") >= 2
    shots = [e for e in events if e.type == "shot_result"]
    assert shots[0].coerced is True  # type: ignore[union-attr]


def test_stop_flag_aborts_before_turns() -> None:
    import threading

    left = ParityBot(random.Random(1), PlayerMeta(name="methodical", kind="bot", model="parity"))
    right = RandomBot(random.Random(2), PlayerMeta(name="random", kind="bot", model="random"))
    stop = threading.Event()
    stop.set()
    events = list(play_match(left, right, seed=1, stop=stop))
    assert isinstance(events[0], MatchStart)
    assert isinstance(events[-1], MatchAbort)
    assert events[-1].turns == 0
    assert events[-1].reason == "stopped"
