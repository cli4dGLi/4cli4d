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


def _countdown() -> None:
    spot = st.empty()
    for text in ["3", "2", "1", "Go!"]:
        spot.markdown(f'<div class="countdown">{text}</div>', unsafe_allow_html=True)
        time.sleep(0.65)
    spot.empty()


def _start() -> None:
    level = database.get_difficulty("wordproblems")
    _countdown()
    try:
        problems = claude_api.generate_word_problems(level)
    except Exception:
        problems = claude_api.fallback_word_problems()
    st.session_state.word_run = {
        "level": level,
        "problems": problems,
        "idx": 0,
        "score": 0,
        "times": [],
        "feedback": None,
        "logged": False,
        "question_started": time.time(),
    }
    st.rerun()


def _answer(run: Dict[str, Any], choice: str) -> None:
    problem = run["problems"][run["idx"]]
    elapsed = time.time() - run.get("question_started", time.time())
    correct = choice == str(problem["answer"])
    run["times"].append(elapsed)
    if correct:
        run["score"] += 1
        st.session_state.word_balloons = True
        message = "You solved the story! Happy sparkle sound! 🎵"
    else:
        message = claude_api.kind_try_next_message()
    run["feedback"] = {"correct": correct, "message": message}
    st.rerun()


def _finish(run: Dict[str, Any]) -> None:
    avg = sum(run["times"]) / max(1, len(run["times"]))
    stars = stars_for_score(run["score"], 5, avg)
    if not run.get("logged"):
        database.log_session("wordproblems", "Story maths", run["score"], stars, run["level"])
        database.adapt_difficulty("wordproblems", run["score"])
        run["logged"] = True
    st.markdown("## Story maths complete!")
    gamify.reward_chest(stars, run["score"], 5)
    st.markdown(styles.stars_html(stars), unsafe_allow_html=True)
    styles.child_card(f"You solved {run['score']} out of 5 story clues! Well done, wise thinker! 🌟")
    if st.button("Play story maths again"):
        st.session_state.pop("word_run", None)
        st.rerun()


def _feedback(run: Dict[str, Any]) -> None:
    if run["feedback"].get("correct") and st.session_state.pop("word_balloons", False):
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
    gamify.helper_tip("Miriam says story clues help wise thinkers choose.", "🧺")
    if st.button("Next story"):
        run["idx"] += 1
        run["feedback"] = None
        run["question_started"] = time.time()
        st.rerun()


def _render_problem(run: Dict[str, Any]) -> None:
    if run["idx"] >= len(run["problems"]):
        _finish(run)
        return
    if run.get("feedback"):
        _feedback(run)
        return

    problem = run["problems"][run["idx"]]
    gamify.mission_progress(run["idx"] + 1, 5, run["score"])
    text = f"{problem.get('emojis', '🌟')}<br>{problem['story']}<br><br>{problem['question']}"
    st.caption(f"Story {run['idx'] + 1} of 5")
    styles.speech_bubble(text)
    read_button(f"{problem['story']} {problem['question']}", key=f"word-read-{run['idx']}")
    options = [str(option) for option in problem["options"]]
    cols = st.columns(4)
    for index, choice in enumerate(options):
        with cols[index]:
            if st.button(choice, key=f"word-{run['idx']}-{index}"):
                _answer(run, choice)


def render() -> None:
    st.markdown("# Word Problems 📚")
    gamify.adventure_header("Bible Story Maths", "🧺", "Solve gentle stories with baskets, scrolls, sheep, bread, and stars.")
    run = st.session_state.get("word_run")
    if run:
        _render_problem(run)
        return
    styles.child_card("Read the little story. Then tap the answer.")
    if st.button("Start story maths"):
        _start()


def render() -> None:
    st.markdown("# Parable Problems 📚")
    gamify.adventure_header("Bible Story Maths", "🧺", "Solve gentle stories with baskets, scrolls, sheep, bread, and stars.")
    run = st.session_state.get("word_run")
    if run:
        _render_problem(run)
        return
    styles.child_card("Read the Bible-style story. Then tap the answer.")
    if st.button("Start parable maths"):
        _start()
