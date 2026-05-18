from __future__ import annotations

from datetime import date
from typing import Any, Dict, List

import database


SKILL_CATALOG: List[Dict[str, str]] = [
    {"module": "maths", "subtopic": "Number bonds to 10", "title": "Power up number bonds", "reason": "Fast number bonds make maths feel easier."},
    {"module": "maths", "subtopic": "Addition (up to 20)", "title": "Save Addition City", "reason": "Addition builds strong number sense."},
    {"module": "maths", "subtopic": "Subtraction (up to 20)", "title": "Subtraction shield drill", "reason": "Taking away needs calm practice."},
    {"module": "english", "subtopic": "Phonics", "title": "Sound hero mission", "reason": "Letter sounds help new words make sense."},
    {"module": "english", "subtopic": "Sight words", "title": "Word shield mission", "reason": "Sight words make reading smoother."},
    {"module": "english", "subtopic": "Read-aloud comprehension", "title": "Story meaning mission", "reason": "Understanding stories matters as much as reading words."},
    {"module": "wordproblems", "subtopic": "Story maths", "title": "Rescue a story problem", "reason": "Story maths connects reading and numbers."},
    {"module": "science", "subtopic": "Natural Science", "title": "Nature discovery", "reason": "Science facts grow curiosity."},
    {"module": "science", "subtopic": "Geography", "title": "Map hero mission", "reason": "Places and maps build world knowledge."},
    {"module": "science", "subtopic": "Geometry", "title": "Shape power mission", "reason": "Shapes help with puzzles, maths, and spatial thinking."},
    {"module": "puzzles", "subtopic": "Pattern Puzzles", "title": "Pattern rescue", "reason": "Patterns train reasoning and prediction."},
    {"module": "puzzles", "subtopic": "Memory Match", "title": "Memory badge mission", "reason": "Memory practice helps learning stick."},
    {"module": "puzzles", "subtopic": "Maze Rescue", "title": "Rescue Pup maze", "reason": "Mazes build planning and careful moves."},
]

MODULE_LABELS = {
    "maths": "Number Hero",
    "english": "Reading Hero",
    "wordproblems": "Story Rescue",
    "science": "Super Science",
    "puzzles": "Puzzle Rescue",
}


def _catalog_key(item: Dict[str, str]) -> str:
    return database.skill_key(item["module"], item["subtopic"])


def _mastery_lookup() -> Dict[str, Dict[str, Any]]:
    rows = database.get_skill_mastery_rows()
    return {row["skill_key"]: dict(row) for row in rows}


def _score_candidate(item: Dict[str, str], mastery_rows: Dict[str, Dict[str, Any]]) -> float:
    row = mastery_rows.get(_catalog_key(item))
    today = date.today().isoformat()
    if not row:
        return 1.25
    mastery = float(row.get("mastery") or 0.35)
    due = str(row.get("next_due_date") or today) <= today
    attempts = int(row.get("attempts") or 0)
    last_score = int(row.get("last_score") or 0)
    priority = (1.0 - mastery) + (0.35 if due else 0) + (0.2 if attempts < 2 else 0)
    if last_score <= 2:
        priority += 0.22
    return round(priority, 4)


def build_daily_plan(force: bool = False) -> List[Dict[str, Any]]:
    existing = database.get_daily_plan()
    if existing and not force:
        return [dict(row) for row in existing]

    mastery_rows = _mastery_lookup()
    ranked = sorted(SKILL_CATALOG, key=lambda item: _score_candidate(item, mastery_rows), reverse=True)
    chosen: List[Dict[str, str]] = []
    used_modules = set()

    for item in ranked:
        if item["module"] not in used_modules:
            chosen.append(item)
            used_modules.add(item["module"])
        if len(chosen) == 4:
            break

    if len(chosen) < 4:
        for item in ranked:
            if item not in chosen:
                chosen.append(item)
            if len(chosen) == 4:
                break

    fun_reward = next((item for item in SKILL_CATALOG if item["module"] == "puzzles" and item not in chosen), None)
    if fun_reward:
        chosen.append(fun_reward)

    plan = []
    for item in chosen[:5]:
        row = mastery_rows.get(_catalog_key(item))
        mastery_pct = int(float(row.get("mastery", 0.35)) * 100) if row else 35
        reason = item["reason"]
        if row and str(row.get("next_due_date") or "") <= date.today().isoformat():
            reason = f"Due for review. {reason}"
        plan.append(
            {
                "module": item["module"],
                "subtopic": item["subtopic"],
                "title": item["title"],
                "reason": f"{reason} Mastery: {mastery_pct}%.",
                "module_label": MODULE_LABELS.get(item["module"], item["module"].title()),
                "status": "planned",
            }
        )

    database.save_daily_plan(plan)
    return [dict(row) for row in database.get_daily_plan()]


def daily_plan_summary() -> Dict[str, int]:
    plan = build_daily_plan()
    done = sum(1 for item in plan if item.get("status") == "done")
    return {"total": len(plan), "done": done, "left": max(0, len(plan) - done)}


def mastery_snapshot(limit: int = 6) -> List[Dict[str, Any]]:
    rows = [dict(row) for row in database.get_skill_mastery_rows()]
    if not rows:
        return []
    for row in rows:
        row["mastery_pct"] = int(float(row.get("mastery") or 0) * 100)
    return rows[:limit]
