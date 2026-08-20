from __future__ import annotations

import random

import pytest

from salvo.referee.board import (
    Board,
    Cell,
    CellError,
    PlacementError,
    format_cell,
    parse_cell,
    random_placement,
    validate_placement,
)

# Same fleets as the client fixture — must remain legal under the no-touch rule.
FIXTURE_LEFT = [
    {"name": "carrier", "cells": ["A1", "A2", "A3", "A4", "A5"]},
    {"name": "battleship", "cells": ["C1", "C2", "C3", "C4"]},
    {"name": "cruiser", "cells": ["E1", "E2", "E3"]},
    {"name": "submarine", "cells": ["G1", "G2", "G3"]},
    {"name": "destroyer", "cells": ["I1", "I2"]},
]

FIXTURE_RIGHT = [
    {"name": "carrier", "cells": ["J6", "J7", "J8", "J9", "J10"]},
    {"name": "battleship", "cells": ["A10", "B10", "C10", "D10"]},
    {"name": "cruiser", "cells": ["F5", "F6", "F7"]},
    {"name": "submarine", "cells": ["A6", "A7", "A8"]},
    {"name": "destroyer", "cells": ["E1", "F1"]},
]


def test_parse_canonical_and_case() -> None:
    assert parse_cell("E5") == Cell(4, 4)
    assert parse_cell(" e5 ") == Cell(4, 4)
    assert parse_cell("J10") == Cell(9, 9)
    assert format_cell(Cell(0, 0)) == "A1"
    assert format_cell(parse_cell("A10")) == "A10"


def test_parse_rejects_transposition_and_junk() -> None:
    with pytest.raises(CellError):
        parse_cell("5E")
    with pytest.raises(CellError):
        parse_cell("(4,4)")
    with pytest.raises(CellError):
        parse_cell("K1")
    with pytest.raises(CellError):
        parse_cell("A0")
    with pytest.raises(CellError):
        parse_cell("A11")


def test_explicit_fixture_placements_are_legal() -> None:
    Board.from_ships(FIXTURE_LEFT)
    Board.from_ships(FIXTURE_RIGHT)


def test_explicit_rejects_orthogonal_touch() -> None:
    touching = [
        {"name": "carrier", "cells": ["A1", "A2", "A3", "A4", "A5"]},
        {"name": "battleship", "cells": ["B1", "B2", "B3", "B4"]},
        {"name": "cruiser", "cells": ["D1", "D2", "D3"]},
        {"name": "submarine", "cells": ["F1", "F2", "F3"]},
        {"name": "destroyer", "cells": ["H1", "H2"]},
    ]
    with pytest.raises(PlacementError, match="touch"):
        Board.from_ships(touching)


def test_explicit_rejects_diagonal_touch() -> None:
    diagonal = [
        {"name": "carrier", "cells": ["A1", "A2", "A3", "A4", "A5"]},
        {"name": "battleship", "cells": ["B7", "C7", "D7", "E7"]},
        {"name": "cruiser", "cells": ["B6", "C6", "D6"]},
        {"name": "submarine", "cells": ["G1", "G2", "G3"]},
        {"name": "destroyer", "cells": ["I1", "I2"]},
    ]
    # B6 is diagonally adjacent to A5.
    diagonal[2] = {"name": "cruiser", "cells": ["B6", "C6", "D6"]}
    with pytest.raises(PlacementError, match="touch"):
        Board.from_ships(
            [
                {"name": "carrier", "cells": ["A1", "A2", "A3", "A4", "A5"]},
                {"name": "battleship", "cells": ["C8", "D8", "E8", "F8"]},
                {"name": "cruiser", "cells": ["B6", "C6", "D6"]},
                {"name": "submarine", "cells": ["H1", "H2", "H3"]},
                {"name": "destroyer", "cells": ["J1", "J2"]},
            ]
        )


def test_one_cell_gap_is_legal() -> None:
    Board.from_ships(FIXTURE_LEFT)


def test_overlap_rejected() -> None:
    ships = [
        {"name": "carrier", "cells": ["A1", "A2", "A3", "A4", "A5"]},
        {"name": "battleship", "cells": ["A5", "A6", "A7", "A8"]},
        {"name": "cruiser", "cells": ["C1", "C2", "C3"]},
        {"name": "submarine", "cells": ["E1", "E2", "E3"]},
        {"name": "destroyer", "cells": ["G1", "G2"]},
    ]
    with pytest.raises(PlacementError, match="overlap"):
        Board.from_ships(ships)


def test_off_board_and_bent_rejected() -> None:
    with pytest.raises(PlacementError):
        Board.from_ships(
            [
                {"name": "carrier", "cells": ["A8", "A9", "A10", "A11", "A12"]},
                {"name": "battleship", "cells": ["C1", "C2", "C3", "C4"]},
                {"name": "cruiser", "cells": ["E1", "E2", "E3"]},
                {"name": "submarine", "cells": ["G1", "G2", "G3"]},
                {"name": "destroyer", "cells": ["I1", "I2"]},
            ]
        )
    with pytest.raises(PlacementError, match="straight"):
        Board.from_ships(
            [
                {"name": "carrier", "cells": ["A1", "A2", "A3", "B3", "C3"]},
                {"name": "battleship", "cells": ["E1", "E2", "E3", "E4"]},
                {"name": "cruiser", "cells": ["G1", "G2", "G3"]},
                {"name": "submarine", "cells": ["I1", "I2", "I3"]},
                {"name": "destroyer", "cells": ["A8", "A9"]},
            ]
        )


def test_wrong_fleet_rejected() -> None:
    with pytest.raises(PlacementError, match="fleet"):
        Board.from_ships(
            [
                {"name": "carrier", "cells": ["A1", "A2", "A3", "A4", "A5"]},
                {"name": "battleship", "cells": ["C1", "C2", "C3", "C4"]},
            ]
        )


def test_random_placement_is_legal_and_seeded() -> None:
    a = random_placement(random.Random(42))
    b = random_placement(random.Random(42))
    c = random_placement(random.Random(43))
    validate_placement(a)
    assert a == b
    assert a != c
    for seed in range(20):
        Board.random(random.Random(seed))


def test_fire_miss_hit_sink_repeat() -> None:
    board = Board.from_ships(FIXTURE_RIGHT)
    miss = board.fire("E5")
    assert miss.result == "miss"
    assert miss.sunk is None

    first = board.fire("E1")
    assert first.result == "hit"
    assert first.sunk is None

    repeat = board.fire("E1")
    assert repeat.result == "repeat"
    assert repeat.sunk is None

    sunk = board.fire("F1")
    assert sunk.result == "hit"
    assert sunk.sunk is not None
    assert sunk.sunk.name == "destroyer"
    assert [format_cell(c) for c in sunk.sunk.cells] == ["E1", "F1"]

    again = board.fire("F1")
    assert again.result == "repeat"
    assert again.sunk is None


def test_all_sunk() -> None:
    board = Board.from_ships(
        [
            {"name": "carrier", "cells": ["A1", "A2", "A3", "A4", "A5"]},
            {"name": "battleship", "cells": ["C1", "C2", "C3", "C4"]},
            {"name": "cruiser", "cells": ["E1", "E2", "E3"]},
            {"name": "submarine", "cells": ["G1", "G2", "G3"]},
            {"name": "destroyer", "cells": ["I1", "I2"]},
        ]
    )
    assert not board.all_sunk()
    for ship in FIXTURE_LEFT:
        for cell in ship["cells"]:
            board.fire(cell)
    assert board.all_sunk()
