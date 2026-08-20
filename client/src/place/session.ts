import type { Arena } from "../scene/arena";
import { Vector2 } from "three";
import type { ShipPlacement, Side } from "../types";
import { FLEET, poseFromClicks, randomFleet, validatePartial, validateShips } from "./rules";

export type HumanPlacements = Partial<Record<Side, ShipPlacement[]>>;

export function attachPlacement(
  arena: Arena,
  sides: Side[],
  onReady: (placements: HumanPlacements) => void,
  onCancel: () => void,
): { detach(): void; fail(reason: string): void } {
  if (!sides.length) throw new Error("placement needs a human side");
  const root = must("#place");
  const status = must("#place-status");
  const hint = must("#place-hint");
  const readyBtn = mustButton("#place-ready");
  const fleets: Record<Side, ShipPlacement[]> = { left: [], right: [] };
  let index = 0;
  let origin: string | null = null;

  const side = () => sides[index] ?? sides[0]!;

  const allReady = () => sides.every((s) => validateShips(fleets[s]) === null);

  const payload = (): HumanPlacements => {
    const out: HumanPlacements = {};
    for (const s of sides) out[s] = fleets[s];
    return out;
  };

  const paint = () => {
    for (const s of sides) arena.placeShips(s, fleets[s]);
    const current = side();
    const ship = FLEET[fleets[current].length];
    if (!ship) {
      status.textContent = sides.length > 1 ? "your fleets placed" : "your fleet placed";
      hint.textContent = "empty opponent board — you hunt by clicking · ready starts the match";
      readyBtn.disabled = !allReady();
      arena.clearHeatmaps();
      return;
    }
    readyBtn.disabled = true;
    status.textContent = `${current} · ${ship.name} · ${ship.length}`;
    hint.textContent = origin
      ? `stern ${ship.length} cells from ${origin}`
      : "place your fleet · you will not see the opponent's ships";
    arena.focusBoard(current);
    if (origin) {
      arena.setBelief(current, [{ cell: origin, p: 1 }]);
    } else {
      arena.clearHeatmaps();
    }
  };

  const advanceIfDone = () => {
    if (validateShips(fleets[side()]) === null && index < sides.length - 1) {
      index += 1;
      origin = null;
    }
  };

  const onClick = (ev: PointerEvent) => {
    const canvas = ev.currentTarget;
    if (!(canvas instanceof HTMLCanvasElement)) return;
    const rect = canvas.getBoundingClientRect();
    const ndc = new Vector2(
      ((ev.clientX - rect.left) / rect.width) * 2 - 1,
      -((ev.clientY - rect.top) / rect.height) * 2 + 1,
    );
    const hit = arena.pick(ndc);
    const current = side();
    if (!hit || hit.side !== current) return;
    const ship = FLEET[fleets[current].length];
    if (!ship) return;
    if (!origin) {
      origin = hit.cell;
      paint();
      return;
    }
    if (hit.cell === origin) {
      origin = null;
      paint();
      return;
    }
    const cells = poseFromClicks(origin, hit.cell, ship.length);
    origin = null;
    if (!cells) {
      hint.textContent = "need a straight line of the right length";
      paint();
      return;
    }
    const next = [...fleets[current], { name: ship.name, cells }];
    const err = validatePartial(next);
    if (err) {
      hint.textContent = err;
      paint();
      return;
    }
    fleets[current] = next;
    advanceIfDone();
    paint();
  };

  const undo = () => {
    if (origin) {
      origin = null;
      paint();
      return;
    }
    const current = side();
    if (fleets[current].length) {
      fleets[current] = fleets[current].slice(0, -1);
    } else if (index > 0) {
      index -= 1;
      const prev = side();
      fleets[prev] = fleets[prev].slice(0, -1);
    }
    paint();
  };

  const randomBoard = () => {
    fleets[side()] = randomFleet();
    origin = null;
    advanceIfDone();
    paint();
  };

  const canvas = mustCanvas("#scene");
  const ac = new AbortController();
  canvas.addEventListener("pointerdown", onClick, { signal: ac.signal });
  mustButton("#place-undo").addEventListener("click", undo, { signal: ac.signal });
  mustButton("#place-random").addEventListener("click", randomBoard, { signal: ac.signal });
  readyBtn.addEventListener("click", () => {
    if (readyBtn.disabled || !allReady()) return;
    readyBtn.disabled = true;
    onReady(payload());
  }, { signal: ac.signal });
  mustButton("#place-cancel").addEventListener("click", () => {
    root.hidden = true;
    onCancel();
  }, { signal: ac.signal });

  arena.reset();
  root.hidden = false;
  paint();

  return {
    detach() {
      ac.abort();
      root.hidden = true;
    },
    fail(reason: string) {
      hint.textContent = reason;
      readyBtn.disabled = !allReady();
    },
  };
}

function must(selector: string): HTMLElement {
  const el = document.querySelector<HTMLElement>(selector);
  if (!el) throw new Error(`missing ${selector}`);
  return el;
}

function mustButton(selector: string): HTMLButtonElement {
  const el = document.querySelector<HTMLButtonElement>(selector);
  if (!el) throw new Error(`missing ${selector}`);
  return el;
}

function mustCanvas(selector: string): HTMLCanvasElement {
  const el = document.querySelector<HTMLCanvasElement>(selector);
  if (!el) throw new Error(`missing ${selector}`);
  return el;
}
