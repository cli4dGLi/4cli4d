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
    "Sequencing",
    "Arrow Paths",
    "Loops",
    "Debugging",
    "If and Then",
]

LESSONS = {
    "Sequencing": "Coding means putting steps in the right order.",
    "Arrow Paths": "A command tells a character where to move next.",
    "Loops": "A loop repeats the same step again and again.",
    "Debugging": "Debugging means finding a mistake and fixing it.",
    "If and Then": "If something happens, then the code chooses what to do.",
}


def _countdown() -> None:
    spot = st.empty()
    for text in ["3", "2", "1", "Go!"]:
        spot.markdown(f'<div class="countdown">{text}</div>', unsafe_allow_html=True)
        time.sleep(0.65)
    spot.empty()


def _start(subtopic: str) -> None:
    level = database.get_difficulty("coding")
    _countdown()
    try:
        items = claude_api.generate_coding_items(subtopic, level)
    except Exception:
        items = claude_api.fallback_coding(subtopic)
    st.session_state.coding_run = {
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
    correct = str(choice) == str(item["answer"])
    run["times"].append(elapsed)
    if correct:
        run["score"] += 1
        st.session_state.coding_balloons = True
        message = "Yes! Your code path worked!"
    else:
        message = claude_api.kind_try_next_message()
    run["feedback"] = {
        "correct": correct,
        "message": message,
        "hint": item.get("hint", "Try one step at a time."),
        "concept": item.get("concept", run["subtopic"]),
    }
    st.rerun()


def _finish(run: Dict[str, Any]) -> None:
    avg = sum(run["times"]) / max(1, len(run["times"]))
    stars = stars_for_score(run["score"], 5, avg)
    if not run.get("logged"):
        database.log_session("coding", run["subtopic"], run["score"], stars, run["level"])
        database.adapt_difficulty("coding", run["score"])
        run["logged"] = True
    st.markdown("## Code Camp complete!")
    gamify.reward_chest(stars, run["score"], 5)
    st.markdown(styles.stars_html(stars), unsafe_allow_html=True)
    styles.child_card(f"You solved {run['score']} out of 5 code puzzles. Your logic is growing!")
    if st.button("Code again"):
        st.session_state.pop("coding_run", None)
        st.rerun()


def _feedback(run: Dict[str, Any]) -> None:
    feedback = run["feedback"]
    if feedback.get("correct") and st.session_state.pop("coding_balloons", False):
        st.balloons()
    mark = "✅" if feedback.get("correct") else "⭐"
    st.markdown(
        f"""
        <div class="brain-card" style="text-align:center;">
            <div style="font-size:88px;">{mark}</div>
            <div class="friendly-text">{feedback['message']}</div>
            <hr>
            <div class="friendly-text">Code clue: {feedback['hint']}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    read_button(feedback["hint"], key=f"coding-hint-read-{run['idx']}", label="Read the clue 🔊")
    if st.button("Next code puzzle"):
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
    st.caption(f"Code puzzle {run['idx'] + 1} of 5")
    visual = item.get("visual", item.get("emoji", "🧭"))
    styles.speech_bubble(f"{visual}<br>{item['prompt']}")
    read_button(item["prompt"], key=f"coding-read-{run['idx']}")

    options = [str(option) for option in item["options"]][:4]
    while len(options) < 4:
        options.append("Try again")
    for row_start in range(0, 4, 2):
        cols = st.columns(2)
        for offset, choice in enumerate(options[row_start : row_start + 2]):
            with cols[offset]:
                if st.button(choice, key=f"coding-{run['idx']}-{row_start}-{offset}"):
                    _answer(run, choice)


def render() -> None:
    st.markdown("# Code Camp 🧭")
    gamify.adventure_header("Daniel's Code Camp", "🧭", "Build tiny programs with steps, arrows, loops, and fixes.")
    run = st.session_state.get("coding_run")
    if run:
        _render_item(run)
        return

    styles.child_card("Pick a coding game. No typing needed. Tap the best code block.")
    for row_start in range(0, len(SUBTOPICS), 2):
        cols = st.columns(2)
        for offset, subtopic in enumerate(SUBTOPICS[row_start : row_start + 2]):
            with cols[offset]:
                if st.button(subtopic, key=f"coding-topic-{subtopic}"):
                    styles.child_card(LESSONS[subtopic])
                    _start(subtopic)
