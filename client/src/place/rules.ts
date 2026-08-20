import { BOARD_SIZE, formatCell, parseCell, type Cell } from "../coords";
import type { ShipPlacement } from "../types";

export const FLEET: readonly { name: string; length: number }[] = [
  { name: "carrier", length: 5 },
  { name: "battleship", length: 4 },
  { name: "cruiser", length: 3 },
  { name: "submarine", length: 3 },
  { name: "destroyer", length: 2 },
];

export function poseFromClicks(start: string, end: string, length: number): string[] | null {
  const a = parseCell(start);
  const b = parseCell(end);
  if (!a || !b) return null;
  if (a.col === b.col) {
    const step = b.row === a.row ? 0 : b.row > a.row ? 1 : -1;
    if (step === 0) return length === 1 ? [start] : null;
    if (Math.abs(b.row - a.row) + 1 !== length) return null;
    return range(length, (i) => formatCell(a.col, a.row + i * step));
  }
  if (a.row === b.row) {
    const step = b.col === a.col ? 0 : b.col > a.col ? 1 : -1;
    if (step === 0) return length === 1 ? [start] : null;
    if (Math.abs(b.col - a.col) + 1 !== length) return null;
    return range(length, (i) => formatCell(a.col + i * step, a.row));
  }
  return null;
}

export function validatePartial(ships: ShipPlacement[]): string | null {
  const expected = Object.fromEntries(FLEET.map((s) => [s.name, s.length]));
  const seen = new Set<string>();
  const occupied: { name: string; cell: Cell }[] = [];
  for (const ship of ships) {
    if (seen.has(ship.name)) return `duplicate ${ship.name}`;
    seen.add(ship.name);
    const length = expected[ship.name];
    if (length === undefined || ship.cells.length !== length) {
      return `${ship.name} must occupy ${length} cells`;
    }
    if (new Set(ship.cells).size !== ship.cells.length) return `${ship.name} has duplicate cells`;
    const parsed: Cell[] = [];
    for (const raw of ship.cells) {
      const cell = parseCell(raw);
      if (!cell) return `illegal cell ${raw}`;
      parsed.push(cell);
    }
    if (!straight(parsed)) return `${ship.name} is not a straight orthogonal line`;
    for (const cell of parsed) occupied.push({ name: ship.name, cell });
  }
  const byCell = new Map<string, string>();
  for (const item of occupied) {
    const key = `${item.cell.col},${item.cell.row}`;
    const other = byCell.get(key);
    if (other) return `overlap at ${formatCell(item.cell.col, item.cell.row)}`;
    byCell.set(key, item.name);
  }
  for (let i = 0; i < occupied.length; i++) {
    const a = occupied[i];
    if (!a) continue;
    for (let j = i + 1; j < occupied.length; j++) {
      const b = occupied[j];
      if (!b || a.name === b.name) continue;
      if (chebyshev(a.cell, b.cell) < 2) return `${a.name} and ${b.name} touch`;
    }
  }
  return null;
}

export function validateShips(ships: ShipPlacement[]): string | null {
  const expected = Object.fromEntries(FLEET.map((s) => [s.name, s.length]));
  const names = ships.map((s) => s.name).sort();
  const want = Object.keys(expected).sort();
  if (names.join() !== want.join()) return `fleet must be ${want.join(", ")}`;
  return validatePartial(ships);
}

export function randomFleet(): ShipPlacement[] {
  for (let attempt = 0; attempt < 250; attempt++) {
    const placed: ShipPlacement[] = [];
    const blocked = new Set<string>();
    let ok = true;
    for (const ship of FLEET) {
      const pose = randomPose(ship.length, blocked);
      if (!pose) {
        ok = false;
        break;
      }
      placed.push({ name: ship.name, cells: pose });
      for (const cell of pose) {
        const parsed = parseCell(cell);
        if (!parsed) continue;
        blocked.add(cell);
        for (const n of neighbors8(parsed)) blocked.add(formatCell(n.col, n.row));
      }
    }
    if (ok && validateShips(placed) === null) return placed;
  }
  throw new Error("could not place fleet");
}

function randomPose(length: number, blocked: Set<string>): string[] | null {
  const poses = allPoses(length);
  for (let i = poses.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    const a = poses[i];
    const b = poses[j];
    if (a && b) {
      poses[i] = b;
      poses[j] = a;
    }
  }
  for (const cells of poses) {
    if (cells.every((c) => !blocked.has(c))) return cells;
  }
  return null;
}

function allPoses(length: number): string[][] {
  const poses: string[][] = [];
  for (let row = 0; row < BOARD_SIZE; row++) {
    for (let col = 0; col <= BOARD_SIZE - length; col++) {
      poses.push(range(length, (i) => formatCell(col + i, row)));
    }
  }
  for (let col = 0; col < BOARD_SIZE; col++) {
    for (let row = 0; row <= BOARD_SIZE - length; row++) {
      poses.push(range(length, (i) => formatCell(col, row + i)));
    }
  }
  return poses;
}

function straight(cells: Cell[]): boolean {
  if (cells.length <= 1) return true;
  const cols = new Set(cells.map((c) => c.col));
  const rows = new Set(cells.map((c) => c.row));
  if (cols.size === 1) {
    const ys = cells.map((c) => c.row).sort((a, b) => a - b);
    return ys.every((y, i) => y === ys[0]! + i);
  }
  if (rows.size === 1) {
    const xs = cells.map((c) => c.col).sort((a, b) => a - b);
    return xs.every((x, i) => x === xs[0]! + i);
  }
  return false;
}

function chebyshev(a: Cell, b: Cell): number {
  return Math.max(Math.abs(a.col - b.col), Math.abs(a.row - b.row));
}

function neighbors8(cell: Cell): Cell[] {
  const out: Cell[] = [];
  for (let dc = -1; dc <= 1; dc++) {
    for (let dr = -1; dr <= 1; dr++) {
      if (dc === 0 && dr === 0) continue;
      const n = { col: cell.col + dc, row: cell.row + dr };
      if (n.col >= 0 && n.col < BOARD_SIZE && n.row >= 0 && n.row < BOARD_SIZE) out.push(n);
    }
  }
  return out;
}

function range(n: number, at: (i: number) => string): string[] {
  return Array.from({ length: n }, (_, i) => at(i));
}
