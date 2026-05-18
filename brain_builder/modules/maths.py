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
    "Addition (up to 20)",
    "Subtraction (up to 20)",
    "Number bonds to 10",
    "Counting in 2s and 5s",
    "Comparing numbers",
    "Simple patterns",
]


def _timer_seconds(level: int) -> int:
    """Give more thinking time early, then gently increase speed challenge."""
    return {1: 90, 2: 60, 3: 45, 4: 30, 5: 20}.get(max(1, min(5, level)), 90)


def _countdown() -> None:
    spot = st.empty()
    for text in ["3", "2", "1", "Go!"]:
        spot.markdown(f'<div class="countdown">{text}</div>', unsafe_allow_html=True)
        time.sleep(0.65)
    spot.empty()


def _start(subtopic: str) -> None:
    level = database.get_difficulty("maths")
    _countdown()
    try:
        questions = claude_api.generate_maths_questions(subtopic, level)
    except Exception:
        questions = claude_api.fallback_maths(subtopic)
    st.session_state.maths_run = {
        "subtopic": subtopic,
        "level": level,
        "timer_seconds": _timer_seconds(level),
        "questions": questions,
        "idx": 0,
        "score": 0,
        "times": [],
        "feedback": None,
        "logged": False,
        "question_started": time.time(),
    }
    st.rerun()


def _finish(run: Dict[str, Any]) -> None:
    avg = sum(run["times"]) / max(1, len(run["times"]))
    stars = stars_for_score(run["score"], 5, avg)
    if not run.get("logged"):
        database.log_session("maths", run["subtopic"], run["score"], stars, run["level"])
        new_level = database.adapt_difficulty("maths", run["score"])
        run["new_level"] = new_level
        run["logged"] = True
    st.markdown("## Super maths!")
    gamify.reward_chest(stars, run["score"], 5)
    st.markdown(styles.stars_html(stars), unsafe_allow_html=True)
    st.markdown(f'<div class="brain-card friendly-text">You solved {run["score"]} out of 5. Brilliant trying! 🌟</div>', unsafe_allow_html=True)
    if st.button("Play maths again"):
        st.session_state.pop("maths_run", None)
        st.rerun()


def _show_feedback(run: Dict[str, Any]) -> None:
    feedback = run.get("feedback") or {}
    if feedback.get("correct") and st.session_state.pop("maths_balloons", False):
        st.balloons()
    mark = "✅" if feedback.get("correct") else "❌"
    color = "#E8F5E9" if feedback.get("correct") else "#FFEBEE"
    text = feedback.get("message", "Great try!")
    st.markdown(
        f"""
        <div class="brain-card" style="background:{color}; text-align:center;">
            <div style="font-size:88px;">{mark}</div>
            <div class="friendly-text">{text}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    gamify.helper_tip(feedback.get("fact", "Keep going, Number Hero!"), "🧮")
    if st.button("Next question"):
        run["idx"] += 1
        run["feedback"] = None
        run["question_started"] = time.time()
        st.rerun()


def _answer(run: Dict[str, Any], choice: str) -> None:
    question = run["questions"][run["idx"]]
    timer_seconds = int(run.get("timer_seconds", _timer_seconds(run.get("level", 1))))
    elapsed = time.time() - run.get("question_started", time.time())
    timed_out = elapsed > timer_seconds
    correct = (choice == str(question["answer"])) and not timed_out
    run["times"].append(min(elapsed, float(timer_seconds)))
    if correct:
        run["score"] += 1
        st.session_state.maths_balloons = True
        message = "Yes! Big green tick! Ding ding! 🎵"
    elif timed_out:
        message = "Almost! The timer had a little nap. Let's try the next one 💪"
    else:
        message = claude_api.kind_try_next_message()
    run["feedback"] = {"correct": correct, "message": message}
    st.rerun()


def _render_question(run: Dict[str, Any]) -> None:
    if run["idx"] >= len(run["questions"]):
        _finish(run)
        return

    if run.get("feedback"):
        _show_feedback(run)
        return

    question = run["questions"][run["idx"]]
    timer_seconds = int(run.get("timer_seconds", _timer_seconds(run.get("level", 1))))
    gamify.mission_progress(run["idx"] + 1, 5, run["score"])
    st.caption(f"Question {run['idx'] + 1} of 5")
    st.caption(f"You have {timer_seconds} seconds.")
    styles.timer_bar(timer_seconds)
    st.markdown(
        f'<div class="question-big">{question.get("emoji", "🌟")}<br>{question["question"]}</div>',
        unsafe_allow_html=True,
    )
    read_button(question["question"], key=f"maths-read-{run['idx']}")

    options = [str(option) for option in question["options"]]
    for row_start in range(0, 4, 2):
        cols = st.columns(2)
        for offset, choice in enumerate(options[row_start : row_start + 2]):
            with cols[offset]:
                if st.button(choice, key=f"maths-{run['idx']}-{choice}-{offset}"):
                    _answer(run, choice)


def render() -> None:
    st.markdown("# Mental Maths 🧮")
    gamify.adventure_header("Number Hero Mission", "⚡", "Help Captain Spark power up Number City.")
    run = st.session_state.get("maths_run")
    if run:
        _render_question(run)
        return

    styles.child_card("Pick a maths game. Then tap the big answer buttons.")
    for row_start in range(0, len(SUBTOPICS), 2):
        cols = st.columns(2)
        for offset, subtopic in enumerate(SUBTOPICS[row_start : row_start + 2]):
            with cols[offset]:
                if st.button(subtopic, key=f"maths-topic-{subtopic}"):
                    _start(subtopic)


def render() -> None:
    st.markdown("# David's Numbers 🧮")
    gamify.adventure_header("David's Number Songs", "🎵", "Count stones, sheep, and stars with careful thinking.")
    run = st.session_state.get("maths_run")
    if run:
        _render_question(run)
        return

    styles.child_card("Pick a number game. Then tap the big answer buttons.")
    for row_start in range(0, len(SUBTOPICS), 2):
        cols = st.columns(2)
        for offset, subtopic in enumerate(SUBTOPICS[row_start : row_start + 2]):
            with cols[offset]:
                if st.button(subtopic, key=f"bible-maths-topic-{subtopic}"):
                    _start(subtopic)
