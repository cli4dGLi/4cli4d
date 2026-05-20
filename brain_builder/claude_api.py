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

import database
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
        return {"maths": [], "english": [], "wordproblems": [], "science": [], "coding": [], "assessment": {}, "passages": []}


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


def _valid_items(
    value: Any,
    required_keys: Iterable[str],
    count: int = 5,
    answer_must_be_option: bool = False,
    min_options: int = 4,
    max_options: int = 4,
) -> bool:
    if not isinstance(value, list) or len(value) < count:
        return False
    for item in value[:count]:
        if not isinstance(item, dict):
            return False
        if any(key not in item for key in required_keys):
            return False
        if "options" in item:
            if not isinstance(item["options"], list) or not min_options <= len(item["options"]) <= max_options:
                return False
            if answer_must_be_option and "answer" in item and str(item["answer"]) not in [str(option) for option in item["options"]]:
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


def _child_context() -> str:
    try:
        return database.ai_child_profile_context()
    except Exception:
        return "No child profile context is available."


def _fresh_request_note(topic: str) -> str:
    seed = random.randint(100000, 999999)
    return f"Freshness seed: {seed}. Create a new set for {topic}; avoid repeating obvious examples from earlier sessions."


def _sample(items: List[Dict[str, Any]], count: int) -> List[Dict[str, Any]]:
    copied = [dict(item) for item in items]
    random.shuffle(copied)
    return copied[:count]


def _level_range(level: int | None, base: int = 10) -> int:
    safe_level = max(1, min(5, int(level or 1)))
    if base == 20:
        return {1: 10, 2: 14, 3: 20, 4: 30, 5: 50}[safe_level]
    return {1: 6, 2: 10, 3: 14, 4: 20, 5: 30}[safe_level]


def _option_set(answer: int | str, distractors: Iterable[int | str]) -> List[str]:
    correct = str(answer)
    options = {correct}
    for item in distractors:
        options.add(str(item))
        if len(options) == 4:
            break
    while len(options) < 4:
        if isinstance(answer, int):
            options.add(str(max(0, answer + random.choice([-3, -2, -1, 1, 2, 3, 4]))))
        else:
            options.add(random.choice(["1", "2", "3", "4", "star", "basket"]))
    option_list = list(options)
    random.shuffle(option_list)
    return option_list[:4]


def _fallback_maths_generated(subtopic: str, count: int, level: int | None) -> List[Dict[str, Any]]:
    topic = subtopic.lower()
    max_value = _level_range(level, 20)
    items: List[Dict[str, Any]] = []
    seen: set[str] = set()
    emojis = ["⭐", "🐑", "🧺", "📜", "🍞", "🌾", "🪨", "⛵"]

    while len(items) < count and len(seen) < 80:
        emoji = random.choice(emojis)
        if "addition" in topic:
            a = random.randint(1, max(3, max_value // 2))
            b = random.randint(1, max(2, max_value - a))
            answer = a + b
            question = f"David has {a} stones. He finds {b} more. How many stones now?"
            key = f"add-{a}-{b}"
            distractors = [answer - 1, answer + 1, answer + 2, max(0, answer - 2), answer + 3]
        elif "subtraction" in topic:
            a = random.randint(3, max_value)
            b = random.randint(1, a - 1)
            answer = a - b
            question = f"Ruth has {a} baskets. She gives away {b}. How many baskets are left?"
            key = f"sub-{a}-{b}"
            distractors = [answer - 1, answer + 1, answer + 2, max(0, answer - 2), a + b]
        elif "number bonds" in topic:
            target = 10
            a = random.randint(0, target)
            answer = target - a
            question = f"What goes with {a} to make {target}?"
            key = f"bond-{a}"
            distractors = [answer - 1, answer + 1, answer + 2, max(0, answer - 2), random.randint(0, 10)]
        elif "counting" in topic:
            step = random.choice([2, 5])
            start = random.choice([0, step, step * 2, step * 3])
            sequence = [start + step * i for i in range(4)]
            answer = sequence[-1] + step
            question = f"What comes next? {sequence[0]}, {sequence[1]}, {sequence[2]}, {sequence[3]}, ?"
            key = f"count-{step}-{start}"
            distractors = [answer + step, answer - step, answer + 1, answer - 1, answer + 2]
        elif "comparing" in topic:
            a = random.randint(1, max_value)
            b = random.randint(1, max_value)
            if a == b:
                b = min(max_value, b + 1)
            ask_bigger = random.choice([True, False])
            answer = max(a, b) if ask_bigger else min(a, b)
            word = "bigger" if ask_bigger else "smaller"
            question = f"Which number is {word}: {a} or {b}?"
            key = f"cmp-{a}-{b}-{word}"
            distractors = [a, b, answer + 1, max(0, answer - 1), random.randint(1, max_value)]
        else:
            patterns = [
                (["⭐", "🌙", "⭐", "🌙"], "⭐"),
                (["red", "blue", "red", "blue"], "red"),
                (["1", "2", "1", "2"], "1"),
                (["🔺", "🔵", "🔺", "🔵"], "🔺"),
                (["big", "small", "big", "small"], "big"),
                (["A", "B", "A", "B"], "A"),
                (["2", "4", "6", "8"], "10"),
                (["5", "10", "15", "20"], "25"),
            ]
            shown, answer = random.choice(patterns)
            question = f"What comes next in this pattern? {' '.join(shown)} ?"
            key = f"pattern-{'-'.join(shown)}"
            distractors = ["⭐", "🌙", "red", "blue", "1", "2", "🔺", "🔵", "small", "big", "A", "B", "10", "25"]
            emoji = "🔁"

        if key in seen:
            continue
        seen.add(key)
        items.append(
            {
                "subtopic": subtopic,
                "question": question,
                "options": _option_set(answer, distractors),
                "answer": str(answer),
                "emoji": emoji,
            }
        )
    return items[:count]


def _fallback_english_generated(task_type: str, count: int) -> List[Dict[str, Any]]:
    task = task_type.lower()
    items: List[Dict[str, Any]] = []
    if "phonics" in task:
        word_bank = {
            "m": ["mat", "man", "mud"],
            "s": ["sun", "sit", "sad"],
            "b": ["bat", "bag", "bed"],
            "t": ["top", "tap", "ten"],
            "c": ["cat", "cup", "can"],
            "d": ["dog", "dad", "dig"],
            "p": ["pan", "pin", "pot"],
            "r": ["red", "run", "rug"],
        }
        letters = random.sample(list(word_bank), min(count, len(word_bank)))
        all_words = [word for words in word_bank.values() for word in words]
        for letter in letters:
            answer = random.choice(word_bank[letter])
            options = {answer}
            while len(options) < 4:
                option = random.choice(all_words)
                if not option.startswith(letter):
                    options.add(option)
            option_list = list(options)
            random.shuffle(option_list)
            items.append({"task_type": task_type, "prompt": f"Which word starts with {letter}?", "options": option_list, "answer": answer, "hint": f"{letter} sound"})
    elif "sight" in task:
        words = ["the", "and", "to", "go", "come", "play", "said", "little", "look", "my", "you", "we", "see", "like"]
        for answer in random.sample(words, count):
            options = {answer}
            while len(options) < 4:
                options.add(random.choice(words))
            option_list = list(options)
            random.shuffle(option_list)
            items.append({"task_type": task_type, "prompt": f"Find the word: {answer}", "options": option_list, "answer": answer, "hint": "look"})
    elif "word pictures" in task:
        pairs = [("🐱", "cat"), ("🐶", "dog"), ("☀️", "sun"), ("🧢", "cap"), ("🍞", "bread"), ("🐟", "fish"), ("🧺", "basket"), ("⭐", "star"), ("⛵", "boat"), ("📜", "scroll")]
        words = [word for _, word in pairs]
        for emoji, answer in random.sample(pairs, count):
            options = {answer}
            while len(options) < 4:
                options.add(random.choice(words))
            option_list = list(options)
            random.shuffle(option_list)
            items.append({"task_type": task_type, "prompt": f"Pick the word for {emoji}", "options": option_list, "answer": answer, "hint": "picture"})
    elif "sentence" in task:
        sentences = ["I can run", "The cat sat", "We like bread", "Dad can hop", "Ruth has a bag", "Daniel can read", "The sun is hot", "I see a boat"]
        for sentence in random.sample(sentences, count):
            words = sentence.split()
            options = words[:]
            random.shuffle(options)
            items.append({"task_type": task_type, "prompt": f"Tap the words to make this sentence: {sentence}.", "options": options, "answer": sentence, "hint": words[0]})
    else:
        stories = [
            ("Daniel has a red book. He reads it in the tent.", "a red book", "book"),
            ("Ruth sees a sheep. The sheep eats grass.", "a sheep", "sheep"),
            ("Miriam has a basket. The basket has bread.", "bread", "bread"),
            ("Noah sees a boat. The boat is on water.", "a boat", "boat"),
            ("Esther sees a star. The star is bright.", "a star", "star"),
            ("David has a small harp. He plays a song.", "a harp", "harp"),
            ("Mum has a cup. The cup has milk.", "milk", "milk"),
            ("The cat sat on the mat. It saw a bug.", "cat", "cat"),
        ]
        answers = [answer for _, answer, _ in stories]
        for story, answer, hint in random.sample(stories, count):
            options = {answer}
            while len(options) < 4:
                options.add(random.choice(answers + ["a fish", "a hat", "a ball"]))
            option_list = list(options)
            random.shuffle(option_list)
            items.append({"task_type": task_type, "prompt": story, "options": option_list, "answer": answer, "hint": hint})
    return items[:count]


def _fallback_word_problems_generated(count: int, level: int | None = None) -> List[Dict[str, Any]]:
    max_value = _level_range(level, 20)
    stories = [
        ("David", "smooth stones", "in his bag", "🪨"),
        ("Ruth", "grain baskets", "near the field", "🌾"),
        ("Miriam", "bread rolls", "for her family", "🍞"),
        ("Noah", "animals", "near the boat", "⛵"),
        ("Esther", "bright stars", "in the sky", "⭐"),
        ("Daniel", "scrolls", "in the room", "📜"),
        ("Joseph", "colour coats", "at home", "🧥"),
        ("Samuel", "small lamps", "in the temple", "🪔"),
    ]
    helpers = ["Sarah", "Moses", "Naomi", "Eli", "Abigail", "Caleb"]
    items: List[Dict[str, Any]] = []
    seen: set[str] = set()
    attempts = 0

    while len(items) < count and attempts < 120:
        attempts += 1
        name, thing, place, emoji = random.choice(stories)
        helper = random.choice(helpers)
        operation = random.choice(["add", "subtract"])

        if operation == "add":
            first = random.randint(1, max(3, max_value // 2))
            second = random.randint(1, max(2, max_value - first))
            answer = first + second
            story = f"{name} has {first} {thing} {place}. {helper} gives {name} {second} more."
            question = f"How many {thing} now?"
            key = f"add-{name}-{thing}-{first}-{second}"
            distractors = [answer - 1, answer + 1, answer + 2, max(0, answer - 2), answer + 3]
        else:
            first = random.randint(3, max_value)
            second = random.randint(1, first - 1)
            answer = first - second
            story = f"{name} has {first} {thing} {place}. {name} shares {second} of them."
            question = f"How many {thing} are left?"
            key = f"sub-{name}-{thing}-{first}-{second}"
            distractors = [answer - 1, answer + 1, answer + 2, max(0, answer - 2), first + second]

        if key in seen:
            continue
        seen.add(key)
        items.append(
            {
                "story": story,
                "question": question,
                "options": _option_set(answer, distractors),
                "answer": str(answer),
                "emojis": f"{emoji} {emoji}",
            }
        )
    return items[:count]


def _fallback_coding_generated(subtopic: str, count: int) -> List[Dict[str, Any]]:
    topic = subtopic.lower()
    items: List[Dict[str, Any]] = []
    names = ["Daniel", "Miriam", "Ruth", "Noah", "David"]
    objects = ["basket", "scroll", "boat", "star", "bread", "tent"]
    seen: set[str] = set()
    attempts = 0
    while len(items) < count and attempts < 120:
        attempts += 1
        name = random.choice(names)
        thing = random.choice(objects)
        if "sequencing" in topic:
            sequences = [
                (["wash", "eat", "read"], "wash -> eat -> read"),
                (["start", "walk", "stop"], "start -> walk -> stop"),
                (["mix", "bake", "eat"], "mix -> bake -> eat"),
                (["look", "choose", "tap"], "look -> choose -> tap"),
                (["get wood", "build", "float"], "get wood -> build -> float"),
            ]
            steps, answer = random.choice(sequences)
            prompt = f"{name} needs code steps for {thing}. Which order is best?"
            visual = " -> ".join(steps)
            options = [answer, " -> ".join(reversed(steps)), f"{steps[1]} -> {steps[0]} -> {steps[2]}", f"{steps[2]} -> {steps[1]} -> {steps[0]}"]
            hint = "Start with the first step."
            concept = "sequence"
            emoji = "📜"
        elif "arrow" in topic:
            moves = [("right", "➡️"), ("left", "⬅️"), ("up", "⬆️"), ("down", "⬇️")]
            word, arrow = random.choice(moves)
            steps = random.randint(1, 3)
            answer = " ".join([arrow] * steps)
            prompt = f"Move {name} {word} {steps} step{'s' if steps > 1 else ''}. Which code works?"
            visual = f"{name} -> {thing}"
            options = [answer, " ".join(["⬅️"] * steps), " ".join(["➡️"] * steps), " ".join(["⬆️"] * steps)]
            hint = f"Choose the {word} arrow."
            concept = "direction"
            emoji = "🧭"
        elif "loop" in topic:
            action = random.choice(["clap", "step", "star", "tap", "draw"])
            repeats = random.randint(2, 5)
            answer = f"repeat {repeats}: {action}"
            prompt = f"{name} needs {action} {repeats} times. Which loop is shorter?"
            visual = " ".join([action] * repeats)
            options = [answer, f"repeat {max(1, repeats - 1)}: {action}", f"repeat {repeats + 1}: {action}", f"repeat {repeats}: stop"]
            hint = f"Repeat {repeats} means do it {repeats} times."
            concept = "loop"
            emoji = "🔁"
        elif "debug" in topic:
            fixes = [
                ("The star is left, but code goes right.", "right should be left"),
                ("We need 3 stars, but code repeats 2.", "repeat 3"),
                ("Daniel wants bread, but code picks stone.", "pick bread"),
                ("Miriam needs two steps, but code has one.", "add one step"),
                ("The sheep should go to grass on the right.", "go right"),
            ]
            prompt, answer = random.choice(fixes)
            visual = "bug hunt 🔎"
            options = [answer, "stop forever", "jump twice", "pick stone"]
            hint = "A bug is a mistake to fix."
            concept = "debug"
            emoji = "🔎"
        else:
            rules = [
                ("If it rains, then choose what?", "umbrella", ["umbrella", "sand", "drum", "star"]),
                ("If a wall is ahead, then what should code do?", "turn", ["turn", "walk into wall", "sleep", "drop bread"]),
                ("If the basket is full, then what should Miriam do?", "stop filling", ["stop filling", "add more forever", "hide", "jump"]),
                ("If the light is red, then what should we do?", "stop", ["stop", "run", "spin", "clap"]),
                ("If Daniel sees a star, then what should he tap?", "star", ["star", "stone", "shoe", "fish"]),
            ]
            prompt, answer, options = random.choice(rules)
            visual = "if -> then"
            hint = "Use the if rule."
            concept = "condition"
            emoji = "🔀"
        clean_options: List[str] = []
        for option in options:
            text = str(option)
            if text not in clean_options:
                clean_options.append(text)
        while len(clean_options) < 4:
            extra = random.choice(["turn", "stop", "go right", "repeat 2", "tap star", "try again"])
            if extra not in clean_options:
                clean_options.append(extra)
        key = f"{prompt}|{answer}"
        if key in seen:
            continue
        seen.add(key)
        random.shuffle(clean_options)
        items.append({"subtopic": subtopic, "prompt": prompt, "visual": visual, "options": clean_options[:4], "answer": answer, "hint": hint, "concept": concept, "emoji": emoji})
    return items[:count]


def _fallback_science_generated(subtopic: str, count: int) -> List[Dict[str, Any]]:
    banks: Dict[str, List[Dict[str, str]]] = {
        "natural science": [
            {"prompt": "What do plants need to grow?", "answer": "sun and water", "options": ["sun and water", "shoes", "a spoon", "a hat"], "fact": "Plants use sun, water, and air to grow.", "emoji": "🌱", "kind": "science"},
            {"prompt": "Which animal lays eggs?", "answer": "hen", "options": ["hen", "goat", "dog", "cat"], "fact": "Many birds hatch from eggs.", "emoji": "🐔", "kind": "science"},
            {"prompt": "What helps fish breathe in water?", "answer": "gills", "options": ["gills", "shoes", "wings", "hands"], "fact": "Fish use gills to breathe in water.", "emoji": "🐟", "kind": "science"},
            {"prompt": "What do bees make?", "answer": "honey", "options": ["honey", "soap", "sand", "paper"], "fact": "Bees also help flowers make fruit.", "emoji": "🐝", "kind": "science"},
            {"prompt": "Which one is a seed?", "answer": "bean", "options": ["bean", "cup", "ball", "shoe"], "fact": "A seed can grow into a plant.", "emoji": "🫘", "kind": "science"},
            {"prompt": "What do roots do for a plant?", "answer": "take water", "options": ["take water", "sing songs", "draw maps", "cook rice"], "fact": "Roots help plants drink water.", "emoji": "🌿", "kind": "science"},
            {"prompt": "Which animal has a shell?", "answer": "turtle", "options": ["turtle", "goat", "hen", "dog"], "fact": "A shell helps protect a turtle.", "emoji": "🐢", "kind": "science"},
            {"prompt": "What do lungs help us do?", "answer": "breathe", "options": ["breathe", "draw", "jump only", "sleep only"], "fact": "Lungs help people breathe air.", "emoji": "🌬️", "kind": "science"},
        ],
        "physics": [
            {"prompt": "What pulls things down to the ground?", "answer": "gravity", "options": ["gravity", "music", "paint", "rice"], "fact": "Gravity helps keep our feet on Earth.", "emoji": "🌍", "kind": "science"},
            {"prompt": "What gives us light in the day?", "answer": "the sun", "options": ["the sun", "a shoe", "a spoon", "a bag"], "fact": "Light helps our eyes see.", "emoji": "☀️", "kind": "science"},
            {"prompt": "What do magnets pull?", "answer": "some metals", "options": ["some metals", "bananas", "water", "paper only"], "fact": "Magnets pull iron and some metals.", "emoji": "🧲", "kind": "science"},
            {"prompt": "What can make a drum sound?", "answer": "a tap", "options": ["a tap", "a smell", "a colour", "a nap"], "fact": "Sound comes from tiny shakes.", "emoji": "🥁", "kind": "science"},
            {"prompt": "Which is faster on a smooth floor?", "answer": "a ball", "options": ["a ball", "a pillow", "a sock", "a leaf"], "fact": "Smooth surfaces can help things roll.", "emoji": "⚽", "kind": "science"},
            {"prompt": "What happens when ice gets warm?", "answer": "it melts", "options": ["it melts", "it sings", "it grows hair", "it jumps"], "fact": "Heat can melt ice into water.", "emoji": "🧊", "kind": "science"},
            {"prompt": "Which force can push a toy car?", "answer": "your hand", "options": ["your hand", "a smell", "a color", "a nap"], "fact": "A push can make things move.", "emoji": "🚗", "kind": "science"},
            {"prompt": "What makes a shadow?", "answer": "blocked light", "options": ["blocked light", "loud sound", "sweet food", "soft cloth"], "fact": "A shadow forms when light is blocked.", "emoji": "🌗", "kind": "science"},
        ],
        "geography": [
            {"prompt": "What is a map for?", "answer": "finding places", "options": ["finding places", "eating lunch", "washing hands", "sleeping"], "fact": "Maps show where places are.", "emoji": "🗺️", "kind": "geography"},
            {"prompt": "Which place has lots of water?", "answer": "ocean", "options": ["ocean", "hill", "road", "classroom"], "fact": "Oceans cover much of Earth.", "emoji": "🌊", "kind": "geography"},
            {"prompt": "Where do many crops grow?", "answer": "farm", "options": ["farm", "sky", "bed", "shoe"], "fact": "Farms help grow food.", "emoji": "🌾", "kind": "geography"},
            {"prompt": "What country is Accra in?", "answer": "Ghana", "options": ["Ghana", "Japan", "Brazil", "France"], "fact": "Accra is Ghana's capital city.", "emoji": "🇬🇭", "kind": "geography"},
            {"prompt": "Which is a hot dry place?", "answer": "desert", "options": ["desert", "river", "lake", "forest"], "fact": "Deserts get very little rain.", "emoji": "🏜️", "kind": "geography"},
            {"prompt": "What shows north and south?", "answer": "compass", "options": ["compass", "cup", "hat", "ball"], "fact": "A compass helps people find direction.", "emoji": "🧭", "kind": "geography"},
            {"prompt": "Which land is very high?", "answer": "mountain", "options": ["mountain", "river", "road", "chair"], "fact": "Mountains are high landforms.", "emoji": "⛰️", "kind": "geography"},
            {"prompt": "What do we call a drawing of Earth?", "answer": "globe", "options": ["globe", "spoon", "shirt", "drum"], "fact": "A globe is a round map.", "emoji": "🌐", "kind": "geography"},
        ],
        "geometry": [
            {"prompt": "Which shape has 3 sides?", "answer": "triangle", "options": ["triangle", "circle", "square", "star"], "fact": "A triangle has three sides.", "emoji": "🔺", "kind": "geometry"},
            {"prompt": "Which shape is round?", "answer": "circle", "options": ["circle", "square", "triangle", "cube"], "fact": "A circle has no corners.", "emoji": "🔵", "kind": "geometry"},
            {"prompt": "How many sides does a square have?", "answer": "4", "options": ["4", "3", "2", "5"], "fact": "A square has four equal sides.", "emoji": "🟦", "kind": "geometry"},
            {"prompt": "Which shape looks like a ball?", "answer": "sphere", "options": ["sphere", "cube", "line", "triangle"], "fact": "A sphere is round like a ball.", "emoji": "🌐", "kind": "geometry"},
            {"prompt": "Which shape can roll best?", "answer": "circle", "options": ["circle", "square", "triangle", "rectangle"], "fact": "Round shapes roll well.", "emoji": "🔄", "kind": "geometry"},
            {"prompt": "Which shape has corners?", "answer": "square", "options": ["square", "circle", "oval", "ball"], "fact": "Corners are where sides meet.", "emoji": "◼️", "kind": "geometry"},
            {"prompt": "Which shape looks like an egg?", "answer": "oval", "options": ["oval", "square", "triangle", "cube"], "fact": "An oval is a stretched circle.", "emoji": "🥚", "kind": "geometry"},
            {"prompt": "What is a straight path called?", "answer": "line", "options": ["line", "circle", "ball", "corner"], "fact": "A line can be straight.", "emoji": "📏", "kind": "geometry"},
        ],
    }
    history_items = [
        {"prompt": "Which old place has big pyramids?", "answer": "Egypt", "options": ["Egypt", "the moon", "a shoe", "a bus"], "fact": "Ancient Egypt built huge pyramids.", "emoji": "🔺", "kind": "history"},
        {"prompt": "What is a museum for?", "answer": "old things and stories", "options": ["old things and stories", "sleeping only", "washing cars", "cooking soup"], "fact": "Museums help us remember the past.", "emoji": "🏛️", "kind": "history"},
        {"prompt": "What helped people travel across the sea?", "answer": "boats", "options": ["boats", "beds", "spoons", "chairs"], "fact": "Boats helped people visit far places.", "emoji": "⛵", "kind": "history"},
        {"prompt": "Who used a telescope long ago?", "answer": "Galileo", "options": ["Galileo", "a goat", "a chef", "a baby"], "fact": "Galileo studied the sky.", "emoji": "🔭", "kind": "history"},
        {"prompt": "What tool helped sailors find direction?", "answer": "compass", "options": ["compass", "cup", "hat", "ball"], "fact": "A compass shows direction.", "emoji": "🧭", "kind": "history"},
        {"prompt": "What did early farmers grow?", "answer": "food plants", "options": ["food plants", "plastic toys", "cars", "computers"], "fact": "Farming helped communities grow.", "emoji": "🌽", "kind": "history"},
        {"prompt": "What did people use to write long ago?", "answer": "marks and pictures", "options": ["marks and pictures", "only phones", "only cars", "only radios"], "fact": "People shared stories before books.", "emoji": "📜", "kind": "history"},
        {"prompt": "What did old traders carry between towns?", "answer": "goods", "options": ["goods", "clouds", "rainbows", "stars"], "fact": "Trade shared tools, food, and ideas.", "emoji": "🧺", "kind": "history"},
    ]
    key = subtopic.lower()
    if "history" in key:
        pool = history_items
    else:
        pool = banks.get(key, [])
    items = _sample(pool, count)
    for item in items:
        item["subtopic"] = subtopic
    return items


def fallback_maths(subtopic: str, count: int = 5, level: int | None = None) -> List[Dict[str, Any]]:
    generated = _fallback_maths_generated(subtopic, count, level)
    if len(generated) >= count:
        return generated
    data = _load_fallbacks().get("maths", [])
    filtered = [item for item in data if item.get("subtopic", "").lower() == subtopic.lower()]
    pool = filtered or data
    return _sample(pool, count)


def fallback_english(task_type: str, count: int = 5) -> List[Dict[str, Any]]:
    generated = _fallback_english_generated(task_type, count)
    if len(generated) >= count:
        return generated
    data = _load_fallbacks().get("english", [])
    filtered = [item for item in data if item.get("task_type", "").lower() == task_type.lower()]
    pool = filtered or data
    return _sample(pool, count)


def fallback_word_problems(count: int = 5, level: int | None = None) -> List[Dict[str, Any]]:
    generated = _fallback_word_problems_generated(count, level)
    if len(generated) >= count:
        return generated
    return _sample(_load_fallbacks().get("wordproblems", []), count)


def fallback_science(subtopic: str, count: int = 5) -> List[Dict[str, Any]]:
    generated = _fallback_science_generated(subtopic, count)
    if len(generated) >= count:
        return generated
    data = _load_fallbacks().get("science", [])
    filtered = [item for item in data if item.get("subtopic", "").lower() == subtopic.lower()]
    pool = filtered or data
    return _sample(pool, count)


def fallback_coding(subtopic: str, count: int = 5) -> List[Dict[str, Any]]:
    generated = _fallback_coding_generated(subtopic, count)
    if len(generated) >= count:
        return generated
    data = _load_fallbacks().get("coding", [])
    filtered = [item for item in data if item.get("subtopic", "").lower() == subtopic.lower()]
    pool = filtered or data
    return _sample(pool, count)


def fallback_assessment(domain: str, count: int) -> List[Dict[str, Any]]:
    bank = _load_fallbacks().get("assessment", {}).get(domain, [])
    return _sample(bank, min(count, len(bank)))


def fallback_passages() -> List[Dict[str, Any]]:
    return list(_load_fallbacks().get("passages", []))


def generate_maths_questions(subtopic: str, level: int) -> List[Dict[str, Any]]:
    system = (
        "You are a cheerful Bible-adventure maths teacher for a 5-year-old. Generate exactly 5 maths "
        "questions in JSON format. Each question must have: 'question' (string, simple "
        "language), 'options' (array of 4 strings), 'answer' (string matching one option), "
        "'emoji' (a fun related emoji). Difficulty level: {level} where 1=easiest, 5=hardest. "
        "Use gentle Bible-era objects when useful, like sheep, stars, scrolls, baskets, wheat, bread, stones, jars, and boats. "
        "Current subtopic: {subtopic}. Return ONLY a valid JSON array, no markdown, no "
        "explanation. Each question must be a complete, clear sentence with enough context "
        "for a young child to understand, answer, and be assessed."
    ).format(level=level, subtopic=subtopic)
    topic_guard = (
        f"Strictly keep all five questions in {subtopic}. "
        "For Subtraction, use taking away or 'left' questions only; do not ask addition."
    )
    return _call_json(
        system,
        f"{_child_context()}\n{topic_guard}\n{_fresh_request_note(subtopic)}",
        fallback=lambda: fallback_maths(subtopic, level=level),
        validator=lambda data: _valid_items(data, ["question", "options", "answer", "emoji"], answer_must_be_option=True),
    )[:5]


def generate_english_items(task_type: str) -> List[Dict[str, Any]]:
    system = (
        "You are a kind Bible-adventure reading teacher for a 5-year-old. Generate content in JSON. "
        "For task type '{task_type}', generate 5 items. Each item: 'prompt' (what to show "
        "child), 'options' (4 choices as strings), 'answer' (correct string), 'hint' "
        "(one simple word hint). Use only simple CVC words and common sight words. "
        "When making stories or examples, use gentle Bible-era scenes such as a scroll, basket, sheep, fish, star, bread, garden, boat, or tent. "
        "Return ONLY a valid JSON array, no markdown. Prompts must use complete, clear "
        "sentences with enough context for the child to understand, respond, and be assessed."
    ).format(task_type=task_type)
    user = (
        f"{_child_context()}\n"
        f"{_fresh_request_note(task_type)}\n"
        "If task_type is sentence builder, make options the shuffled words and answer the full sentence. "
        "If task_type is read-aloud comprehension, make prompt a 2-3 sentence story under 30 words."
    )
    return _call_json(
        system,
        user,
        fallback=lambda: fallback_english(task_type),
        validator=lambda data: _valid_items(data, ["prompt", "options", "answer", "hint"], min_options=3),
    )[:5]


def generate_word_problems(level: int = 1) -> List[Dict[str, Any]]:
    system = (
        "You are a joyful Bible-story maths teacher for a 5-year-old. Create 5 maths "
        "word problems in JSON. Use gentle Bible-inspired story settings and characters "
        "(David, Ruth, Esther, Daniel, Moses, Miriam, Joseph, Noah) with objects like "
        "scrolls, baskets, sheep, fish, bread, stones, stars, wheat, jars, and boats. "
        "Keep stories respectful, non-preachy, and easy for children from different homes. "
        "Each item: 'story' (2 sentences max, under 25 words), 'question' (1 short "
        "question), 'options' (4 number strings), 'answer' (correct string), 'emojis' "
        "(2-3 relevant emojis). Return ONLY a valid JSON array, no markdown. The story and "
        "question must be complete, clear, and self-contained enough to answer."
    )
    return _call_json(
        system,
        f"Difficulty level: {level}\n{_child_context()}\n{_fresh_request_note('word problems')}",
        fallback=lambda: fallback_word_problems(level=level),
        validator=lambda data: _valid_items(data, ["story", "question", "options", "answer", "emojis"], answer_must_be_option=True),
    )[:5]


def generate_science_items(subtopic: str, level: int) -> List[Dict[str, Any]]:
    system = (
        "You are a joyful Creation Lab science and history teacher for a 5-year-old child. "
        "Generate exactly 5 multiple-choice learning questions in JSON. Each item must have "
        "'prompt' (simple Grade 1 words), 'options' (array of 4 short strings), 'answer' "
        "(string matching one option), 'fact' (one happy science or history fact, max 16 words), "
        "'emoji' (one fun related emoji), and 'kind' ('science', 'geography', 'geometry', or 'history'). "
        f"Difficulty level: {level} where 1=easiest and 5=hardest. Current subtopic: {subtopic}. "
        "Use nature, ancient world, Bible-era daily life, maps, plants, animals, stars, water, shapes, tools, and boats when useful. "
        "For history, use safe, age-kind facts about people, places, inventions, culture, and long-ago life. "
        "Return ONLY a valid JSON array, no markdown, no explanation. Prompts and facts must be "
        "complete, clear sentences with enough context for the child to understand and respond."
    )
    return _call_json(
        system,
        f"{_child_context()}\n{_fresh_request_note(subtopic)}",
        fallback=lambda: fallback_science(subtopic),
        validator=lambda data: _valid_items(data, ["prompt", "options", "answer", "fact", "emoji", "kind"], answer_must_be_option=True),
        max_tokens=2200,
    )[:5]


def generate_coding_items(subtopic: str, level: int) -> List[Dict[str, Any]]:
    system = (
        "You are a joyful coding teacher for a 5-year-old. Generate exactly 5 coding "
        "thinking questions in JSON. Each item must have 'prompt' (simple Grade 1 words), "
        "'visual' (emoji or arrow blocks), 'options' (array of 4 short code choices), "
        "'answer' (string matching one option), 'hint' (one short clue), 'concept' "
        "('sequence', 'direction', 'loop', 'debug', or 'condition'), and 'emoji'. "
        f"Difficulty level: {level} where 1=easiest and 5=hardest. Current subtopic: {subtopic}. "
        "No typed programming language. Use block-code ideas like arrows, first-next-last, "
        "repeat 3 times, find the bug, and if/then choices. Use gentle Bible-adventure "
        "settings with Daniel, Miriam, Noah, Ruth, baskets, stars, paths, tents, boats, and scrolls. "
        "Return ONLY a valid JSON array, no markdown. Every prompt must be clear enough for "
        "a young child to understand, answer, and be assessed."
    )
    return _call_json(
        system,
        f"{_child_context()}\n{_fresh_request_note(subtopic)}",
        fallback=lambda: fallback_coding(subtopic),
        validator=lambda data: _valid_items(data, ["prompt", "visual", "options", "answer", "hint", "concept", "emoji"], answer_must_be_option=True),
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
        f"Generate exactly {count} items. Return ONLY a valid JSON array. Each prompt must be a "
        "complete, clear sentence with enough context to understand, answer, and assess."
    )
    return _call_json(
        system,
        _child_context(),
        fallback=lambda: fallback_assessment(domain, count),
        validator=lambda data: _valid_items(data, ["prompt", "options", "answer", "hint", "visual", "task_type"], count=min(count, 1), answer_must_be_option=True),
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
        "cognitive development. Based on the active child's parent-approved profile "
        "when available, and the child's "
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
        "  'monthly_milestone': string (what the child should achieve next month),\n"
        "  'percentile_trajectory': string (honest assessment of path to top 1%),\n"
        "  'parent_tip': string (one specific, evidence-based parenting tip for this week)\n"
        "}\n"
        "Return ONLY valid JSON, no markdown."
    )
    user = json.dumps(
        {
            "child_profile_context": _child_context(),
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
            "summary": "The child is building a broad set of early thinking skills. Short, joyful daily practice will help turn strengths into steady growth.",
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
            "parent_tip": "Praise the strategy the child used, such as checking again or listening carefully, more than the score.",
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
        "This week, the child practised early maths, reading, coding, science, history, and thinking games. Strong moments came when tasks were short, lively, and repeated. "
        "Next week, keep sessions to about 20 minutes and rotate memory, phonics, code paths, story maths, and Creation Lab. Offline activity: count the items on the dinner table, "
        "then ask the child to explain how they counted."
    )
    payload = dict(history)
    payload["child_profile_context"] = _child_context()
    return _call_text(
        "You write warm 300-word weekly parent reports for early learning. Use plain language and practical advice.",
        json.dumps(payload),
        fallback,
        max_tokens=1200,
    )


def generate_passage_library() -> List[Dict[str, Any]]:
    system = (
        "You are a kind Bible-adventure early reading teacher. Generate 30 reading passages in JSON: "
        "10 starter, 10 developing, and 10 fluent. Each item must have 'difficulty', 'text', "
        "and 'target_phonics'. Starter passages are 1 sentence and 5-8 common words. "
        "Developing passages are 2-3 sentences and 15-25 words. Fluent passages are 40-60 words. "
        "Use gentle Bible-era contexts like tents, gardens, sheep, boats, baskets, bread, scrolls, family, animals, and food. Every passage must "
        "be a complete, meaningful mini-story that supports a simple comprehension question. "
        "Return ONLY a valid JSON array."
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
        "DIBELS methodology. A child just read a passage "
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
    user = f"{_child_context()}\nOriginal passage: {passage}\nChild transcript: {transcript}"
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
    user = json.dumps({"child_profile_context": _child_context(), "passage": passage, "question": question, "answer": answer})
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
