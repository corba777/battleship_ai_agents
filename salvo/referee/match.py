from __future__ import annotations

import json
import random
from collections.abc import Iterator
from typing import Protocol

from salvo.agents.observe import Observation, ShotRecord
from salvo.agents.contract import Action, ContractError, parse_action
from salvo.referee.board import Board, all_cells, format_cell
from salvo.referee.events import (
    Belief,
    Illegal,
    MatchAbort,
    MatchEnd,
    MatchEvent,
    MatchStart,
    PlayerMeta,
    ShotResult,
    Side,
    SideStats,
    Sunk,
    Thinking,
    Turn,
    opponent,
)


class Player(Protocol):
    meta: PlayerMeta

    def act(self, obs: Observation, error: str | None = None) -> dict[str, object] | str: ...


class StopFlag(Protocol):
    def is_set(self) -> bool: ...


class MatchStopped(Exception):
    """Human inbox closed or STOP while waiting for a click."""


def play_match(
    left: Player,
    right: Player,
    seed: int,
    *,
    left_ships: list[dict[str, object]] | None = None,
    right_ships: list[dict[str, object]] | None = None,
    stop: StopFlag | None = None,
) -> Iterator[MatchEvent]:
    rng = random.Random(seed)
    boards: dict[Side, Board] = {
        "left": Board.from_ships(left_ships) if left_ships is not None else Board.random(rng),
        "right": Board.from_ships(right_ships) if right_ships is not None else Board.random(rng),
    }
    coerce_rng = random.Random(rng.random())
    players: dict[Side, Player] = {"left": left, "right": right}
    observations: dict[Side, Observation] = {
        "left": Observation(side="left", board=boards["left"]),
        "right": Observation(side="right", board=boards["right"]),
    }
    stats: dict[Side, SideStats] = {"left": SideStats(), "right": SideStats()}

    hashes: dict[str, str] = {}
    for label, player in players.items():
        digest = getattr(player, "prompt_hash", None)
        if isinstance(digest, str):
            hashes[label] = digest

    yield MatchStart(
        seed=seed,
        players={"left": left.meta, "right": right.meta},
        placements={
            "left": boards["left"].placement_dicts(),
            "right": boards["right"].placement_dicts(),
        },
        prompt_hashes=hashes,
    )

    side: Side = "left"
    turn_index = 0
    while True:
        if stop is not None and stop.is_set():
            yield MatchAbort(turns=turn_index, stats=stats)
            return
        turn_index += 1
        yield Turn(side=side, index=turn_index)
        try:
            action, coerced, illegal_events = _take_action(
                players[side], observations[side], coerce_rng
            )
        except MatchStopped:
            yield MatchAbort(turns=turn_index, stats=stats)
            return
        for event in illegal_events:
            stats[side].illegals += 1
            yield event
        if coerced:
            stats[side].coerced += 1
        yield Thinking(side=side, say=action.say, belief=list(action.belief))
        target = opponent(side)
        fired = boards[target].fire(action.shot)
        cell_name = format_cell(fired.cell)
        yield ShotResult(
            side=side, cell=cell_name, result=fired.result, coerced=coerced
        )
        stats[side].shots += 1
        if fired.result == "hit":
            stats[side].hits += 1
        elif fired.result == "miss":
            stats[side].misses += 1
        else:
            stats[side].repeats += 1
        sunk_name = fired.sunk.name if fired.sunk else None
        observations[side].history.append(
            ShotRecord(cell=cell_name, result=fired.result, sunk=sunk_name)
        )
        if fired.sunk is not None:
            cells = [format_cell(c) for c in fired.sunk.cells]
            observations[side].sunk_cells.update(cells)
            yield Sunk(side=side, ship=fired.sunk.name, cells=cells)
            if boards[target].all_sunk():
                yield MatchEnd(winner=side, turns=turn_index, stats=stats)
                return
        side = opponent(side)


def _take_action(
    player: Player, obs: Observation, rng: random.Random
) -> tuple[Action, bool, list[Illegal]]:
    illegal: list[Illegal] = []
    error: str | None = None
    for attempt in (1, 2):
        raw = player.act(obs, error=error)
        try:
            return parse_action(raw), False, illegal
        except ContractError as exc:
            error = str(exc)
            illegal.append(
                Illegal(
                    side=obs.side,
                    raw=_raw_text(raw),
                    reason=error,
                    attempt=attempt,
                )
            )
    cell = format_cell(rng.choice(list(all_cells())))
    action = Action(
        shot=cell,
        belief=(
            Belief(cell=cell, p=0.33),
            Belief(cell=cell, p=0.22),
            Belief(cell=cell, p=0.11),
        ),
        say="Coerced. The referee picked for me.",
        raw="coerced",
    )
    return action, True, illegal


def _raw_text(raw: dict[str, object] | str) -> str:
    return raw if isinstance(raw, str) else json.dumps(raw, ensure_ascii=False)
