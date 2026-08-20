from __future__ import annotations

from fastapi.testclient import TestClient

from salvo.server import app as app_mod

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


def test_live_bot_match_streams(monkeypatch, tmp_path) -> None:
    logs = tmp_path / "logs"
    logs.mkdir()
    monkeypatch.setattr(app_mod, "LOGS", logs)
    client = TestClient(app_mod.app)
    with client.websocket_connect("/ws?left=parity&right=random&seed=42") as ws:
        first = ws.receive_json()
        assert first["type"] == "match_start"
        assert first["seed"] == 42
        last = first
        while last["type"] != "match_end":
            last = ws.receive_json()
        assert last["winner"] in ("left", "right")
    written = list(logs.glob("*.jsonl"))
    assert written


def test_live_abort_stops_match(monkeypatch, tmp_path) -> None:
    import time

    from salvo.referee.events import MatchAbort, MatchStart, SideStats

    logs = tmp_path / "logs"
    logs.mkdir()
    monkeypatch.setattr(app_mod, "LOGS", logs)

    def fake_play(left, right, seed, stop=None, **_kwargs):
        yield MatchStart(
            seed=seed,
            players={"left": left.meta, "right": right.meta},
            placements={"left": [], "right": []},
        )
        while stop is None or not stop.is_set():
            time.sleep(0.02)
        yield MatchAbort(
            turns=0,
            stats={"left": SideStats(), "right": SideStats()},
        )

    monkeypatch.setattr(app_mod, "play_match", fake_play)
    client = TestClient(app_mod.app)
    with client.websocket_connect("/ws?left=parity&right=random&seed=1") as ws:
        first = ws.receive_json()
        assert first["type"] == "match_start"
        ws.send_json({"type": "abort"})
        last = ws.receive_json()
        assert last["type"] == "match_abort"
        assert last["reason"] == "stopped"
    written = list(logs.glob("*.jsonl"))
    assert written


def test_human_waits_for_start_and_accepts_shot(monkeypatch, tmp_path) -> None:
    logs = tmp_path / "logs"
    logs.mkdir()
    monkeypatch.setattr(app_mod, "LOGS", logs)
    client = TestClient(app_mod.app)
    with client.websocket_connect("/ws?left=human&right=random&seed=1") as ws:
        preview = ws.receive_json()
        assert preview["type"] == "board_preview"
        assert preview["placements"]["right"]
        assert "left" not in preview["placements"]
        ws.send_json({"type": "start", "placements": {"left": []}})
        err = ws.receive_json()
        assert err["type"] == "placement_error"
        ws.send_json(
            {
                "type": "start",
                "placements": {"left": FIXTURE_LEFT, "right": FIXTURE_RIGHT},
            }
        )
        first = ws.receive_json()
        assert first["type"] == "match_start"
        assert first["players"]["left"]["kind"] == "human"
        assert first["placements"]["left"][0]["cells"] == FIXTURE_LEFT[0]["cells"]
        assert first["placements"]["right"] == preview["placements"]["right"]
        turn = ws.receive_json()
        assert turn["type"] == "turn"
        assert turn["side"] == "left"
        ws.send_json({"type": "human_shot", "cell": "J6", "side": "left"})
        thinking = ws.receive_json()
        assert thinking["type"] == "thinking"
        assert thinking["say"] == "Firing at J6."
        shot = ws.receive_json()
        assert shot["type"] == "shot_result"
        assert shot["cell"] == "J6"
        ws.send_json({"type": "abort"})
        last = shot
        while last["type"] not in {"match_abort", "match_end"}:
            last = ws.receive_json()
        assert last["type"] == "match_abort"


def test_human_random_start_lets_referee_place_both(monkeypatch, tmp_path) -> None:
    import random

    from salvo.referee.board import Board

    logs = tmp_path / "logs"
    logs.mkdir()
    monkeypatch.setattr(app_mod, "LOGS", logs)
    rng = random.Random(9)
    expected_right = Board.random(rng).placement_dicts()
    expected_left = Board.random(rng).placement_dicts()
    client = TestClient(app_mod.app)
    with client.websocket_connect("/ws?left=human&right=parity&seed=9") as ws:
        preview = ws.receive_json()
        assert preview["type"] == "board_preview"
        assert preview["placements"]["right"] == expected_right
        ws.send_json({"type": "start"})
        first = ws.receive_json()
        assert first["type"] == "match_start"
        assert first["placements"]["left"] == expected_left
        assert first["placements"]["right"] == expected_right
        ws.send_json({"type": "abort"})
        last = first
        while last["type"] not in {"match_abort", "match_end"}:
            last = ws.receive_json()