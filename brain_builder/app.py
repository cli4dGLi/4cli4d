from __future__ import annotations

import time

import streamlit as st

import database
from modules import assessment, english, maths, progress, science, wordproblems
from utils import gamify
from utils import styles


st.set_page_config(
    page_title="Brain Builder",
    page_icon="🌟",
    layout="wide",
    initial_sidebar_state="collapsed",
)

database.init_db()
styles.inject_global_css()


PAGES = {
    "home": "Home",
    "maths": "Mental Maths",
    "english": "English & Reading",
    "wordproblems": "Word Problems",
    "science": "Wonder Lab",
    "progress": "My Progress",
    "assessment": "OB's Assessment Centre",
}


def _reset_active_runs() -> None:
    for key in [
        "maths_run",
        "english_run",
        "word_run",
        "science_run",
        "assessment_run",
        "english_topic",
        "assessment_last_summary",
    ]:
        st.session_state.pop(key, None)


def _session_timeout() -> None:
    now = time.time()
    last = st.session_state.get("last_activity", now)
    if now - last > 600:
        st.session_state.page = "home"
        _reset_active_runs()
        st.warning("Welcome back! Let's start again from home. 🌟")
    st.session_state.last_activity = now


def _confirm_child_name() -> bool:
    if database.get_setting("child_name_confirmed", "false") == "true":
        return True
    st.markdown("# Brain Builder 🌟")
    st.markdown('<div class="brain-card friendly-text">Grown-up, please check the child name once.</div>', unsafe_allow_html=True)
    name = st.text_input("Child name", value=database.get_setting("child_name", "OB") or "OB", max_chars=20)
    if st.button("Save and start"):
        clean = name.strip() or "OB"
        database.set_setting("child_name", clean)
        database.set_setting("child_name_confirmed", "true")
        st.rerun()
    return False


def _go(page: str) -> None:
    st.session_state.page = page
    st.rerun()


def _home() -> None:
    child_name = database.get_setting("child_name", "OB") or "OB"
    st.markdown(f"# Hello {child_name}! Ready to play? 🌟")
    gamify.player_hud()
    gamify.mascot_banner("Star Scout, Book Buddy, Drip the Scientist, and Puzzle Bot have new missions for you.")
    styles.child_card("Pick a quest. Win stars. Fill your adventure bar.")

    modules = [
        ("MATH QUEST 🧮", "maths"),
        ("BOOK QUEST 📖", "english"),
        ("STORY QUEST 📚", "wordproblems"),
        ("WONDER LAB 🔬", "science"),
        ("TREASURE MAP 🌟", "progress"),
        ("GROWN-UP BASE 🔐", "assessment"),
    ]
    for row_start in range(0, len(modules), 2):
        cols = st.columns(2)
        for offset, (label, page) in enumerate(modules[row_start : row_start + 2]):
            with cols[offset]:
                if st.button(label, key=f"home-{page}"):
                    _go(page)


def _render_page(page: str) -> None:
    if page != "home":
        if st.button("🏠 Home"):
            st.session_state.page = "home"
            st.rerun()

    try:
        if page == "maths":
            maths.render()
        elif page == "english":
            english.render()
        elif page == "wordproblems":
            wordproblems.render()
        elif page == "science":
            science.render()
        elif page == "progress":
            progress.render()
        elif page == "assessment":
            assessment.render()
        else:
            _home()
    except Exception:
        st.info("Let's try again! 🔄")
        if st.button("Back home"):
            st.session_state.page = "home"
            st.rerun()


def main() -> None:
    _session_timeout()
    if not _confirm_child_name():
        return
    page = st.session_state.get("page", "home")
    _render_page(page)


if __name__ == "__main__":
    main()
