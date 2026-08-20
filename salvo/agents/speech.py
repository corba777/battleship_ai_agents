from __future__ import annotations

from pathlib import Path
from typing import Literal

PROMPTS = Path(__file__).resolve().parent / "prompts" / "speech"

SPEECH_PROFILES = ("standard", "raw-ru")
SpeechProfile = Literal["standard", "raw-ru"]

SPEECH_LABELS: dict[str, str] = {
    "standard": "STANDARD",
    "raw-ru": "PROFANE RUSSIAN (16+)",
}


def is_speech_profile(value: object) -> bool:
    return isinstance(value, str) and value in SPEECH_PROFILES


def pick_speech(value: str | None = None) -> SpeechProfile:
    if is_speech_profile(value):
        return value  # type: ignore[return-value]
    if value in (None, ""):
        return "standard"
    raise ValueError(f"unknown speech: {value}")


def load_speech(profile: SpeechProfile) -> str:
    if profile == "standard":
        return ""
    path = PROMPTS / f"{profile}.md"
    if not path.is_file():
        raise FileNotFoundError(f"unknown speech overlay: {profile}")
    return path.read_text(encoding="utf-8").strip()


def compose_system(persona_prompt: str, profile: SpeechProfile) -> str:
    overlay = load_speech(profile)
    if not overlay:
        return persona_prompt
    return f"{persona_prompt}\n\n{overlay}"
