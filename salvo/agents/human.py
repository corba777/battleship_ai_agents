from __future__ import annotations

import queue
from typing import Any

from salvo.agents.observe import Observation
from salvo.referee.board import CellError, all_cells, format_cell, parse_cell
from salvo.referee.events import PlayerMeta
from salvo.referee.match import MatchStopped


class HumanPlayer:
    def __init__(
        self,
        side: str,
        inbox: queue.Queue[str | None],
        stop: Any | None = None,
    ) -> None:
        self.side = side
        self._inbox = inbox
        self._stop = stop
        self.meta = PlayerMeta(name="human", kind="human", model="human")

    def act(self, obs: Observation, error: str | None = None) -> dict[str, object]:
        del obs, error
        while True:
            if self._stop is not None and self._stop.is_set():
                raise MatchStopped()
            try:
                item = self._inbox.get(timeout=0.15)
            except queue.Empty:
                continue
            if item is None:
                raise MatchStopped()
            try:
                cell = format_cell(parse_cell(item))
            except CellError:
                continue
            extras = _belief_cells(cell)
            return {
                "shot": cell,
                "belief": [
                    {"cell": c, "p": p} for c, p in zip(extras, (1.0, 0.2, 0.1))
                ],
                "say": f"Firing at {cell}.",
            }


def _belief_cells(shot: str) -> list[str]:
    out = [shot]
    origin = parse_cell(shot)
    for n in origin.neighbors8():
        name = format_cell(n)
        if name not in out:
            out.append(name)
        if len(out) == 3:
            return out
    for cell in all_cells():
        name = format_cell(cell)
        if name not in out:
            out.append(name)
        if len(out) == 3:
            return out
    while len(out) < 3:
        out.append(shot)
    return out[:3]
