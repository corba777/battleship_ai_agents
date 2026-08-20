from __future__ import annotations

import argparse
import os
import random
import sys
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import quote, urlencode

from salvo.agents.catalog import is_llm_name
from salvo.agents.factory import make_player
from salvo.agents.speech import SPEECH_PROFILES
from salvo.referee.log import write_log
from salvo.referee.match import play_match

ROOT = Path(__file__).resolve().parents[1]
LOGS = ROOT / "logs"
PERSONAS = ("methodical", "intuitive")


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] not in {"play", "replay", "live", "-h", "--help"}:
        argv = ["play", *argv]

    parser = argparse.ArgumentParser(prog="salvo")
    sub = parser.add_subparsers(dest="cmd", required=True)

    play = sub.add_parser("play", help="run a match to JSONL")
    _add_match_flags(play)

    live = sub.add_parser("live", help="print the client URL for a live match")
    _add_match_flags(live)
    live.add_argument("--pace", type=float, default=1.5)
    live.add_argument("--port", type=int, default=8000)

    replay = sub.add_parser("replay", help="print the client URL for a recorded match")
    replay.add_argument("log")
    replay.add_argument("--pace", type=float, default=1.5)
    replay.add_argument("--port", type=int, default=8000)

    args = parser.parse_args(argv)
    if args.cmd == "play":
        return cmd_play(args)
    if args.cmd == "live":
        return cmd_live(args)
    return cmd_replay(args.log, args.pace, args.port)


def _add_match_flags(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--left",
        default="parity",
        help="parity|random|human|gemini|claude|opus|openai|ollama or a model id",
    )
    parser.add_argument(
        "--right",
        default="random",
        help="parity|random|human|gemini|claude|opus or a model id",
    )
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--persona-left", default="methodical", choices=PERSONAS)
    parser.add_argument("--persona-right", default="intuitive", choices=PERSONAS)
    parser.add_argument("--speech-left", default="standard", choices=SPEECH_PROFILES)
    parser.add_argument("--speech-right", default="standard", choices=SPEECH_PROFILES)
    parser.add_argument("--model-left", default=None)
    parser.add_argument("--model-right", default=None)
    parser.add_argument(
        "--provider-left",
        default=None,
        choices=("vertex", "gemini", "anthropic", "openai", "ollama"),
        help="vertex | gemini API | anthropic API | openai | ollama. Default follows the model family.",
    )
    parser.add_argument(
        "--provider-right",
        default=None,
        choices=("vertex", "gemini", "anthropic", "openai", "ollama"),
    )


def cmd_play(args: argparse.Namespace) -> int:
    if args.left == "human" or args.right == "human":
        print("human players only work in the live client (WATCH LIVE).", file=sys.stderr)
        return 1
    left = make_player(
        args.left,
        random.Random(args.seed + 1),
        persona=args.persona_left,
        speech=args.speech_left,
        model=args.model_left,
        provider=args.provider_left,
        side="left",
    )
    right = make_player(
        args.right,
        random.Random(args.seed + 2),
        persona=args.persona_right,
        speech=args.speech_right,
        model=args.model_right,
        provider=args.provider_right,
        side="right",
    )
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    match_id = f"{stamp}-{args.left}-{args.right}-{args.seed}.jsonl"
    path = LOGS / match_id
    write_log(path, play_match(left, right, args.seed))
    print(path)
    if is_llm_name(args.left) or is_llm_name(args.right):
        print("note: this burned tokens. Replay the log instead of re-running.", file=sys.stderr)
    return 0


def cmd_live(args: argparse.Namespace) -> int:
    query = {
        "live": "1",
        "left": args.left,
        "right": args.right,
        "seed": args.seed,
        "persona_left": args.persona_left,
        "persona_right": args.persona_right,
        "speech_left": args.speech_left,
        "speech_right": args.speech_right,
        "pace": args.pace,
    }
    if args.model_left:
        query["model_left"] = args.model_left
    if args.model_right:
        query["model_right"] = args.model_right
    if args.provider_left:
        query["provider_left"] = args.provider_left
    if args.provider_right:
        query["provider_right"] = args.provider_right
    encoded = urlencode(query)
    origin = os.environ.get("SALVO_CLIENT_ORIGIN", "http://localhost:5173")
    print(f"{origin}/?{encoded}")
    print(f"server: uv run uvicorn salvo.server.app:app --reload --port {args.port}")
    return 0


def cmd_replay(log: str, pace: float, port: int) -> int:
    src = Path(log)
    LOGS.mkdir(parents=True, exist_ok=True)
    name = src.name
    dest = LOGS / name
    if src.is_file() and src.resolve() != dest.resolve():
        dest.write_bytes(src.read_bytes())
    elif not dest.is_file():
        print(f"log not found: {log}", file=sys.stderr)
        return 1
    origin = os.environ.get("SALVO_CLIENT_ORIGIN", "http://localhost:5173")
    ws_origin = origin.replace("https://", "wss://", 1).replace("http://", "ws://", 1)
    ws = f"{ws_origin}/ws/replay/{quote(name)}"
    print(f"{origin}/?ws={quote(ws, safe='')}&pace={pace}")
    print(f"server: uv run uvicorn salvo.server.app:app --reload --port {port}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
