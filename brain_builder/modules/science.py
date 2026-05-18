from __future__ import annotations

import time
from typing import Any, Dict

import streamlit as st

import claude_api
import database
from utils import gamify
from utils import styles
from utils.scoring import stars_for_score
from utils.tts import read_button


SUBTOPICS = [
    "Natural Science",
    "Physics",
    "Geography",
    "Geometry",
    "Science Facts",
    "Science History",
    "World History",
]


def _countdown() -> None:
    spot = st.empty()
    for text in ["3", "2", "1", "Go!"]:
        spot.markdown(f'<div class="countdown">{text}</div>', unsafe_allow_html=True)
        time.sleep(0.65)
    spot.empty()


def _start(subtopic: str) -> None:
    level = database.get_difficulty("science")
    _countdown()
    try:
        items = claude_api.generate_science_items(subtopic, level)
    except Exception:
        items = claude_api.fallback_science(subtopic)
    st.session_state.science_run = {
        "subtopic": subtopic,
        "level": level,
        "items": items,
        "idx": 0,
        "score": 0,
        "times": [],
        "feedback": None,
        "logged": False,
        "question_started": time.time(),
    }
    st.rerun()


def _answer(run: Dict[str, Any], choice: str) -> None:
    item = run["items"][run["idx"]]
    elapsed = time.time() - run.get("question_started", time.time())
    correct = choice == str(item["answer"])
    run["times"].append(elapsed)
    if correct:
        run["score"] += 1
        st.session_state.science_balloons = True
        message = "Yes! Your brain found it! Sparkle sound!"
    else:
        message = claude_api.kind_try_next_message()
    run["feedback"] = {
        "correct": correct,
        "message": message,
        "fact": item.get("fact", "You learned something new today."),
    }
    st.rerun()


def _finish(run: Dict[str, Any]) -> None:
    avg = sum(run["times"]) / max(1, len(run["times"]))
    stars = stars_for_score(run["score"], 5, avg)
    if not run.get("logged"):
        database.log_session("science", run["subtopic"], run["score"], stars, run["level"])
        database.adapt_difficulty("science", run["score"])
        run["logged"] = True
    st.markdown("## Wonder Lab complete!")
    gamify.reward_chest(stars, run["score"], 5)
    st.markdown(styles.stars_html(stars), unsafe_allow_html=True)
    styles.child_card(f"You got {run['score']} out of 5. Curious thinking! 🌟")
    if st.button("Explore again"):
        st.session_state.pop("science_run", None)
        st.rerun()


def _feedback(run: Dict[str, Any]) -> None:
    feedback = run["feedback"]
    if feedback.get("correct") and st.session_state.pop("science_balloons", False):
        st.balloons()
    mark = "✅" if feedback.get("correct") else "⭐"
    st.markdown(
        f"""
        <div class="brain-card" style="text-align:center;">
            <div style="font-size:88px;">{mark}</div>
            <div class="friendly-text">{feedback['message']}</div>
            <hr>
            <div class="friendly-text">Did you know? {feedback['fact']}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    read_button(feedback["fact"], key=f"science-fact-read-{run['idx']}", label="Read the fact 🔊")
    if st.button("Next wonder"):
        run["idx"] += 1
        run["feedback"] = None
        run["question_started"] = time.time()
        st.rerun()


def _render_item(run: Dict[str, Any]) -> None:
    if run["idx"] >= len(run["items"]):
        _finish(run)
        return
    if run.get("feedback"):
        _feedback(run)
        return

    item = run["items"][run["idx"]]
    gamify.mission_progress(run["idx"] + 1, 5, run["score"])
    st.caption(f"Wonder {run['idx'] + 1} of 5")
    styles.speech_bubble(f"{item.get('emoji', '🌟')}<br>{item['prompt']}")
    read_button(item["prompt"], key=f"science-read-{run['idx']}")

    options = [str(option) for option in item["options"]]
    for row_start in range(0, 4, 2):
        cols = st.columns(2)
        for offset, choice in enumerate(options[row_start : row_start + 2]):
            with cols[offset]:
                if st.button(choice, key=f"science-{run['idx']}-{row_start}-{offset}"):
                    _answer(run, choice)


def render() -> None:
    st.markdown("# Wonder Lab 🔬")
    gamify.adventure_header("Wonder Lab", "🔬", "Drip the Scientist has facts, places, shapes, and history to discover.")
    run = st.session_state.get("science_run")
    if run:
        _render_item(run)
        return

    styles.child_card("Pick a wonder topic. Learn facts, places, shapes, and history.")
    for row_start in range(0, len(SUBTOPICS), 2):
        cols = st.columns(2)
        for offset, subtopic in enumerate(SUBTOPICS[row_start : row_start + 2]):
            with cols[offset]:
                if st.button(subtopic, key=f"science-topic-{subtopic}"):
                    _start(subtopic)
