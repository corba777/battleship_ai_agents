import type { Arena } from "../scene/arena";
import type { Hud } from "../hud/hud";
import type { Belief, MatchEvent, PlayerMeta, ShipPlacement, Side } from "../types";
import { opponent } from "../types";

export class Projector {
  private players: Record<Side, PlayerMeta> | null = null;
  private active: Side | null = null;
  private lastBelief: Record<Side, Belief[] | null> = { left: null, right: null };
  private sunk = { left: new Set<string>(), right: new Set<string>() };
  private shipCount = { left: 0, right: 0 };
  private placements: Record<Side, ShipPlacement[]> = { left: [], right: [] };
  private fog = false;

  constructor(
    private readonly arena: Arena,
    private readonly hud: Hud,
    private readonly seat: Side | null = null,
  ) {}

  humanTurn(): Side | null {
    if (!this.active || !this.players) return null;
    return this.players[this.active].kind === "human" ? this.active : null;
  }

  apply(event: MatchEvent): void {
    switch (event.type) {
      case "match_start":
        this.players = event.players;
        this.active = null;
        this.lastBelief = { left: null, right: null };
        this.sunk = { left: new Set(), right: new Set() };
        this.placements = event.placements;
        this.fog =
          event.players.left.kind === "human" || event.players.right.kind === "human";
        this.shipCount = {
          left: event.placements.left.length,
          right: event.placements.right.length,
        };
        this.arena.reset();
        for (const side of ["left", "right"] as const) {
          if (this.hideFleet(side)) continue;
          this.arena.placeShips(side, event.placements[side]);
        }
        this.hud.matchStart(event.players);
        this.arena.director.idle();
        break;
      case "turn":
        this.active = event.side;
        this.arena.clearHeatmaps();
        this.hud.turn(event.side);
        this.arena.focusBoard(opponent(event.side));
        break;
      case "thinking":
        this.lastBelief[event.side] = event.belief;
        this.hud.say(event.side, event.say);
        this.arena.setBelief(opponent(event.side), event.belief);
        {
          const focus = event.belief[0]?.cell;
          if (focus) this.arena.focusCell(opponent(event.side), focus);
        }
        break;
      case "shot_result": {
        const target = opponent(event.side);
        this.arena.peg(target, event.cell, event.result);
        this.arena.focusCell(target, event.cell);
        const top = this.lastBelief[event.side]?.[0]?.cell;
        const mismatch = top !== undefined && top !== event.cell;
        this.hud.shot(event.side, event.result, event.coerced, mismatch);
        if (event.result === "repeat") this.beep(140, 0.18);
        else if (event.result === "hit") this.beep(420, 0.12);
        else this.beep(220, 0.1);
        break;
      }
      case "sunk": {
        const owner = opponent(event.side);
        if (this.hideFleet(owner)) {
          this.arena.revealShip(owner, { name: event.ship, cells: event.cells });
        }
        this.arena.sink(owner, event.ship);
        this.sunk[owner].add(event.ship);
        this.beep(180, 0.35);
        if (this.sunk[owner].size >= this.shipCount[owner] && this.shipCount[owner] > 0) {
          this.arena.director.finale();
        }
        break;
      }
      case "illegal":
        this.hud.illegal(event);
        this.beep(90, 0.22);
        break;
      case "match_abort":
        this.revealHidden();
        this.hud.matchAbort(event.turns);
        break;
      case "match_end":
        this.revealHidden();
        this.hud.matchEnd(event.winner, event.turns);
        this.arena.director.finale();
        break;
    }
  }

  private hideFleet(side: Side): boolean {
    if (!this.fog) return false;
    if (this.seat) return side !== this.seat;
    return this.players?.[side]?.kind !== "human";
  }

  private revealHidden(): void {
    if (!this.fog) return;
    for (const side of ["left", "right"] as const) {
      if (!this.hideFleet(side)) continue;
      for (const ship of this.placements[side]) {
        if (this.sunk[side].has(ship.name)) continue;
        this.arena.revealShip(side, ship);
      }
    }
  }

  private beep(freq: number, seconds: number): void {
    try {
      const ctx = audio();
      if (!ctx) return;
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.frequency.value = freq;
      osc.type = "sine";
      gain.gain.value = 0.04;
      gain.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + seconds);
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.start();
      osc.stop(ctx.currentTime + seconds);
    } catch {
      // Autoplay may be blocked until a gesture; pegs and HUD still carry the beat.
    }
  }
}

let ctx: AudioContext | null = null;

export function unlockAudio(): void {
  const a = audio();
  void a?.resume();
}

function audio(): AudioContext | null {
  const Ctor = window.AudioContext || (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
  if (!Ctor) return null;
  ctx ??= new Ctor();
  return ctx;
}
