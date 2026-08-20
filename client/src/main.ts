import { Hud } from "./hud/hud";
import { attachSetup, showSetup } from "./hud/setup";
import { attachPicker } from "./input/picker";
import { Projector, unlockAudio } from "./net/apply";
import { PacedBuffer } from "./net/buffer";
import { connectSocket, paceFromPage, wsUrlFromPage } from "./net/socket";
import { attachPlacement, type HumanPlacements } from "./place/session";
import { Arena } from "./scene/arena";
import { sampleMatch } from "./fixtures/sample-match";
import { opponent, type HumanShot, type MatchEvent, type Side } from "./types";

const canvas = document.querySelector<HTMLCanvasElement>("#scene");
if (!canvas) throw new Error("missing #scene");

const arena = new Arena(canvas);
const hud = new Hud();
const seat = seatFromPage();
const projector = new Projector(arena, hud, seat);
const pace = paceFromPage(1.5);
const buffer = new PacedBuffer((event) => projector.apply(event), pace);
const stopBtn = document.querySelector<HTMLButtonElement>("#stop");

const wsUrl = wsUrlFromPage();
const fixture = new URLSearchParams(window.location.search).get("fixture") === "1";
const humanMatch = hasHuman();
const manualSides = humanManualSides();
let sendShot: ((shot: HumanShot) => void) | null = null;
let closeLive: (() => void) | null = null;
let sendStart: ((placements: HumanPlacements) => void) | null = null;
let placement: { detach(): void; fail(reason: string): void } | null = null;

function startFixture(): void {
  buffer.reset();
  hud.setMode("replay · fixture");
  setStopVisible(true);
  buffer.pushAll(sampleMatch());
}

function halt(): void {
  closeLive?.();
  closeLive = null;
  sendShot = null;
  sendStart = null;
  placement?.detach();
  placement = null;
  buffer.stop();
  arena.reset();
  setStopVisible(false);
  hud.setMode("stopped");
  hud.matchAbort();
  history.replaceState({}, "", "/");
  showSetup();
}

function setStopVisible(on: boolean): void {
  if (stopBtn) stopBtn.hidden = !on;
}

function onMatchEvent(event: MatchEvent): void {
  if (event.type === "match_start") {
    placement?.detach();
    placement = null;
  }
  buffer.push(event);
  if (event.type === "match_end" || event.type === "match_abort") {
    setStopVisible(false);
  }
}

function openLive(url: string, autoStart?: HumanPlacements): void {
  hud.setMode(url.includes("/replay/") ? "replay" : "live");
  setStopVisible(true);
  let opened = false;
  let queued: HumanPlacements | undefined;
  const sock = connectSocket(
    url,
    onMatchEvent,
    (notice) => {
      if (notice.type === "placement_error") {
        const reason = typeof notice.reason === "string" ? notice.reason : "illegal fleet";
        placement?.fail(reason);
        hud.setMode(`place · ${reason}`);
      } else if (notice.type === "room_waiting" && typeof notice.waiting_for === "string") {
        hud.setMode(`waiting for ${notice.waiting_for}`);
      } else if (placement) {
        return;
      } else if (notice.type === "room_hello" && typeof notice.waiting_for === "string") {
        hud.setMode(`waiting for ${notice.waiting_for}`);
      } else if (notice.type === "room_peer") {
        hud.setMode("opponent joined");
      }
    },
  );
  sendShot = (shot) => sock.send(shot);
  sendStart = (next) => {
    if (opened) sock.send({ type: "start", placements: next });
    else queued = next;
  };
  closeLive = () => {
    sock.send({ type: "abort" });
    sock.close();
  };
  void sock.ready
    .then(() => {
      opened = true;
      const first = queued ?? autoStart;
      if (first !== undefined) sock.send({ type: "start", placements: first });
    })
    .catch(() => {
      hud.setMode("websocket failed");
      halt();
    });
}

attachSetup(startFixture, Boolean(wsUrl) || fixture);

if (wsUrl && manualSides.length) {
  hud.setMode("place");
  setStopVisible(true);
  placement = attachPlacement(
    arena,
    manualSides,
    (placements) => {
      if (sendStart) sendStart(placements);
    },
    halt,
  );
  openLive(wsUrl);
} else if (wsUrl) {
  openLive(wsUrl, humanMatch ? {} : undefined);
} else if (fixture) {
  startFixture();
} else {
  hud.setMode("setup");
}

stopBtn?.addEventListener("click", halt);

attachPicker(
  canvas,
  arena,
  (target) => {
    if (placement) return false;
    const acting = projector.humanTurn();
    if (acting === null) return false;
    if (seat && acting !== seat) return false;
    return target === opponent(acting);
  },
  (cell) => {
    const acting = projector.humanTurn();
    if (!acting) return;
    if (seat && acting !== seat) return;
    sendShot?.({ type: "human_shot", cell, side: acting });
  },
);

canvas.addEventListener("pointerdown", () => unlockAudio(), { once: true });

function frame(now: number): void {
  buffer.tick(now);
  hud.tick();
  arena.tick();
  requestAnimationFrame(frame);
}

requestAnimationFrame(frame);

function hasHuman(): boolean {
  const params = new URLSearchParams(window.location.search);
  return params.get("left") === "human" || params.get("right") === "human";
}

function seatFromPage(): Side | null {
  const seat = new URLSearchParams(window.location.search).get("seat");
  return seat === "left" || seat === "right" ? seat : null;
}

function humanManualSides(): Side[] {
  const params = new URLSearchParams(window.location.search);
  if (params.get("live") !== "1") return [];
  if (params.get("left") === "human" && params.get("right") === "human") {
    const mine = params.get("seat") === "right" ? "right" : "left";
    if ((params.get(`place_${mine}`) ?? "manual") === "manual") return [mine];
    return [];
  }
  const sides: Side[] = [];
  for (const side of ["left", "right"] as const) {
    if (params.get(side) !== "human") continue;
    if ((params.get(`place_${side}`) ?? "manual") === "manual") sides.push(side);
  }
  return sides;
}
