from __future__ import annotations

import json
from uuid import uuid4

import streamlit as st
import streamlit.components.v1 as components


def speak_text(text: str, *, key: str | None = None, rate: float = 0.82) -> None:
    safe_text = json.dumps(text)
    element_id = f"tts-{key or uuid4().hex}"
    components.html(
        f"""
        <div id="{element_id}"></div>
        <script>
        const text = {safe_text};
        const utterance = new SpeechSynthesisUtterance(text);
        utterance.lang = "en-GB";
        utterance.rate = {rate};
        utterance.pitch = 1.05;
        window.speechSynthesis.cancel();
        window.speechSynthesis.speak(utterance);
        </script>
        """,
        height=0,
    )


def read_button(text: str, *, key: str, label: str = "Read to me 🔊") -> None:
    if st.button(label, key=key):
        speak_text(text, key=key)
