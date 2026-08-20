import type { MatchEvent } from "../types";

const BEATS: Record<MatchEvent["type"], number> = {
  match_start: 1.4,
  turn: 0.25,
  thinking: 1,
  shot_result: 0.85,
  sunk: 1.15,
  illegal: 0.9,
  match_abort: 0.4,
  match_end: 2.2,
};

/**
 * Incoming events wait here. The scene only sees them after the dwell for the
 * previous event. Live matches run ahead; the client never assumes turn duration.
 */
export class PacedBuffer {
  private readonly queue: MatchEvent[] = [];
  private waiting: MatchEvent | null = null;
  private due = 0;
  private ended = false;

  constructor(
    private readonly emit: (event: MatchEvent) => void,
    private readonly paceSeconds: number,
  ) {}

  push(event: MatchEvent): void {
    if (this.ended) return;
    this.queue.push(event);
  }

  pushAll(events: MatchEvent[]): void {
    for (const event of events) this.push(event);
  }

  tick(now: number): void {
    if (this.waiting && now < this.due) return;
    this.waiting = null;
    const next = this.queue.shift();
    if (!next) return;
    this.emit(next);
    this.waiting = next;
    this.due = now + BEATS[next.type] * this.paceSeconds * 1000;
    if (next.type === "match_end" || next.type === "match_abort") this.ended = true;
  }

  stop(): void {
    this.queue.length = 0;
    this.waiting = null;
    this.ended = true;
  }

  reset(): void {
    this.queue.length = 0;
    this.waiting = null;
    this.ended = false;
    this.due = 0;
  }
}
