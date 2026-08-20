import * as THREE from "three";
import { parseCell } from "../coords";
import type { ShipPlacement, Side } from "../types";
import type { Board } from "./board";

const HULL = 0x8b9aa8;
const DECK = 0xd9c7a2;
const SUPER = 0xc5d0d8;
const FUNNEL = 0xb23b32;
const BOTTOM = 0xa44b3c;
const SUB = 0x5c6b74;
const SUNK = 0x6b7380;

export class Fleet {
  private readonly ships = new Map<string, THREE.Group>();

  constructor(private readonly board: Board) {}

  load(placements: ShipPlacement[]): void {
    this.clear();
    for (const ship of placements) {
      const mesh = placeShip(ship, this.board);
      if (!mesh) continue;
      this.ships.set(key(this.board.side, ship.name), mesh);
      this.board.group.add(mesh);
    }
  }

  add(placement: ShipPlacement): void {
    const id = key(this.board.side, placement.name);
    if (this.ships.has(id)) return;
    const mesh = placeShip(placement, this.board);
    if (!mesh) return;
    this.ships.set(id, mesh);
    this.board.group.add(mesh);
  }

  markSunk(name: string): void {
    const group = this.ships.get(key(this.board.side, name));
    if (!group) return;
    group.traverse((obj) => {
      if (!(obj instanceof THREE.Mesh)) return;
      const mat = obj.material;
      if (mat instanceof THREE.MeshStandardMaterial) {
        mat.color.setHex(SUNK);
        mat.emissive.setHex(0x000000);
        mat.metalness = 0.15;
        mat.opacity = 0.78;
        mat.transparent = true;
      }
    });
    group.position.y -= 0.1;
  }

  clear(): void {
    for (const group of this.ships.values()) {
      this.board.group.remove(group);
      group.traverse((obj) => {
        if (obj instanceof THREE.Mesh) {
          obj.geometry.dispose();
          const mat = obj.material;
          if (Array.isArray(mat)) mat.forEach((m) => m.dispose());
          else mat.dispose();
        }
      });
    }
    this.ships.clear();
  }
}

function key(side: Side, name: string): string {
  return `${side}:${name}`;
}

function placeShip(ship: ShipPlacement, board: Board): THREE.Group | null {
  const firstName = ship.cells[0];
  const lastName = ship.cells[ship.cells.length - 1];
  if (!firstName || !lastName) return null;

  const first = parseCell(firstName);
  const last = parseCell(lastName);
  const a = board.cellLocal(firstName, 0);
  const b = board.cellLocal(lastName, 0);
  if (!first || !last || !a || !b) return null;

  const vertical = first.col === last.col;
  const cells = ship.cells.length;
  const model = buildShip(ship.name, cells);
  model.name = `ship-${ship.name}`;
  model.position.set((a.x + b.x) / 2, 0.05, (a.z + b.z) / 2);

  if (vertical) {
    model.rotation.y = last.row >= first.row ? Math.PI : 0;
  } else {
    model.rotation.y = last.col >= first.col ? Math.PI / 2 : -Math.PI / 2;
  }
  return model;
}

function buildShip(name: string, cells: number): THREE.Group {
  const kind = name.toLowerCase();
  if (kind.includes("sub")) return makeSubmarine(cells);
  if (kind.includes("carrier")) return makeCarrier(cells);
  return makeSurface(cells, kind.includes("battle") ? "battleship" : kind.includes("destroy") ? "destroyer" : "cruiser");
}

function paint(color: number, extra?: { roughness?: number; metalness?: number }): THREE.MeshStandardMaterial {
  return new THREE.MeshStandardMaterial({
    color,
    roughness: extra?.roughness ?? 0.48,
    metalness: extra?.metalness ?? 0.22,
  });
}

function makeSurface(cells: number, kind: "battleship" | "cruiser" | "destroyer"): THREE.Group {
  const length = cells * 0.9;
  const beam = kind === "destroyer" ? 0.4 : 0.5;
  const height = 0.2;
  const group = new THREE.Group();

  const hull = new THREE.Mesh(hullGeometry(length, beam, height), paint(HULL));
  hull.castShadow = true;
  hull.receiveShadow = true;
  group.add(hull);

  const bottom = new THREE.Mesh(hullGeometry(length * 0.96, beam * 0.82, 0.05), paint(BOTTOM, { roughness: 0.7 }));
  bottom.position.y = -0.04;
  group.add(bottom);

  const superLen = kind === "battleship" ? length * 0.32 : length * 0.26;
  const house = new THREE.Mesh(
    new THREE.BoxGeometry(beam * 0.7, 0.18, superLen),
    paint(SUPER, { roughness: 0.4 }),
  );
  house.position.set(0, height + 0.1, -length * 0.08);
  house.castShadow = true;
  group.add(house);

  const funnel = new THREE.Mesh(
    new THREE.CylinderGeometry(beam * 0.12, beam * 0.14, 0.26, 10),
    paint(FUNNEL, { roughness: 0.35, metalness: 0.3 }),
  );
  funnel.position.set(0, height + 0.3, -length * 0.04);
  funnel.castShadow = true;
  group.add(funnel);

  if (kind === "battleship") {
    group.add(turret(0, height + 0.05, length * 0.22, beam));
    group.add(turret(0, height + 0.05, -length * 0.28, beam));
  } else if (kind === "cruiser") {
    group.add(turret(0, height + 0.04, length * 0.2, beam * 0.9));
  }

  const bridge = new THREE.Mesh(new THREE.BoxGeometry(beam * 0.38, 0.08, 0.12), paint(DECK, { roughness: 0.55 }));
  bridge.position.set(0, height + 0.2, -length * 0.08);
  group.add(bridge);

  const mast = new THREE.Mesh(
    new THREE.CylinderGeometry(0.018, 0.022, kind === "destroyer" ? 0.55 : 0.48, 6),
    paint(0x6a7680, { metalness: 0.4, roughness: 0.35 }),
  );
  mast.position.set(0, height + (kind === "destroyer" ? 0.48 : 0.44), -length * 0.12);
  mast.castShadow = true;
  group.add(mast);

  return group;
}

function makeCarrier(cells: number): THREE.Group {
  const length = cells * 0.92;
  const beam = 0.62;
  const group = new THREE.Group();

  const hull = new THREE.Mesh(hullGeometry(length, beam, 0.14), paint(HULL));
  hull.castShadow = true;
  hull.receiveShadow = true;
  group.add(hull);

  const deck = new THREE.Mesh(
    new THREE.BoxGeometry(beam * 0.92, 0.045, length * 0.92),
    paint(0xc9c3b4, { roughness: 0.62, metalness: 0.08 }),
  );
  deck.position.y = 0.16;
  deck.castShadow = true;
  group.add(deck);

  const island = new THREE.Mesh(new THREE.BoxGeometry(0.1, 0.22, 0.34), paint(SUPER));
  island.position.set(beam * 0.28, 0.28, -length * 0.06);
  island.castShadow = true;
  group.add(island);

  const stack = new THREE.Mesh(
    new THREE.CylinderGeometry(0.035, 0.04, 0.16, 8),
    paint(FUNNEL, { roughness: 0.35 }),
  );
  stack.position.set(beam * 0.28, 0.42, -length * 0.02);
  group.add(stack);

  return group;
}

function makeSubmarine(cells: number): THREE.Group {
  const length = cells * 0.88;
  const r = 0.16;
  const group = new THREE.Group();
  const mat = paint(SUB, { roughness: 0.38, metalness: 0.4 });

  const body = new THREE.Mesh(new THREE.CylinderGeometry(r, r, length * 0.78, 16), mat);
  body.rotation.x = Math.PI / 2;
  body.castShadow = true;
  group.add(body);

  const bow = new THREE.Mesh(new THREE.SphereGeometry(r, 12, 10), mat.clone());
  bow.position.z = length * 0.39;
  bow.scale.set(1, 1, 1.35);
  bow.castShadow = true;
  group.add(bow);

  const stern = new THREE.Mesh(new THREE.SphereGeometry(r, 12, 10), mat.clone());
  stern.position.z = -length * 0.39;
  stern.scale.set(1, 1, 1.2);
  group.add(stern);

  const tower = new THREE.Mesh(new THREE.BoxGeometry(0.12, 0.14, 0.22), paint(0x6a7880));
  tower.position.y = r + 0.04;
  tower.castShadow = true;
  group.add(tower);

  const periscope = new THREE.Mesh(new THREE.CylinderGeometry(0.015, 0.015, 0.16, 8), paint(0x4a555c));
  periscope.position.y = r + 0.16;
  group.add(periscope);

  return group;
}

function turret(x: number, y: number, z: number, beam: number): THREE.Group {
  const g = new THREE.Group();
  const base = new THREE.Mesh(
    new THREE.CylinderGeometry(beam * 0.16, beam * 0.18, 0.07, 12),
    paint(HULL, { metalness: 0.35 }),
  );
  base.position.set(x, y, z);
  g.add(base);
  const barrel = new THREE.Mesh(
    new THREE.CylinderGeometry(0.018, 0.022, beam * 0.42, 8),
    paint(0x5a646c, { metalness: 0.5, roughness: 0.3 }),
  );
  barrel.rotation.x = Math.PI / 2;
  barrel.position.set(x, y + 0.02, z + beam * 0.22);
  g.add(barrel);
  return g;
}

function hullGeometry(length: number, beam: number, height: number): THREE.BufferGeometry {
  const l = length / 2;
  const b = beam / 2;
  const shape = new THREE.Shape();
  shape.moveTo(0, l);
  shape.bezierCurveTo(b * 0.18, l, b, l * 0.42, b, 0.05 * l);
  shape.lineTo(b * 0.7, -l * 0.82);
  shape.lineTo(b * 0.38, -l);
  shape.lineTo(-b * 0.38, -l);
  shape.lineTo(-b * 0.7, -l * 0.82);
  shape.lineTo(-b, 0.05 * l);
  shape.bezierCurveTo(-b, l * 0.42, -b * 0.18, l, 0, l);

  const geom = new THREE.ExtrudeGeometry(shape, {
    depth: height,
    bevelEnabled: true,
    bevelThickness: height * 0.18,
    bevelSize: Math.min(beam, height) * 0.12,
    bevelSegments: 2,
    curveSegments: 8,
  });
  geom.rotateX(-Math.PI / 2);
  geom.translate(0, height / 2, 0);
  geom.computeVertexNormals();
  return geom;
}
