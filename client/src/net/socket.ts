import { isMatchEvent, type ClientMessage, type MatchEvent } from "../types";

export function connectSocket(
  url: string,
  onEvent: (event: MatchEvent) => void,
  onNotice?: (message: Record<string, unknown>) => void,
): { send(message: ClientMessage): void; close(): void; ready: Promise<void> } {
  const ws = new WebSocket(url);

  const ready = new Promise<void>((resolve, reject) => {
    ws.addEventListener("open", () => resolve(), { once: true });
    ws.addEventListener("error", () => reject(new Error("websocket failed")), { once: true });
  });

  ws.addEventListener("message", (msg) => {
    if (typeof msg.data !== "string") return;
    let parsed: unknown;
    try {
      parsed = JSON.parse(msg.data);
    } catch {
      return;
    }
    if (isMatchEvent(parsed)) {
      onEvent(parsed);
      return;
    }
    if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
      onNotice?.(parsed as Record<string, unknown>);
    }
  });

  return {
    send(message: ClientMessage) {
      if (ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify(message));
    },
    close() {
      ws.close();
    },
    ready,
  };
}

export function wsUrlFromPage(): string | null {
  const params = new URLSearchParams(window.location.search);
  if (params.get("fixture") === "1") return null;
  const explicit = params.get("ws") ?? import.meta.env.VITE_WS_URL ?? null;
  if (explicit) return explicit;
  if (params.get("live") !== "1") return null;
  const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
  const base = `${proto}//${window.location.host}/ws`;
  const q = new URLSearchParams();
  for (const key of [
    "left",
    "right",
    "seed",
    "persona_left",
    "persona_right",
    "speech_left",
    "speech_right",
    "model_left",
    "model_right",
    "provider_left",
    "provider_right",
    "adk_left",
    "adk_right",
    "room",
    "seat",
  ]) {
    const value = params.get(key);
    if (value) q.set(key, value);
  }
  const suffix = q.toString();
  return suffix ? `${base}?${suffix}` : base;
}

export function paceFromPage(fallback = 1.5): number {
  const raw = new URLSearchParams(window.location.search).get("pace");
  if (!raw) return fallback;
  const n = Number(raw);
  return Number.isFinite(n) && n > 0 ? n : fallback;
}
