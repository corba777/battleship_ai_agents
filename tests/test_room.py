from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from salvo.server import app as app_mod
from salvo.server import rooms
from tests.test_live import FIXTURE_LEFT, FIXTURE_RIGHT


def _until(ws, typ: str, limit: int = 40) -> dict:
    last = {}
    for _ in range(limit):
        last = ws.receive_json()
        if last.get("type") == typ:
            return last
    raise AssertionError(f"no {typ} in {last}")


def test_human_room_starts_after_both_place(monkeypatch, tmp_path) -> None:
    logs = tmp_path / "logs"
    logs.mkdir()
    monkeypatch.setattr(app_mod, "LOGS", logs)
    rooms.ROOMS.clear()
    client = TestClient(app_mod.app)
    q = "left=human&right=human&room=AB23&seed=1"
    with client.websocket_connect(f"/ws?{q}&seat=left") as left:
        hello = left.receive_json()
        assert hello["type"] == "room_hello"
        assert hello["seat"] == "left"
        with client.websocket_connect(f"/ws?{q}&seat=right") as right:
            assert right.receive_json()["type"] == "room_hello"
            left.send_json({"type": "start", "placements": {"left": FIXTURE_LEFT}})
            waiting = _until(left, "room_waiting")
            assert waiting["waiting_for"] == "right"
            right.send_json({"type": "start", "placements": {"right": FIXTURE_RIGHT}})
            start_l = _until(left, "match_start")
            start_r = _until(right, "match_start")
            assert start_l["players"]["left"]["kind"] == "human"
            assert start_r["placements"]["left"][0]["cells"] == FIXTURE_LEFT[0]["cells"]
            assert start_r["placements"]["right"][0]["cells"] == FIXTURE_RIGHT[0]["cells"]
            left.send_json({"type": "human_shot", "cell": "J6", "side": "left"})
            thinking = _until(left, "thinking")
            assert thinking["say"] == "Firing at J6."
            shot = _until(left, "shot_result")
            assert shot["cell"] == "J6"
            right.send_json({"type": "abort"})
            last = shot
            while last["type"] not in {"match_abort", "match_end"}:
                last = left.receive_json()
            assert last["type"] == "match_abort"


def test_room_seat_taken(monkeypatch, tmp_path) -> None:
    logs = tmp_path / "logs"
    logs.mkdir()
    monkeypatch.setattr(app_mod, "LOGS", logs)
    rooms.ROOMS.clear()
    client = TestClient(app_mod.app)
    q = "/ws?left=human&right=human&room=CD45&seat=left&seed=1"
    with client.websocket_connect(q) as occupied:
        assert occupied.receive_json()["type"] == "room_hello"
        with client.websocket_connect(q) as stolen:
            with pytest.raises(WebSocketDisconnect):
                stolen.receive_json()
