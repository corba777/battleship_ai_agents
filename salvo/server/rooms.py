from __future__ import annotations

import asyncio
import json
import queue
import random
import re
import threading
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect

from salvo.agents.factory import make_player
from salvo.referee.board import Board, PlacementError
from salvo.referee.log import write_log
from salvo.referee.match import play_match

_CODE = re.compile(r"^[A-HJ-NP-Z2-9]{4}$")


@dataclass
class Room:
    code: str
    seed: int
    stop: threading.Event = field(default_factory=threading.Event)
    inboxes: dict[str, queue.Queue[str | None]] = field(
        default_factory=lambda: {"left": queue.Queue(), "right": queue.Queue()}
    )
    sockets: dict[str, WebSocket | None] = field(
        default_factory=lambda: {"left": None, "right": None}
    )
    ships: dict[str, list[dict[str, object]] | None] = field(
        default_factory=lambda: {"left": None, "right": None}
    )
    placed: dict[str, bool] = field(default_factory=lambda: {"left": False, "right": False})
    feeds: dict[str, queue.Queue[object]] = field(default_factory=dict)
    started: bool = False
    recorded: list[object] = field(default_factory=list)
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    left_player: Any = None
    right_player: Any = None


ROOMS: dict[str, Room] = {}
_ROOMS = asyncio.Lock()


def valid_room(code: str) -> bool:
    return bool(_CODE.fullmatch(code.upper()))


async def join_room(ws: WebSocket, *, room: str, seat: str | None, seed: int) -> None:
    from salvo.server import app as app_mod

    code = room.strip().upper()
    if not valid_room(code):
        await ws.accept()
        await ws.close(code=1011, reason="bad room code")
        return
    if seat not in {"left", "right"}:
        await ws.accept()
        await ws.close(code=1011, reason="seat must be left or right")
        return

    await ws.accept()
    async with _ROOMS:
        held = ROOMS.get(code)
        if held is None:
            held = _new_room(code, seed)
            ROOMS[code] = held
        room_state = held

    async with room_state.lock:
        if room_state.sockets[seat] is not None:
            await ws.close(code=1011, reason="seat taken")
            return
        room_state.sockets[seat] = ws
        feed: queue.Queue[object] = queue.Queue()
        room_state.feeds[seat] = feed

    other = "right" if seat == "left" else "left"
    await ws.send_json(
        {
            "type": "room_hello",
            "room": code,
            "seat": seat,
            "waiting_for": other if room_state.sockets[other] is None else None,
        }
    )
    if room_state.sockets[other] is not None:
        await _notify(room_state, other, {"type": "room_peer", "seat": seat})

    async def listen() -> None:
        try:
            while True:
                message = await ws.receive()
                if message["type"] == "websocket.disconnect":
                    _halt(room_state)
                    return
                payload = _decode(message.get("text"))
                kind = payload.get("type")
                if kind == "abort":
                    _stop_match(room_state)
                    if not room_state.started:
                        _broadcast(room_state, None)
                        return
                elif kind == "start" and not room_state.started:
                    await _take_placement(ws, room_state, seat, payload)
                elif kind == "human_shot" and room_state.started:
                    cell = payload.get("cell")
                    if isinstance(cell, str) and payload.get("side", seat) == seat:
                        room_state.inboxes[seat].put(cell)
        except WebSocketDisconnect:
            _halt(room_state)
            return

    listener = asyncio.create_task(listen())
    try:
        while True:
            item = await asyncio.to_thread(feed.get)
            if item is None:
                break
            if isinstance(item, Exception):
                await ws.close(code=1011, reason=str(item)[:120])
                break
            if isinstance(item, dict):
                await ws.send_json(item)
            else:
                await ws.send_json(item.as_dict())  # type: ignore[union-attr]
    except WebSocketDisconnect:
        pass
    finally:
        _halt(room_state)
        listener.cancel()
        async with room_state.lock:
            if room_state.sockets.get(seat) is ws:
                room_state.sockets[seat] = None
            room_state.feeds.pop(seat, None)
            empty = room_state.sockets["left"] is None and room_state.sockets["right"] is None
        if empty:
            async with _ROOMS:
                if ROOMS.get(code) is room_state:
                    ROOMS.pop(code, None)
            if room_state.recorded:
                app_mod.LOGS.mkdir(parents=True, exist_ok=True)
                stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
                path = app_mod.LOGS / f"{stamp}-human-human-{room_state.seed}.jsonl"
                write_log(path, room_state.recorded)  # type: ignore[arg-type]


def _new_room(code: str, seed: int) -> Room:
    room = Room(code=code, seed=seed)
    room.left_player = make_player(
        "human", random.Random(seed + 1), side="left", inbox=room.inboxes["left"], stop=room.stop
    )
    room.right_player = make_player(
        "human", random.Random(seed + 2), side="right", inbox=room.inboxes["right"], stop=room.stop
    )
    return room


async def _take_placement(
    _ws: WebSocket, room: Room, seat: str, payload: dict[str, Any]
) -> None:
    raw = payload.get("placements", {})
    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        _notify_now(room, seat, {"type": "placement_error", "reason": "placements must be an object"})
        return
    try:
        fleet = _human_fleet(raw.get(seat))
    except (PlacementError, TypeError, ValueError) as exc:
        _notify_now(room, seat, {"type": "placement_error", "reason": str(exc)})
        return
    if fleet is None:
        fleet = Board.random(random.Random(room.seed + (1 if seat == "left" else 2))).placement_dicts()
    async with room.lock:
        room.ships[seat] = fleet
        room.placed[seat] = True
        other = "right" if seat == "left" else "left"
        waiting = not room.placed[other]
        should_start = room.placed["left"] and room.placed["right"] and not room.started
        if should_start:
            room.started = True
    if waiting:
        _notify_now(room, seat, {"type": "room_waiting", "waiting_for": other})
        return
    if should_start:
        threading.Thread(target=_run_match, args=(room,), daemon=True).start()


def _run_match(room: Room) -> None:
    try:
        for event in play_match(
            room.left_player,
            room.right_player,
            room.seed,
            left_ships=room.ships["left"],
            right_ships=room.ships["right"],
            stop=room.stop,
        ):
            room.recorded.append(event)
            _broadcast(room, event)
    except Exception as exc:
        _broadcast(room, exc)
    finally:
        _broadcast(room, None)


def _broadcast(room: Room, item: object) -> None:
    for feed in list(room.feeds.values()):
        feed.put(item)


def _stop_match(room: Room) -> None:
    room.stop.set()
    for box in room.inboxes.values():
        box.put(None)


def _halt(room: Room) -> None:
    _stop_match(room)
    _broadcast(room, None)


def _notify_now(room: Room, seat: str, payload: dict[str, Any]) -> None:
    feed = room.feeds.get(seat)
    if feed is not None:
        feed.put(payload)


async def _notify(room: Room, seat: str, payload: dict[str, Any]) -> None:
    _notify_now(room, seat, payload)


def _human_fleet(raw: object) -> list[dict[str, object]] | None:
    if raw is None or raw == "random":
        return None
    if not isinstance(raw, list):
        raise PlacementError("each side needs a ship list")
    ships: list[dict[str, object]] = []
    for item in raw:
        if not isinstance(item, dict):
            raise PlacementError("ship must be an object")
        ships.append(item)
    Board.from_ships(ships)
    return ships


def _decode(raw: object) -> dict[str, Any]:
    if not isinstance(raw, str) or not raw:
        return {}
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}
