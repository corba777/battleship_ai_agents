from __future__ import annotations

import queue
import random
import threading
import time

import pytest

from salvo.agents.bots import RandomBot
from salvo.agents.factory import make_player
from salvo.agents.human import HumanPlayer
from salvo.referee.events import MatchAbort, MatchStart, PlayerMeta, ShotResult, Turn
from salvo.referee.match import MatchStopped, play_match

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


def test_human_needs_inbox() -> None:
    with pytest.raises(ValueError, match="inbox"):
        make_player("human", random.Random(0), side="left")


def test_human_act_from_inbox() -> None:
    inbox: queue.Queue[str | None] = queue.Queue()
    player = make_player("human", random.Random(0), side="left", inbox=inbox)
    assert isinstance(player, HumanPlayer)
    assert player.meta.kind == "human"
    inbox.put(" e5 ")
    action = player.act(None)  # type: ignore[arg-type]
    assert action["shot"] == "E5"
    assert action["say"] == "Firing at E5."
    belief = action["belief"]
    assert isinstance(belief, list) and len(belief) == 3
    assert belief[0] == {"cell": "E5", "p": 1.0}


def test_human_skips_illegal_cells_then_fires() -> None:
    inbox: queue.Queue[str | None] = queue.Queue()
    player = HumanPlayer("left", inbox)
    inbox.put("5E")
    inbox.put("B7")
    action = player.act(None)  # type: ignore[arg-type]
    assert action["shot"] == "B7"


def test_human_stop_raises() -> None:
    inbox: queue.Queue[str | None] = queue.Queue()
    stop = threading.Event()
    player = HumanPlayer("left", inbox, stop)
    stop.set()
    with pytest.raises(MatchStopped):
        player.act(None)  # type: ignore[arg-type]


def test_human_vs_bot_uses_explicit_fleets() -> None:
    inbox: queue.Queue[str | None] = queue.Queue()
    stop = threading.Event()
    human = HumanPlayer("left", inbox, stop)
    bot = RandomBot(random.Random(2), PlayerMeta(name="random", kind="bot", model="random"))
    events: list[object] = []

    def run() -> None:
        events.extend(
            play_match(
                human,
                bot,
                seed=1,
                left_ships=FIXTURE_LEFT,
                right_ships=FIXTURE_RIGHT,
                stop=stop,
            )
        )

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    deadline = time.time() + 2
    while time.time() < deadline and not any(isinstance(e, Turn) for e in events):
        time.sleep(0.02)
    inbox.put("J6")
    deadline = time.time() + 2
    while time.time() < deadline and not any(isinstance(e, ShotResult) for e in events):
        time.sleep(0.02)
    stop.set()
    inbox.put(None)
    thread.join(timeout=2)
    assert isinstance(events[0], MatchStart)
    assert events[0].placements["left"][0]["cells"] == FIXTURE_LEFT[0]["cells"]
    assert events[0].placements["right"][0]["cells"] == FIXTURE_RIGHT[0]["cells"]
    shots = [e for e in events if isinstance(e, ShotResult)]
    assert shots and shots[0].cell == "J6"
    assert isinstance(events[-1], MatchAbort)
