from __future__ import annotations

import html
from pathlib import Path

import streamlit as st

import database
from utils import learning_engine


BASE_DIR = Path(__file__).resolve().parents[1]
MASCOT_PATH = BASE_DIR / "assets" / "bible_story_companions.png"


def mascot_banner(caption: str = "Your Bible adventure friends are ready!") -> None:
    if MASCOT_PATH.exists():
        st.image(str(MASCOT_PATH), use_container_width=True)
    st.markdown(
        '<div class="mission-card">'
        '<div class="mission-title">Bible Adventure</div>'
        f'<div class="mission-text">{html.escape(caption)}</div>'
        '</div>',
        unsafe_allow_html=True,
    )


def daily_training_card() -> None:
    plan = learning_engine.build_daily_plan()
    summary = learning_engine.daily_plan_summary()
    profile = database.get_child_profile()
    growth = learning_engine.development_plan(profile)
    rows: list[str] = []
    for item in plan:
        status = "&#10003;" if item.get("status") == "done" else "&#10024;"
        module = html.escape(learning_engine.MODULE_LABELS.get(item["module"], item["module"].title()))
        title = html.escape(str(item["title"]))
        subtopic = html.escape(str(item["subtopic"]))
        reason = html.escape(str(item["reason"]))
        rows.append(
            '<div class="training-item">'
            f'<div class="training-status">{status}</div>'
            '<div>'
            f'<div class="training-title">{title}</div>'
            f'<div class="training-reason">{module}: {subtopic} &middot; {reason}</div>'
            '</div>'
            '</div>'
        )

    growth_title = html.escape(str(growth["title"]))
    growth_focus = html.escape(str(growth["focus"]))
    st.markdown(
        '<div class="training-card">'
        "<div class=\"mission-title\">Today's Wisdom Journey</div>"
        f'<div class="mission-text">{summary["done"]} done &middot; {summary["left"]} to go</div>'
        '<div class="training-item">'
        '<div class="training-status">&#127793;</div>'
        '<div>'
        f'<div class="training-title">{growth_title}</div>'
        f'<div class="training-reason">{growth_focus}</div>'
        '</div>'
        '</div>'
        f'{"".join(rows)}'
        '</div>',
        unsafe_allow_html=True,
    )


def player_hud() -> None:
    stars = database.get_total_stars()
    streak = database.get_current_streak()
    level = max(1, stars // 12 + 1)
    progress = min(100, int((stars % 12) / 12 * 100))
    st.markdown(
        '<div class="hud">'
        f'<div class="hud-stat">&#10024; Wisdom Stars<br><b>{stars}</b></div>'
        f'<div class="hud-stat">&#128293; Day Streak<br><b>{streak}</b></div>'
        f'<div class="hud-stat">&#127793; Growth Level<br><b>{level}</b></div>'
        '</div>'
        f'<div class="level-shell"><div class="level-fill" style="width:{progress}%"></div></div>',
        unsafe_allow_html=True,
    )


def adventure_header(title: str, mascot: str, mission: str) -> None:
    st.markdown(
        '<div class="adventure-header">'
        f'<div class="mascot-bubble">{html.escape(mascot)}</div>'
        '<div>'
        f'<div class="mission-title">{html.escape(title)}</div>'
        f'<div class="mission-text">{html.escape(mission)}</div>'
        '</div>'
        '</div>',
        unsafe_allow_html=True,
    )


def mission_progress(current: int, total: int, score: int) -> None:
    pct = int((current / max(total, 1)) * 100)
    st.markdown(
        '<div class="mission-strip">'
        f'<span>&#127919; Quest {current} of {total}</span>'
        f'<span>&#10024; {score} wisdom points</span>'
        '</div>'
        f'<div class="level-shell"><div class="level-fill" style="width:{pct}%"></div></div>',
        unsafe_allow_html=True,
    )


def reward_chest(stars: int, score: int, total: int = 5) -> None:
    chest = "&#127942;" if stars == 3 else "&#127807;" if stars == 2 else "&#10024;"
    st.markdown(
        '<div class="reward-chest">'
        f'<div class="reward-icon">{chest}</div>'
        '<div class="mission-title">Wisdom Quest Complete!</div>'
        f'<div class="mission-text">You finished {score} of {total} learning challenges.</div>'
        '</div>',
        unsafe_allow_html=True,
    )


def helper_tip(text: str, mascot: str = "&#10024;") -> None:
    st.markdown(
        '<div class="helper-tip">'
        f'<span class="helper-face">{mascot}</span>'
        f'<span>{html.escape(text)}</span>'
        '</div>',
        unsafe_allow_html=True,
    )
