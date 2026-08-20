from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Literal

from salvo.referee.board import CellError, format_cell, parse_cell
from salvo.referee.events import Belief

IllegalKind = Literal["rules", "schema"]


class ContractError(ValueError):
    """Agent output failed the contract. `kind` is HUD/stats, not repair policy."""

    kind: IllegalKind

    def __init__(self, message: str, *, kind: IllegalKind) -> None:
        super().__init__(message)
        self.kind = kind


@dataclass(frozen=True, slots=True)
class Action:
    shot: str
    belief: tuple[Belief, ...]
    say: str
    raw: str


def parse_action(payload: dict[str, object] | str) -> Action:
    if isinstance(payload, str):
        raw = payload
        try:
            data = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise ContractError(f"unparseable: {exc.msg}", kind="rules") from exc
    else:
        data = payload
        raw = json.dumps(payload, ensure_ascii=False)
    if not isinstance(data, dict):
        raise ContractError("output is not an object", kind="rules")
    shot_raw = data.get("shot")
    if not isinstance(shot_raw, str):
        raise ContractError("missing shot", kind="schema")
    try:
        shot = format_cell(parse_cell(shot_raw))
    except CellError as exc:
        raise ContractError(str(exc), kind="rules") from exc
    belief = _parse_belief(data.get("belief"))
    say = data.get("say")
    if not isinstance(say, str) or not say.strip():
        raise ContractError("missing say", kind="schema")
    return Action(shot=shot, belief=tuple(belief), say=say.strip(), raw=raw)


def _parse_belief(raw: object) -> list[Belief]:
    if not isinstance(raw, list) or not (1 <= len(raw) <= 3):
        raise ContractError("belief must have 1 to 3 entries", kind="schema")
    out: list[Belief] = []
    prev = 2.0
    for item in raw:
        if not isinstance(item, dict):
            raise ContractError("belief entry must be an object", kind="schema")
        cell_raw = item.get("cell")
        p = item.get("p")
        if not isinstance(cell_raw, str) or not isinstance(p, (int, float)):
            raise ContractError("belief needs cell and p", kind="schema")
        if not 0 <= float(p) <= 1:
            raise ContractError("belief p out of range", kind="schema")
        if float(p) > prev:
            raise ContractError("belief must be descending p", kind="schema")
        try:
            cell = format_cell(parse_cell(cell_raw))
        except CellError as exc:
            raise ContractError(str(exc), kind="schema") from exc
        out.append(Belief(cell=cell, p=float(p)))
        prev = float(p)
    return out
