/** Canonical cell: column A–J, then row 1–10, uppercase, no separator. `E5`. */

export const COLUMNS = "ABCDEFGHIJ";
export const BOARD_SIZE = 10;
export const CELL_SIZE = 1;

export type Cell = { col: number; row: number };

export function parseCell(raw: string): Cell | null {
  const s = raw.trim().toUpperCase();
  const m = /^([A-J])(10|[1-9])$/.exec(s);
  if (!m) return null;
  const letter = m[1];
  const digits = m[2];
  if (letter === undefined || digits === undefined) return null;
  return { col: COLUMNS.indexOf(letter), row: Number(digits) - 1 };
}

export function formatCell(col: number, row: number): string {
  const letter = COLUMNS[col];
  if (letter === undefined || row < 0 || row >= BOARD_SIZE) {
    throw new RangeError(`cell out of range: ${col},${row}`);
  }
  return `${letter}${row + 1}`;
}

/**
 * Board-local position of a cell center.
 * A1 is near-left: −X is A, +Z is row 1 (toward a camera on +Z).
 */
export function cellLocal(cell: Cell, y = 0): { x: number; y: number; z: number } {
  return {
    x: (cell.col - 4.5) * CELL_SIZE,
    y,
    z: (4.5 - cell.row) * CELL_SIZE,
  };
}

export function localToCell(x: number, z: number): Cell | null {
  const col = Math.floor(x / CELL_SIZE + 5);
  const row = Math.floor(5 - z / CELL_SIZE);
  if (col < 0 || col >= BOARD_SIZE || row < 0 || row >= BOARD_SIZE) return null;
  return { col, row };
}
