from __future__ import annotations

import random

from salvo.agents.bots import ParityBot, RandomBot
from salvo.referee.events import Illegal, MatchAbort, MatchEnd, MatchStart, PlayerMeta, ShotResult
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
    illegals = [e for e in events if isinstance(e, Illegal)]
    assert all(e.kind == "rules" for e in illegals)
    shots = [e for e in events if e.type == "shot_result"]
    assert shots[0].coerced is True  # type: ignore[union-attr]


class _FourBeliefs:
    meta = PlayerMeta(name="chatty", kind="bot", model="chatty")

    def act(self, obs: object, error: str | None = None) -> str:
        del obs, error
        return (
            '{"shot":"D2","belief":['
            '{"cell":"D2","p":0.9},{"cell":"D3","p":0.4},'
            '{"cell":"C2","p":0.2},{"cell":"E2","p":0.1}'
            '],"say":"D2 is the cell."}'
        )


def test_schema_illegal_does_not_count_as_rules() -> None:
    left = _FourBeliefs()
    right = RandomBot(random.Random(1), PlayerMeta(name="random", kind="bot", model="random"))
    events = []
    for event in play_match(left, right, seed=3):  # type: ignore[arg-type]
        events.append(event)
        if len(events) > 12:
            break
    illegals = [e for e in events if isinstance(e, Illegal)]
    assert len(illegals) >= 2
    assert all(e.kind == "schema" for e in illegals)
    start = events[0]
    assert isinstance(start, MatchStart)
    end_or_shot = next(e for e in events if e.type == "shot_result")
    assert end_or_shot.coerced is True  # type: ignore[union-attr]
    # match_end may not have arrived yet; stats live on later events
    stats_event = next(
        (e for e in events if e.type in ("match_end", "match_abort")),
        None,
    )
    if stats_event is not None and hasattr(stats_event, "stats"):
        assert stats_event.stats["left"].illegals == 0  # type: ignore[union-attr]
        assert stats_event.stats["left"].schema >= 2  # type: ignore[union-attr]


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
