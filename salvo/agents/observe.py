from __future__ import annotations

import re
from dataclasses import dataclass, field

from salvo.referee.board import Board, format_cell
from salvo.referee.events import Side

_CELL_RE = re.compile(r"[A-J](?:10|[1-9])")


@dataclass
class ShotRecord:
    cell: str
    result: str
    sunk: str | None = None


@dataclass
class Observation:
    """Own fleet + own shot history. Never the opponent's placement."""

    side: Side
    board: Board
    history: list[ShotRecord] = field(default_factory=list)
    sunk_cells: set[str] = field(default_factory=set)

    def fired(self) -> set[str]:
        return {h.cell for h in self.history}


def render_observation(obs: Observation, error: str | None = None) -> str:
    lines = ["Your fleet:"]
    for ship in obs.board.ships:
        cells = " ".join(format_cell(c) for c in ship.cells)
        lines.append(f"- {ship.name}: {cells}")
    lines.append("")
    lines.append("Your shots:")
    if not obs.history:
        lines.append("- (none yet)")
    else:
        for rec in obs.history:
            extra = f", sunk {rec.sunk}" if rec.sunk else ""
            lines.append(f"- {rec.cell} {rec.result}{extra}")
    if error:
        lines.append("")
        lines.append(f"Your last output was illegal: {error}")
        lines.append("Send a valid JSON object only. No fences, no prose outside it.")
    lines.append("")
    lines.append("Fire now. JSON only.")
    return "\n".join(lines)


def cells_in_text(text: str) -> set[str]:
    return {m.group(0) for m in _CELL_RE.finditer(text.upper())}


def forbidden_foe_cells(own: Board, foe: Board, history: list[ShotRecord]) -> set[str]:
    mine = {format_cell(c) for ship in own.ships for c in ship.cells}
    shots = {rec.cell for rec in history}
    theirs = {format_cell(c) for ship in foe.ships for c in ship.cells}
    return theirs - mine - shots


def leaked_foe_cells(text: str, own: Board, foe: Board, history: list[ShotRecord]) -> set[str]:
    return cells_in_text(text) & forbidden_foe_cells(own, foe, history)
