from __future__ import annotations

import random

from salvo.agents.bots import OccupancyBot, occupancy_scores
from salvo.agents.contract import parse_action
from salvo.agents.factory import make_player
from salvo.agents.observe import Observation, ShotRecord
from salvo.referee.board import Board, parse_cell
from salvo.referee.events import MatchEnd, PlayerMeta, ShotResult
from salvo.referee.match import play_match


def test_factory_occupancy() -> None:
    player = make_player("occupancy", random.Random(0), side="left")
    assert isinstance(player, OccupancyBot)
    assert player.meta.kind == "bot"
    assert player.meta.model == "occupancy"


def test_occupancy_after_hit_fires_orthogonal() -> None:
    obs = Observation(side="left", board=Board.random(random.Random(1)))
    obs.history.append(ShotRecord(cell="E5", result="hit"))
    bot = OccupancyBot(random.Random(0))
    action = parse_action(bot.act(obs))
    assert action.shot in {"E4", "E6", "D5", "F5"}
    assert action.belief[0].cell == action.shot
    assert action.say.startswith("Highest occupancy")


def test_occupancy_never_reshoots_when_cells_remain() -> None:
    obs = Observation(side="left", board=Board.random(random.Random(2)))
    obs.history.append(ShotRecord(cell="A1", result="miss"))
    bot = OccupancyBot(random.Random(3))
    action = parse_action(bot.act(obs))
    assert action.shot != "A1"


def test_occupancy_target_scores_neighbors_of_hit() -> None:
    obs = Observation(side="left", board=Board.random(random.Random(4)))
    obs.history.append(ShotRecord(cell="E5", result="hit"))
    scores = occupancy_scores(obs)
    neighbor = max(
        (parse_cell(c) for c in ("E4", "E6", "D5", "F5")),
        key=lambda c: scores[c],
    )
    assert scores[neighbor] > scores[parse_cell("A10")]


def test_occupancy_vs_random_finishes() -> None:
    left = OccupancyBot(random.Random(1), PlayerMeta(name="occupancy", kind="bot", model="occupancy"))
    right = make_player("random", random.Random(2), side="right")
    events = list(play_match(left, right, seed=42))
    assert isinstance(events[-1], MatchEnd)
    shots = [e for e in events if isinstance(e, ShotResult)]
    assert shots
    assert events[-1].winner in ("left", "right")
