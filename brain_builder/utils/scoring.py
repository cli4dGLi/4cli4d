from __future__ import annotations

from datetime import date
from typing import Dict, Iterable, List, Tuple


DOMAIN_LABELS = {
    "vci": "Verbal Comprehension",
    "wmi": "Working Memory",
    "psi": "Processing Speed",
    "fri": "Fluid Reasoning",
    "vsi": "Visual-Spatial",
    "pa": "Phonological Awareness",
}

DOMAIN_WEIGHTS = {
    "vci": 0.22,
    "wmi": 0.22,
    "psi": 0.20,
    "fri": 0.20,
    "vsi": 0.10,
    "pa": 0.06,
}

PERCENTILE_TABLE = [
    (90, 25),
    (95, 37),
    (100, 50),
    (105, 63),
    (110, 75),
    (115, 84),
    (120, 91),
    (125, 95),
    (130, 98),
]


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def percent_to_standard_score(score_pct: float) -> float:
    """Map game accuracy to a parent-facing age-normed estimate."""
    return round(clamp(70 + (score_pct * 0.60), 70, 130), 1)


def calculate_composite(domain_scores: Dict[str, float]) -> float:
    if not domain_scores:
        return 100.0
    total = 0.0
    weight_total = 0.0
    for domain, weight in DOMAIN_WEIGHTS.items():
        if domain in domain_scores:
            total += domain_scores[domain] * weight
            weight_total += weight
    if weight_total == 0:
        return 100.0
    return round(total / weight_total, 1)


def percentile_for_score(score: float) -> float:
    if score <= PERCENTILE_TABLE[0][0]:
        return float(PERCENTILE_TABLE[0][1])
    if score >= PERCENTILE_TABLE[-1][0]:
        extra = min(1.0, (score - 130) / 10)
        return round(98 + extra, 1)

    for (s1, p1), (s2, p2) in zip(PERCENTILE_TABLE, PERCENTILE_TABLE[1:]):
        if s1 <= score <= s2:
            ratio = (score - s1) / (s2 - s1)
            return round(p1 + ratio * (p2 - p1), 1)
    return 50.0


def score_band(score: float) -> str:
    if score >= 130:
        return "Gifted / Top 2%"
    if score >= 120:
        return "Superior / Top 9%"
    if score >= 110:
        return "High Average / Top 25%"
    if score >= 90:
        return "Average"
    if score >= 80:
        return "Low Average"
    return "Developing"


def stars_for_score(score: int, total: int = 5, avg_seconds: float | None = None) -> int:
    accuracy = score / max(total, 1)
    if accuracy >= 0.8:
        return 3
    if accuracy >= 0.6:
        return 2
    return 1


def running_record_level(accuracy_pct: float) -> str:
    if accuracy_pct >= 95:
        return "Independent level"
    if accuracy_pct >= 90:
        return "Instructional level"
    return "Frustration level"


def wpm_band(wpm: float) -> str:
    if wpm >= 60:
        return "Above benchmark"
    if wpm >= 30:
        return "At benchmark"
    if wpm >= 10:
        return "Below benchmark"
    return "Well below benchmark"


def strongest_domain(domain_scores: Dict[str, float]) -> str:
    if not domain_scores:
        return "No data yet"
    domain = max(domain_scores, key=domain_scores.get)
    return DOMAIN_LABELS.get(domain, domain.upper())


def weak_domains_from_sessions(rows: Iterable[dict]) -> List[Tuple[str, float]]:
    totals: Dict[str, List[int]] = {}
    for row in rows:
        key = row.get("subtopic") or row.get("module") or "Practice"
        totals.setdefault(str(key), []).append(int(row.get("score") or 0))
    averages = [(key, round(sum(vals) / (len(vals) * 5) * 100, 1)) for key, vals in totals.items()]
    return sorted(averages, key=lambda item: item[1])[:5]


def today_iso() -> str:
    return date.today().isoformat()
