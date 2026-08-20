from __future__ import annotations

import json
from dataclasses import dataclass

from salvo.referee.board import CellError, format_cell, parse_cell
from salvo.referee.events import Belief


class ContractError(ValueError):
    pass


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
            raise ContractError(f"unparseable: {exc.msg}") from exc
    else:
        data = payload
        raw = json.dumps(payload, ensure_ascii=False)
    if not isinstance(data, dict):
        raise ContractError("output is not an object")
    shot_raw = data.get("shot")
    if not isinstance(shot_raw, str):
        raise ContractError("missing shot")
    try:
        shot = format_cell(parse_cell(shot_raw))
    except CellError as exc:
        raise ContractError(str(exc)) from exc
    belief = _parse_belief(data.get("belief"))
    say = data.get("say")
    if not isinstance(say, str) or not say.strip():
        raise ContractError("missing say")
    return Action(shot=shot, belief=tuple(belief), say=say.strip(), raw=raw)


def _parse_belief(raw: object) -> list[Belief]:
    if not isinstance(raw, list) or len(raw) != 3:
        raise ContractError("belief must have exactly 3 entries")
    out: list[Belief] = []
    prev = 2.0
    for item in raw:
        if not isinstance(item, dict):
            raise ContractError("belief entry must be an object")
        cell_raw = item.get("cell")
        p = item.get("p")
        if not isinstance(cell_raw, str) or not isinstance(p, (int, float)):
            raise ContractError("belief needs cell and p")
        if not 0 <= float(p) <= 1:
            raise ContractError("belief p out of range")
        if float(p) > prev:
            raise ContractError("belief must be descending p")
        try:
            cell = format_cell(parse_cell(cell_raw))
        except CellError as exc:
            raise ContractError(str(exc)) from exc
        out.append(Belief(cell=cell, p=float(p)))
        prev = float(p)
    return out
