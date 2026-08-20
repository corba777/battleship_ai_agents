import * as THREE from "three";
import type { Belief } from "../types";
import type { Board } from "./board";

const COUNT = 10;

/** Translucent quads on the target board. Presentation only — `p` comes from the event. */
export class Heatmap {
  private readonly quads: THREE.Mesh[] = [];

  constructor(private readonly board: Board) {
    for (let i = 0; i < COUNT; i++) {
      const mesh = new THREE.Mesh(
        new THREE.PlaneGeometry(0.94, 0.94),
        new THREE.MeshBasicMaterial({
          color: 0xff8a1a,
          transparent: true,
          opacity: 0,
          depthWrite: false,
          fog: false,
          side: THREE.DoubleSide,
        }),
      );
      mesh.rotation.x = -Math.PI / 2;
      mesh.position.y = 0.07;
      mesh.renderOrder = 2;
      mesh.visible = false;
      this.board.group.add(mesh);
      this.quads.push(mesh);
    }
  }

  set(belief: Belief[]): void {
    this.clear();
    for (let i = 0; i < COUNT; i++) {
      const entry = belief[i];
      const quad = this.quads[i];
      if (!entry || !quad) continue;
      const local = this.board.cellLocal(entry.cell, 0.07);
      if (!local) continue;
      quad.position.x = local.x;
      quad.position.z = local.z;
      const mat = quad.material as THREE.MeshBasicMaterial;
      mat.opacity = 0.18 + Math.min(1, Math.max(0, entry.p)) * 0.62;
      quad.visible = true;
    }
  }

  clear(): void {
    for (const quad of this.quads) {
      quad.visible = false;
      (quad.material as THREE.MeshBasicMaterial).opacity = 0;
    }
  }
}
