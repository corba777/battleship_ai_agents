from __future__ import annotations

from salvo.agents.observe import Observation, leaked_foe_cells, render_observation
from salvo.agents.player import LlmPlayer
from salvo.referee.board import Board
from tests.test_board import FIXTURE_LEFT, FIXTURE_RIGHT


def test_left_observation_does_not_name_right_only_cells() -> None:
    left = Board.from_ships(FIXTURE_LEFT)
    right = Board.from_ships(FIXTURE_RIGHT)
    obs = Observation(side="left", board=left)
    text = render_observation(obs)
    assert leaked_foe_cells(text, left, right, []) == set()
    assert "J6" not in text
    assert "A10" not in text
    assert "Your fleet:" in text
    assert "A1" in text


def test_wrong_board_would_leak() -> None:
    left = Board.from_ships(FIXTURE_LEFT)
    right = Board.from_ships(FIXTURE_RIGHT)
    poisoned = Observation(side="left", board=right)
    text = render_observation(poisoned)
    leaked = leaked_foe_cells(text, left, right, [])
    assert "J6" in leaked


def test_llm_user_payload_does_not_leak() -> None:
    left = Board.from_ships(FIXTURE_LEFT)
    right = Board.from_ships(FIXTURE_RIGHT)
    captured: dict[str, str] = {}

    def complete(system: str, user: str) -> str:
        captured["system"] = system
        captured["user"] = user
        return (
            '{"shot":"C7","belief":[{"cell":"C7","p":0.5},{"cell":"C8","p":0.3},'
            '{"cell":"D7","p":0.1}],"say":"Opening on C7."}'
        )

    player = LlmPlayer("gemini", "methodical", complete=complete)
    obs = Observation(side="left", board=left)
    player.act(obs)
    assert leaked_foe_cells(captured["user"], left, right, []) == set()
    assert "You cannot see the enemy placement" in captured["system"]


def test_reprompt_includes_error_not_foe_board() -> None:
    left = Board.from_ships(FIXTURE_LEFT)
    right = Board.from_ships(FIXTURE_RIGHT)
    users: list[str] = []

    def complete(system: str, user: str) -> str:
        del system
        users.append(user)
        return "5E"

    player = LlmPlayer("claude", "intuitive", complete=complete)
    obs = Observation(side="left", board=left)
    player.act(obs, error="illegal cell: '5E'")
    assert users[0].count("illegal cell") == 1
    assert leaked_foe_cells(users[0], left, right, []) == set()
