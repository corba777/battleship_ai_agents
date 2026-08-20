export type Side = "left" | "right";

export type PlayerKind = "llm" | "bot" | "human";

export type ShotKind = "hit" | "miss" | "repeat";

export interface PlayerMeta {
  name: string;
  kind: PlayerKind;
  model: string;
  persona?: string;
  speech?: string;
  provider?: string;
  adk?: boolean;
}

export interface ShipPlacement {
  name: string;
  cells: string[];
}

export interface Belief {
  cell: string;
  p: number;
}

export type IllegalKind = "rules" | "schema";

export interface SideStats {
  shots: number;
  hits: number;
  misses: number;
  repeats: number;
  illegals: number;
  schema?: number;
  coerced: number;
}

export interface MatchStart {
  type: "match_start";
  seed: number;
  players: { left: PlayerMeta; right: PlayerMeta };
  placements: { left: ShipPlacement[]; right: ShipPlacement[] };
}

export interface Turn {
  type: "turn";
  side: Side;
  index: number;
}

export interface Thinking {
  type: "thinking";
  side: Side;
  say: string;
  belief: Belief[];
}

export interface ShotResult {
  type: "shot_result";
  side: Side;
  cell: string;
  result: ShotKind;
  coerced: boolean;
}

export interface Sunk {
  type: "sunk";
  side: Side;
  ship: string;
  cells: string[];
}

export interface Illegal {
  type: "illegal";
  side: Side;
  raw: string;
  reason: string;
  kind?: IllegalKind;
  attempt: number;
}

export interface MatchAbort {
  type: "match_abort";
  turns: number;
  reason: string;
  stats: { left: SideStats; right: SideStats };
}

export interface MatchEnd {
  type: "match_end";
  winner: Side;
  turns: number;
  stats: { left: SideStats; right: SideStats };
}

export type MatchEvent =
  | MatchStart
  | Turn
  | Thinking
  | ShotResult
  | Sunk
  | Illegal
  | MatchAbort
  | MatchEnd;

export interface HumanShot {
  type: "human_shot";
  cell: string;
  side?: Side;
}

export interface AbortMatch {
  type: "abort";
}

export interface StartMatch {
  type: "start";
  placements?: { left?: ShipPlacement[]; right?: ShipPlacement[] };
}

export type ClientMessage = HumanShot | AbortMatch | StartMatch;

export function opponent(side: Side): Side {
  return side === "left" ? "right" : "left";
}

export function isMatchEvent(value: unknown): value is MatchEvent {
  if (typeof value !== "object" || value === null) return false;
  const type = (value as { type?: unknown }).type;
  return (
    type === "match_start" ||
    type === "turn" ||
    type === "thinking" ||
    type === "shot_result" ||
    type === "sunk" ||
    type === "illegal" ||
    type === "match_abort" ||
    type === "match_end"
  );
}
