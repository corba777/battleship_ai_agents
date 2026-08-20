import * as THREE from "three";
import { BOARD_SIZE, CELL_SIZE, cellLocal, formatCell, localToCell, parseCell } from "../coords";

const SLAB = 11.4;

export class Board {
  readonly group = new THREE.Group();
  readonly deck: THREE.Mesh;
  private readonly shake = { t: 0, amp: 0 };
  private readonly rest = new THREE.Vector3();

  constructor(readonly side: "left" | "right") {
    this.group.name = `board-${side}`;

    const slab = new THREE.Mesh(
      new THREE.BoxGeometry(SLAB, 0.22, SLAB),
      new THREE.MeshStandardMaterial({
        color: 0xe7f1f6,
        roughness: 0.55,
        metalness: 0.08,
      }),
    );
    slab.position.y = -0.11;
    slab.castShadow = true;
    slab.receiveShadow = true;
    this.group.add(slab);

    this.deck = new THREE.Mesh(
      new THREE.PlaneGeometry(10, 10),
      new THREE.MeshStandardMaterial({
        map: makeDeckTexture(),
        roughness: 0.78,
        metalness: 0.08,
      }),
    );
    this.deck.rotation.x = -Math.PI / 2;
    this.deck.position.y = 0.002;
    this.deck.receiveShadow = true;
    this.group.add(this.deck);

    const grid = new THREE.GridHelper(10, BOARD_SIZE, 0xffffff, 0xd7eaf3);
    grid.position.y = 0.01;
    const gridMat = grid.material;
    if (!Array.isArray(gridMat)) {
      gridMat.transparent = true;
      gridMat.opacity = 0.55;
    }
    this.group.add(grid);

    this.group.add(makeLabels(side));
  }

  cellLocal(cell: string, y = 0.02): THREE.Vector3 | null {
    const parsed = parseCell(cell);
    if (!parsed) return null;
    const p = cellLocal(parsed, y);
    return new THREE.Vector3(p.x, p.y, p.z);
  }

  cellWorld(cell: string, y = 0.02, target = new THREE.Vector3()): THREE.Vector3 | null {
    const local = this.cellLocal(cell, y);
    if (!local) return null;
    return this.group.localToWorld(target.copy(local));
  }

  pick(raycaster: THREE.Raycaster): string | null {
    const hits = raycaster.intersectObject(this.deck, false);
    const hit = hits[0];
    if (!hit) return null;
    const local = this.group.worldToLocal(hit.point.clone());
    const cell = localToCell(local.x, local.z);
    if (!cell) return null;
    return formatCell(cell.col, cell.row);
  }

  bump(): void {
    this.shake.t = 0;
    this.shake.amp = 1;
  }

  update(dt: number): void {
    this.shake.t += dt;
    this.shake.amp *= Math.pow(0.001, dt);
    const a = this.shake.amp;
    this.group.position.x = this.rest.x + Math.sin(this.shake.t * 42) * a * 0.16;
    this.group.position.z = this.rest.z + Math.cos(this.shake.t * 31) * a * 0.1;
  }

  setRest(x: number, y: number, z: number): void {
    this.rest.set(x, y, z);
    this.group.position.copy(this.rest);
  }
}

function makeDeckTexture(): THREE.CanvasTexture {
  const size = 1024;
  const canvas = document.createElement("canvas");
  canvas.width = size;
  canvas.height = size;
  const ctx = canvas.getContext("2d");
  if (!ctx) throw new Error("2d context unavailable");

  ctx.fillStyle = "#5eb3d1";
  ctx.fillRect(0, 0, size, size);

  const cell = size / BOARD_SIZE;
  for (let r = 0; r < BOARD_SIZE; r++) {
    for (let c = 0; c < BOARD_SIZE; c++) {
      if ((r + c) % 2 === 0) {
        ctx.fillStyle = "#6fc0db";
        ctx.fillRect(c * cell, r * cell, cell, cell);
      }
    }
  }

  const texture = new THREE.CanvasTexture(canvas);
  texture.anisotropy = 8;
  texture.colorSpace = THREE.SRGBColorSpace;
  return texture;
}

function makeLabels(side: "left" | "right"): THREE.Group {
  const group = new THREE.Group();
  const numX = side === "left" ? -5.55 : 5.55;
  for (let i = 0; i < BOARD_SIZE; i++) {
    const col = sprite(String.fromCharCode(65 + i));
    col.position.set((i - 4.5) * CELL_SIZE, 0.02, 5.55);
    group.add(col);

    const row = sprite(String(i + 1));
    row.position.set(numX, 0.02, (4.5 - i) * CELL_SIZE);
    group.add(row);
  }
  return group;
}

function sprite(text: string): THREE.Sprite {
  const canvas = document.createElement("canvas");
  canvas.width = 128;
  canvas.height = 128;
  const ctx = canvas.getContext("2d");
  if (!ctx) throw new Error("2d context unavailable");
  ctx.fillStyle = "#1f4f6e";
  ctx.font = "600 56px 'IBM Plex Mono', monospace";
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillText(text, 64, 64);
  const map = new THREE.CanvasTexture(canvas);
  map.colorSpace = THREE.SRGBColorSpace;
  const mat = new THREE.SpriteMaterial({ map, transparent: true, depthTest: false });
  const s = new THREE.Sprite(mat);
  s.scale.set(0.42, 0.42, 1);
  return s;
}
