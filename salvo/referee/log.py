from __future__ import annotations

import json
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Any

from salvo.referee.events import MatchEvent


def write_log(path: Path, events: Iterable[MatchEvent]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for event in events:
            fh.write(json.dumps(event.as_dict(), ensure_ascii=False) + "\n")


def read_log(path: Path) -> Iterator[dict[str, Any]]:
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            if obj.get("type") == "header":
                yield {
                    "type": "match_start",
                    "seed": obj["seed"],
                    "players": obj["players"],
                    "placements": obj["placements"],
                    **(
                        {"prompt_hashes": obj["prompt_hashes"]}
                        if obj.get("prompt_hashes")
                        else {}
                    ),
                }
                continue
            yield obj
