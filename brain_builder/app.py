from __future__ import annotations

import time
from datetime import date

import streamlit as st

import database
from modules import assessment, coding, english, maths, progress, puzzles, science, wordproblems
from utils import auth
from utils import gamify
from utils import styles


st.set_page_config(
    page_title="Brain Builder",
    page_icon="✨",
    layout="wide",
    initial_sidebar_state="expanded",
)

database.init_db()
styles.inject_global_css()


PAGES = {
    "home": "Home",
    "maths": "David's Numbers",
    "english": "Reading Scrolls",
    "wordproblems": "Parable Problems",
    "science": "Creation Lab",
    "coding": "Code Camp",
    "puzzles": "Wisdom Puzzles",
    "progress": "Growth Garden",
    "assessment": "Grown-up Tent",
    "admin": "Admin Settings",
}


def _reset_active_runs() -> None:
    for key in [
        "maths_run",
        "english_run",
        "word_run",
        "science_run",
        "coding_run",
        "puzzle_run",
        "maze_run",
        "puzzle_topic",
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
        st.warning("Welcome back! Let's start again from home. ✨")
    st.session_state.last_activity = now


def _age_from_birth_date(birth_date: date) -> int:
    today = date.today()
    years = today.year - birth_date.year
    if (today.month, today.day) < (birth_date.month, birth_date.day):
        years -= 1
    return max(2, min(12, years))


def _active_child_sidebar() -> None:
    profile = database.get_child_profile()
    if not profile:
        return
    with st.sidebar:
        st.markdown(f"Learning as **{profile['name']}**")
        if st.button("Switch learner"):
            st.session_state.pop("active_child_id", None)
            st.rerun()


def _choose_child_profile() -> bool:
    active = st.session_state.get("active_child_id")
    if active and database.get_child_profile(int(active)):
        _active_child_sidebar()
        return True

    st.markdown("# Who is learning today? ✨")
    styles.child_card("Tap your name, or add your name to begin.")
    if st.session_state.get("auth_role") == "admin":
        if st.button("ADMIN SETTINGS 🔐", key="profile-admin-settings"):
            st.session_state.page = "admin"
            st.rerun()
    profiles = [dict(row) for row in database.get_child_profiles()]
    if profiles:
        for row_start in range(0, len(profiles), 3):
            cols = st.columns(3)
            for offset, profile in enumerate(profiles[row_start : row_start + 3]):
                with cols[offset]:
                    label = f"{profile['name']}\nAge {profile['age_years'] or '?'}"
                    if st.button(label, key=f"child-profile-{profile['id']}"):
                        st.session_state.active_child_id = int(profile["id"])
                        database.touch_child_profile(int(profile["id"]))
                        st.rerun()

    with st.expander("Add my name", expanded=not profiles):
        name = st.text_input("My name", max_chars=60, key="new-child-name")
        age = st.number_input("My age", min_value=2, max_value=12, value=5, step=1, key="new-child-age")
        default_birth = date(max(2013, date.today().year - int(age)), 1, 1)
        birth_date = st.date_input(
            "My birthday",
            value=default_birth,
            min_value=date(2013, 1, 1),
            max_value=date.today(),
            key="new-child-dob",
        )
        if st.button("Start my Bible adventure"):
            clean = name.strip()
            if len(clean) < 2:
                st.warning("Please type your name.")
            else:
                child_id = database.create_child_profile(
                    clean,
                    int(age) or _age_from_birth_date(birth_date),
                    birth_date.isoformat(),
                    st.session_state.get("auth_user"),
                )
                st.session_state.active_child_id = child_id
                st.rerun()
    return False


def _go(page: str) -> None:
    st.session_state.page = page
    st.rerun()


def _home() -> None:
    profile = database.get_child_profile()
    child_name = profile["name"] if profile else "friend"
    st.markdown(f"# Hello {child_name}! Ready for a Bible adventure? ✨")
    gamify.player_hud()
    gamify.mascot_banner("David, Esther, Daniel, Ruth, Moses, and Miriam have joyful learning quests for you.")
    styles.child_card("Pick a wisdom quest. Earn stars. Grow your learning garden.")
    gamify.daily_training_card()

    modules = [
        ("DAVID'S NUMBERS 🧮", "maths"),
        ("READING SCROLLS 📖", "english"),
        ("PARABLE PROBLEMS 📚", "wordproblems"),
        ("CREATION LAB 🔬", "science"),
        ("CODE CAMP 🧭", "coding"),
        ("WISDOM PUZZLES 🧩", "puzzles"),
        ("GROWTH GARDEN 🌟", "progress"),
        ("GROWN-UP TENT 🔐", "assessment"),
    ]
    if st.session_state.get("auth_role") == "admin":
        modules.append(("ADMIN SETTINGS 🔐", "admin"))
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
        elif page == "coding":
            coding.render()
        elif page == "puzzles":
            puzzles.render()
        elif page == "progress":
            progress.render()
        elif page == "assessment":
            assessment.render()
        elif page == "admin":
            auth.render_admin_page()
        else:
            _home()
    except Exception:
        st.info("Let's try again! 🔄")
        if st.button("Back home"):
            st.session_state.page = "home"
            st.rerun()


def main() -> None:
    if not auth.require_login():
        return
    _session_timeout()
    page = st.session_state.get("page", "home")
    if page == "admin":
        _render_page(page)
        return
    if not _choose_child_profile():
        return
    _render_page(page)


if __name__ == "__main__":
    main()
