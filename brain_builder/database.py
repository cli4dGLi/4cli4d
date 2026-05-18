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
    "difficulty_assessment": "1",
    "voice_notice_ack": "false",
}


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with connect() as conn:
        conn.executescript(
            """
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
            """
        )
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


def get_difficulty(module: str) -> int:
    value = get_setting(f"difficulty_{module}", "1") or "1"
    try:
        return max(1, min(5, int(value)))
    except ValueError:
        return 1


def set_difficulty(module: str, level: int) -> None:
    set_setting(f"difficulty_{module}", str(max(1, min(5, level))))


def log_session(module: str, subtopic: str, score: int, stars: int, difficulty_level: int) -> int:
    with connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO sessions(module, subtopic, score, stars, difficulty_level, timestamp)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (module, subtopic, int(score), int(stars), int(difficulty_level), now_iso()),
        )
        conn.commit()
        session_id = int(cur.lastrowid)
    check_award_badges()
    return session_id


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


def get_recent_sessions(module: str | None = None, limit: int = 7) -> List[sqlite3.Row]:
    query = "SELECT * FROM sessions"
    params: list[Any] = []
    if module:
        query += " WHERE module = ?"
        params.append(module)
    query += " ORDER BY datetime(timestamp) DESC LIMIT ?"
    params.append(limit)
    with connect() as conn:
        return list(conn.execute(query, params).fetchall())


def get_all_sessions() -> List[sqlite3.Row]:
    with connect() as conn:
        return list(conn.execute("SELECT * FROM sessions ORDER BY datetime(timestamp) DESC").fetchall())


def get_total_stars() -> int:
    with connect() as conn:
        row = conn.execute("SELECT COALESCE(SUM(stars), 0) AS total FROM sessions").fetchone()
    return int(row["total"] or 0)


def get_current_streak() -> int:
    dates = set()
    with connect() as conn:
        for table, column in [("sessions", "timestamp"), ("assessments", "date"), ("reading_assessments", "date")]:
            rows = conn.execute(f"SELECT {column} AS played FROM {table}").fetchall()
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


def _module_average(module: str, limit: int | None = None) -> tuple[int, float]:
    query = "SELECT score FROM sessions WHERE module = ? ORDER BY datetime(timestamp) DESC"
    params: list[Any] = [module]
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
        ("maths", 10, 0.80, "Maths Wizard"),
        ("english", 10, 0.80, "Word Champion"),
        ("wordproblems", 5, 0.80, "Story Solver"),
        ("science", 10, 0.80, "Wonder Explorer"),
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


def weak_areas() -> List[Dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT module, subtopic, COUNT(*) AS attempts, AVG(score) AS avg_score
            FROM sessions
            GROUP BY module, subtopic
            HAVING attempts >= 1
            ORDER BY avg_score ASC
            LIMIT 6
            """
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
) -> int:
    with connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO assessments(
                assessment_type, date, composite_score, percentile_rank,
                vci_score, wmi_score, psi_score, fri_score, vsi_score, pa_score,
                duration_seconds, ai_insights
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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


def get_assessments(limit: int | None = None) -> List[sqlite3.Row]:
    query = "SELECT * FROM assessments ORDER BY datetime(date) DESC"
    params: list[Any] = []
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


def get_weekly_domain_practice() -> Dict[str, Dict[str, int]]:
    today = date.today()
    days = [(today - timedelta(days=offset)).isoformat() for offset in range(6, -1, -1)]
    matrix = {day: {domain: 0 for domain in ["vci", "wmi", "psi", "fri", "vsi", "pa"]} for day in days}
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT substr(a.date, 1, 10) AS day, dt.domain
            FROM domain_tasks dt
            JOIN assessments a ON a.id = dt.assessment_id
            WHERE date(a.date) >= date('now', '-6 days')
            GROUP BY day, dt.domain
            """
        ).fetchall()
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
) -> int:
    with connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO reading_assessments(
                date, passage_id, passage_difficulty, accuracy_pct, reading_level,
                error_types_json, phonics_strong_json, phonics_weak_json,
                comprehension_score, wpm_estimate
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            ),
        )
        conn.commit()
        return int(cur.lastrowid)


def get_reading_assessments(limit: int | None = None) -> List[sqlite3.Row]:
    query = """
        SELECT ra.*, p.text AS passage_text
        FROM reading_assessments ra
        LEFT JOIN passages p ON p.id = ra.passage_id
        ORDER BY datetime(ra.date) DESC
    """
    params: list[Any] = []
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
