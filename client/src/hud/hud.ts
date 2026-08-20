import type { MatchEvent, PlayerMeta, Side } from "../types";

export interface HudHandles {
  mode: HTMLElement;
  left: SidePanel;
  right: SidePanel;
  shots: HTMLElement;
  hitrate: HTMLElement;
  repeats: HTMLElement;
  illegals: HTMLElement;
  schema: HTMLElement;
  illegal: HTMLElement;
  banner: HTMLElement;
}

interface SidePanel {
  root: HTMLElement;
  name: HTMLElement;
  model: HTMLElement;
  speech: HTMLElement;
  say: HTMLElement;
  tags: HTMLElement;
}

const emptyStats = () => ({ shots: 0, hits: 0, repeats: 0, illegals: 0, schema: 0 });

export class Hud {
  private readonly el: HudHandles;
  private stats = { left: emptyStats(), right: emptyStats() };
  private toastTimer = 0;

  constructor() {
    this.el = {
      mode: must("#mode"),
      left: panel("left"),
      right: panel("right"),
      shots: must("#c-shots"),
      hitrate: must("#c-hitrate"),
      repeats: must("#c-repeats"),
      illegals: must("#c-illegals"),
      schema: must("#c-schema"),
      illegal: must("#illegal"),
      banner: must("#banner"),
    };
  }

  setMode(text: string): void {
    this.el.mode.textContent = text;
  }

  reset(): void {
    this.stats = { left: emptyStats(), right: emptyStats() };
    this.el.banner.hidden = true;
    this.el.illegal.hidden = true;
    for (const side of ["left", "right"] as const) {
      this.el[side].say.textContent = "";
      this.el[side].speech.textContent = "";
      this.el[side].tags.replaceChildren();
      this.el[side].root.classList.remove("is-active");
    }
    this.paintCounters();
  }

  matchStart(players: { left: PlayerMeta; right: PlayerMeta }): void {
    this.reset();
    this.fillPlayer("left", players.left);
    this.fillPlayer("right", players.right);
  }

  turn(side: Side): void {
    this.el.left.root.classList.toggle("is-active", side === "left");
    this.el.right.root.classList.toggle("is-active", side === "right");
    this.el[side].tags.replaceChildren();
  }

  say(side: Side, text: string): void {
    this.el[side].say.textContent = text;
  }

  shot(side: Side, result: "hit" | "miss" | "repeat", coerced: boolean, mismatch: boolean): void {
    const s = this.stats[side];
    s.shots += 1;
    if (result === "hit") s.hits += 1;
    if (result === "repeat") s.repeats += 1;
    const tags: HTMLSpanElement[] = [];
    if (coerced) tags.push(tag("coerced", "coerced"));
    if (mismatch) tags.push(tag("belief ≠ shot", "mismatch"));
    if (result === "repeat") tags.push(tag("repeat", "mismatch"));
    this.el[side].tags.replaceChildren(...tags);
    this.paintCounters();
  }

  illegal(event: Extract<MatchEvent, { type: "illegal" }>): void {
    const kind = event.kind === "schema" ? "schema" : "rules";
    if (kind === "schema") this.stats[event.side].schema += 1;
    else this.stats[event.side].illegals += 1;
    this.el.illegal.hidden = false;
    this.el.illegal.classList.toggle("is-schema", kind === "schema");
    const label = kind === "schema" ? "schema" : "illegal";
    this.el.illegal.textContent = `${event.side} ${label} #${event.attempt}: ${event.reason}\n${event.raw}`;
    this.toastTimer = performance.now() + 4200;
    this.paintCounters();
  }

  matchEnd(winner: Side, turns: number): void {
    this.el.banner.hidden = false;
    this.el.banner.textContent = `${winner} wins · ${turns} turns`;
  }

  matchAbort(turns?: number): void {
    this.el.banner.hidden = false;
    this.el.banner.textContent =
      turns === undefined ? "stopped" : `stopped · ${turns} turns`;
  }

  tick(): void {
    if (!this.el.illegal.hidden && performance.now() > this.toastTimer) {
      this.el.illegal.hidden = true;
    }
  }

  private fillPlayer(side: Side, player: PlayerMeta): void {
    this.el[side].name.textContent = player.name;
    this.el[side].model.textContent = [
      player.provider && player.provider !== "vertex" ? `${player.model} · ${player.provider}` : player.model,
      player.adk ? "adk" : "",
    ]
      .filter(Boolean)
      .join(" · ");
    this.el[side].speech.textContent = player.speech === "raw-ru" ? "ru 16+" : "";
  }

  private paintCounters(): void {
    const shots = this.stats.left.shots + this.stats.right.shots;
    const hits = this.stats.left.hits + this.stats.right.hits;
    const repeats = this.stats.left.repeats + this.stats.right.repeats;
    const illegals = this.stats.left.illegals + this.stats.right.illegals;
    const schema = this.stats.left.schema + this.stats.right.schema;
    this.el.shots.textContent = String(shots);
    this.el.repeats.textContent = String(repeats);
    this.el.illegals.textContent = String(illegals);
    this.el.schema.textContent = String(schema);
    this.el.hitrate.textContent = shots === 0 ? "—" : `${Math.round((hits / shots) * 100)}%`;
  }
}

function panel(side: Side): SidePanel {
  return {
    root: must(`#panel-${side}`),
    name: must(`#name-${side}`),
    model: must(`#model-${side}`),
    speech: must(`#speech-${side}`),
    say: must(`#say-${side}`),
    tags: must(`#tags-${side}`),
  };
}

function must(selector: string): HTMLElement {
  const el = document.querySelector<HTMLElement>(selector);
  if (!el) throw new Error(`missing ${selector}`);
  return el;
}

function tag(label: string, cls: string): HTMLSpanElement {
  const span = document.createElement("span");
  span.className = `tag ${cls}`;
  span.textContent = label;
  return span;
}
