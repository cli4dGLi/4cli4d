from __future__ import annotations

import csv
import io
import json
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "brain_builder.db"


DEFAULT_SETTINGS = {
    "child_name": "OB",
    "parent_pin": "1234",
    "difficulty_maths": "1",
    "difficulty_english": "1",
    "difficulty_wordproblems": "1",
    "difficulty_science": "1",
    "difficulty_puzzles": "1",
    "difficulty_assessment": "1",
    "voice_notice_ack": "false",
    "ai_child_profile_context_allowed": "false",
}


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    columns = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in columns:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def init_db() -> None:
    with connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS child_profiles (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                age_years INTEGER,
                date_of_birth TEXT,
                created_by_user TEXT,
                created_at TEXT,
                updated_at TEXT,
                last_seen_at TEXT
            );

            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY,
                module TEXT,
                subtopic TEXT,
                score INTEGER,
                stars INTEGER,
                difficulty_level INTEGER,
                timestamp TEXT
            );

            CREATE TABLE IF NOT EXISTS badges (
                id INTEGER PRIMARY KEY,
                badge_name TEXT UNIQUE,
                earned_date TEXT
            );

            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            );

            CREATE TABLE IF NOT EXISTS assessments (
                id INTEGER PRIMARY KEY,
                assessment_type TEXT,
                date TEXT,
                composite_score REAL,
                percentile_rank REAL,
                vci_score REAL,
                wmi_score REAL,
                psi_score REAL,
                fri_score REAL,
                vsi_score REAL,
                pa_score REAL,
                duration_seconds INTEGER,
                ai_insights TEXT
            );

            CREATE TABLE IF NOT EXISTS domain_tasks (
                id INTEGER PRIMARY KEY,
                assessment_id INTEGER,
                domain TEXT,
                task_description TEXT,
                correct INTEGER,
                response_time_ms INTEGER,
                difficulty INTEGER,
                FOREIGN KEY (assessment_id) REFERENCES assessments(id)
            );

            CREATE TABLE IF NOT EXISTS reading_assessments (
                id INTEGER PRIMARY KEY,
                date TEXT,
                passage_id INTEGER,
                passage_difficulty TEXT,
                accuracy_pct REAL,
                reading_level TEXT,
                error_types_json TEXT,
                phonics_strong_json TEXT,
                phonics_weak_json TEXT,
                comprehension_score INTEGER,
                wpm_estimate REAL,
                FOREIGN KEY (passage_id) REFERENCES passages(id)
            );

            CREATE TABLE IF NOT EXISTS passages (
                id INTEGER PRIMARY KEY,
                difficulty TEXT,
                text TEXT,
                word_count INTEGER,
                target_phonics TEXT
            );

            CREATE TABLE IF NOT EXISTS skill_mastery (
                skill_key TEXT PRIMARY KEY,
                module TEXT,
                subtopic TEXT,
                display_name TEXT,
                mastery REAL,
                attempts INTEGER,
                correct_total INTEGER,
                total_questions INTEGER,
                avg_response_ms INTEGER,
                streak INTEGER,
                last_score INTEGER,
                last_practiced TEXT,
                next_due_date TEXT
            );

            CREATE TABLE IF NOT EXISTS daily_plans (
                id INTEGER PRIMARY KEY,
                plan_date TEXT,
                position INTEGER,
                module TEXT,
                subtopic TEXT,
                title TEXT,
                reason TEXT,
                status TEXT DEFAULT 'planned',
                created_at TEXT,
                UNIQUE(plan_date, module, subtopic)
            );

            CREATE TABLE IF NOT EXISTS app_users (
                id INTEGER PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                display_name TEXT,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'learner',
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT,
                updated_at TEXT,
                last_login_at TEXT
            );
            """
        )
        _ensure_column(conn, "sessions", "child_profile_id", "INTEGER")
        _ensure_column(conn, "assessments", "child_profile_id", "INTEGER")
        _ensure_column(conn, "reading_assessments", "child_profile_id", "INTEGER")
        _ensure_column(conn, "skill_mastery", "child_profile_id", "INTEGER")
        _ensure_column(conn, "daily_plans", "child_profile_id", "INTEGER")
        for key, value in DEFAULT_SETTINGS.items():
            conn.execute("INSERT OR IGNORE INTO settings(key, value) VALUES (?, ?)", (key, value))
        conn.commit()


def now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat()


def get_setting(key: str, default: Optional[str] = None) -> Optional[str]:
    with connect() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else default


def set_setting(key: str, value: str) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT INTO settings(key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )
        conn.commit()


def get_parent_pin() -> str:
    return get_setting("parent_pin", "1234") or "1234"


def set_parent_pin(pin: str) -> None:
    set_setting("parent_pin", pin)


def get_active_child_id() -> int | None:
    try:
        import streamlit as st

        value = st.session_state.get("active_child_id")
        return int(value) if value else None
    except Exception:
        return None


def _resolve_child_id(child_profile_id: int | None = None) -> int | None:
    return child_profile_id if child_profile_id is not None else get_active_child_id()


def create_child_profile(
    name: str,
    age_years: int,
    date_of_birth: str,
    created_by_user: str | None = None,
) -> int:
    clean_name = name.strip()[:60] or "Friend"
    safe_age = max(2, min(12, int(age_years)))
    now = now_iso()
    with connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO child_profiles(name, age_years, date_of_birth, created_by_user, created_at, updated_at, last_seen_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (clean_name, safe_age, date_of_birth, created_by_user, now, now, now),
        )
        conn.commit()
        return int(cur.lastrowid)


def get_child_profiles() -> List[sqlite3.Row]:
    with connect() as conn:
        return list(conn.execute("SELECT * FROM child_profiles ORDER BY last_seen_at DESC, name ASC").fetchall())


def get_child_profile(child_profile_id: int | None = None) -> sqlite3.Row | None:
    child_id = _resolve_child_id(child_profile_id)
    if child_id is None:
        return None
    with connect() as conn:
        return conn.execute("SELECT * FROM child_profiles WHERE id = ?", (int(child_id),)).fetchone()


def touch_child_profile(child_profile_id: int) -> None:
    with connect() as conn:
        conn.execute(
            "UPDATE child_profiles SET last_seen_at = ?, updated_at = ? WHERE id = ?",
            (now_iso(), now_iso(), int(child_profile_id)),
        )
        conn.commit()


def child_first_name(child_profile_id: int | None = None, default: str = "friend") -> str:
    profile = get_child_profile(child_profile_id)
    if not profile:
        return default
    return str(profile["name"]).strip().split()[0]


def ai_child_profile_context_allowed() -> bool:
    return get_setting("ai_child_profile_context_allowed", "false") == "true"


def set_ai_child_profile_context_allowed(allowed: bool) -> None:
    set_setting("ai_child_profile_context_allowed", "true" if allowed else "false")


def ai_child_profile_context(child_profile_id: int | None = None) -> str:
    profile = get_child_profile(child_profile_id)
    if not ai_child_profile_context_allowed():
        age_text = f" Active child age_years={profile['age_years']}." if profile else ""
        return (
            "Parent has not approved sharing the child's name or date of birth with Claude. "
            f"{age_text} Tailor only from age band, active difficulty, and learning performance."
        )
    if not profile:
        return "No active child profile is selected."
    return (
        "Parent-approved child profile for personalization: "
        f"name={profile['name']}; age_years={profile['age_years']}; "
        f"date_of_birth={profile['date_of_birth']}. "
        "Use this only to adapt tone, difficulty, examples, and development planning. "
        "Do not reveal the date of birth back to the child."
    )


def normalize_username(username: str) -> str:
    return username.strip().lower()


def get_app_user(username: str) -> sqlite3.Row | None:
    clean = normalize_username(username)
    with connect() as conn:
        return conn.execute("SELECT * FROM app_users WHERE username = ?", (clean,)).fetchone()


def list_app_users() -> List[sqlite3.Row]:
    with connect() as conn:
        return list(conn.execute("SELECT * FROM app_users ORDER BY role ASC, username ASC").fetchall())


def upsert_app_user(
    username: str,
    password_hash: str,
    role: str = "learner",
    display_name: str | None = None,
    is_active: bool = True,
) -> None:
    clean = normalize_username(username)
    safe_role = role if role in {"admin", "learner"} else "learner"
    now = now_iso()
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO app_users(username, display_name, password_hash, role, is_active, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(username) DO UPDATE SET
                display_name = COALESCE(excluded.display_name, app_users.display_name),
                password_hash = excluded.password_hash,
                role = excluded.role,
                is_active = excluded.is_active,
                updated_at = excluded.updated_at
            """,
            (clean, display_name or clean, password_hash, safe_role, int(is_active), now, now),
        )
        conn.commit()


def create_app_user(username: str, display_name: str, password_hash: str, role: str = "learner") -> None:
    clean = normalize_username(username)
    safe_role = role if role in {"admin", "learner"} else "learner"
    now = now_iso()
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO app_users(username, display_name, password_hash, role, is_active, created_at, updated_at)
            VALUES (?, ?, ?, ?, 1, ?, ?)
            """,
            (clean, display_name.strip() or clean, password_hash, safe_role, now, now),
        )
        conn.commit()


def update_app_user(
    username: str,
    display_name: str | None = None,
    password_hash: str | None = None,
    role: str | None = None,
    is_active: bool | None = None,
) -> None:
    clean = normalize_username(username)
    assignments = ["updated_at = ?"]
    params: list[Any] = [now_iso()]
    if display_name is not None:
        assignments.append("display_name = ?")
        params.append(display_name.strip() or clean)
    if password_hash is not None:
        assignments.append("password_hash = ?")
        params.append(password_hash)
    if role is not None:
        assignments.append("role = ?")
        params.append(role if role in {"admin", "learner"} else "learner")
    if is_active is not None:
        assignments.append("is_active = ?")
        params.append(int(is_active))
    params.append(clean)
    with connect() as conn:
        conn.execute(f"UPDATE app_users SET {', '.join(assignments)} WHERE username = ?", params)
        conn.commit()


def record_user_login(username: str) -> None:
    clean = normalize_username(username)
    with connect() as conn:
        conn.execute("UPDATE app_users SET last_login_at = ? WHERE username = ?", (now_iso(), clean))
        conn.commit()


def get_difficulty(module: str) -> int:
    value = get_setting(f"difficulty_{module}", "1") or "1"
    try:
        return max(1, min(5, int(value)))
    except ValueError:
        return 1


def set_difficulty(module: str, level: int) -> None:
    set_setting(f"difficulty_{module}", str(max(1, min(5, level))))


def log_session(
    module: str,
    subtopic: str,
    score: int,
    stars: int,
    difficulty_level: int,
    child_profile_id: int | None = None,
) -> int:
    timestamp = now_iso()
    child_id = _resolve_child_id(child_profile_id)
    with connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO sessions(module, subtopic, score, stars, difficulty_level, timestamp, child_profile_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (module, subtopic, int(score), int(stars), int(difficulty_level), timestamp, child_id),
        )
        conn.commit()
        session_id = int(cur.lastrowid)
    update_skill_mastery(module, subtopic, score, 5, child_profile_id=child_id)
    mark_daily_plan_done(module, subtopic, child_profile_id=child_id)
    check_award_badges()
    return session_id


def skill_key(module: str, subtopic: str, child_profile_id: int | None = None) -> str:
    child_id = _resolve_child_id(child_profile_id)
    prefix = f"child-{child_id}:" if child_id else "shared:"
    safe = "".join(ch.lower() if ch.isalnum() else "-" for ch in f"{prefix}{module}:{subtopic}")
    while "--" in safe:
        safe = safe.replace("--", "-")
    return safe.strip("-")


def update_skill_mastery(
    module: str,
    subtopic: str,
    score: int,
    total_questions: int = 5,
    avg_response_ms: int | None = None,
    child_profile_id: int | None = None,
) -> None:
    child_id = _resolve_child_id(child_profile_id)
    key = skill_key(module, subtopic, child_id)
    today = date.today()
    accuracy = max(0.0, min(1.0, int(score) / max(1, int(total_questions))))
    with connect() as conn:
        row = conn.execute("SELECT * FROM skill_mastery WHERE skill_key = ?", (key,)).fetchone()
        if row:
            old_mastery = float(row["mastery"] or 0.35)
            attempts = int(row["attempts"] or 0) + 1
            correct_total = int(row["correct_total"] or 0) + int(score)
            total = int(row["total_questions"] or 0) + int(total_questions)
            streak = int(row["streak"] or 0) + 1 if accuracy >= 0.8 else 0
            old_avg = int(row["avg_response_ms"] or 0)
        else:
            old_mastery = 0.35
            attempts = 1
            correct_total = int(score)
            total = int(total_questions)
            streak = 1 if accuracy >= 0.8 else 0
            old_avg = 0

        new_mastery = round(max(0.05, min(0.99, (old_mastery * 0.68) + (accuracy * 0.32))), 3)
        if accuracy >= 0.9:
            gap_days = 4
        elif accuracy >= 0.7:
            gap_days = 2
        elif accuracy >= 0.5:
            gap_days = 1
        else:
            gap_days = 0
        due = (today + timedelta(days=gap_days)).isoformat()
        if avg_response_ms:
            avg_ms = int((old_avg * 0.7) + (int(avg_response_ms) * 0.3)) if old_avg else int(avg_response_ms)
        else:
            avg_ms = old_avg

        conn.execute(
            """
            INSERT INTO skill_mastery(
                skill_key, module, subtopic, display_name, mastery, attempts,
                correct_total, total_questions, avg_response_ms, streak,
                last_score, last_practiced, next_due_date, child_profile_id
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(skill_key) DO UPDATE SET
                module = excluded.module,
                subtopic = excluded.subtopic,
                display_name = excluded.display_name,
                mastery = excluded.mastery,
                attempts = excluded.attempts,
                correct_total = excluded.correct_total,
                total_questions = excluded.total_questions,
                avg_response_ms = excluded.avg_response_ms,
                streak = excluded.streak,
                last_score = excluded.last_score,
                last_practiced = excluded.last_practiced,
                next_due_date = excluded.next_due_date,
                child_profile_id = excluded.child_profile_id
            """,
            (
                key,
                module,
                subtopic,
                subtopic,
                new_mastery,
                attempts,
                correct_total,
                total,
                avg_ms,
                streak,
                int(score),
                today.isoformat(),
                due,
                child_id,
            ),
        )
        conn.commit()


def get_skill_mastery_rows(child_profile_id: int | None = None) -> List[sqlite3.Row]:
    child_id = _resolve_child_id(child_profile_id)
    with connect() as conn:
        if child_id is None:
            return list(conn.execute("SELECT * FROM skill_mastery ORDER BY mastery ASC, next_due_date ASC").fetchall())
        return list(
            conn.execute(
                "SELECT * FROM skill_mastery WHERE child_profile_id = ? ORDER BY mastery ASC, next_due_date ASC",
                (child_id,),
            ).fetchall()
        )


def _daily_plan_key(day: str, child_profile_id: int | None = None) -> str:
    child_id = _resolve_child_id(child_profile_id)
    return f"child-{child_id}:{day}" if child_id else day


def get_daily_plan(plan_date: str | None = None, child_profile_id: int | None = None) -> List[sqlite3.Row]:
    day = plan_date or date.today().isoformat()
    key = _daily_plan_key(day, child_profile_id)
    with connect() as conn:
        return list(
            conn.execute(
                "SELECT * FROM daily_plans WHERE plan_date = ? ORDER BY position ASC",
                (key,),
            ).fetchall()
        )


def save_daily_plan(
    items: Iterable[Dict[str, Any]],
    plan_date: str | None = None,
    child_profile_id: int | None = None,
) -> None:
    day = plan_date or date.today().isoformat()
    child_id = _resolve_child_id(child_profile_id)
    key = _daily_plan_key(day, child_id)
    with connect() as conn:
        conn.execute("DELETE FROM daily_plans WHERE plan_date = ?", (key,))
        for index, item in enumerate(items, 1):
            conn.execute(
                """
                INSERT INTO daily_plans(plan_date, position, module, subtopic, title, reason, status, created_at, child_profile_id)
                VALUES (?, ?, ?, ?, ?, ?, 'planned', ?, ?)
                """,
                (
                    key,
                    index,
                    item["module"],
                    item["subtopic"],
                    item["title"],
                    item["reason"],
                    now_iso(),
                    child_id,
                ),
            )
        conn.commit()


def mark_daily_plan_done(
    module: str,
    subtopic: str,
    plan_date: str | None = None,
    child_profile_id: int | None = None,
) -> None:
    day = plan_date or date.today().isoformat()
    key = _daily_plan_key(day, child_profile_id)
    with connect() as conn:
        conn.execute(
            """
            UPDATE daily_plans
            SET status = 'done'
            WHERE plan_date = ? AND module = ? AND subtopic = ?
            """,
            (key, module, subtopic),
        )
        conn.commit()


def adapt_difficulty(module: str, score: int) -> int:
    level = get_difficulty(module)
    rows = get_recent_sessions(module=module, limit=2)
    if len(rows) >= 2 and all(int(row["score"]) >= 4 for row in rows):
        level += 1
    elif int(score) <= 2:
        level -= 1
    level = max(1, min(5, level))
    set_difficulty(module, level)
    return level


def get_recent_sessions(module: str | None = None, limit: int = 7, child_profile_id: int | None = None) -> List[sqlite3.Row]:
    child_id = _resolve_child_id(child_profile_id)
    query = "SELECT * FROM sessions"
    params: list[Any] = []
    clauses: list[str] = []
    if module:
        clauses.append("module = ?")
        params.append(module)
    if child_id is not None:
        clauses.append("child_profile_id = ?")
        params.append(child_id)
    if clauses:
        query += " WHERE " + " AND ".join(clauses)
    query += " ORDER BY datetime(timestamp) DESC LIMIT ?"
    params.append(limit)
    with connect() as conn:
        return list(conn.execute(query, params).fetchall())


def get_all_sessions(child_profile_id: int | None = None) -> List[sqlite3.Row]:
    child_id = _resolve_child_id(child_profile_id)
    query = """
        SELECT s.*, cp.name AS child_name
        FROM sessions s
        LEFT JOIN child_profiles cp ON cp.id = s.child_profile_id
    """
    params: list[Any] = []
    if child_id is not None:
        query += " WHERE s.child_profile_id = ?"
        params.append(child_id)
    query += " ORDER BY datetime(s.timestamp) DESC"
    with connect() as conn:
        return list(conn.execute(query, params).fetchall())


def get_total_stars(child_profile_id: int | None = None) -> int:
    child_id = _resolve_child_id(child_profile_id)
    with connect() as conn:
        if child_id is None:
            row = conn.execute("SELECT COALESCE(SUM(stars), 0) AS total FROM sessions").fetchone()
        else:
            row = conn.execute(
                "SELECT COALESCE(SUM(stars), 0) AS total FROM sessions WHERE child_profile_id = ?",
                (child_id,),
            ).fetchone()
    return int(row["total"] or 0)


def get_current_streak(child_profile_id: int | None = None) -> int:
    child_id = _resolve_child_id(child_profile_id)
    dates = set()
    with connect() as conn:
        for table, column in [("sessions", "timestamp"), ("assessments", "date"), ("reading_assessments", "date")]:
            if child_id is None:
                rows = conn.execute(f"SELECT {column} AS played FROM {table}").fetchall()
            else:
                rows = conn.execute(
                    f"SELECT {column} AS played FROM {table} WHERE child_profile_id = ?",
                    (child_id,),
                ).fetchall()
            for row in rows:
                value = row["played"]
                if value:
                    dates.add(str(value)[:10])
    streak = 0
    cursor = date.today()
    while cursor.isoformat() in dates:
        streak += 1
        cursor -= timedelta(days=1)
    return streak


def _module_average(module: str, limit: int | None = None, child_profile_id: int | None = None) -> tuple[int, float]:
    child_id = _resolve_child_id(child_profile_id)
    query = "SELECT score FROM sessions WHERE module = ? ORDER BY datetime(timestamp) DESC"
    params: list[Any] = [module]
    if child_id is not None:
        query = "SELECT score FROM sessions WHERE module = ? AND child_profile_id = ? ORDER BY datetime(timestamp) DESC"
        params.append(child_id)
    if limit:
        query += " LIMIT ?"
        params.append(limit)
    with connect() as conn:
        rows = conn.execute(query, params).fetchall()
    if not rows:
        return 0, 0.0
    return len(rows), sum(int(row["score"]) for row in rows) / (len(rows) * 5)


def check_award_badges() -> None:
    rules = [
        ("maths", 10, 0.80, "Number Hero"),
        ("english", 10, 0.80, "Reading Hero"),
        ("wordproblems", 5, 0.80, "Story Rescue Hero"),
        ("science", 10, 0.80, "Super Scientist"),
        ("puzzles", 10, 0.80, "Puzzle Hero"),
    ]
    today = date.today().isoformat()
    with connect() as conn:
        for module, needed, target, badge in rules:
            count, avg = _module_average(module)
            if count >= needed and avg >= target:
                conn.execute(
                    "INSERT OR IGNORE INTO badges(badge_name, earned_date) VALUES (?, ?)",
                    (badge, today),
                )
        conn.commit()


def get_badges() -> List[sqlite3.Row]:
    with connect() as conn:
        return list(conn.execute("SELECT * FROM badges ORDER BY earned_date DESC").fetchall())


def get_score_chart_rows(module: str | None = None, limit: int = 7) -> List[Dict[str, Any]]:
    rows = list(reversed(get_recent_sessions(module=module, limit=limit)))
    return [
        {
            "Session": str(i + 1),
            "Score": int(row["score"]),
            "Module": row["module"],
            "Subtopic": row["subtopic"],
            "Date": str(row["timestamp"])[:10],
        }
        for i, row in enumerate(rows)
    ]


def weak_areas(child_profile_id: int | None = None) -> List[Dict[str, Any]]:
    child_id = _resolve_child_id(child_profile_id)
    where = "WHERE child_profile_id = ?" if child_id is not None else ""
    params: list[Any] = [child_id] if child_id is not None else []
    with connect() as conn:
        rows = conn.execute(
            f"""
            SELECT module, subtopic, COUNT(*) AS attempts, AVG(score) AS avg_score
            FROM sessions
            {where}
            GROUP BY module, subtopic
            HAVING attempts >= 1
            ORDER BY avg_score ASC
            LIMIT 6
            """,
            params,
        ).fetchall()
    return [dict(row) for row in rows]


def log_assessment(
    assessment_type: str,
    domain_scores: Dict[str, float],
    composite_score: float,
    percentile_rank: float,
    duration_seconds: int,
    ai_insights: Dict[str, Any],
    tasks: Iterable[Dict[str, Any]],
    child_profile_id: int | None = None,
) -> int:
    child_id = _resolve_child_id(child_profile_id)
    with connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO assessments(
                assessment_type, date, composite_score, percentile_rank,
                vci_score, wmi_score, psi_score, fri_score, vsi_score, pa_score,
                duration_seconds, ai_insights, child_profile_id
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                assessment_type,
                now_iso(),
                composite_score,
                percentile_rank,
                domain_scores.get("vci"),
                domain_scores.get("wmi"),
                domain_scores.get("psi"),
                domain_scores.get("fri"),
                domain_scores.get("vsi"),
                domain_scores.get("pa"),
                duration_seconds,
                json.dumps(ai_insights),
                child_id,
            ),
        )
        assessment_id = int(cur.lastrowid)
        for task in tasks:
            conn.execute(
                """
                INSERT INTO domain_tasks(
                    assessment_id, domain, task_description, correct, response_time_ms, difficulty
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    assessment_id,
                    task.get("domain"),
                    task.get("task_description", ""),
                    int(bool(task.get("correct"))),
                    int(task.get("response_time_ms") or 0),
                    int(task.get("difficulty") or 1),
                ),
            )
        conn.commit()
    return assessment_id


def get_assessments(limit: int | None = None, child_profile_id: int | None = None) -> List[sqlite3.Row]:
    child_id = _resolve_child_id(child_profile_id)
    query = "SELECT * FROM assessments ORDER BY datetime(date) DESC"
    params: list[Any] = []
    if child_id is not None:
        query = "SELECT * FROM assessments WHERE child_profile_id = ? ORDER BY datetime(date) DESC"
        params.append(child_id)
    if limit:
        query += " LIMIT ?"
        params.append(limit)
    with connect() as conn:
        return list(conn.execute(query, params).fetchall())


def get_latest_assessment() -> sqlite3.Row | None:
    rows = get_assessments(limit=1)
    return rows[0] if rows else None


def get_domain_tasks(assessment_id: int | None = None) -> List[sqlite3.Row]:
    query = "SELECT dt.*, a.date FROM domain_tasks dt JOIN assessments a ON a.id = dt.assessment_id"
    params: list[Any] = []
    if assessment_id is not None:
        query += " WHERE assessment_id = ?"
        params.append(assessment_id)
    query += " ORDER BY datetime(a.date) DESC, dt.id ASC"
    with connect() as conn:
        return list(conn.execute(query, params).fetchall())


def get_weekly_domain_practice(child_profile_id: int | None = None) -> Dict[str, Dict[str, int]]:
    child_id = _resolve_child_id(child_profile_id)
    today = date.today()
    days = [(today - timedelta(days=offset)).isoformat() for offset in range(6, -1, -1)]
    matrix = {day: {domain: 0 for domain in ["vci", "wmi", "psi", "fri", "vsi", "pa"]} for day in days}
    with connect() as conn:
        query = """
            SELECT substr(a.date, 1, 10) AS day, dt.domain
            FROM domain_tasks dt
            JOIN assessments a ON a.id = dt.assessment_id
            WHERE date(a.date) >= date('now', '-6 days')
        """
        params: list[Any] = []
        if child_id is not None:
            query += " AND a.child_profile_id = ?"
            params.append(child_id)
        query += """
            GROUP BY day, dt.domain
        """
        rows = conn.execute(query, params).fetchall()
    for row in rows:
        day = row["day"]
        domain = row["domain"]
        if day in matrix and domain in matrix[day]:
            matrix[day][domain] = 1
    return matrix


def save_passages(passages: Iterable[Dict[str, Any]]) -> None:
    with connect() as conn:
        for passage in passages:
            text = str(passage.get("text", "")).strip()
            difficulty = str(passage.get("difficulty", "starter")).strip().lower()
            if not text:
                continue
            word_count = len(text.split())
            conn.execute(
                """
                INSERT INTO passages(difficulty, text, word_count, target_phonics)
                VALUES (?, ?, ?, ?)
                """,
                (difficulty, text, word_count, str(passage.get("target_phonics", "mixed"))),
            )
        conn.commit()


def count_passages() -> int:
    with connect() as conn:
        row = conn.execute("SELECT COUNT(*) AS count FROM passages").fetchone()
    return int(row["count"] or 0)


def get_passages(difficulty: str | None = None) -> List[sqlite3.Row]:
    query = "SELECT * FROM passages"
    params: list[Any] = []
    if difficulty:
        query += " WHERE difficulty = ?"
        params.append(difficulty)
    query += " ORDER BY id ASC"
    with connect() as conn:
        return list(conn.execute(query, params).fetchall())


def get_passage(passage_id: int) -> sqlite3.Row | None:
    with connect() as conn:
        return conn.execute("SELECT * FROM passages WHERE id = ?", (passage_id,)).fetchone()


def log_reading_assessment(
    passage_id: int,
    passage_difficulty: str,
    accuracy_pct: float,
    reading_level: str,
    error_types: Dict[str, Any],
    phonics_strong: List[str],
    phonics_weak: List[str],
    comprehension_score: int,
    wpm_estimate: float,
    child_profile_id: int | None = None,
) -> int:
    child_id = _resolve_child_id(child_profile_id)
    with connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO reading_assessments(
                date, passage_id, passage_difficulty, accuracy_pct, reading_level,
                error_types_json, phonics_strong_json, phonics_weak_json,
                comprehension_score, wpm_estimate, child_profile_id
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                now_iso(),
                passage_id,
                passage_difficulty,
                accuracy_pct,
                reading_level,
                json.dumps(error_types),
                json.dumps(phonics_strong),
                json.dumps(phonics_weak),
                int(comprehension_score),
                float(wpm_estimate),
                child_id,
            ),
        )
        conn.commit()
        return int(cur.lastrowid)


def get_reading_assessments(limit: int | None = None, child_profile_id: int | None = None) -> List[sqlite3.Row]:
    child_id = _resolve_child_id(child_profile_id)
    query = """
        SELECT ra.*, p.text AS passage_text
        FROM reading_assessments ra
        LEFT JOIN passages p ON p.id = ra.passage_id
    """
    params: list[Any] = []
    if child_id is not None:
        query += " WHERE ra.child_profile_id = ?"
        params.append(child_id)
    query += " ORDER BY datetime(ra.date) DESC"
    if limit:
        query += " LIMIT ?"
        params.append(limit)
    with connect() as conn:
        return list(conn.execute(query, params).fetchall())


def export_history_csv() -> str:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["record_type", "date", "module_or_domain", "subtopic", "score", "details"])

    for row in get_all_sessions():
        writer.writerow([
            "learning_session",
            row["timestamp"],
            row["module"],
            row["subtopic"],
            row["score"],
            f"stars={row['stars']}; difficulty={row['difficulty_level']}",
        ])

    for row in get_assessments():
        writer.writerow([
            "cognitive_assessment",
            row["date"],
            row["assessment_type"],
            "composite",
            row["composite_score"],
            f"percentile={row['percentile_rank']}",
        ])

    for row in get_reading_assessments():
        writer.writerow([
            "reading_assessment",
            row["date"],
            "reading",
            row["passage_difficulty"],
            row["accuracy_pct"],
            f"level={row['reading_level']}; wpm={row['wpm_estimate']}; comprehension={row['comprehension_score']}",
        ])

    return output.getvalue()
