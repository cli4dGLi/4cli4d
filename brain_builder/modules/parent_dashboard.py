from __future__ import annotations

import json
from typing import Any, Dict, List

import streamlit as st
import streamlit.components.v1 as components
import plotly.graph_objects as go

import claude_api
import database
from utils.scoring import DOMAIN_LABELS, percentile_for_score, score_band, strongest_domain


ROADMAP = [
    (
        "Phase 1 (Month 1-3): Foundation",
        "70th percentile composite",
        "Establish daily 20-min sessions. Identify OB's 2 weakest domains. Build working memory and phonological awareness as priority.",
        "OB can count to 100, reads 50 sight words, holds 4-digit span",
    ),
    (
        "Phase 2 (Month 4-6): Acceleration",
        "85th percentile composite",
        "Introduce matrix reasoning puzzles. Multi-step word problems. Speed maths drills. Reading simple 3-sentence stories independently.",
        "OB solves 2-step addition problems mentally, reads simple books independently, pattern recognition at 75th percentile",
    ),
    (
        "Phase 3 (Month 7-9): Mastery",
        "93rd percentile composite",
        "Complex analogical reasoning. Chapter-level comprehension. Cross-domain tasks. Memory palace techniques simplified for age 6.",
        "OB in top 7%, verbal score equivalent 120+",
    ),
    (
        "Phase 4 (Month 10-12): Elite",
        "99th percentile composite",
        "Monthly full simulation. Advanced vocabulary. Abstract reasoning. Creative problem solving. Processing speed elite.",
        "Full Scale IQ equivalent 130+, globally top 1% for age",
    ),
]


def _domain_scores(row: Any) -> Dict[str, float]:
    if row is None:
        return {}
    return {
        domain: float(row[f"{domain}_score"])
        for domain in DOMAIN_LABELS
        if row[f"{domain}_score"] is not None
    }


def _latest_insights(row: Any) -> Dict[str, Any] | None:
    if not row or not row["ai_insights"]:
        return None
    try:
        return json.loads(row["ai_insights"])
    except Exception:
        return None


def _most_improved(rows: List[Any]) -> str:
    if len(rows) < 2:
        return "More data needed"
    ordered = list(reversed(rows))
    first = _domain_scores(ordered[0])
    last = _domain_scores(ordered[-1])
    changes = {
        domain: last.get(domain, 0) - first.get(domain, 0)
        for domain in DOMAIN_LABELS
        if domain in first and domain in last
    }
    if not changes:
        return "More data needed"
    domain = max(changes, key=changes.get)
    return DOMAIN_LABELS[domain]


def _radar(scores: Dict[str, float]) -> None:
    labels = [DOMAIN_LABELS[d] for d in DOMAIN_LABELS if d in scores]
    values = [scores[d] for d in DOMAIN_LABELS if d in scores]
    average = [100 for _ in values]
    if not values:
        return
    fig = go.Figure()
    fig.add_trace(go.Scatterpolar(r=values + values[:1], theta=labels + labels[:1], fill="toself", name="OB"))
    fig.add_trace(go.Scatterpolar(r=average + average[:1], theta=labels + labels[:1], name="Age-5 average"))
    fig.update_layout(
        polar=dict(radialaxis=dict(visible=True, range=[70, 135])),
        height=430,
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Nunito", size=14),
        margin=dict(l=30, r=30, t=40, b=30),
    )
    st.plotly_chart(fig, use_container_width=True)


def _trend(rows: List[Any]) -> None:
    ordered = list(reversed(rows))
    if not ordered:
        return
    fig = go.Figure()
    fig.add_scatter(
        x=[row["date"][:10] for row in ordered],
        y=[row["composite_score"] for row in ordered],
        mode="lines+markers",
        line=dict(color="#42A5F5", width=4),
        marker=dict(size=12),
    )
    fig.update_layout(
        height=330,
        yaxis=dict(title="Composite estimate", range=[70, 135]),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(255,255,255,0.72)",
        font=dict(family="Nunito", size=14),
        margin=dict(l=20, r=20, t=30, b=20),
    )
    st.plotly_chart(fig, use_container_width=True)


def _percentile_bar(scores: Dict[str, float]) -> None:
    if not scores:
        return
    labels = [DOMAIN_LABELS[d] for d in DOMAIN_LABELS if d in scores]
    percentiles = [percentile_for_score(scores[d]) for d in DOMAIN_LABELS if d in scores]
    fig = go.Figure()
    fig.add_bar(x=labels, y=percentiles, marker_color="#66BB6A")
    fig.add_hline(y=99, line_dash="dash", line_color="red", annotation_text="99th percentile target")
    fig.update_layout(
        height=360,
        yaxis=dict(title="Percentile", range=[0, 100]),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(255,255,255,0.72)",
        font=dict(family="Nunito", size=14),
        margin=dict(l=20, r=20, t=30, b=80),
    )
    st.plotly_chart(fig, use_container_width=True)


def _heatmap() -> None:
    matrix = database.get_weekly_domain_practice()
    days = list(matrix.keys())
    domains = list(DOMAIN_LABELS.keys())
    z = [[matrix[day][domain] for day in days] for domain in domains]
    fig = go.Figure(
        data=go.Heatmap(
            z=z,
            x=[day[5:] for day in days],
            y=[DOMAIN_LABELS[d] for d in domains],
            colorscale=[[0, "#E0E0E0"], [1, "#66BB6A"]],
            showscale=False,
        )
    )
    fig.update_layout(
        height=330,
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Nunito", size=14),
        margin=dict(l=20, r=20, t=30, b=20),
    )
    st.plotly_chart(fig, use_container_width=True)


def render_dashboard() -> None:
    rows = database.get_assessments(limit=12)
    latest = rows[0] if rows else None
    if not latest:
        st.info("Run an assessment to fill this dashboard.")
        return

    scores = _domain_scores(latest)
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Composite", f"{latest['composite_score']:.1f}", score_band(float(latest["composite_score"])))
    col2.metric("Global percentile", f"{latest['percentile_rank']:.1f}")
    col3.metric("Strongest", strongest_domain(scores))
    col4.metric("Most improved", _most_improved(rows))
    col5.metric("Streak", database.get_current_streak())
    st.caption(
        "Scores are indicative estimates based on WPPSI-IV normative frameworks and are intended for educational tracking only, not clinical diagnosis."
    )

    st.markdown("### Cognitive profile")
    _radar(scores)
    st.markdown("### Composite trend")
    _trend(rows)
    st.markdown("### Domain percentiles")
    _percentile_bar(scores)
    st.markdown("### Weekly practice heatmap")
    _heatmap()

    st.download_button(
        "Download OB's full history CSV",
        database.export_history_csv(),
        file_name="ob_brain_builder_history.csv",
        mime="text/csv",
    )


def render_insights() -> None:
    latest = database.get_latest_assessment()
    insights = _latest_insights(latest)
    if insights:
        st.markdown("### Latest AI insights")
        st.markdown(f"**Summary:** {insights.get('summary', '')}")
        st.markdown("**Strengths**")
        for item in insights.get("strengths", []):
            st.write(f"- {item}")
        st.markdown("**Priority areas**")
        for item in insights.get("priority_areas", []):
            st.write(f"- {item}")
        st.markdown("**Weekly plan**")
        st.dataframe(insights.get("weekly_plan", []), use_container_width=True)
        st.markdown(f"**Monthly milestone:** {insights.get('monthly_milestone', '')}")
        st.markdown(f"**Path to top 1%:** {insights.get('percentile_trajectory', '')}")
        st.markdown(f"**Parent tip:** {insights.get('parent_tip', '')}")
    else:
        st.info("Run an assessment to generate AI insights.")

    st.markdown("### 12-month roadmap")
    for phase, target, focus, milestone in ROADMAP:
        st.markdown(
            f"""
            <div class="brain-card">
              <h3>{phase}</h3>
              <p><b>Target:</b> {target}</p>
              <p><b>Focus:</b> {focus}</p>
              <p><b>Milestone:</b> {milestone}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    if st.button("Generate this week's report"):
        history = {
            "sessions": [dict(row) for row in database.get_recent_sessions(limit=20)],
            "assessments": [dict(row) for row in database.get_assessments(limit=3)],
            "reading": [dict(row) for row in database.get_reading_assessments(limit=5)],
        }
        st.session_state.weekly_parent_report = claude_api.generate_weekly_parent_report(history)

    report = st.session_state.get("weekly_parent_report")
    if report:
        st.markdown("### Weekly parent email report")
        st.markdown(f'<div class="brain-card">{report}</div>', unsafe_allow_html=True)
        escaped = json.dumps(report)
        components.html(
            f"""
            <button onclick='navigator.clipboard.writeText({escaped})'
              style="min-height:54px;border:0;border-radius:14px;background:#42A5F5;color:white;font-size:18px;font-weight:800;padding:10px 16px;">
              Copy to clipboard
            </button>
            """,
            height=80,
        )
