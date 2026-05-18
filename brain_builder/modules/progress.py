from __future__ import annotations

import streamlit as st
import plotly.graph_objects as go

import database
from utils import gamify
from utils import learning_engine
from utils import styles


def _scores_chart() -> None:
    rows = database.get_score_chart_rows(limit=7)
    if not rows:
        st.info("Play a game to see your bars grow.")
        return
    fig = go.Figure()
    fig.add_bar(
        x=[row["Session"] for row in rows],
        y=[row["Score"] for row in rows],
        marker_color=["#42A5F5", "#66BB6A", "#FFA726", "#AB47BC", "#EC407A", "#26A69A", "#FFCA28"][: len(rows)],
        text=[row["Module"] for row in rows],
    )
    fig.update_layout(
        height=330,
        yaxis=dict(range=[0, 5], title="Score out of 5"),
        xaxis_title="Last 7 sessions",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(255,255,255,0.7)",
        font=dict(family="Nunito", size=16),
        margin=dict(l=20, r=20, t=30, b=20),
    )
    st.plotly_chart(fig, use_container_width=True)


def _badges() -> None:
    badges = database.get_badges()
    if not badges:
        styles.child_card("Badges will pop up here as you practise. 🌟")
        return
    html = "".join(f'<span class="badge-pill">🏅 {row["badge_name"]}</span>' for row in badges)
    st.markdown(html, unsafe_allow_html=True)


def _parent_summary() -> None:
    with st.expander("Parent summary"):
        pin = st.text_input("Parent PIN", type="password", max_chars=4, key="progress-pin")
        if pin != database.get_parent_pin():
            if pin:
                st.warning("Please ask a grown-up to try again.")
            return

        sessions = [dict(row) for row in database.get_all_sessions()]
        st.markdown("### Full learning history")
        st.dataframe(sessions, use_container_width=True)

        st.markdown("### Weak areas")
        weak = database.weak_areas()
        if weak:
            st.dataframe(weak, use_container_width=True)
        else:
            st.write("No weak areas yet. More sessions will help.")

        st.download_button(
            "Download full history CSV",
            database.export_history_csv(),
            file_name="brain_builder_history.csv",
            mime="text/csv",
        )


def render() -> None:
    st.markdown("# Hero Map 🌟")
    gamify.adventure_header("Hero Map", "🗺️", "See your hero points, badges, and learning trails.")
    gamify.player_hud()
    c1, c2, c3 = st.columns(3)
    c1.metric("Hero points", database.get_total_stars())
    c2.metric("Day streak", database.get_current_streak())
    c3.metric("Goal", "2 modules today")

    st.markdown("## Daily Hero Training")
    gamify.daily_training_card()
    snapshot = learning_engine.mastery_snapshot()
    if snapshot:
        st.markdown("## Skills to grow")
        st.dataframe(
            [
                {
                    "Skill": row["display_name"],
                    "Module": learning_engine.MODULE_LABELS.get(row["module"], row["module"].title()),
                    "Mastery": f"{row['mastery_pct']}%",
                    "Due": row["next_due_date"],
                    "Attempts": row["attempts"],
                }
                for row in snapshot
            ],
            use_container_width=True,
        )

    st.markdown("## Last games")
    _scores_chart()

    st.markdown("## Badges")
    _badges()

    styles.child_card("Today's goal: Complete 2 modules today!")
    _parent_summary()
