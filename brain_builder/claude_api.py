from __future__ import annotations

import difflib
import json
import os
import random
import re
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List

try:
    import anthropic
except Exception:  # pragma: no cover - handled at runtime
    anthropic = None

try:
    import streamlit as st
except Exception:  # pragma: no cover
    st = None

from utils.scoring import running_record_level


MODEL = "claude-sonnet-4-20250514"
BASE_DIR = Path(__file__).resolve().parent
FALLBACK_PATH = BASE_DIR / "assets" / "fallback_content.json"


def _api_key() -> str | None:
    key = os.getenv("ANTHROPIC_API_KEY")
    if key:
        return key
    if st is not None:
        try:
            return st.secrets.get("ANTHROPIC_API_KEY")
        except Exception:
            return None
    return None


def _client():
    key = _api_key()
    if not key or anthropic is None:
        return None
    return anthropic.Anthropic(api_key=key)


def _load_fallbacks() -> Dict[str, Any]:
    try:
        return json.loads(FALLBACK_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {"maths": [], "english": [], "wordproblems": [], "science": [], "assessment": {}, "passages": []}


def _extract_text(response: Any) -> str:
    parts: list[str] = []
    for block in getattr(response, "content", []) or []:
        text = getattr(block, "text", None)
        if text is None and isinstance(block, dict):
            text = block.get("text")
        if text:
            parts.append(str(text))
    return "\n".join(parts).strip()


def _json_from_text(text: str) -> Any:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text).strip()
        text = re.sub(r"```$", "", text).strip()
    return json.loads(text)


def _valid_items(value: Any, required_keys: Iterable[str], count: int = 5) -> bool:
    if not isinstance(value, list) or len(value) < count:
        return False
    for item in value[:count]:
        if not isinstance(item, dict):
            return False
        if any(key not in item for key in required_keys):
            return False
        if "options" in item and (not isinstance(item["options"], list) or len(item["options"]) != 4):
            return False
    return True


def _call_json(
    system: str,
    user: str,
    *,
    fallback: Callable[[], Any],
    validator: Callable[[Any], bool],
    max_tokens: int = 1800,
) -> Any:
    client = _client()
    if client is None:
        return fallback()

    for _ in range(2):
        try:
            response = client.messages.create(
                model=MODEL,
                max_tokens=max_tokens,
                temperature=0.7,
                system=system,
                messages=[{"role": "user", "content": user or "Generate the requested JSON now."}],
            )
            data = _json_from_text(_extract_text(response))
            if validator(data):
                return data
        except Exception:
            continue
    return fallback()


def _call_text(system: str, user: str, fallback: str, max_tokens: int = 1200) -> str:
    client = _client()
    if client is None:
        return fallback
    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=max_tokens,
            temperature=0.6,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        text = _extract_text(response)
        return text or fallback
    except Exception:
        return fallback


def _sample(items: List[Dict[str, Any]], count: int) -> List[Dict[str, Any]]:
    if len(items) <= count:
        return [dict(item) for item in items]
    return [dict(item) for item in random.sample(items, count)]


def fallback_maths(subtopic: str, count: int = 5) -> List[Dict[str, Any]]:
    data = _load_fallbacks().get("maths", [])
    filtered = [item for item in data if item.get("subtopic", "").lower() == subtopic.lower()]
    pool = filtered if len(filtered) >= count else data
    return _sample(pool, count)


def fallback_english(task_type: str, count: int = 5) -> List[Dict[str, Any]]:
    data = _load_fallbacks().get("english", [])
    filtered = [item for item in data if item.get("task_type", "").lower() == task_type.lower()]
    pool = filtered if len(filtered) >= count else data
    return _sample(pool, count)


def fallback_word_problems(count: int = 5) -> List[Dict[str, Any]]:
    return _sample(_load_fallbacks().get("wordproblems", []), count)


def fallback_science(subtopic: str, count: int = 5) -> List[Dict[str, Any]]:
    data = _load_fallbacks().get("science", [])
    filtered = [item for item in data if item.get("subtopic", "").lower() == subtopic.lower()]
    pool = filtered if len(filtered) >= count else data
    return _sample(pool, count)


def fallback_assessment(domain: str, count: int) -> List[Dict[str, Any]]:
    bank = _load_fallbacks().get("assessment", {}).get(domain, [])
    return _sample(bank, min(count, len(bank)))


def fallback_passages() -> List[Dict[str, Any]]:
    return list(_load_fallbacks().get("passages", []))


def generate_maths_questions(subtopic: str, level: int) -> List[Dict[str, Any]]:
    system = (
        "You are a cheerful maths teacher for a 5-year-old. Generate exactly 5 maths "
        "questions in JSON format. Each question must have: 'question' (string, simple "
        "language), 'options' (array of 4 strings), 'answer' (string matching one option), "
        "'emoji' (a fun related emoji). Difficulty level: {level} where 1=easiest, 5=hardest. "
        "Current subtopic: {subtopic}. Return ONLY a valid JSON array, no markdown, no "
        "explanation."
    ).format(level=level, subtopic=subtopic)
    return _call_json(
        system,
        "",
        fallback=lambda: fallback_maths(subtopic),
        validator=lambda data: _valid_items(data, ["question", "options", "answer", "emoji"]),
    )[:5]


def generate_english_items(task_type: str) -> List[Dict[str, Any]]:
    system = (
        "You are a kind reading teacher for a 5-year-old. Generate content in JSON. "
        "For task type '{task_type}', generate 5 items. Each item: 'prompt' (what to show "
        "child), 'options' (4 choices as strings), 'answer' (correct string), 'hint' "
        "(one simple word hint). Use only simple CVC words and common sight words. "
        "Return ONLY a valid JSON array, no markdown."
    ).format(task_type=task_type)
    user = (
        "If task_type is sentence builder, make options the shuffled words and answer the full sentence. "
        "If task_type is read-aloud comprehension, make prompt a 2-3 sentence story under 30 words."
    )
    return _call_json(
        system,
        user,
        fallback=lambda: fallback_english(task_type),
        validator=lambda data: _valid_items(data, ["prompt", "options", "answer", "hint"]),
    )[:5]


def generate_word_problems(level: int = 1) -> List[Dict[str, Any]]:
    system = (
        "You are a storytelling maths teacher for a 5-year-old in Ghana. Create 5 maths "
        "word problems in JSON. Use local names (Kofi, Ama, Kwame, Abena), familiar "
        "settings (market, school, home, farm), and real objects (fruits, balls, books). "
        "Each item: 'story' (2 sentences max, under 25 words), 'question' (1 short "
        "question), 'options' (4 number strings), 'answer' (correct string), 'emojis' "
        "(2-3 relevant emojis). Return ONLY a valid JSON array, no markdown."
    )
    return _call_json(
        system,
        f"Difficulty level: {level}",
        fallback=fallback_word_problems,
        validator=lambda data: _valid_items(data, ["story", "question", "options", "answer", "emojis"]),
    )[:5]


def generate_science_items(subtopic: str, level: int) -> List[Dict[str, Any]]:
    system = (
        "You are a joyful science and history teacher for a 5-year-old child in Ghana. "
        "Generate exactly 5 multiple-choice learning questions in JSON. Each item must have "
        "'prompt' (simple Grade 1 words), 'options' (array of 4 short strings), 'answer' "
        "(string matching one option), 'fact' (one happy science or history fact, max 16 words), "
        "'emoji' (one fun related emoji), and 'kind' ('science', 'geography', 'geometry', or 'history'). "
        f"Difficulty level: {level} where 1=easiest and 5=hardest. Current subtopic: {subtopic}. "
        "For history, use safe, age-kind facts about people, places, inventions, culture, and long-ago life. "
        "Return ONLY a valid JSON array, no markdown, no explanation."
    )
    return _call_json(
        system,
        "",
        fallback=lambda: fallback_science(subtopic),
        validator=lambda data: _valid_items(data, ["prompt", "options", "answer", "fact", "emoji", "kind"]),
        max_tokens=2200,
    )[:5]


def generate_assessment_tasks(domain: str, count: int, difficulty: int) -> List[Dict[str, Any]]:
    domain_names = {
        "vci": "verbal comprehension",
        "fri": "fluid reasoning",
        "pa": "phonological awareness",
        "vsi": "visual-spatial processing",
    }
    system = (
        "You create playful cognitive game questions for a 5-year-old. Generate JSON only. "
        "Each item must have 'prompt', 'options' as 4 short strings, 'answer' matching one option, "
        "'hint', 'visual', and 'task_type'. Use simple words, Ghana-friendly contexts, and emojis. "
        f"Domain: {domain_names.get(domain, domain)}. Difficulty 1-5: {difficulty}. "
        f"Generate exactly {count} items. Return ONLY a valid JSON array."
    )
    return _call_json(
        system,
        "",
        fallback=lambda: fallback_assessment(domain, count),
        validator=lambda data: _valid_items(data, ["prompt", "options", "answer", "hint", "visual", "task_type"], count=min(count, 1)),
        max_tokens=2200,
    )[:count]


def kind_try_next_message() -> str:
    return _call_text(
        "You are a gentle teacher for a 5-year-old. Write one short kind sentence after a missed answer. Never use the word wrong.",
        "Write the sentence.",
        "Almost! Let's try the next one 💪",
        max_tokens=80,
    )


def generate_assessment_insights(
    domain_scores: Dict[str, float],
    last_three: List[Dict[str, Any]],
    goal: str = "top 1% by 12 months",
) -> Dict[str, Any]:
    system = (
        "You are a child educational psychologist specialising in early childhood "
        "cognitive development. OB is a 5-year-3-month-old boy. Based on his "
        "assessment scores across 6 WPPSI-IV cognitive domains, generate a "
        "structured parent report in JSON format with these fields:\n"
        "{\n"
        "  'summary': string (2 sentences, plain language, positive framing),\n"
        "  'strengths': [array of 2 domain names with one-sentence explanation each],\n"
        "  'priority_areas': [array of 2 domain names with one actionable sentence each],\n"
        "  'weekly_plan': [\n"
        "    {'day': 'Monday', 'activity': string, 'duration_minutes': int, 'domain': string},\n"
        "    ... (7 days)\n"
        "  ],\n"
        "  'monthly_milestone': string (what OB should achieve next month),\n"
        "  'percentile_trajectory': string (honest assessment of path to top 1%),\n"
        "  'parent_tip': string (one specific, evidence-based parenting tip for this week)\n"
        "}\n"
        "Return ONLY valid JSON, no markdown."
    )
    user = json.dumps(
        {
            "age": "5 years 3 months",
            "domain_scores": domain_scores,
            "last_3_assessments": last_three,
            "parent_goal": goal,
        }
    )

    def fallback() -> Dict[str, Any]:
        sorted_domains = sorted(domain_scores.items(), key=lambda item: item[1], reverse=True)
        strengths = sorted_domains[:2] or [("vci", 100), ("fri", 100)]
        priorities = sorted_domains[-2:] or [("wmi", 100), ("pa", 100)]
        return {
            "summary": "OB is building a broad set of early thinking skills. Short, joyful daily practice will help turn strengths into steady growth.",
            "strengths": [f"{name.upper()}: this area is showing confident performance." for name, _ in strengths],
            "priority_areas": [f"{name.upper()}: practise this area for 5-10 playful minutes each day." for name, _ in priorities],
            "weekly_plan": [
                {"day": "Monday", "activity": "Play a four-number memory game.", "duration_minutes": 10, "domain": "Working Memory"},
                {"day": "Tuesday", "activity": "Read five sight words and make a silly sentence.", "duration_minutes": 10, "domain": "Phonological Awareness"},
                {"day": "Wednesday", "activity": "Solve animal pattern puzzles.", "duration_minutes": 10, "domain": "Fluid Reasoning"},
                {"day": "Thursday", "activity": "Compare numbers while setting the table.", "duration_minutes": 10, "domain": "Processing Speed"},
                {"day": "Friday", "activity": "Describe three new words from a story.", "duration_minutes": 10, "domain": "Verbal Comprehension"},
                {"day": "Saturday", "activity": "Build shapes from blocks and copy patterns.", "duration_minutes": 15, "domain": "Visual-Spatial"},
                {"day": "Sunday", "activity": "Retell a short story in his own words.", "duration_minutes": 10, "domain": "Verbal Comprehension"},
            ],
            "monthly_milestone": "Hold a 4-digit sequence, read 20 common sight words, and explain one simple pattern.",
            "percentile_trajectory": "The path to the top 1% is ambitious and will require consistent practice, sleep, reading, and varied problem-solving.",
            "parent_tip": "Praise the strategy OB used, such as checking again or listening carefully, more than the score.",
        }

    data = _call_json(
        system,
        user,
        fallback=fallback,
        validator=lambda value: isinstance(value, dict)
        and all(key in value for key in ["summary", "strengths", "priority_areas", "weekly_plan", "monthly_milestone", "percentile_trajectory", "parent_tip"]),
        max_tokens=2600,
    )
    return data if isinstance(data, dict) else fallback()


def generate_weekly_parent_report(history: Dict[str, Any]) -> str:
    fallback = (
        "This week, OB practised early maths, reading, science, history, and thinking games. His strongest moments came when tasks were short, lively, and repeated. "
        "Next week, keep sessions to about 20 minutes and rotate memory, phonics, story maths, and Wonder Lab. Offline activity: count the items on the dinner table, "
        "then ask OB to explain how he counted."
    )
    return _call_text(
        "You write warm 300-word weekly parent reports for early learning. Use plain language and practical advice.",
        json.dumps(history),
        fallback,
        max_tokens=1200,
    )


def generate_passage_library() -> List[Dict[str, Any]]:
    system = (
        "You are a kind early reading teacher in Ghana. Generate 30 reading passages in JSON: "
        "10 starter, 10 developing, and 10 fluent. Each item must have 'difficulty', 'text', "
        "and 'target_phonics'. Starter passages are 1 sentence and 5-8 common words. "
        "Developing passages are 2-3 sentences and 15-25 words. Fluent passages are 40-60 words. "
        "Use familiar contexts like market, family, school, animals, and food. Return ONLY a valid JSON array."
    )
    return _call_json(
        system,
        "",
        fallback=fallback_passages,
        validator=lambda data: isinstance(data, list)
        and len(data) >= 30
        and all(isinstance(item, dict) and "difficulty" in item and "text" in item and "target_phonics" in item for item in data),
        max_tokens=4000,
    )


def _normalise_words(text: str) -> List[str]:
    return re.findall(r"[a-z']+", text.lower())


def _fallback_reading_assessment(passage: str, transcript: str) -> Dict[str, Any]:
    original_words = _normalise_words(passage)
    spoken_words = _normalise_words(transcript)
    matcher = difflib.SequenceMatcher(a=original_words, b=spoken_words)
    errors: list[dict[str, str]] = []
    summary = {"substitution": 0, "omission": 0, "insertion": 0, "self_correction": 0}
    correct = 0

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            correct += i2 - i1
        elif tag == "replace":
            for original, said in zip(original_words[i1:i2], spoken_words[j1:j2]):
                errors.append({"original": original, "said": said, "error_type": "substitution"})
                summary["substitution"] += 1
        elif tag == "delete":
            for original in original_words[i1:i2]:
                errors.append({"original": original, "said": "", "error_type": "omission"})
                summary["omission"] += 1
        elif tag == "insert":
            for said in spoken_words[j1:j2]:
                errors.append({"original": "", "said": said, "error_type": "insertion"})
                summary["insertion"] += 1

    accuracy = round((correct / max(len(original_words), 1)) * 100, 1)
    level = "advanced" if accuracy >= 97 else "above_expected" if accuracy >= 94 else "at_expected" if accuracy >= 90 else "below_expected"
    return {
        "accuracy_pct": accuracy,
        "errors": errors[:20],
        "error_types_summary": summary,
        "reading_level": level,
        "fluency_note": f"The passage was at {running_record_level(accuracy).lower()} for today.",
        "phonics_patterns_strong": ["CVC words"] if accuracy >= 90 else ["short vowel sounds"],
        "phonics_patterns_weak": ["missed words"] if accuracy < 95 else [],
        "comprehension_question": "What happened in the story?",
        "encouragement": "You read with brave focus and kept going beautifully!",
    }


def assess_reading(passage: str, transcript: str) -> Dict[str, Any]:
    system = (
        "You are an expert early literacy assessor using Running Records and "
        "DIBELS methodology. A child aged 5 years 3 months just read a passage "
        "aloud. Compare the spoken transcript to the original passage and return "
        "a JSON assessment:\n"
        "{\n"
        "  'accuracy_pct': float (words correct / total words × 100),\n"
        "  'errors': [{'original': string, 'said': string, 'error_type': string}],\n"
        "  'error_types_summary': {'substitution': int, 'omission': int, 'insertion': int, 'self_correction': int},\n"
        "  'reading_level': string ('below_expected' | 'at_expected' | 'above_expected' | 'advanced'),\n"
        "  'fluency_note': string (1 sentence observation),\n"
        "  'phonics_patterns_strong': [list of phonics patterns handled well],\n"
        "  'phonics_patterns_weak': [list of phonics patterns needing work],\n"
        "  'comprehension_question': string (one simple question to ask about what was read),\n"
        "  'encouragement': string (warm, specific praise, 1 sentence)\n"
        "}\n"
        "Return ONLY valid JSON."
    )
    user = f"Original passage: {passage}\nChild transcript: {transcript}"
    fallback = lambda: _fallback_reading_assessment(passage, transcript)
    return _call_json(
        system,
        user,
        fallback=fallback,
        validator=lambda value: isinstance(value, dict)
        and all(key in value for key in ["accuracy_pct", "errors", "error_types_summary", "reading_level", "comprehension_question", "encouragement"]),
        max_tokens=1800,
    )


def score_comprehension(passage: str, question: str, answer: str) -> Dict[str, Any]:
    system = (
        "You score a 5-year-old child's spoken answer to a simple comprehension question. "
        "Return ONLY JSON with fields 'score' as 1 or 0 and 'note' as one short parent-facing sentence."
    )
    user = json.dumps({"passage": passage, "question": question, "answer": answer})
    fallback = {"score": 1 if len(_normalise_words(answer)) >= 2 else 0, "note": "Answer contained enough detail for a basic response."}
    data = _call_json(
        system,
        user,
        fallback=lambda: fallback,
        validator=lambda value: isinstance(value, dict) and "score" in value and "note" in value,
        max_tokens=250,
    )
    data["score"] = 1 if int(data.get("score", 0)) else 0
    return data
