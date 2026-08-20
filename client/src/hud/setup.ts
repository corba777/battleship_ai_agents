export const SPEECH_PROFILES = ["standard", "raw-ru"] as const;
export type SpeechProfile = (typeof SPEECH_PROFILES)[number];

export const PERSONAS = ["methodical", "intuitive"] as const;
export type Persona = (typeof PERSONAS)[number];

export const FLEET_MODES = ["manual", "random"] as const;
export type FleetMode = (typeof FLEET_MODES)[number];

type ProviderId =
  | "vertex"
  | "anthropic"
  | "openai"
  | "gemini"
  | "ollama"
  | "human"
  | "parity"
  | "random"
  | "occupancy";

interface ProviderInfo {
  ok: boolean;
  label: string;
  hint: string;
  default?: string;
  models?: string[];
}

interface Catalog {
  providers: Record<string, ProviderInfo>;
}

const FALLBACK: Catalog = {
  providers: {
    vertex: {
      ok: true,
      label: "Vertex AI",
      hint: "default",
      default: "gemini-3.5-flash-lite",
      models: [
        "gemini-3.5-flash-lite",
        "gemini-3.5-flash",
        "gemini-3.7-flash",
        "claude-opus-4-6",
      ],
    },
    anthropic: {
      ok: false,
      label: "Anthropic",
      hint: "no key",
      default: "claude-sonnet-5",
      models: ["claude-sonnet-5", "claude-opus-5"],
    },
    openai: {
      ok: false,
      label: "OpenAI",
      hint: "no key",
      default: "gpt-5.4-nano",
      models: ["gpt-5.4-nano", "gpt-5.6-luna", "gpt-5.6-sol"],
    },
    gemini: {
      ok: false,
      label: "Gemini API",
      hint: "no key",
      default: "gemini-3.5-flash-lite",
      models: ["gemini-3.5-flash-lite", "gemini-3.5-flash", "gemini-3.7-flash"],
    },
    ollama: {
      ok: true,
      label: "Ollama",
      hint: "http://localhost:11434",
      default: "llama3.1",
      models: ["llama3.1"],
    },
  },
};

const LLM_PROVIDERS: ProviderId[] = ["vertex", "anthropic", "openai", "gemini", "ollama"];

export function attachSetup(onFixture: () => void, startHidden = false): void {
  const root = document.querySelector<HTMLElement>("#setup");
  if (!root) return;
  root.hidden = startHidden;
  void boot(root, onFixture);
}

export function showSetup(): void {
  const root = document.querySelector<HTMLElement>("#setup");
  if (root) root.hidden = false;
}

async function boot(root: HTMLElement, onFixture: () => void): Promise<void> {
  const catalog = await loadCatalog();
  disableMissingProviders(root, catalog);
  const params = new URLSearchParams(window.location.search);
  const left = bindSlot(root, catalog, "left", params, "vertex", "methodical", "gemini-3.5-flash-lite");
  const right = bindSlot(root, catalog, "right", params, "vertex", "intuitive", "claude-opus-4-6");
  const seed = root.querySelector<HTMLInputElement>("#setup-seed");
  if (seed && params.get("seed")) seed.value = params.get("seed") ?? seed.value;
  const hint = root.querySelector<HTMLElement>("#setup-human-hint");
  const roomBox = root.querySelector<HTMLElement>("#setup-room");
  const roomUrl = root.querySelector<HTMLInputElement>("#setup-room-url");
  const roomCodeEl = root.querySelector<HTMLElement>("#setup-room-code");
  let roomCode = params.get("room")?.toUpperCase() || newRoomCode();
  let hostSeat: "left" | "right" = params.get("seat") === "right" ? "right" : "left";
  let forcedManual = false;
  let firstHuman: "left" | "right" | null =
    params.get("left") === "human" && params.get("right") !== "human"
      ? "left"
      : params.get("right") === "human" && params.get("left") !== "human"
        ? "right"
        : params.get("seat") === "right"
          ? "right"
          : params.get("left") === "human"
            ? "left"
            : null;

  const paintHuman = () => {
    const l = left.providerId() === "human";
    const r = right.providerId() === "human";
    if (l && !r) firstHuman = "left";
    else if (r && !l) firstHuman = "right";
    else if (!l && !r) firstHuman = null;
    const both = l && r;
    if (hint) {
      hint.hidden = !l && !r;
      hint.textContent = both
        ? "Human vs human: share the guest URL. Each player places their own fleet. Fog of war."
        : "You place your fleet. The AI board is fogged — hunt by clicking, watch it miss yours.";
    }
    if (roomBox) roomBox.hidden = !both;
    if (both) {
      hostSeat = firstHuman ?? "left";
      if (!forcedManual) {
        left.setFleet("manual");
        right.setFleet("manual");
        forcedManual = true;
      }
      paintRoomUrl();
    } else {
      forcedManual = false;
    }
  };
  const paintRoomUrl = () => {
    const guest = hostSeat === "left" ? "right" : "left";
    if (roomCodeEl) roomCodeEl.textContent = roomCode;
    if (roomUrl) {
      const q = new URLSearchParams({
        live: "1",
        left: "human",
        right: "human",
        room: roomCode,
        seat: guest,
        place_left: "manual",
        place_right: "manual",
        seed: seed?.value.trim() || "1",
      });
      roomUrl.value = `${window.location.origin}/?${q.toString()}`;
    }
  };
  paintHuman();
  root.querySelector("#setup-left")?.addEventListener("change", paintHuman);
  root.querySelector("#setup-right")?.addEventListener("change", paintHuman);
  seed?.addEventListener("input", () => {
    if (left.providerId() === "human" && right.providerId() === "human") paintRoomUrl();
  });
  root.querySelector("#setup-room-copy")?.addEventListener("click", () => {
    if (roomUrl?.value) void navigator.clipboard.writeText(roomUrl.value);
  });

  root.querySelector("#setup-live")?.addEventListener("click", () => {
    const both = left.providerId() === "human" && right.providerId() === "human";
    const q = new URLSearchParams({
      live: "1",
      left: left.player(),
      right: right.player(),
      persona_left: left.persona(),
      persona_right: right.persona(),
      speech_left: left.speech(),
      speech_right: right.speech(),
      seed: seed?.value.trim() || "1",
    });
    const leftProvider = left.provider();
    const rightProvider = right.provider();
    if (leftProvider) q.set("provider_left", leftProvider);
    if (rightProvider) q.set("provider_right", rightProvider);
    if (left.providerId() === "human") q.set("place_left", both ? "manual" : left.fleet());
    if (right.providerId() === "human") q.set("place_right", both ? "manual" : right.fleet());
    if (both) {
      q.set("room", roomCode);
      q.set("seat", hostSeat);
    }
    window.location.search = q.toString();
  });
  root.querySelector("#setup-fixture")?.addEventListener("click", () => {
    root.hidden = true;
    onFixture();
  });
}

async function loadCatalog(): Promise<Catalog> {
  try {
    const res = await fetch("/catalog");
    if (!res.ok) return FALLBACK;
    return (await res.json()) as Catalog;
  } catch {
    return FALLBACK;
  }
}

function disableMissingProviders(root: HTMLElement, catalog: Catalog): void {
  for (const select of root.querySelectorAll<HTMLSelectElement>("select[id^='setup-']")) {
    if (select.id.endsWith("-model")) continue;
    for (const opt of select.options) {
      const info = catalog.providers[opt.value];
      if (!info) continue;
      if (info.ok === false) {
        opt.disabled = true;
        opt.label = `${info.label} · ${info.hint}`;
      }
    }
  }
}

function bindSlot(
  root: HTMLElement,
  catalog: Catalog,
  side: "left" | "right",
  params: URLSearchParams,
  defaultProvider: ProviderId,
  defaultPersona: Persona,
  defaultModel?: string,
) {
  const providerSelect = root.querySelector<HTMLSelectElement>(`#setup-${side}`);
  const modelSelect = root.querySelector<HTMLSelectElement>(`#setup-${side}-model`);
  const llmBox = root.querySelector<HTMLElement>(`[data-llm="${side}"]`);
  const extras = root.querySelector<HTMLElement>(`[data-extras="${side}"]`);
  const placeBox = root.querySelector<HTMLElement>(`[data-place="${side}"]`);
  const initial = parseInitial(
    params.get(side),
    params.get(`provider_${side}`),
    defaultProvider,
  );
  if (!initial.model && defaultModel) initial.model = defaultModel;
  if (providerSelect) {
    const info = catalog.providers[initial.provider];
    providerSelect.value = info && info.ok === false ? defaultProvider : initial.provider;
  }

  const fillModels = () => {
    if (!modelSelect || !providerSelect) return;
    const provider = providerSelect.value as ProviderId;
    const llm = LLM_PROVIDERS.includes(provider);
    if (llmBox) llmBox.hidden = !llm;
    if (extras) extras.hidden = provider === "human";
    if (placeBox) placeBox.hidden = provider !== "human";
    if (!llm) return;
    const family = catalog.providers[provider];
    const models = family?.models ?? [];
    modelSelect.replaceChildren();
    for (const id of models) {
      const opt = document.createElement("option");
      opt.value = id;
      opt.textContent = id;
      modelSelect.append(opt);
    }
    const wanted =
      initial.provider === provider && initial.model ? initial.model : family?.default;
    const fallback = family?.default ?? models[0];
    modelSelect.value = wanted && models.includes(wanted) ? wanted : fallback ?? "";
  };

  providerSelect?.addEventListener("change", fillModels);
  fillModels();

  const persona = bindToggle<Persona>(
    root,
    side,
    "persona",
    params.get(`persona_${side}`) === "intuitive" ? "intuitive" : defaultPersona,
  );
  const speech = bindToggle<SpeechProfile>(
    root,
    side,
    "speech",
    params.get(`speech_${side}`) === "raw-ru" ? "raw-ru" : "standard",
  );
  const fleet = bindToggle<FleetMode>(
    root,
    side,
    "fleet",
    params.get(`place_${side}`) === "random" ? "random" : "manual",
  );

  return {
    player: () => {
      const provider = (providerSelect?.value ?? defaultProvider) as ProviderId;
      if (LLM_PROVIDERS.includes(provider)) {
        return modelSelect?.value || catalog.providers[provider]?.default || provider;
      }
      return provider;
    },
    persona: persona.get,
    speech: speech.get,
    fleet: fleet.get,
    setFleet: fleet.set,
    provider: () => {
      const provider = (providerSelect?.value ?? defaultProvider) as ProviderId;
      return LLM_PROVIDERS.includes(provider) ? provider : null;
    },
    providerId: () => (providerSelect?.value ?? defaultProvider) as ProviderId,
  };
}

function parseInitial(
  raw: string | null,
  providerParam: string | null,
  fallback: ProviderId,
): { provider: ProviderId; model?: string } {
  if (providerParam && LLM_PROVIDERS.includes(providerParam as ProviderId)) {
    const parsed: { provider: ProviderId; model?: string } = {
      provider: providerParam as ProviderId,
    };
    if (raw && !["gemini", "claude", "opus", "openai", "ollama"].includes(raw)) parsed.model = raw;
    return parsed;
  }
  if (!raw || raw === "gemini" || raw === "claude" || raw === "opus") {
    return { provider: fallback };
  }
  if (raw === "parity" || raw === "random" || raw === "occupancy" || raw === "human") return { provider: raw };
  if (raw === "openai") return { provider: "openai" };
  if (raw === "ollama") return { provider: "ollama" };
  if (raw.includes(":")) return { provider: "ollama", model: raw };
  if (raw.startsWith("gpt-") || /^o[0-9]/.test(raw)) {
    return { provider: "openai", model: raw };
  }
  if (raw.startsWith("gemini")) return { provider: "vertex", model: raw };
  if (raw.startsWith("claude-sonnet-5") || raw.startsWith("claude-opus-5")) {
    return { provider: "anthropic", model: raw };
  }
  if (raw.startsWith("claude")) return { provider: "vertex", model: raw };
  return { provider: fallback };
}

function bindToggle<T extends string>(
  root: HTMLElement,
  side: "left" | "right",
  attr: string,
  initial: T,
): { get: () => T; set: (value: T) => void } {
  const buttons = [...root.querySelectorAll<HTMLButtonElement>(`[data-side="${side}"][data-${attr}]`)];
  let current = initial;
  const paint = () => {
    for (const btn of buttons) {
      btn.classList.toggle("is-on", btn.dataset[attr] === current);
    }
  };
  for (const btn of buttons) {
    btn.addEventListener("click", () => {
      const next = btn.dataset[attr];
      if (next) current = next as T;
      paint();
    });
  }
  paint();
  return {
    get: () => current,
    set: (value: T) => {
      current = value;
      paint();
    },
  };
}

function newRoomCode(): string {
  const chars = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789";
  let out = "";
  for (let i = 0; i < 4; i++) out += chars[Math.floor(Math.random() * chars.length)];
  return out;
}
