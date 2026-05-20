from __future__ import annotations

import re
import time
from typing import Any, Dict, List

import streamlit as st

import claude_api
import database
from modules import reading_assessment
from utils import gamify
from utils import styles
from utils.scoring import stars_for_score
from utils.tts import read_button


SUBTOPICS = [
    "Phonics",
    "Sight words",
    "Word pictures",
    "Sentence builder",
    "Read-aloud comprehension",
    "Read to Me",
]


def _normalise(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower().replace(".", ""))


def _countdown() -> None:
    spot = st.empty()
    for text in ["3", "2", "1", "Go!"]:
        spot.markdown(f'<div class="countdown">{text}</div>', unsafe_allow_html=True)
        time.sleep(0.65)
    spot.empty()


def _start(task_type: str) -> None:
    level = database.get_difficulty("english")
    _countdown()
    try:
        items = claude_api.generate_english_items(task_type)
    except Exception:
        items = claude_api.fallback_english(task_type)
    st.session_state.english_run = {
        "task_type": task_type,
        "level": level,
        "items": items,
        "idx": 0,
        "score": 0,
        "times": [],
        "feedback": None,
        "logged": False,
        "selected_words": [],
        "question_started": time.time(),
    }
    st.rerun()


def _answer(run: Dict[str, Any], choice: str) -> None:
    item = run["items"][run["idx"]]
    elapsed = time.time() - run.get("question_started", time.time())
    correct = _normalise(choice) == _normalise(str(item["answer"]))
    run["times"].append(elapsed)
    if correct:
        run["score"] += 1
        st.session_state.english_balloons = True
        message = "Yes! You found it! Sparkle sound! 🎵"
    else:
        message = claude_api.kind_try_next_message()
    run["feedback"] = {"correct": correct, "message": message}
    st.rerun()


def _finish(run: Dict[str, Any]) -> None:
    avg = sum(run["times"]) / max(1, len(run["times"]))
    stars = stars_for_score(run["score"], 5, avg)
    if not run.get("logged"):
        database.log_session("english", run["task_type"], run["score"], stars, run["level"])
        database.adapt_difficulty("english", run["score"])
        run["logged"] = True
    st.markdown("## Reading stars!")
    gamify.reward_chest(stars, run["score"], 5)
    st.markdown(styles.stars_html(stars), unsafe_allow_html=True)
    styles.child_card(f"You read {run['score']} out of 5 scroll words. Joyful reading! 🌟")
    if st.button("Play reading again"):
        st.session_state.pop("english_run", None)
        st.rerun()


def _feedback(run: Dict[str, Any]) -> None:
    if run["feedback"].get("correct") and st.session_state.pop("english_balloons", False):
        st.balloons()
    mark = "✅" if run["feedback"].get("correct") else "❌"
    st.markdown(
        f"""
        <div class="brain-card" style="text-align:center;">
            <div style="font-size:88px;">{mark}</div>
            <div class="friendly-text">{run['feedback']['message']}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    gamify.helper_tip("Esther says every try grows your reading wisdom.", "📖")
    if st.button("Next"):
        run["idx"] += 1
        run["feedback"] = None
        run["selected_words"] = []
        run["question_started"] = time.time()
        st.rerun()


def _sentence_builder(run: Dict[str, Any], item: Dict[str, Any]) -> None:
    selected: List[str] = run.setdefault("selected_words", [])
    st.markdown(
        f'<div class="brain-card friendly-text">Your sentence: {" ".join(selected) or "Tap the words in order to make a clear sentence."}</div>',
        unsafe_allow_html=True,
    )
    options = [str(option) for option in item["options"]]
    cols = st.columns(max(1, len(options)))
    for index, word in enumerate(options):
        with cols[index]:
            if st.button(word, key=f"eng-word-{run['idx']}-{index}-{len(selected)}"):
                selected.append(word)
                st.rerun()
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Clear"):
            run["selected_words"] = []
            st.rerun()
    with c2:
        if st.button("Check sentence"):
            _answer(run, " ".join(selected))


def _render_item(run: Dict[str, Any]) -> None:
    if run["idx"] >= len(run["items"]):
        _finish(run)
        return
    if run.get("feedback"):
        _feedback(run)
        return

    item = run["items"][run["idx"]]
    gamify.mission_progress(run["idx"] + 1, 5, run["score"])
    st.caption(f"Question {run['idx'] + 1} of 5")
    styles.speech_bubble(item["prompt"])
    read_button(item["prompt"], key=f"eng-read-{run['idx']}")
    if item.get("hint"):
        st.caption(f"Hint: {item['hint']}")

    if run["task_type"] == "Sentence builder":
        _sentence_builder(run, item)
        return

    options = [str(option) for option in item["options"]]
    for row_start in range(0, 4, 2):
        cols = st.columns(2)
        for offset, choice in enumerate(options[row_start : row_start + 2]):
            with cols[offset]:
                if st.button(choice, key=f"eng-{run['idx']}-{row_start}-{offset}"):
                    _answer(run, choice)


def render() -> None:
    st.markdown("# Reading Scrolls 📖")
    gamify.adventure_header("Esther's Reading Scrolls", "📖", "Listen for sounds, find words, and understand kind stories.")
    if st.session_state.get("english_topic") == "Read to Me":
        reading_assessment.render("english")
        if st.button("Back to reading scrolls"):
            st.session_state.pop("english_topic", None)
            st.rerun()
        return

    run = st.session_state.get("english_run")
    if run:
        _render_item(run)
        return

    styles.child_card("Pick a reading game. Tap, listen, and play.")
    for row_start in range(0, len(SUBTOPICS), 2):
        cols = st.columns(2)
        for offset, topic in enumerate(SUBTOPICS[row_start : row_start + 2]):
            with cols[offset]:
                if st.button(topic, key=f"bible-english-topic-{topic}"):
                    if topic == "Read to Me":
                        st.session_state.english_topic = topic
                        st.rerun()
                    else:
                        _start(topic)
