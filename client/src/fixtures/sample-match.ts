import type { Belief, MatchEvent, ShipPlacement, Side } from "../types";

const LEFT: ShipPlacement[] = [
  { name: "carrier", cells: ["A1", "A2", "A3", "A4", "A5"] },
  { name: "battleship", cells: ["C1", "C2", "C3", "C4"] },
  { name: "cruiser", cells: ["E1", "E2", "E3"] },
  { name: "submarine", cells: ["G1", "G2", "G3"] },
  { name: "destroyer", cells: ["I1", "I2"] },
];

const RIGHT: ShipPlacement[] = [
  { name: "carrier", cells: ["J6", "J7", "J8", "J9", "J10"] },
  { name: "battleship", cells: ["A10", "B10", "C10", "D10"] },
  { name: "cruiser", cells: ["F5", "F6", "F7"] },
  { name: "submarine", cells: ["A6", "A7", "A8"] },
  { name: "destroyer", cells: ["E1", "F1"] },
];

interface ScriptShot {
  side: Side;
  cell?: string;
  say?: string;
  belief?: Belief[];
  illegal?: { raw: string; reason: string; attempt: number };
  coerced?: boolean;
}

/**
 * Hand-authored spectator tape. Hit/miss/sunk are baked into the events so the
 * runtime projector never decides them. Occupied sets here are fixture-only.
 */
export function sampleMatch(): MatchEvent[] {
  const rightOccupied = occupy(RIGHT);
  const leftOccupied = occupy(LEFT);
  const resolved = {
    left: new Set<string>(),
    right: new Set<string>(),
  };
  const sunk = { left: new Set<string>(), right: new Set<string>() };
  const events: MatchEvent[] = [
    {
      type: "match_start",
      seed: 42,
      players: {
        left: { name: "methodical", kind: "bot", model: "parity", persona: "methodical" },
        right: { name: "intuitive", kind: "bot", model: "random", persona: "intuitive" },
      },
      placements: { left: LEFT, right: RIGHT },
    },
  ];

  const script: ScriptShot[] = [
    {
      side: "left",
      cell: "E5",
      say: "The hunt cell is E5. That's where a ship has to be.",
      belief: [
        { cell: "E5", p: 0.92 },
        { cell: "E6", p: 0.41 },
        { cell: "D5", p: 0.28 },
      ],
    },
    {
      side: "right",
      cell: "A3",
      say: "A3 feels like a spine. I'm not hunting, I'm confirming.",
      belief: [
        { cell: "A3", p: 0.81 },
        { cell: "B3", p: 0.33 },
        { cell: "A4", p: 0.3 },
      ],
    },
    {
      side: "left",
      cell: "E6",
      say: "E5 was a miss, so the mass shifts one cell down. E6 is the one.",
      belief: [
        { cell: "E6", p: 0.74 },
        { cell: "F5", p: 0.36 },
        { cell: "D5", p: 0.22 },
      ],
    },
    {
      side: "right",
      cell: "A4",
      say: "It runs along A. I stay on the line.",
      belief: [
        { cell: "A4", p: 0.88 },
        { cell: "A2", p: 0.4 },
        { cell: "A5", p: 0.29 },
      ],
    },
    {
      side: "left",
      cell: "F6",
      say: "Parity puts me on F6. Quiet square, high value.",
      belief: [
        { cell: "F6", p: 0.67 },
        { cell: "F5", p: 0.31 },
        { cell: "G6", p: 0.18 },
      ],
    },
    {
      side: "right",
      cell: "A2",
      say: "Still the same ship. I'm walking it home.",
      belief: [
        { cell: "A2", p: 0.9 },
        { cell: "A1", p: 0.44 },
        { cell: "A5", p: 0.2 },
      ],
    },
    {
      side: "left",
      cell: "F7",
      say: "Hit at F6 has to continue vertically. Down.",
      belief: [
        { cell: "F7", p: 0.86 },
        { cell: "F5", p: 0.48 },
        { cell: "F8", p: 0.21 },
      ],
    },
    {
      side: "right",
      cell: "A1",
      say: "One more on A and the whole thing folds.",
      belief: [
        { cell: "A1", p: 0.77 },
        { cell: "A5", p: 0.51 },
        { cell: "B1", p: 0.12 },
      ],
    },
    {
      side: "left",
      cell: "F5",
      say: "The third cell has to be F5. Cruiser, I think.",
      belief: [
        { cell: "F5", p: 0.93 },
        { cell: "F8", p: 0.14 },
        { cell: "E6", p: 0.08 },
      ],
    },
    {
      side: "right",
      cell: "A5",
      say: "Carrier. I knew it before the pegs did.",
      belief: [
        { cell: "A5", p: 0.95 },
        { cell: "B5", p: 0.11 },
        { cell: "A6", p: 0.09 },
      ],
    },
    {
      side: "left",
      illegal: { raw: "5E", reason: "transposed coordinate", attempt: 1 },
    },
    {
      side: "left",
      cell: "E5",
      say: "Returning to E5. I still don't believe that miss.",
      belief: [
        { cell: "G4", p: 0.55 },
        { cell: "E5", p: 0.4 },
        { cell: "C8", p: 0.22 },
      ],
    },
    {
      side: "right",
      cell: "E2",
      say: "E2 is sitting on something. Don't ask how.",
      belief: [
        { cell: "E2", p: 0.7 },
        { cell: "E3", p: 0.27 },
        { cell: "D2", p: 0.19 },
      ],
    },
    {
      side: "left",
      illegal: { raw: "fire the middle somewhere", reason: "unparseable", attempt: 2 },
    },
    {
      side: "left",
      cell: "C8",
      coerced: true,
      say: "C8. Forced, but it still looks empty to me.",
      belief: [
        { cell: "J6", p: 0.48 },
        { cell: "C8", p: 0.2 },
        { cell: "H3", p: 0.11 },
      ],
    },
    {
      side: "right",
      cell: "E3",
      say: "Keep going. The line wants E3.",
      belief: [
        { cell: "E3", p: 0.84 },
        { cell: "E1", p: 0.36 },
        { cell: "F2", p: 0.15 },
      ],
    },
    {
      side: "left",
      cell: "E1",
      say: "Destroyer hunt. E1 is the remaining short hull.",
      belief: [
        { cell: "E1", p: 0.61 },
        { cell: "F1", p: 0.44 },
        { cell: "E2", p: 0.1 },
      ],
    },
    {
      side: "right",
      cell: "C2",
      say: "The next spine is C. I'm already on it.",
      belief: [
        { cell: "C2", p: 0.73 },
        { cell: "C3", p: 0.41 },
        { cell: "B2", p: 0.16 },
      ],
    },
    {
      side: "left",
      cell: "F1",
      say: "And the twin cell. That's the destroyer.",
      belief: [
        { cell: "F1", p: 0.9 },
        { cell: "G1", p: 0.17 },
        { cell: "F2", p: 0.08 },
      ],
    },
  ];

  let turnIndex = 0;
  let lastSide: Side | null = null;
  for (const step of script) {
    if (step.side !== lastSide) {
      turnIndex += 1;
      events.push({ type: "turn", side: step.side, index: turnIndex });
      lastSide = step.side;
    }
    if (step.illegal) {
      events.push({
        type: "illegal",
        side: step.side,
        raw: step.illegal.raw,
        reason: step.illegal.reason,
        attempt: step.illegal.attempt,
      });
      continue;
    }
    if (!step.cell) continue;
    if (step.say && step.belief) {
      events.push({ type: "thinking", side: step.side, say: step.say, belief: step.belief });
    }
    const targetOcc = step.side === "left" ? rightOccupied : leftOccupied;
    const seen = resolved[step.side];
    const result = seen.has(step.cell)
      ? "repeat"
      : targetOcc.has(step.cell)
        ? "hit"
        : "miss";
    seen.add(step.cell);
    events.push({
      type: "shot_result",
      side: step.side,
      cell: step.cell,
      result,
      coerced: step.coerced ?? false,
    });
    if (result === "hit") {
      const fleet = step.side === "left" ? RIGHT : LEFT;
      const owner = step.side === "left" ? "right" : "left";
      for (const ship of fleet) {
        if (sunk[owner].has(ship.name)) continue;
        if (ship.cells.every((c) => resolved[step.side].has(c))) {
          sunk[owner].add(ship.name);
          events.push({ type: "sunk", side: step.side, ship: ship.name, cells: ship.cells });
        }
      }
    }
  }

  events.push({
    type: "match_end",
    winner: "right",
    turns: turnIndex,
    stats: {
      left: { shots: 0, hits: 0, misses: 0, repeats: 0, illegals: 0, coerced: 0 },
      right: { shots: 0, hits: 0, misses: 0, repeats: 0, illegals: 0, coerced: 0 },
    },
  });
  return events;
}

function occupy(ships: ShipPlacement[]): Set<string> {
  const cells = new Set<string>();
  for (const ship of ships) {
    for (const cell of ship.cells) cells.add(cell);
  }
  return cells;
}
