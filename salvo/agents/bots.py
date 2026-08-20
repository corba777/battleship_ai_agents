from __future__ import annotations

import random

from salvo.agents.observe import Observation, ShotRecord
from salvo.referee.board import FLEET, Cell, all_cells, all_poses, format_cell, parse_cell
from salvo.referee.events import PlayerMeta

__all__ = ["Observation", "ShotRecord", "RandomBot", "ParityBot", "OccupancyBot"]


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


class OccupancyBot:
    """Independent occupancy over remaining legal poses. Token-free fixture."""

    def __init__(self, rng: random.Random, meta: PlayerMeta | None = None) -> None:
        self.rng = rng
        self.meta = meta or PlayerMeta(
            name="occupancy", kind="bot", model="occupancy", persona="methodical"
        )

    def act(self, obs: Observation, error: str | None = None) -> dict[str, object]:
        del error
        fired = obs.fired()
        scores = occupancy_scores(obs)
        unfired = [c for c in all_cells() if format_cell(c) not in fired]
        if not unfired:
            unfired = list(all_cells())
        ranked = sorted(
            unfired,
            key=lambda c: (-scores.get(c, 0), c.col, c.row),
        )
        best = scores.get(ranked[0], 0)
        ties = [c for c in ranked if scores.get(c, 0) == best]
        target = self.rng.choice(ties)
        shot = format_cell(target)
        top = [shot]
        for cell in ranked:
            name = format_cell(cell)
            if name not in top:
                top.append(name)
            if len(top) == 3:
                break
        while len(top) < 3:
            top.append(shot)
        raw = [scores.get(parse_cell(cell), 0) for cell in top]
        peak = max(raw) or 1
        vals = [s / peak for s in raw]
        for i in range(1, len(vals)):
            if vals[i] >= vals[i - 1]:
                vals[i] = max(0.0, round(vals[i - 1] - 0.01, 4))
        belief = [{"cell": cell, "p": round(p, 4)} for cell, p in zip(top, vals)]
        return {
            "shot": shot,
            "belief": belief,
            "say": f"Highest occupancy is {shot}.",
        }


def occupancy_scores(obs: Observation) -> dict[Cell, int]:
    misses: set[Cell] = set()
    hits: set[Cell] = set()
    sunk_names: set[str] = set()
    for rec in obs.history:
        if rec.result == "miss":
            misses.add(parse_cell(rec.cell))
        elif rec.result == "hit":
            hits.add(parse_cell(rec.cell))
        if rec.sunk:
            sunk_names.add(rec.sunk)
    sunk_cells = {parse_cell(name) for name in obs.sunk_cells}
    unsunk_hits = hits - sunk_cells
    blocked = set(misses) | set(sunk_cells)
    for cell in sunk_cells:
        blocked.update(cell.neighbors8())
    remaining = [length for name, length in FLEET if name not in sunk_names]
    fired = {parse_cell(c) for c in obs.fired()}
    scores: dict[Cell, int] = {c: 0 for c in all_cells()}

    def add_poses(*, require_hit: bool) -> int:
        added = 0
        for length in remaining:
            for pose in all_poses(length):
                if any(c in blocked for c in pose):
                    continue
                if require_hit and unsunk_hits.isdisjoint(pose):
                    continue
                added += 1
                for cell in pose:
                    if cell not in fired:
                        scores[cell] += 1
        return added

    if unsunk_hits:
        if add_poses(require_hit=True) == 0:
            add_poses(require_hit=False)
    else:
        add_poses(require_hit=False)
    return scores


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
