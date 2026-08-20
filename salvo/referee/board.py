"""Referee board: placement, shot resolution, sink detection.

No-touch rule: Chebyshev distance between any cells of two ships must be
>= 2 (a one-cell gap, including diagonally).
"""

from __future__ import annotations

import random
import re
from dataclasses import dataclass, field
from typing import Literal, Sequence

COLUMNS = "ABCDEFGHIJ"
BOARD_SIZE = 10
FLEET: tuple[tuple[str, int], ...] = (
    ("carrier", 5),
    ("battleship", 4),
    ("cruiser", 3),
    ("submarine", 3),
    ("destroyer", 2),
)

ShotKind = Literal["hit", "miss", "repeat"]
_CELL_RE = re.compile(r"^([A-J])(10|[1-9])$")


class CellError(ValueError):
    pass


class PlacementError(ValueError):
    pass


@dataclass(frozen=True, order=True, slots=True)
class Cell:
    col: int
    row: int

    def neighbors8(self) -> tuple[Cell, ...]:
        out: list[Cell] = []
        for dc in (-1, 0, 1):
            for dr in (-1, 0, 1):
                if dc == 0 and dr == 0:
                    continue
                n = Cell(self.col + dc, self.row + dr)
                if n.on_board():
                    out.append(n)
        return tuple(out)

    def on_board(self) -> bool:
        return 0 <= self.col < BOARD_SIZE and 0 <= self.row < BOARD_SIZE

    def chebyshev(self, other: Cell) -> int:
        return max(abs(self.col - other.col), abs(self.row - other.row))


def parse_cell(raw: str) -> Cell:
    """Canonical form is `E5`. Case and surrounding whitespace are forgiven.

    Transposition is not: `5E` raises CellError.
    """
    s = raw.strip().upper()
    m = _CELL_RE.fullmatch(s)
    if not m:
        raise CellError(f"illegal cell: {raw!r}")
    return Cell(COLUMNS.index(m.group(1)), int(m.group(2)) - 1)


def format_cell(cell: Cell) -> str:
    if not cell.on_board():
        raise CellError(f"cell out of range: {cell}")
    return f"{COLUMNS[cell.col]}{cell.row + 1}"


def all_cells() -> tuple[Cell, ...]:
    return tuple(Cell(c, r) for r in range(BOARD_SIZE) for c in range(BOARD_SIZE))


@dataclass(frozen=True, slots=True)
class Ship:
    name: str
    cells: tuple[Cell, ...]

    def as_dict(self) -> dict[str, object]:
        return {"name": self.name, "cells": [format_cell(c) for c in self.cells]}


@dataclass(frozen=True, slots=True)
class FireResult:
    cell: Cell
    result: ShotKind
    sunk: Ship | None = None


@dataclass
class Board:
    ships: tuple[Ship, ...]
    _resolved: dict[Cell, Literal["hit", "miss"]] = field(default_factory=dict)
    _hits: dict[str, set[Cell]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self._hits:
            self._hits = {ship.name: set() for ship in self.ships}

    @classmethod
    def from_ships(cls, ships: Sequence[dict[str, object] | Ship]) -> Board:
        placed = tuple(_coerce_ship(s) for s in ships)
        validate_placement(placed)
        return cls(ships=placed)

    @classmethod
    def random(cls, rng: random.Random) -> Board:
        return cls(ships=random_placement(rng))

    def fire(self, cell: Cell | str) -> FireResult:
        target = parse_cell(cell) if isinstance(cell, str) else cell
        if not target.on_board():
            raise CellError(f"cell out of range: {target}")
        if target in self._resolved:
            return FireResult(cell=target, result="repeat")
        occupant = self._occupant(target)
        if occupant is None:
            self._resolved[target] = "miss"
            return FireResult(cell=target, result="miss")
        self._resolved[target] = "hit"
        self._hits[occupant.name].add(target)
        sunk = occupant if set(occupant.cells) <= self._hits[occupant.name] else None
        return FireResult(cell=target, result="hit", sunk=sunk)

    def all_sunk(self) -> bool:
        return all(set(ship.cells) <= self._hits[ship.name] for ship in self.ships)

    def placement_dicts(self) -> list[dict[str, object]]:
        return [ship.as_dict() for ship in self.ships]

    def _occupant(self, cell: Cell) -> Ship | None:
        for ship in self.ships:
            if cell in ship.cells:
                return ship
        return None


def validate_placement(ships: Sequence[Ship]) -> None:
    expected = {name: length for name, length in FLEET}
    got_names = [s.name for s in ships]
    if sorted(got_names) != sorted(expected):
        raise PlacementError(f"fleet must be {list(expected)}, got {got_names}")
    occupied: list[tuple[Ship, Cell]] = []
    for ship in ships:
        want = expected[ship.name]
        if len(ship.cells) != want:
            raise PlacementError(f"{ship.name} must occupy {want} cells")
        if len(set(ship.cells)) != len(ship.cells):
            raise PlacementError(f"{ship.name} has duplicate cells")
        for cell in ship.cells:
            if not cell.on_board():
                raise PlacementError(f"{ship.name} leaves the board at {format_cell(cell)}")
        if not _is_straight(ship.cells):
            raise PlacementError(f"{ship.name} is not a straight orthogonal line")
        occupied.extend((ship, c) for c in ship.cells)
    by_cell: dict[Cell, str] = {}
    for ship, cell in occupied:
        other = by_cell.get(cell)
        if other is not None:
            raise PlacementError(f"overlap at {format_cell(cell)} ({other} / {ship.name})")
        by_cell[cell] = ship.name
    for i, (a_ship, a_cell) in enumerate(occupied):
        for b_ship, b_cell in occupied[i + 1 :]:
            if a_ship.name == b_ship.name:
                continue
            if a_cell.chebyshev(b_cell) < 2:
                raise PlacementError(
                    f"{a_ship.name} and {b_ship.name} touch at "
                    f"{format_cell(a_cell)} / {format_cell(b_cell)}"
                )


def random_placement(rng: random.Random, *, attempts: int = 250) -> tuple[Ship, ...]:
    for _ in range(attempts):
        placed: list[Ship] = []
        blocked: set[Cell] = set()
        ok = True
        for name, length in FLEET:
            ship = _place_one(rng, name, length, blocked)
            if ship is None:
                ok = False
                break
            placed.append(ship)
            for cell in ship.cells:
                blocked.add(cell)
                blocked.update(cell.neighbors8())
        if ok:
            validate_placement(placed)
            return tuple(placed)
    raise PlacementError("could not place fleet")


def _place_one(
    rng: random.Random, name: str, length: int, blocked: set[Cell]
) -> Ship | None:
    poses = _all_poses(length)
    rng.shuffle(poses)
    for cells in poses:
        if any(c in blocked for c in cells):
            continue
        return Ship(name=name, cells=cells)
    return None


def _all_poses(length: int) -> list[tuple[Cell, ...]]:
    poses: list[tuple[Cell, ...]] = []
    for row in range(BOARD_SIZE):
        for col in range(BOARD_SIZE - length + 1):
            poses.append(tuple(Cell(col + i, row) for i in range(length)))
    for col in range(BOARD_SIZE):
        for row in range(BOARD_SIZE - length + 1):
            poses.append(tuple(Cell(col, row + i) for i in range(length)))
    return poses


def all_poses(length: int) -> list[tuple[Cell, ...]]:
    return _all_poses(length)


def _is_straight(cells: Sequence[Cell]) -> bool:
    if len(cells) <= 1:
        return True
    cols = {c.col for c in cells}
    rows = {c.row for c in cells}
    if len(cols) == 1:
        ys = sorted(c.row for c in cells)
        return ys == list(range(ys[0], ys[0] + len(ys)))
    if len(rows) == 1:
        xs = sorted(c.col for c in cells)
        return xs == list(range(xs[0], xs[0] + len(xs)))
    return False


def _coerce_ship(spec: dict[str, object] | Ship) -> Ship:
    if isinstance(spec, Ship):
        return spec
    name = spec.get("name")
    raw_cells = spec.get("cells")
    if not isinstance(name, str) or not isinstance(raw_cells, (list, tuple)):
        raise PlacementError("ship needs name and cells")
    parsed: list[Cell] = []
    for item in raw_cells:
        if isinstance(item, Cell):
            parsed.append(item)
        elif isinstance(item, str):
            try:
                parsed.append(parse_cell(item))
            except CellError as exc:
                raise PlacementError(str(exc)) from exc
        else:
            raise PlacementError(f"bad cell in {name}: {item!r}")
    return Ship(name=name, cells=tuple(parsed))
