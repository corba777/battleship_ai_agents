import * as THREE from "three";
import type { Arena } from "../scene/arena";
import type { Side } from "../types";

export function attachPicker(
  canvas: HTMLCanvasElement,
  arena: Arena,
  canFire: (target: Side) => boolean,
  fire: (cell: string) => void,
): void {
  const ndc = new THREE.Vector2();

  canvas.addEventListener("pointerdown", (ev) => {
    const rect = canvas.getBoundingClientRect();
    ndc.x = ((ev.clientX - rect.left) / rect.width) * 2 - 1;
    ndc.y = -((ev.clientY - rect.top) / rect.height) * 2 + 1;
    const hit = arena.pick(ndc);
    if (!hit) return;
    if (!canFire(hit.side)) return;
    fire(hit.cell);
  });
}
