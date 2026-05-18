from __future__ import annotations

from pathlib import Path

import streamlit as st

import database
from utils import learning_engine


BASE_DIR = Path(__file__).resolve().parents[1]
MASCOT_PATH = BASE_DIR / "assets" / "hero_academy_team.png"


def mascot_banner(caption: str = "Your hero team is ready!") -> None:
    if MASCOT_PATH.exists():
        st.image(str(MASCOT_PATH), use_container_width=True)
    st.markdown(
        f"""
        <div class="mission-card">
            <div class="mission-title">Hero Academy</div>
            <div class="mission-text">{caption}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def daily_training_card() -> None:
    plan = learning_engine.build_daily_plan()
    summary = learning_engine.daily_plan_summary()
    rows = []
    for item in plan:
        status = "✅" if item.get("status") == "done" else "⚡"
        module = learning_engine.MODULE_LABELS.get(item["module"], item["module"].title())
        rows.append(
            f"""
            <div class="training-item">
                <div class="training-status">{status}</div>
                <div>
                    <div class="training-title">{item['title']}</div>
                    <div class="training-reason">{module}: {item['subtopic']} · {item['reason']}</div>
                </div>
            </div>
            """
        )
    st.markdown(
        f"""
        <div class="training-card">
            <div class="mission-title">Today's Hero Training</div>
            <div class="mission-text">{summary['done']} done · {summary['left']} to go</div>
            {''.join(rows)}
        </div>
        """,
        unsafe_allow_html=True,
    )


def player_hud() -> None:
    stars = database.get_total_stars()
    streak = database.get_current_streak()
    level = max(1, stars // 12 + 1)
    progress = min(100, int((stars % 12) / 12 * 100))
    st.markdown(
        f"""
        <div class="hud">
            <div class="hud-stat">⚡ Hero Points<br><b>{stars}</b></div>
            <div class="hud-stat">🔥 Day Streak<br><b>{streak}</b></div>
            <div class="hud-stat">🦸 Hero Rank<br><b>{level}</b></div>
        </div>
        <div class="level-shell"><div class="level-fill" style="width:{progress}%"></div></div>
        """,
        unsafe_allow_html=True,
    )


def adventure_header(title: str, mascot: str, mission: str) -> None:
    st.markdown(
        f"""
        <div class="adventure-header">
            <div class="mascot-bubble">{mascot}</div>
            <div>
                <div class="mission-title">{title}</div>
                <div class="mission-text">{mission}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def mission_progress(current: int, total: int, score: int) -> None:
    pct = int((current / max(total, 1)) * 100)
    st.markdown(
        f"""
        <div class="mission-strip">
            <span>🎯 Rescue {current} of {total}</span>
            <span>⚡ {score} power points</span>
        </div>
        <div class="level-shell"><div class="level-fill" style="width:{pct}%"></div></div>
        """,
        unsafe_allow_html=True,
    )


def reward_chest(stars: int, score: int, total: int = 5) -> None:
    chest = "🏆" if stars == 3 else "🛡️" if stars == 2 else "⚡"
    st.markdown(
        f"""
        <div class="reward-chest">
            <div class="reward-icon">{chest}</div>
            <div class="mission-title">Hero Mission Complete!</div>
            <div class="mission-text">You powered up {score} of {total} hero challenges.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def helper_tip(text: str, mascot: str = "🌟") -> None:
    st.markdown(
        f"""
        <div class="helper-tip">
            <span class="helper-face">{mascot}</span>
            <span>{text}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
