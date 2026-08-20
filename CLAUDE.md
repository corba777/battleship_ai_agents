# CLAUDE.md — salvo

> Rename `salvo` if a better name shows up. Everything below assumes the package
> name is `salvo` on the Python side and `@salvo/client` on the TS side.

## What this is

A spectator-first Battleship arena. Two LLM agents (or a human and an agent) play
a standard 10×10 game; a Three.js frontend renders both boards **to the viewer**,
including the information neither agent has.

**Prime directive: this is entertainment, not a benchmark.** The interesting
artifact is the moment an agent narrates total confidence about a square that the
viewer already knows is empty water. Every design decision resolves in favor of
making that moment legible on screen. If a change makes the game stronger but the
dramatic irony weaker, it is the wrong change.

Corollary: do **not** add Elo tracking, density/Monte-Carlo baselines,
tournament harnesses, or statistical writeups. Those are a different project. A
deterministic bot exists here only as a token-free dev fixture (see Testing).

## Architecture

```
salvo/
  referee/          # Python. Sole owner of game truth.
    board.py        # placement, shot resolution, sink detection
    match.py        # turn loop, match state machine
    events.py       # event dataclasses -> JSON
    log.py          # JSONL match recorder
  agents/           # Python. ADK orchestration.
    player.py       # LlmAgent wrapper, one instance per side
    human.py        # click-driven player; same act() contract
    contract.py     # output schema + parsing + repair policy
    prompts/        # system prompts, one file per persona
  server/
    app.py          # FastAPI, WebSocket event stream, replay endpoint
  client/           # TypeScript + Vite + Three.js. Thin.
    src/scene/      # boards, pegs, ships, camera rigs, water
    src/hud/        # reasoning panel, belief heatmap, counters
    src/place/      # director fleet overlay (UX port of board.py)
    src/net/        # WS subscribe, event -> scene mutation
  logs/             # match JSONL, gitignored
```

### The boundary that matters

The referee holds ground truth for both boards. The client is a **projection of
an event stream** and computes nothing about the game.

- The client MUST NOT decide hit/miss, MUST NOT decide when a ship is sunk, MUST
  NOT track whose turn it is by inference. It receives `shot_result`, `sunk`,
  `turn` and renders them.
- If you catch yourself writing ship-adjacency logic in TypeScript, stop. That
  logic already exists in `referee/board.py` and the second copy will diverge.
  The placement overlay in `client/src/place/` is the one exception: it ports
  no-touch for director UX, and the server still re-validates.

The one thing the client legitimately owns is presentation state: camera
position, animation queues, which panel is expanded.

## Non-negotiables

1. **Never leak the true board into agent context.** Agents receive only their
   own placement and their own shot history. There is a test for this
   (`test_no_leak.py`) that asserts the rendered prompt for side A contains no
   coordinate from side B's placement. Keep it passing. This is the whole show —
   if it breaks, the drama is fake and nothing else matters.
2. **Never silently repair agent output.** Illegal shots are the best material in
   the project. Log every one with the raw text. Policy: on illegal or
   unparseable output, re-prompt once with an explicit error message; on second
   failure, the referee picks a uniform random legal cell and marks the turn
   `coerced: true`. Coerced turns render differently in the HUD.
3. **Repeat shots are legal and are not errors.** Firing at an already-resolved
   cell wastes the turn, increments `repeat_count`, and is rendered with a
   distinct sound and a shake. Do not block it, do not warn the agent
   pre-emptively. It is a feature.
4. **Seeds are recorded.** Placements come from a seeded RNG; the seed goes in the
   match log header so any match can be reconstructed exactly.

## Coordinate convention

One canonical form, everywhere, no exceptions: **column letter A–J, then row
number 1–10, uppercase, no separator.** `E5`. Not `5E`, not `e5`, not `(4,4)`.

- `referee/board.py` exposes `parse_cell()` / `format_cell()`. Everything goes
  through them, including the client (port them, do not reinvent).
- Agent output is normalized once at the contract boundary. Case and whitespace
  are forgiven; transposition is **not** — `5E` is an illegal move and gets
  logged as one. Models transposing coordinates is content.

## Agent contract

Each turn the agent returns a single JSON object, no prose outside it, no fences:

```json
{
  "shot": "E5",
  "belief": [
    {"cell": "E5", "p": 0.42},
    {"cell": "E6", "p": 0.31},
    {"cell": "D5", "p": 0.19}
  ],
  "say": "The hit at E4 has to run vertically. Continuing down."
}
```

- `shot` — required, canonical cell.
- `belief` — required, exactly 3 entries, descending `p`, values in [0,1], need
  not sum to 1. `belief[0].cell` SHOULD equal `shot` but is not forced; when it
  doesn't, that's a highlight, so log the mismatch rather than correcting it.
  This field drives the heatmap and is the primary visual signal of the agent's
  model of the world diverging from reality.
- `say` — required, one or two sentences, first person, present tense.

### Speech profiles

Orthogonal to persona. Each LLM slot picks `standard` | `raw-ru` before the
match (CLI `--speech-left` / `--speech-right`, live query `speech_left` /
`speech_right`, or the setup overlay). Menu label **PROFANE RUSSIAN (16+)** —
wire id stays `raw-ru`. `standard` leaves `say` in English. `raw-ru` appends a
short overlay that forces Russian + мат in `say` only; JSON keys and cells stay
`E5`. Overlay never enters the opponent observation. Unknown ids are rejected,
not silently repaired.

### `say` is spectator-only

`say` is rendered in the HUD and is **never** placed in the opponent's
observation. There is no trash-talk channel in this project. This is a
deliberate choice, not an oversight — but it must stay documented here, because
a channel that looks like communication and silently goes nowhere is exactly the
kind of thing that quietly invalidates a whole corpus. If a future mode does
give agents a real channel, it goes through the referee as an explicit event
type and gets its own test asserting delivery.

### Personas

Each side loads a prompt from `agents/prompts/`. Personas differ in *stated
reasoning style*, not in tool access or information: e.g. `methodical.md`
(parity search, explicit elimination) vs `intuitive.md` (claims to read
patterns, commits hard to hypotheses). Contrast between styles is the point of
a matchup. Keep prompts short; long ones flatten the differences. Both sides
may use the same persona.

### Models and providers

Setup is provider-first. **Vertex AI** lists Gemini plus Vertex-hosted Claude
(`claude-opus-4-6`). **Anthropic** is a separate list (`claude-sonnet-5`,
`claude-opus-5`) and needs `ANTHROPIC_API_KEY`. **OpenAI** defaults to
`gpt-5.4-nano` (`OPENAI_API_KEY`). **Gemini API** is Google AI Studio
(`GEMINI_API_KEY`). **Ollama** is local (`OLLAMA_URL`, default
`http://localhost:11434`); same `/api/chat` body as amber (`format: json`,
`think: false`). `OLLAMA_THINK=1` turns CoT on. `GET /catalog` is the menu
source. Keys never go to the client.

## Event stream

Server → client over WebSocket, one JSON object per message, `type` discriminated:

| type | payload |
|---|---|
| `match_start` | seed, both placements (**viewer-only**, see note), player metadata |
| `turn` | side, turn index |
| `thinking` | side, `say`, `belief` |
| `shot_result` | side, cell, `hit` \| `miss` \| `repeat`, `coerced` |
| `sunk` | side, ship name, cells |
| `illegal` | side, raw output, reason, attempt number |
| `match_abort` | turns, reason (`stopped`), stats so far. No winner. |
| `match_end` | winner, turn count, final stats |

Client → server (live `/ws` only):

| type | payload |
|---|---|
| `start` | optional `placements` for **human** sides only. Omitted / `"random"` → seeded RNG. LLM/bot fleets are never taken from the client. |
| `human_shot` | `cell` (`E5`), `side` (`left` \| `right`) |
| `abort` | stop the match; partial JSONL is still written |

`placement_error` is a control message, not a match event: illegal fleets are rejected and the overlay stays up.

Human vs human rooms (`/ws?room=&seat=`) add three more control messages: `room_hello` (your seat), `room_peer` (the other seat joined), `room_waiting` (you placed; the other seat has not). Each seat's `start` carries **only that seat's** fleet.

`match_start` carrying both placements is what makes the spectator view work. It
travels to the browser and nowhere near an agent's context. Do not "simplify" by
routing agent prompts through the same channel.

## Human vs AI

Pick **Human** in the setup overlay, then **MANUAL** or **RANDOM** for that side's fleet. After WATCH LIVE, manual placement is **your board only**: bow click, then stern on the same row or column at the ship's length. No-touch including diagonal, same rule as `referee/board.py`. RANDOM BOARD can still fill your side in the overlay. READY sends `start` with that fleet.

The LLM/bot fleet is the referee's seeded RNG. **Fog of war:** the human does not see those ships until a `sunk` (or match end, when leftovers are revealed). Hits and misses are still pegs. Your own fleet stays visible — that is the remaining dramatic irony: the model talks confidence over a board you can see and it cannot.

LLM vs LLM is the omniscient spectator show: both fleets stay visible. Do not fog that mode.

Firing is click-only on the opponent's board when it is the human's turn. `say` is `"Firing at E5."` — there is no speech prompt. `say` stays spectator-only.

The placement overlay ports `parse_cell` / no-touch for UX. The referee still owns legality; do not add shot/sink logic in TypeScript.

## Human vs Human

Two browsers, one 4-character room (`ABCDEFGHJKLMNPQRSTUVWXYZ23456789`, no `0/O/1/I`). If the first Human pick is left, the guest URL seats **right**; if right was first, the guest sits **left**. Setup defaults both fleets to **manual**. Host WATCH LIVE keeps `seat` as the host; the overlay shows the guest URL (`live=1&left=human&right=human&room=AB23&seat=…`).

Each player places **their** board only. Match starts when both have sent `start`. Fog is by seat: you never see the other hulls until `sunk` / match end. `human_shot` is accepted only from that seat. No accounts; the room dies when both sockets drop. JSONL is still written (`human-human-{seed}`).

## Rendering notes

- Two boards, angled toward the camera, ocean plane between them.
- Pegs: single `InstancedMesh` per color (white/red), ~200 instances, one draw
  call each. Do not create per-peg meshes.
- Belief heatmap: translucent quads on the *target* board, opacity from `p`,
  cleared at the start of each turn. This is the highest-value visual in the
  project — build it before the water shader.
- Camera rigs: `idle` (slow orbit), `focus` (push in on the active cell),
  `finale` (slow flyover triggered on the final `sunk`). Rigs are driven by
  events, never by a timer that assumes turn duration.
- Counters in the corner: repeats, illegals, shots fired, hit rate. Small, always
  visible, no animation.
- Water shader is the last thing you build, and it is allowed to be indulgent
  once everything above works.

## Match log & replay

Every match writes `logs/<match_id>.jsonl`: one header line (seed, placements,
model ids, prompt hashes) then one line per emitted event.

`server/app.py` exposes a replay endpoint that streams a recorded log to the
client with configurable pacing and **zero LLM calls**. Do all rendering, HUD,
and camera work against replays. Recording ten matches once and then iterating on
the visuals for free is the difference between this being a weekend project and
a token sink.

## Testing

- `test_no_leak.py` — see Non-negotiables #1. Highest priority test in the repo.
- `test_board.py` — placement legality, shot resolution, sink detection, repeat
  handling. Pure, fast, no LLM.
- `test_human.py` — `HumanPlayer` inbox, explicit fleets, factory requires inbox.
- `test_room.py` — two-seat human room: both `start`s before `match_start`, seat-taken close.
- `RandomBot` and `ParityBot` in `agents/bots.py` implement the same contract as
  LLM players. `HumanPlayer` does too, with clicks instead of inference. They are
  dev fixtures — do not build ranking or comparison features around them.

## Dev workflow

```bash
# referee + server
uv sync && uv run pytest
uv run uvicorn salvo.server.app:app --reload

# client
cd client && npm install && npm run dev

# a bot-vs-bot match, no tokens burned
uv run python -m salvo.cli --left parity --right random --seed 42

# replay a recorded match into the browser
uv run python -m salvo.cli replay logs/<match_id>.jsonl --pace 1.5

# live LLM match (Vertex). Local: gcloud ADC. Docker: mounted JSON.
# GOOGLE_CLOUD_PROJECT defaults to example-project.
# Gemini default: gemini-3.5-flash-lite. Claude/opus default: claude-opus-4-6.
gcloud auth application-default login
uv run python -m salvo.cli live --left gemini-3.5-flash --right claude-sonnet-4-6 --seed 1
# API instead of Vertex (needs GEMINI_API_KEY / ANTHROPIC_API_KEY):
# uv run python -m salvo.cli live --left gemini --provider-left gemini --right opus --provider-right anthropic
# Ollama (local or LAN; Docker rewrites localhost → host.docker.internal):
# uv run python -m salvo.cli live --left ollama --right gemini --seed 1

# whole stack in Docker (ADC from ../google_account, never baked into the image)
docker compose up --build
# then open http://localhost:8080/ and pick speech, or
# http://localhost:8080/?live=1&left=gemini&right=opus&speech_left=raw-ru&speech_right=standard&seed=1
# Human vs AI (you place your fleet; AI is seeded random):
# http://localhost:8080/?live=1&left=human&right=gemini-3.5-flash-lite&place_left=manual&seed=1
# Human vs human (host left; guest opens the URL from the setup overlay):
# http://localhost:8080/?live=1&left=human&right=human&room=AB23&seat=left&place_left=manual&place_right=manual&seed=1
```

## Non-goals

- Skill measurement of any kind. A fifty-line heuristic beats every LLM here and
  everyone already knows it.
- Salvo/advanced rule variants, fog-of-war fleets, custom board sizes.
- Agents holding their own boards and self-reporting hits (a commit-reveal honesty
  variant). Interesting, genuinely — and a different repo with different goals.
  Referee-authoritative here, always.
- Accounts, lobbies, or persistence beyond the JSONL logs. A two-seat human room is in scope; that is not a ranked ladder.

## Open questions

- Turn pacing for watchability: real inference latency is uneven and probably too
  slow. Likely answer is to decouple — let the referee run ahead and have the
  client play back at a fixed pace from a buffer.
