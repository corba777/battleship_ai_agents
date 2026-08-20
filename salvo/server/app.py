from __future__ import annotations

import asyncio
import json
import queue
import random
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from salvo.agents.catalog import catalog_payload
from salvo.agents.factory import make_player
from salvo.agents.speech import is_speech_profile, pick_speech
from salvo.referee.board import Board, PlacementError
from salvo.referee.log import read_log, write_log
from salvo.referee.match import play_match
from salvo.server.rooms import join_room

ROOT = Path(__file__).resolve().parents[2]
LOGS = ROOT / "logs"

app = FastAPI(title="salvo")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:8080",
        "http://127.0.0.1:8080",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/catalog")
def catalog() -> dict:
    return catalog_payload()


@app.get("/logs")
def list_logs() -> dict[str, list[str]]:
    LOGS.mkdir(parents=True, exist_ok=True)
    names = sorted(p.name for p in LOGS.glob("*.jsonl"))
    return {"logs": names}


@app.websocket("/ws")
async def live(
    ws: WebSocket,
    left: str = "parity",
    right: str = "random",
    seed: int = 42,
    persona_left: str = "methodical",
    persona_right: str = "intuitive",
    speech_left: str = "standard",
    speech_right: str = "standard",
    model_left: str | None = None,
    model_right: str | None = None,
    provider_left: str | None = None,
    provider_right: str | None = None,
    room: str | None = None,
    seat: str | None = None,
) -> None:
    if room:
        await join_room(ws, room=room, seat=seat, seed=seed)
        return
    await ws.accept()
    if not is_speech_profile(speech_left) or not is_speech_profile(speech_right):
        await ws.close(code=1011, reason="unknown speech profile")
        return

    stop = threading.Event()
    inboxes: dict[str, queue.Queue[str | None]] = {
        "left": queue.Queue(),
        "right": queue.Queue(),
    }
    try:
        left_player = make_player(
            left,
            random.Random(seed + 1),
            persona=persona_left,
            speech=pick_speech(speech_left),
            model=model_left,
            provider=provider_left,
            side="left",
            inbox=inboxes["left"],
            stop=stop,
        )
        right_player = make_player(
            right,
            random.Random(seed + 2),
            persona=persona_right,
            speech=pick_speech(speech_right),
            model=model_right,
            provider=provider_right,
            side="right",
            inbox=inboxes["right"],
            stop=stop,
        )
    except Exception as exc:
        await ws.close(code=1011, reason=str(exc)[:120])
        return

    left_ships: list[dict[str, object]] | None = None
    right_ships: list[dict[str, object]] | None = None
    human_left = left_player.meta.kind == "human"
    human_right = right_player.meta.kind == "human"
    if human_left or human_right:
        rng = random.Random(seed)
        if not human_left:
            left_ships = Board.random(rng).placement_dicts()
        if not human_right:
            right_ships = Board.random(rng).placement_dicts()
        preview = {
            side: ships
            for side, ships in (("left", left_ships), ("right", right_ships))
            if ships is not None
        }
        if preview:
            await ws.send_json({"type": "board_preview", "placements": preview})
        started = await _await_start(ws, stop, human_left=human_left, human_right=human_right)
        if started is None:
            return
        got_left, got_right = started
        if human_left:
            left_ships = got_left if got_left is not None else Board.random(rng).placement_dicts()
        if human_right:
            right_ships = got_right if got_right is not None else Board.random(rng).placement_dicts()

    outgoing: queue.Queue[object] = queue.Queue()
    recorded: list[object] = []

    def run() -> None:
        try:
            for event in play_match(
                left_player,
                right_player,
                seed,
                left_ships=left_ships,
                right_ships=right_ships,
                stop=stop,
            ):
                recorded.append(event)
                outgoing.put(event)
        except Exception as exc:
            outgoing.put(exc)
        finally:
            outgoing.put(None)

    threading.Thread(target=run, daemon=True).start()

    async def listen() -> None:
        try:
            while True:
                message = await ws.receive()
                if message["type"] == "websocket.disconnect":
                    _halt(stop, inboxes)
                    return
                payload = _decode(message.get("text"))
                if payload.get("type") == "abort":
                    _halt(stop, inboxes)
                elif payload.get("type") == "human_shot":
                    _route_shot(payload, left_player, right_player, inboxes)
        except WebSocketDisconnect:
            _halt(stop, inboxes)

    listener = asyncio.create_task(listen())
    try:
        while True:
            item = await asyncio.to_thread(outgoing.get)
            if item is None:
                break
            if isinstance(item, Exception):
                await ws.close(code=1011, reason=str(item)[:120])
                break
            await ws.send_json(item.as_dict())  # type: ignore[union-attr]
    except WebSocketDisconnect:
        _halt(stop, inboxes)
    finally:
        _halt(stop, inboxes)
        listener.cancel()
        if recorded:
            LOGS.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
            path = LOGS / f"{stamp}-{left}-{right}-{seed}.jsonl"
            write_log(path, recorded)  # type: ignore[arg-type]


@app.websocket("/ws/replay/{name}")
async def replay(ws: WebSocket, name: str) -> None:
    path = _safe_log(name)
    await ws.accept()
    try:
        for event in read_log(path):
            await ws.send_json(event)
    except WebSocketDisconnect:
        return


def _halt(stop: threading.Event, inboxes: dict[str, queue.Queue[str | None]]) -> None:
    stop.set()
    for box in inboxes.values():
        box.put(None)


def _decode(raw: object) -> dict[str, Any]:
    if not isinstance(raw, str) or not raw:
        return {}
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _route_shot(
    payload: dict[str, Any],
    left_player: object,
    right_player: object,
    inboxes: dict[str, queue.Queue[str | None]],
) -> None:
    cell = payload.get("cell")
    if not isinstance(cell, str):
        return
    side = payload.get("side")
    humans = {
        name: player
        for name, player in (("left", left_player), ("right", right_player))
        if getattr(getattr(player, "meta", None), "kind", None) == "human"
    }
    if side in humans:
        inboxes[side].put(cell)
        return
    if len(humans) == 1:
        only = next(iter(humans))
        inboxes[only].put(cell)


async def _await_start(
    ws: WebSocket,
    stop: threading.Event,
    *,
    human_left: bool,
    human_right: bool,
) -> tuple[list[dict[str, object]] | None, list[dict[str, object]] | None] | None:
    try:
        while not stop.is_set():
            message = await ws.receive()
            if message["type"] == "websocket.disconnect":
                stop.set()
                return None
            payload = _decode(message.get("text"))
            kind = payload.get("type")
            if kind == "abort":
                stop.set()
                return None
            if kind != "start":
                continue
            raw = payload.get("placements", {})
            if raw is None:
                raw = {}
            if not isinstance(raw, dict):
                await ws.send_json({"type": "placement_error", "reason": "placements must be an object"})
                continue
            try:
                left = _human_fleet(raw.get("left")) if human_left else None
                right = _human_fleet(raw.get("right")) if human_right else None
            except (PlacementError, TypeError, ValueError) as exc:
                await ws.send_json({"type": "placement_error", "reason": str(exc)})
                continue
            return left, right
    except WebSocketDisconnect:
        stop.set()
    return None


def _human_fleet(raw: object) -> list[dict[str, object]] | None:
    """None / 'random' → referee RNG. A ship list is validated and kept."""
    if raw is None or raw == "random":
        return None
    ships = _as_ships(raw)
    Board.from_ships(ships)
    return ships


def _as_ships(raw: object) -> list[dict[str, object]]:
    if not isinstance(raw, list):
        raise PlacementError("each side needs a ship list")
    out: list[dict[str, object]] = []
    for item in raw:
        if not isinstance(item, dict):
            raise PlacementError("ship must be an object")
        out.append(item)
    return out


def _safe_log(name: str) -> Path:
    if Path(name).name != name or not name.endswith(".jsonl"):
        raise HTTPException(status_code=400, detail="invalid log name")
    path = (LOGS / name).resolve()
    if not path.is_relative_to(LOGS.resolve()) or not path.is_file():
        raise HTTPException(status_code=404, detail="log not found")
    return path
