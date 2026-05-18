from __future__ import annotations

import random
from typing import Any, Dict, List

from claude_api import generate_assessment_tasks


DOMAINS = {
    "vci": "Verbal Comprehension",
    "wmi": "Working Memory",
    "psi": "Processing Speed",
    "fri": "Fluid Reasoning",
    "vsi": "Visual-Spatial",
    "pa": "Phonological Awareness",
}

DOMAIN_COUNTS = {
    "vci": 8,
    "wmi": 6,
    "psi": 6,
    "fri": 8,
    "vsi": 6,
    "pa": 6,
}


def domains_for_assessment(assessment_type: str, mini_domain: str | None = None) -> List[str]:
    if assessment_type == "full":
        return list(DOMAINS.keys())
    if assessment_type == "quick":
        return random.sample(list(DOMAINS.keys()), 3)
    if mini_domain in DOMAINS:
        return [mini_domain]
    return [random.choice(list(DOMAINS.keys()))]


def task_count(domain: str, assessment_type: str) -> int:
    if assessment_type == "mini":
        return 5
    return DOMAIN_COUNTS.get(domain, 6)


def _sequence_options(answer: List[str], alphabet: List[str]) -> List[str]:
    answer_text = " ".join(answer)
    options = {answer_text}
    while len(options) < 4:
        shuffled = answer[:]
        random.shuffle(shuffled)
        if shuffled == answer:
            idx = random.randrange(len(shuffled))
            shuffled[idx] = random.choice(alphabet)
        options.add(" ".join(shuffled))
    options_list = list(options)
    random.shuffle(options_list)
    return options_list


def _wmi_tasks(count: int, difficulty: int) -> List[Dict[str, Any]]:
    tasks: List[Dict[str, Any]] = []
    digits = [str(i) for i in range(1, 10)]
    pictures = ["🍎", "⚽", "🐶", "📚", "🥭", "⭐", "🚌", "🐐"]
    colours = ["red", "blue", "green", "yellow"]
    for idx in range(count):
        span = min(6, 3 + (difficulty - 1) // 2 + (idx % 2))
        if idx % 3 == 0:
            sequence = random.sample(digits, span)
            answer = " ".join(sequence)
            tasks.append(
                {
                    "prompt": "Watch the numbers. Pick the same order.",
                    "options": _sequence_options(sequence, digits),
                    "answer": answer,
                    "hint": "same order",
                    "visual": " ".join(sequence),
                    "sequence": sequence,
                    "task_type": "digit_span",
                    "domain": "wmi",
                }
            )
        elif idx % 3 == 1:
            sequence = random.sample(pictures, min(4, span))
            answer = " ".join(sequence)
            tasks.append(
                {
                    "prompt": "Look at the pictures. Pick the ones you saw.",
                    "options": _sequence_options(sequence, pictures),
                    "answer": answer,
                    "hint": "pictures",
                    "visual": " ".join(sequence),
                    "sequence": sequence,
                    "task_type": "picture_span",
                    "domain": "wmi",
                }
            )
        else:
            sequence = [random.choice(colours) for _ in range(min(5, span))]
            answer = " ".join(sequence)
            tasks.append(
                {
                    "prompt": "Watch the colours. Pick the same pattern.",
                    "options": _sequence_options(sequence, colours),
                    "answer": answer,
                    "hint": "repeat",
                    "visual": " | ".join(sequence),
                    "sequence": sequence,
                    "task_type": "pattern_repeat",
                    "domain": "wmi",
                }
            )
    return tasks


def _psi_tasks(count: int, difficulty: int) -> List[Dict[str, Any]]:
    tasks: List[Dict[str, Any]] = []
    for idx in range(count):
        if idx % 3 == 0:
            a = random.randint(1, 5 + difficulty)
            b = random.randint(1, 4 + difficulty)
            answer = str(a + b)
            options = {answer, str(a + b + 1), str(max(0, a + b - 1)), str(a + b + 2)}
            tasks.append(
                {
                    "prompt": f"Fast answer: {a} + {b}",
                    "options": list(options)[:4],
                    "answer": answer,
                    "hint": "add",
                    "visual": "⚡",
                    "task_type": "speed_math",
                    "domain": "psi",
                    "timed": True,
                }
            )
        elif idx % 3 == 1:
            stars = random.randint(3, 8 + difficulty)
            distractor = random.choice(["🌙", "🔵", "🍎"])
            row = " ".join(["⭐"] * stars + [distractor] * random.randint(1, 3))
            parts = row.split()
            random.shuffle(parts)
            answer = str(stars)
            options = {answer, str(max(1, stars - 1)), str(stars + 1), str(stars + 2)}
            tasks.append(
                {
                    "prompt": "How many stars do you see?",
                    "options": list(options)[:4],
                    "answer": answer,
                    "hint": "count stars",
                    "visual": " ".join(parts),
                    "task_type": "symbol_scan",
                    "domain": "psi",
                    "timed": True,
                }
            )
        else:
            left = random.randint(1, 10 + difficulty * 2)
            right = random.randint(1, 10 + difficulty * 2)
            while right == left:
                right = random.randint(1, 10 + difficulty * 2)
            answer = str(max(left, right))
            options = [str(left), str(right), str(min(left, right) + 1), str(max(left, right) + 2)]
            random.shuffle(options)
            tasks.append(
                {
                    "prompt": f"Which is bigger: {left} or {right}?",
                    "options": options[:4],
                    "answer": answer,
                    "hint": "bigger",
                    "visual": f"{left}  ?  {right}",
                    "task_type": "number_compare",
                    "domain": "psi",
                    "timed": True,
                }
            )
    for task in tasks:
        random.shuffle(task["options"])
    return tasks


def _ensure_domain(items: List[Dict[str, Any]], domain: str) -> List[Dict[str, Any]]:
    for item in items:
        item.setdefault("domain", domain)
        item.setdefault("visual", "")
        item.setdefault("hint", "")
        item.setdefault("task_type", domain)
    return items


def build_domain_tasks(domain: str, count: int, difficulty: int) -> List[Dict[str, Any]]:
    if domain == "wmi":
        return _wmi_tasks(count, difficulty)
    if domain == "psi":
        return _psi_tasks(count, difficulty)
    items = generate_assessment_tasks(domain, count, difficulty)
    if len(items) < count:
        items.extend(generate_assessment_tasks(domain, count - len(items), 1))
    return _ensure_domain(items[:count], domain)
