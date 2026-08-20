from __future__ import annotations

import random

import pytest
from fastapi.testclient import TestClient

from salvo.agents.factory import make_player
from salvo.agents.observe import Observation, leaked_foe_cells
from salvo.agents.player import LlmPlayer
from salvo.agents.speech import compose_system, load_speech, pick_speech
from salvo.referee.board import Board
from salvo.server import app as app_mod
from tests.test_board import FIXTURE_LEFT, FIXTURE_RIGHT


def test_pick_speech_defaults_and_rejects() -> None:
    assert pick_speech(None) == "standard"
    assert pick_speech("") == "standard"
    assert pick_speech("raw-ru") == "raw-ru"
    with pytest.raises(ValueError, match="unknown speech"):
        pick_speech("pohuy")


def test_raw_ru_overlay_is_russian_and_stays_out_of_observation() -> None:
    overlay = load_speech("raw-ru")
    assert "ГОВОРИ ПО-РУССКИ" in overlay
    assert "say" in overlay
    system = compose_system("persona body", "raw-ru")
    assert system.startswith("persona body")
    assert "ГОВОРИ ПО-РУССКИ" in system
    assert compose_system("persona body", "standard") == "persona body"


def test_independent_speech_changes_prompt_hash() -> None:
    std = LlmPlayer("gemini", "methodical", speech="standard", complete=lambda s, u: "{}")
    ru = LlmPlayer("gemini", "methodical", speech="raw-ru", complete=lambda s, u: "{}")
    assert std.prompt_hash != ru.prompt_hash
    assert std.meta.speech == "standard"
    assert ru.meta.speech == "raw-ru"
    assert "ГОВОРИ ПО-РУССКИ" in ru.system
    assert "ГОВОРИ ПО-РУССКИ" not in std.system


def test_raw_ru_system_does_not_leak_foe_board() -> None:
    left = Board.from_ships(FIXTURE_LEFT)
    right = Board.from_ships(FIXTURE_RIGHT)
    captured: dict[str, str] = {}

    def complete(system: str, user: str) -> str:
        captured["system"] = system
        captured["user"] = user
        return (
            '{"shot":"C7","belief":[{"cell":"C7","p":0.5},{"cell":"C8","p":0.3},'
            '{"cell":"D7","p":0.1}],"say":"Открываю C7."}'
        )

    player = LlmPlayer("gemini", "methodical", complete=complete, speech="raw-ru")
    player.act(Observation(side="left", board=left))
    assert leaked_foe_cells(captured["user"], left, right, []) == set()
    assert "J6" not in captured["system"]


def test_factory_speech_per_side() -> None:
    left = make_player("gemini", random.Random(0), speech="standard", side="left")
    right = make_player("opus", random.Random(1), speech="raw-ru", side="right")
    assert left.meta.speech == "standard"
    assert right.meta.speech == "raw-ru"


def test_live_rejects_unknown_speech() -> None:
    client = TestClient(app_mod.app)
    with client.websocket_connect("/ws?left=parity&right=random&speech_left=raw-ru&speech_right=nope") as ws:
        with pytest.raises(Exception):
            ws.receive_json()
