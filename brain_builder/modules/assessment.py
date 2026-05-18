from __future__ import annotations

import json
import time
from typing import Any, Dict, List

import streamlit as st

import claude_api
import database
from modules import parent_dashboard, reading_assessment
from modules.assessment_tasks import DOMAINS, build_domain_tasks, domains_for_assessment, task_count
from utils import styles
from utils.scoring import calculate_composite, percent_to_standard_score, percentile_for_score
from utils.tts import read_button


def _pin_gate() -> bool:
    if st.session_state.get("assessment_parent_ok"):
        return True
    st.markdown("# OB's Assessment Centre 🔐")
    styles.child_card("This area is for grown-ups.")
    pin = st.text_input("Parent PIN", type="password", max_chars=4, key="assessment-pin")
    if pin == database.get_parent_pin():
        st.session_state.assessment_parent_ok = True
        st.rerun()
    elif pin:
        st.warning("Please ask a grown-up to try again.")
    return False


def _settings_panel() -> None:
    with st.expander("Parent settings"):
        st.write("Change parent PIN")
        new_pin = st.text_input("New 4-digit PIN", type="password", max_chars=4, key="new-parent-pin")
        if st.button("Save new PIN"):
            if new_pin.isdigit() and len(new_pin) == 4:
                database.set_parent_pin(new_pin)
                st.success("PIN updated.")
            else:
                st.warning("Use exactly 4 digits.")


def _countdown() -> None:
    spot = st.empty()
    for text in ["3", "2", "1", "Go!"]:
        spot.markdown(f'<div class="countdown">{text}</div>', unsafe_allow_html=True)
        time.sleep(0.65)
    spot.empty()


def _start_assessment(assessment_type: str, mini_domain: str | None) -> None:
    difficulty = database.get_difficulty("assessment")
    domains = domains_for_assessment(assessment_type, mini_domain)
    tasks_by_domain: Dict[str, List[Dict[str, Any]]] = {}
    _countdown()
    with st.spinner("Building playful tasks..."):
        for domain in domains:
            tasks_by_domain[domain] = build_domain_tasks(domain, task_count(domain, assessment_type), difficulty)
    st.session_state.assessment_run = {
        "assessment_type": assessment_type,
        "difficulty": difficulty,
        "domains": domains,
        "tasks_by_domain": tasks_by_domain,
        "domain_index": 0,
        "task_index": 0,
        "responses": [],
        "points": {domain: 0.0 for domain in domains},
        "max_points": {domain: float(len(tasks_by_domain[domain])) for domain in domains},
        "feedback": None,
        "start_time": time.time(),
        "task_started": time.time(),
        "seen_sequences": {},
    }
    st.rerun()


def _domain_done(run: Dict[str, Any]) -> None:
    domain = run["domains"][run["domain_index"]]
    st.markdown("## Great job! You're so smart! 🌟")
    styles.child_card(f"{DOMAINS[domain]} game finished. Take a happy breath.")
    if st.button("Keep going"):
        run["domain_index"] += 1
        run["task_index"] = 0
        run["feedback"] = None
        run["task_started"] = time.time()
        st.rerun()


def _finish(run: Dict[str, Any]) -> None:
    raw_domain_pct = {
        domain: (run["points"][domain] / max(1.0, run["max_points"][domain])) * 100
        for domain in run["domains"]
    }
    domain_scores = {
        domain: percent_to_standard_score(percent)
        for domain, percent in raw_domain_pct.items()
    }
    composite = calculate_composite(domain_scores)
    percentile = percentile_for_score(composite)
    last_three = [dict(row) for row in database.get_assessments(limit=3)]
    insights = claude_api.generate_assessment_insights(domain_scores, last_three)
    duration = int(time.time() - run["start_time"])
    database.log_assessment(
        run["assessment_type"],
        domain_scores,
        composite,
        percentile,
        duration,
        insights,
        run["responses"],
    )
    if composite >= 115:
        database.set_difficulty("assessment", database.get_difficulty("assessment") + 1)
    elif composite < 90:
        database.set_difficulty("assessment", database.get_difficulty("assessment") - 1)
    st.session_state.assessment_last_summary = {
        "domain_scores": domain_scores,
        "composite": composite,
        "percentile": percentile,
        "insights": insights,
    }
    st.session_state.pop("assessment_run", None)
    st.rerun()


def _show_summary() -> None:
    summary = st.session_state.get("assessment_last_summary")
    if not summary:
        return
    st.success("Assessment saved.")
    c1, c2 = st.columns(2)
    c1.metric("Composite estimate", f"{summary['composite']:.1f}")
    c2.metric("Percentile estimate", f"{summary['percentile']:.1f}")
    st.dataframe(
        [{"Domain": DOMAINS[d], "Score": v} for d, v in summary["domain_scores"].items()],
        use_container_width=True,
    )
    if st.button("Start another assessment"):
        st.session_state.pop("assessment_last_summary", None)
        st.rerun()


def _show_sequence_once(run: Dict[str, Any], domain: str, task_index: int, task: Dict[str, Any]) -> None:
    task_type = task.get("task_type")
    if task_type not in {"digit_span", "picture_span", "pattern_repeat"}:
        return
    key = f"{domain}-{task_index}"
    if run["seen_sequences"].get(key):
        return
    spot = st.empty()
    sequence = task.get("sequence", [])
    for item in sequence:
        spot.markdown(f'<div class="countdown">{item}</div>', unsafe_allow_html=True)
        time.sleep(1.0)
    spot.markdown('<div class="countdown">?</div>', unsafe_allow_html=True)
    time.sleep(0.4)
    spot.empty()
    run["seen_sequences"][key] = True


def _answer_task(run: Dict[str, Any], task: Dict[str, Any], choice: str) -> None:
    elapsed_ms = int((time.time() - run.get("task_started", time.time())) * 1000)
    correct = str(choice) == str(task.get("answer"))
    points = 0.0
    if correct:
        points = 1.0
        if task.get("domain") == "psi":
            if elapsed_ms > 10000:
                points = 0.45
            elif elapsed_ms > 7000:
                points = 0.65
            elif elapsed_ms > 4500:
                points = 0.82
    domain = task.get("domain")
    run["points"][domain] += points
    run["responses"].append(
        {
            "domain": domain,
            "task_description": task.get("prompt", ""),
            "correct": 1 if correct else 0,
            "response_time_ms": elapsed_ms,
            "difficulty": run["difficulty"],
            "points": points,
        }
    )
    if correct:
        st.session_state.assessment_balloons = True
        message = "You're doing brilliantly! 🌟"
    else:
        message = "That was a hard one! Keep going!"
    run["feedback"] = {"correct": correct, "message": message}
    st.rerun()


def _render_feedback(run: Dict[str, Any]) -> None:
    if run["feedback"].get("correct") and st.session_state.pop("assessment_balloons", False):
        st.balloons()
    mark = "✅" if run["feedback"]["correct"] else "⭐"
    st.markdown(
        f"""
        <div class="brain-card" style="text-align:center;">
          <div style="font-size:86px;">{mark}</div>
          <div class="friendly-text">{run['feedback']['message']}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if st.button("Next game"):
        run["task_index"] += 1
        run["feedback"] = None
        run["task_started"] = time.time()
        st.rerun()


def _render_current_task(run: Dict[str, Any]) -> None:
    if run["domain_index"] >= len(run["domains"]):
        _finish(run)
        return
    domain = run["domains"][run["domain_index"]]
    tasks = run["tasks_by_domain"][domain]
    if run["task_index"] >= len(tasks):
        _domain_done(run)
        return
    if run.get("feedback"):
        _render_feedback(run)
        return

    task = tasks[run["task_index"]]
    st.caption(f"{DOMAINS[domain]}: game {run['task_index'] + 1} of {len(tasks)}")
    _show_sequence_once(run, domain, run["task_index"], task)
    styles.speech_bubble(f"{task.get('visual', '')}<br>{task.get('prompt', '')}")
    read_button(task.get("prompt", ""), key=f"assess-read-{domain}-{run['task_index']}")
    options = [str(option) for option in task.get("options", [])][:4]
    while len(options) < 4:
        options.append("⭐")
    for row_start in range(0, 4, 2):
        cols = st.columns(2)
        for offset, choice in enumerate(options[row_start : row_start + 2]):
            with cols[offset]:
                if st.button(choice, key=f"assess-{domain}-{run['task_index']}-{row_start}-{offset}"):
                    _answer_task(run, task, choice)


def render_run_assessment() -> None:
    _show_summary()
    run = st.session_state.get("assessment_run")
    if run:
        _render_current_task(run)
        return

    st.markdown("### Run Assessment")
    assessment_type = st.radio(
        "Assessment type",
        ["full", "quick", "mini"],
        format_func=lambda value: {"full": "Full assessment (~25 min)", "quick": "Quick assessment (~10 min)", "mini": "Mini-check (~3 min)"}[value],
        horizontal=True,
    )
    mini_domain = None
    if assessment_type == "mini":
        mini_domain = st.selectbox("Mini-check domain", list(DOMAINS.keys()), format_func=lambda value: DOMAINS[value])
    if st.button("Start assessment"):
        _start_assessment(assessment_type, mini_domain)


def render() -> None:
    if not _pin_gate():
        return
    st.markdown("# OB's Assessment Centre 🧠")
    _settings_panel()
    tab_run, tab_dash, tab_insights, tab_reading = st.tabs(
        ["A) Run Assessment", "B) Intelligence Dashboard", "C) AI Insights & Roadmap", "Read to Me"]
    )
    with tab_run:
        render_run_assessment()
    with tab_dash:
        parent_dashboard.render_dashboard()
    with tab_insights:
        parent_dashboard.render_insights()
    with tab_reading:
        reading_assessment.render("assessment")
