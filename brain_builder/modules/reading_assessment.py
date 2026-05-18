from __future__ import annotations

import json
from typing import Any, Dict

import streamlit as st

import claude_api
import database
from utils import gamify
from utils import styles
from utils.scoring import running_record_level, wpm_band
from utils.speech_component import privacy_notice, speech_recognizer
from utils.tts import read_button


def ensure_passages() -> None:
    if database.count_passages() >= 30:
        return
    try:
        passages = claude_api.generate_passage_library()
    except Exception:
        passages = claude_api.fallback_passages()
    database.save_passages(passages)


def _pin_gate_for_notice() -> bool:
    if database.get_setting("voice_notice_ack", "false") == "true":
        return True
    st.markdown("### Parent check")
    pin = st.text_input("Enter parent PIN to use voice reading", type="password", max_chars=4, key="voice-pin")
    if pin == database.get_parent_pin():
        privacy_notice()
        if st.button("I understand"):
            database.set_setting("voice_notice_ack", "true")
            st.rerun()
    elif pin:
        st.warning("Please ask a grown-up to try again.")
    return False


def _select_passage() -> Dict[str, Any] | None:
    ensure_passages()
    difficulty = st.radio(
        "Reading level",
        ["starter", "developing", "fluent"],
        index=0,
        horizontal=True,
        key="reading-difficulty",
    )
    passages = database.get_passages(difficulty)
    if not passages:
        return None
    labels = [f"{row['id']}: {row['text'][:52]}..." if len(row["text"]) > 52 else f"{row['id']}: {row['text']}" for row in passages]
    choice = st.selectbox("Pick a passage", labels, key="reading-passage")
    passage_id = int(choice.split(":", 1)[0])
    row = database.get_passage(passage_id)
    return dict(row) if row else None


def _star_count(accuracy: float, comprehension_score: int) -> int:
    if accuracy >= 95 and comprehension_score:
        return 3
    if accuracy >= 90:
        return 2
    return 1


def _parent_results(result: Dict[str, Any]) -> None:
    with st.expander("Parent reading details"):
        pin = st.text_input("Parent PIN", type="password", max_chars=4, key="reading-parent-pin")
        if pin == database.get_parent_pin():
            assessment = result["assessment"]
            col1, col2, col3 = st.columns(3)
            col1.metric("Accuracy", f"{assessment['accuracy_pct']:.1f}%")
            col2.metric("Running record", running_record_level(float(assessment["accuracy_pct"])))
            col3.metric("WPM", f"{result['wpm']:.1f}", wpm_band(result["wpm"]))
            st.write("Error types")
            st.json(assessment.get("error_types_summary", {}))
            st.write("Phonics strengths")
            st.write(", ".join(assessment.get("phonics_patterns_strong", [])) or "No pattern yet")
            st.write("Phonics to practise")
            st.write(", ".join(assessment.get("phonics_patterns_weak", [])) or "Keep building")
            st.write("Comprehension")
            st.write(result.get("comprehension_note", ""))
        elif pin:
            st.warning("Please ask a grown-up to try again.")


def render(context_key: str = "english") -> None:
    st.markdown("## Read to Me 🎙️")
    gamify.adventure_header("Read-Aloud Stage", "🎙️", "Book Buddy listens for brave reading.")
    if not _pin_gate_for_notice():
        return

    result_key = f"{context_key}_reading_result"
    pending_key = f"{context_key}_reading_pending"
    active_key = f"{context_key}_reading_active"

    if result_key in st.session_state:
        result = st.session_state[result_key]
        assessment = result["assessment"]
        gamify.reward_chest(result["stars"], result["stars"], 3)
        st.markdown(styles.stars_html(result["stars"]), unsafe_allow_html=True)
        styles.child_card(assessment.get("encouragement", "You read beautifully! 🌟"))
        _parent_results(result)
        if st.button("Try another passage", key=f"{context_key}-new-reading"):
            for key in [result_key, pending_key, active_key]:
                st.session_state.pop(key, None)
            st.rerun()
        return

    if pending_key in st.session_state:
        pending = st.session_state[pending_key]
        question = pending["assessment"]["comprehension_question"]
        st.markdown("### One little question")
        styles.speech_bubble(question)
        read_button(question, key=f"{context_key}-comp-read")
        value = speech_recognizer(key=f"{context_key}-comp-mic", seconds=15, prompt="Answer the question.")
        if value.get("listening"):
            st.markdown('<span class="mic-dot"></span> Listening now', unsafe_allow_html=True)
        if value.get("transcript"):
            st.success("I heard your answer.")
        if value.get("transcript") and st.button("Score my answer", key=f"{context_key}-score-comp"):
            comp = claude_api.score_comprehension(pending["passage_text"], question, value["transcript"])
            assessment = pending["assessment"]
            elapsed_seconds = max(1.0, pending.get("elapsed_ms", 0) / 1000)
            wpm = (pending["word_count"] / elapsed_seconds) * 60
            stars = _star_count(float(assessment["accuracy_pct"]), int(comp["score"]))
            database.log_reading_assessment(
                pending["passage_id"],
                pending["difficulty"],
                float(assessment["accuracy_pct"]),
                str(assessment["reading_level"]),
                dict(assessment.get("error_types_summary", {})),
                list(assessment.get("phonics_patterns_strong", [])),
                list(assessment.get("phonics_patterns_weak", [])),
                int(comp["score"]),
                float(wpm),
            )
            st.session_state[result_key] = {
                "assessment": assessment,
                "stars": stars,
                "wpm": wpm,
                "comprehension_note": comp.get("note", ""),
            }
            st.session_state.pop(pending_key, None)
            st.session_state.pop(active_key, None)
            st.rerun()
        return

    if active_key not in st.session_state:
        passage = _select_passage()
        if not passage:
            st.info("Let's try again! 🔄")
            return
        st.markdown(
            f"""
            <div class="brain-card" style="font-size:28px; line-height:2; font-weight:900;">
            {passage['text']}
            </div>
            """,
            unsafe_allow_html=True,
        )
        read_button(passage["text"], key=f"{context_key}-passage-read", label="Read passage to me 🔊")
        if st.button("Start reading check", key=f"{context_key}-start-reading"):
            st.session_state[active_key] = {
                "passage_id": passage["id"],
                "difficulty": passage["difficulty"],
                "text": passage["text"],
                "word_count": passage["word_count"],
            }
            st.rerun()
        return

    active = st.session_state[active_key]
    st.markdown(
        f"""
        <div class="brain-card" style="font-size:28px; line-height:2; font-weight:900;">
        {active['text']}
        </div>
        """,
        unsafe_allow_html=True,
    )
    value = speech_recognizer(key=f"{context_key}-reading-mic", seconds=30, prompt="Press start and read the passage.")
    if value.get("listening"):
        st.markdown('<span class="mic-dot"></span> Listening now', unsafe_allow_html=True)
    if value.get("transcript"):
        st.success("I heard your reading.")
    if value.get("transcript") and st.button("Check my reading", key=f"{context_key}-check-reading"):
        assessment = claude_api.assess_reading(active["text"], value["transcript"])
        st.session_state[pending_key] = {
            "assessment": assessment,
            "passage_id": active["passage_id"],
            "difficulty": active["difficulty"],
            "passage_text": active["text"],
            "word_count": active["word_count"],
            "elapsed_ms": value.get("elapsedMs", 0),
        }
        st.rerun()
