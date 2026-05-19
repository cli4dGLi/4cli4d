from __future__ import annotations

from datetime import date
from typing import Any, Dict, List

import database


SKILL_CATALOG: List[Dict[str, str]] = [
    {"module": "maths", "subtopic": "Number bonds to 10", "title": "David's number song", "reason": "Fast number bonds make maths feel easier."},
    {"module": "maths", "subtopic": "Addition (up to 20)", "title": "Joseph's storehouse counting", "reason": "Addition builds strong number sense."},
    {"module": "maths", "subtopic": "Subtraction (up to 20)", "title": "Moses' careful counting", "reason": "Taking away needs calm practice."},
    {"module": "english", "subtopic": "Phonics", "title": "Samuel listens for sounds", "reason": "Letter sounds help new words make sense."},
    {"module": "english", "subtopic": "Sight words", "title": "Esther's word scrolls", "reason": "Sight words make reading smoother."},
    {"module": "english", "subtopic": "Read-aloud comprehension", "title": "Daniel's story wisdom", "reason": "Understanding stories matters as much as reading words."},
    {"module": "wordproblems", "subtopic": "Story maths", "title": "Parable maths path", "reason": "Story maths connects reading and numbers."},
    {"module": "science", "subtopic": "Natural Science", "title": "Creation discovery", "reason": "Science facts grow curiosity."},
    {"module": "science", "subtopic": "Geography", "title": "Jonah's map journey", "reason": "Places and maps build world knowledge."},
    {"module": "science", "subtopic": "Geometry", "title": "Noah's shape workshop", "reason": "Shapes help with puzzles, maths, and spatial thinking."},
    {"module": "coding", "subtopic": "Sequencing", "title": "Daniel's code steps", "reason": "Sequencing builds planning and early coding thinking."},
    {"module": "coding", "subtopic": "Arrow Paths", "title": "Miriam's arrow path", "reason": "Direction commands grow logic and spatial reasoning."},
    {"module": "coding", "subtopic": "Loops", "title": "Noah's repeat loop", "reason": "Loops teach efficient repeated thinking."},
    {"module": "puzzles", "subtopic": "Pattern Puzzles", "title": "Solomon's pattern wisdom", "reason": "Patterns train reasoning and prediction."},
    {"module": "puzzles", "subtopic": "Memory Match", "title": "Ruth's memory basket", "reason": "Memory practice helps learning stick."},
    {"module": "puzzles", "subtopic": "Maze Rescue", "title": "Miriam's path maze", "reason": "Mazes build planning and careful moves."},
]

MODULE_LABELS = {
    "maths": "David's Numbers",
    "english": "Reading Scrolls",
    "wordproblems": "Parable Problems",
    "science": "Creation Lab",
    "coding": "Code Camp",
    "puzzles": "Wisdom Puzzles",
}


def development_plan(profile: Any | None = None) -> Dict[str, str]:
    age = 5
    name = "friend"
    if profile:
        try:
            age = int(profile["age_years"] or 5)
            name = str(profile["name"] or "friend").split()[0]
        except Exception:
            pass
    if age <= 4:
        focus = "Build listening, counting to 10, rhyme play, colors, and short memory games."
        exercises = "Use quick picture choices, songs, and two-step directions."
    elif age == 5:
        focus = "Build number bonds, phonics, sight words, story meaning, patterns, coding steps, and working memory."
        exercises = "Mix reading scrolls, David's numbers, code paths, memory baskets, and simple parable maths."
    elif age == 6:
        focus = "Grow reading fluency, two-step maths, map language, geometry, coding loops, and reasoning speed."
        exercises = "Use timed number paths, sentence building, code debugging, mazes, and creation facts."
    else:
        focus = "Stretch reasoning, independent reading, multi-step problems, and rich vocabulary."
        exercises = "Use harder puzzles, longer passages, word problems, and explain-your-thinking tasks."
    return {
        "title": f"{name}'s growth plan",
        "focus": focus,
        "exercises": exercises,
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
        if len(chosen) == 5:
            break

    if len(chosen) < 5:
        for item in ranked:
            if item not in chosen:
                chosen.append(item)
            if len(chosen) == 5:
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
