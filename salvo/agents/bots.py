from __future__ import annotations

import random

from salvo.agents.observe import Observation, ShotRecord
from salvo.referee.board import Cell, all_cells, format_cell, parse_cell
from salvo.referee.events import PlayerMeta

__all__ = ["Observation", "ShotRecord", "RandomBot", "ParityBot"]


class RandomBot:
    def __init__(self, rng: random.Random, meta: PlayerMeta | None = None) -> None:
        self.rng = rng
        self.meta = meta or PlayerMeta(name="random", kind="bot", model="random")

    def act(self, obs: Observation, error: str | None = None) -> dict[str, object]:
        del error
        pool = [c for c in all_cells() if format_cell(c) not in obs.fired()]
        if not pool:
            pool = list(all_cells())
        cell = format_cell(self.rng.choice(pool))
        extras = [format_cell(c) for c in pool if format_cell(c) != cell]
        self.rng.shuffle(extras)
        while len(extras) < 2:
            extras.append(cell)
        return {
            "shot": cell,
            "belief": [
                {"cell": cell, "p": 0.4},
                {"cell": extras[0], "p": 0.2},
                {"cell": extras[1], "p": 0.1},
            ],
            "say": f"Firing at {cell}.",
        }


class ParityBot:
    def __init__(self, rng: random.Random, meta: PlayerMeta | None = None) -> None:
        self.rng = rng
        self.meta = meta or PlayerMeta(
            name="methodical", kind="bot", model="parity", persona="methodical"
        )

    def act(self, obs: Observation, error: str | None = None) -> dict[str, object]:
        del error
        fired = obs.fired()
        target = self._adjacent_hit(obs, fired) or self._hunt(fired)
        if target is None:
            leftover = [c for c in all_cells() if format_cell(c) not in fired]
            target = leftover[0] if leftover else all_cells()[0]
        shot = format_cell(target)
        candidates = _pad_candidates(shot, fired)
        return {
            "shot": shot,
            "belief": [
                {"cell": c, "p": p} for c, p in zip(candidates, (0.72, 0.41, 0.18))
            ],
            "say": f"Parity hunt continues at {shot}.",
        }

    def _adjacent_hit(self, obs: Observation, fired: set[str]) -> Cell | None:
        for rec in reversed(obs.history):
            if rec.result != "hit" or rec.cell in obs.sunk_cells:
                continue
            cell = parse_cell(rec.cell)
            for n in (
                Cell(cell.col + 1, cell.row),
                Cell(cell.col - 1, cell.row),
                Cell(cell.col, cell.row + 1),
                Cell(cell.col, cell.row - 1),
            ):
                if n.on_board() and format_cell(n) not in fired:
                    return n
        return None

    def _hunt(self, fired: set[str]) -> Cell | None:
        for c in all_cells():
            if (c.col + c.row) % 2 == 0 and format_cell(c) not in fired:
                return c
        rest = [c for c in all_cells() if format_cell(c) not in fired]
        return rest[0] if rest else None


def _pad_candidates(shot: str, fired: set[str]) -> list[str]:
    out = [shot]
    origin = parse_cell(shot)
    for n in origin.neighbors8():
        name = format_cell(n)
        if name not in fired and name not in out:
            out.append(name)
        if len(out) == 3:
            return out
    for c in all_cells():
        name = format_cell(c)
        if name not in out:
            out.append(name)
        if len(out) == 3:
            return out
    while len(out) < 3:
        out.append(shot)
    return out[:3]
