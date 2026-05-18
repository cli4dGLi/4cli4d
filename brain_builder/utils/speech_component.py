from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import streamlit as st
import streamlit.components.v1 as components


COMPONENT_DIR = Path(__file__).parent / "speech_component_frontend"

speech_recognition_component = components.declare_component(
    "brain_builder_speech_recognition",
    path=str(COMPONENT_DIR),
)


def speech_recognizer(*, key: str, seconds: int = 30, prompt: str = "Press the microphone and read.") -> Dict[str, Any]:
    value = speech_recognition_component(
        key=key,
        seconds=seconds,
        prompt=prompt,
        default={"transcript": "", "listening": False, "done": False, "elapsedMs": 0},
    )
    if not isinstance(value, dict):
        return {"transcript": "", "listening": False, "done": False, "elapsedMs": 0}
    transcript = str(value.get("transcript", ""))[:2000]
    return {
        "transcript": transcript,
        "listening": bool(value.get("listening", False)),
        "done": bool(value.get("done", False)),
        "elapsedMs": int(value.get("elapsedMs") or 0),
    }


def privacy_notice() -> None:
    st.info(
        "Voice assessment is processed in your browser. No audio recordings are stored anywhere. "
        "Only the text of what OB reads is analysed. You can turn off microphone access in your browser settings at any time."
    )
