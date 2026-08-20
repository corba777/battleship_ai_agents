import * as THREE from "three";
import type { Board } from "./board";
import type { ShotKind } from "../types";

const MAX = 100;

export class Pegs {
  private readonly miss: THREE.InstancedMesh;
  private readonly hit: THREE.InstancedMesh;
  private missCount = 0;
  private hitCount = 0;
  private readonly dummy = new THREE.Object3D();
  private readonly occupied = new Set<string>();

  constructor(private readonly board: Board) {
    const geom = new THREE.CylinderGeometry(0.12, 0.14, 0.58, 10);
    this.miss = new THREE.InstancedMesh(
      geom,
      new THREE.MeshStandardMaterial({
        color: 0xf2f0ea,
        roughness: 0.35,
        metalness: 0.05,
      }),
      MAX,
    );
    this.hit = new THREE.InstancedMesh(
      geom,
      new THREE.MeshStandardMaterial({
        color: 0xc4453c,
        roughness: 0.32,
        metalness: 0.12,
        emissive: 0x3a0808,
      }),
      MAX,
    );
    this.miss.count = 0;
    this.hit.count = 0;
    this.miss.castShadow = true;
    this.hit.castShadow = true;
    this.board.group.add(this.miss, this.hit);
  }

  place(cell: string, kind: ShotKind): void {
    if (kind === "repeat") return;
    if (this.occupied.has(cell)) return;
    const local = this.board.cellLocal(cell, 0.32);
    if (!local) return;

    this.dummy.position.copy(local);
    this.dummy.rotation.set(0, 0, 0);
    this.dummy.updateMatrix();

    if (kind === "hit") {
      if (this.hitCount >= MAX) return;
      this.hit.setMatrixAt(this.hitCount, this.dummy.matrix);
      this.hitCount += 1;
      this.hit.count = this.hitCount;
      this.hit.instanceMatrix.needsUpdate = true;
    } else {
      if (this.missCount >= MAX) return;
      this.miss.setMatrixAt(this.missCount, this.dummy.matrix);
      this.missCount += 1;
      this.miss.count = this.missCount;
      this.miss.instanceMatrix.needsUpdate = true;
    }
    this.occupied.add(cell);
  }

  clear(): void {
    this.missCount = 0;
    this.hitCount = 0;
    this.miss.count = 0;
    this.hit.count = 0;
    this.miss.instanceMatrix.needsUpdate = true;
    this.hit.instanceMatrix.needsUpdate = true;
    this.occupied.clear();
  }
}
