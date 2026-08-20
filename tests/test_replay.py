from __future__ import annotations

import random

from fastapi.testclient import TestClient

from salvo.agents.bots import ParityBot, RandomBot
from salvo.referee.events import PlayerMeta
from salvo.referee.log import write_log
from salvo.referee.match import play_match
from salvo.server import app as app_mod


def test_replay_websocket(tmp_path, monkeypatch) -> None:
    logs = tmp_path / "logs"
    logs.mkdir()
    monkeypatch.setattr(app_mod, "LOGS", logs)
    left = ParityBot(random.Random(1), PlayerMeta(name="methodical", kind="bot", model="parity"))
    right = RandomBot(random.Random(2), PlayerMeta(name="random", kind="bot", model="random"))
    path = logs / "seed42.jsonl"
    write_log(path, play_match(left, right, seed=42))

    client = TestClient(app_mod.app)
    listed = client.get("/logs")
    assert "seed42.jsonl" in listed.json()["logs"]

    with client.websocket_connect("/ws/replay/seed42.jsonl") as ws:
        first = ws.receive_json()
        assert first["type"] == "match_start"
        assert "placements" in first
        last = first
        while True:
            try:
                last = ws.receive_json()
            except Exception:
                break
            if last["type"] == "match_end":
                break
        assert last["type"] == "match_end"
        assert last["winner"] in ("left", "right")
