from __future__ import annotations

import random
import time
from typing import Any, Dict, List, Tuple

import streamlit as st

import claude_api
import database
from utils import gamify, styles
from utils.scoring import stars_for_score
from utils.tts import read_button


SUBTOPICS = ["Pattern Puzzles", "Odd One Out", "Memory Match", "Maze Rescue"]


PATTERN_BANK = [
    {"prompt": "What comes next?", "visual": "🔴 🔵 🔴 🔵 ?", "options": ["🔴", "🔵", "🟢", "🟡"], "answer": "🔴", "tip": "The colours take turns."},
    {"prompt": "What comes next?", "visual": "⭐ 🌙 ⭐ 🌙 ?", "options": ["⭐", "🌙", "☀️", "⚡"], "answer": "⭐", "tip": "The star comes after the moon."},
    {"prompt": "What comes next?", "visual": "1 2 1 2 ?", "options": ["1", "2", "3", "4"], "answer": "1", "tip": "The numbers repeat."},
    {"prompt": "What comes next?", "visual": "🟦 🟨 🟦 🟨 ?", "options": ["🟦", "🟨", "🟩", "🟥"], "answer": "🟦", "tip": "Blue starts the pattern again."},
    {"prompt": "What comes next?", "visual": "small BIG small BIG ?", "options": ["small", "BIG", "red", "round"], "answer": "small", "tip": "The sizes take turns."},
    {"prompt": "What comes next?", "visual": "2 4 6 8 ?", "options": ["9", "10", "11", "12"], "answer": "10", "tip": "Counting by twos makes this pattern."},
    {"prompt": "What comes next?", "visual": "A B A B ?", "options": ["A", "B", "C", "D"], "answer": "A", "tip": "The letters repeat."},
    {"prompt": "What comes next?", "visual": "🔺 🔺 🔵 🔺 🔺 🔵 ?", "options": ["🔺", "🔵", "🟩", "⭐"], "answer": "🔺", "tip": "Two triangles come before the circle."},
]


ODD_BANK = [
    {"prompt": "Which one does not belong?", "visual": "🐶 🐱 🐐 🥤", "options": ["dog", "cat", "goat", "cup"], "answer": "cup", "tip": "The cup is not an animal."},
    {"prompt": "Which one does not belong?", "visual": "🍎 🍌 🥭 ⚽", "options": ["apple", "banana", "mango", "ball"], "answer": "ball", "tip": "The ball is not food."},
    {"prompt": "Which one does not belong?", "visual": "red blue green table", "options": ["red", "blue", "green", "table"], "answer": "table", "tip": "The table is not a colour."},
    {"prompt": "Which one does not belong?", "visual": "circle square triangle banana", "options": ["circle", "square", "triangle", "banana"], "answer": "banana", "tip": "The banana is not a shape."},
    {"prompt": "Which one does not belong?", "visual": "car bus bike fish", "options": ["car", "bus", "bike", "fish"], "answer": "fish", "tip": "The fish is not a road ride."},
    {"prompt": "Which one does not belong?", "visual": "sun moon star shoe", "options": ["sun", "moon", "star", "shoe"], "answer": "shoe", "tip": "The shoe is not in the sky."},
    {"prompt": "Which one does not belong?", "visual": "book pencil crayon orange", "options": ["book", "pencil", "crayon", "orange"], "answer": "orange", "tip": "The orange is not a school tool."},
    {"prompt": "Which one does not belong?", "visual": "hand foot nose spoon", "options": ["hand", "foot", "nose", "spoon"], "answer": "spoon", "tip": "The spoon is not a body part."},
]


MEMORY_BANK = [
    ["⭐", "🛡️", "⚡"],
    ["🐶", "📚", "🧩"],
    ["🔬", "🌙", "🍎"],
    ["🚀", "🎈", "🏆"],
    ["🟦", "🟨", "🟥"],
    ["🥭", "🐐", "🏠", "☀️"],
    ["🔺", "🔵", "⬛", "⭐"],
]


MAZES = [
    ["S....", ".##..", "...#.", ".#...", "...#G"],
    ["S..#..", ".#.#..", ".#....", "...##.", "##....", "....#G"],
    ["S..#...", ".#.#.#.", ".#...#.", "...#...", "##.#.##", "...#...", ".#...#G"],
    ["S...#..", "##..#..", "...#...", ".#.#.##", ".#.....", ".###.#.", ".....#G"],
    ["S..#....", ".#.#.##.", ".#...#..", ".###.#.#", "...#...#", "##.#.#..", "...#....", ".#...##G"],
]


def _countdown() -> None:
    spot = st.empty()
    for text in ["3", "2", "1", "Go!"]:
        spot.markdown(f'<div class="countdown">{text}</div>', unsafe_allow_html=True)
        time.sleep(0.65)
    spot.empty()


def _sample_items(bank: List[Dict[str, Any]], count: int = 5) -> List[Dict[str, Any]]:
    items = random.sample(bank, min(count, len(bank)))
    return [dict(item) for item in items]


def _memory_items(level: int) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    distractors = ["🧁", "🚗", "🎵", "🌈", "🍌", "🦶", "🧸", "🌍"]
    for sequence in random.sample(MEMORY_BANK, 5):
        shown = sequence[: min(len(sequence), 3 + (1 if level >= 3 else 0))]
        answer = random.choice(shown)
        options = {answer}
        while len(options) < 4:
            options.add(random.choice(distractors + [item for row in MEMORY_BANK for item in row]))
        option_list = list(options)
        random.shuffle(option_list)
        items.append(
            {
                "prompt": "Which badge did you see?",
                "visual": " ".join(shown),
                "options": option_list,
                "answer": answer,
                "tip": "Look, remember, then choose.",
                "memory": True,
            }
        )
    return items


def _start_puzzle(subtopic: str) -> None:
    level = database.get_difficulty("puzzles")
    _countdown()
    if subtopic == "Pattern Puzzles":
        items = _sample_items(PATTERN_BANK)
    elif subtopic == "Odd One Out":
        items = _sample_items(ODD_BANK)
    else:
        items = _memory_items(level)
    st.session_state.puzzle_run = {
        "subtopic": subtopic,
        "level": level,
        "items": items,
        "idx": 0,
        "score": 0,
        "times": [],
        "feedback": None,
        "shown_memory": {},
        "logged": False,
        "question_started": time.time(),
    }
    st.rerun()


def _finish_puzzle(run: Dict[str, Any]) -> None:
    avg = sum(run["times"]) / max(1, len(run["times"]))
    stars = stars_for_score(run["score"], 5, avg)
    if not run.get("logged"):
        database.log_session("puzzles", run["subtopic"], run["score"], stars, run["level"])
        database.adapt_difficulty("puzzles", run["score"])
        run["logged"] = True
    st.markdown("## Puzzle Rescue complete!")
    gamify.reward_chest(stars, run["score"], 5)
    st.markdown(styles.stars_html(stars), unsafe_allow_html=True)
    styles.child_card(f"You solved {run['score']} out of 5 puzzle missions. Puzzle Bot is cheering! 🌟")
    if st.button("Play more puzzles"):
        st.session_state.pop("puzzle_run", None)
        st.rerun()


def _answer_puzzle(run: Dict[str, Any], choice: str) -> None:
    item = run["items"][run["idx"]]
    elapsed = time.time() - run.get("question_started", time.time())
    correct = choice == str(item["answer"])
    run["times"].append(elapsed)
    if correct:
        run["score"] += 1
        st.session_state.puzzle_balloons = True
        message = "Yes! Puzzle Bot found the path!"
    else:
        message = claude_api.kind_try_next_message()
    run["feedback"] = {"correct": correct, "message": message, "tip": item.get("tip", "Try the next puzzle power.")}
    st.rerun()


def _render_puzzle_feedback(run: Dict[str, Any]) -> None:
    feedback = run["feedback"]
    if feedback.get("correct") and st.session_state.pop("puzzle_balloons", False):
        st.balloons()
    mark = "✅" if feedback.get("correct") else "⭐"
    st.markdown(
        f"""
        <div class="brain-card" style="text-align:center;">
            <div style="font-size:88px;">{mark}</div>
            <div class="friendly-text">{feedback['message']}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    gamify.helper_tip(feedback["tip"], "🧩")
    if st.button("Next puzzle"):
        run["idx"] += 1
        run["feedback"] = None
        run["question_started"] = time.time()
        st.rerun()


def _show_memory_once(run: Dict[str, Any], item: Dict[str, Any]) -> None:
    key = str(run["idx"])
    if not item.get("memory") or run["shown_memory"].get(key):
        return
    spot = st.empty()
    spot.markdown(f'<div class="countdown">{" ".join(item["visual"].split())}</div>', unsafe_allow_html=True)
    time.sleep(2.4)
    spot.markdown('<div class="countdown">?</div>', unsafe_allow_html=True)
    time.sleep(0.35)
    spot.empty()
    run["shown_memory"][key] = True


def _render_puzzle_question(run: Dict[str, Any]) -> None:
    if run["idx"] >= len(run["items"]):
        _finish_puzzle(run)
        return
    if run.get("feedback"):
        _render_puzzle_feedback(run)
        return

    item = run["items"][run["idx"]]
    _show_memory_once(run, item)
    gamify.mission_progress(run["idx"] + 1, 5, run["score"])
    styles.speech_bubble(f"🧩<br>{item['prompt']}<br><br>{item['visual'] if not item.get('memory') else ''}")
    read_button(item["prompt"], key=f"puzzle-read-{run['idx']}")

    options = [str(option) for option in item["options"]]
    for row_start in range(0, 4, 2):
        cols = st.columns(2)
        for offset, choice in enumerate(options[row_start : row_start + 2]):
            with cols[offset]:
                if st.button(choice, key=f"puzzle-{run['idx']}-{row_start}-{offset}"):
                    _answer_puzzle(run, choice)


def _maze_for_level(level: int) -> List[str]:
    return MAZES[max(0, min(len(MAZES) - 1, level - 1))]


def _find_cell(grid: List[str], target: str) -> Tuple[int, int]:
    for row_index, row in enumerate(grid):
        for col_index, cell in enumerate(row):
            if cell == target:
                return row_index, col_index
    return 0, 0


def _start_maze() -> None:
    level = database.get_difficulty("puzzles")
    grid = _maze_for_level(level)
    st.session_state.maze_run = {
        "level": level,
        "grid": grid,
        "pos": _find_cell(grid, "S"),
        "goal": _find_cell(grid, "G"),
        "moves": 0,
        "visited": [_find_cell(grid, "S")],
        "message": "Help Rescue Pup reach the pink goal!",
        "logged": False,
    }
    st.rerun()


def _maze_score(moves: int, level: int) -> Tuple[int, int]:
    targets = {1: 8, 2: 12, 3: 16, 4: 18, 5: 22}
    target = targets.get(level, 14)
    if moves <= target:
        return 5, 3
    if moves <= target + 5:
        return 4, 2
    if moves <= target + 10:
        return 3, 2
    return 2, 1


def _move_maze(run: Dict[str, Any], dr: int, dc: int) -> None:
    row, col = run["pos"]
    nr, nc = row + dr, col + dc
    grid = run["grid"]
    if nr < 0 or nc < 0 or nr >= len(grid) or nc >= len(grid[0]):
        run["message"] = "That way is outside the city wall."
        st.rerun()
        return
    if grid[nr][nc] == "#":
        run["message"] = "A blue wall blocks that way."
        st.rerun()
        return
    run["pos"] = (nr, nc)
    run["moves"] += 1
    if (nr, nc) not in run["visited"]:
        run["visited"].append((nr, nc))
    if run["pos"] == run["goal"]:
        score, stars = _maze_score(run["moves"], run["level"])
        if not run.get("logged"):
            database.log_session("puzzles", "Maze Rescue", score, stars, run["level"])
            database.adapt_difficulty("puzzles", score)
            run["logged"] = True
        run["score"] = score
        run["stars"] = stars
        run["message"] = "Rescue complete! You found the way!"
        st.session_state.maze_balloons = True
    else:
        run["message"] = "Good move. Keep finding the path!"
    st.rerun()


def _render_maze_grid(run: Dict[str, Any]) -> None:
    grid = run["grid"]
    cols = len(grid[0])
    cells = []
    for r, row in enumerate(grid):
        for c, cell in enumerate(row):
            pos = (r, c)
            if pos == run["pos"]:
                cells.append('<div class="maze-cell maze-hero">🐶</div>')
            elif pos == run["goal"]:
                cells.append('<div class="maze-cell maze-goal">🏁</div>')
            elif cell == "#":
                cells.append('<div class="maze-cell maze-wall">🧱</div>')
            elif pos in run["visited"]:
                cells.append('<div class="maze-cell maze-path">✨</div>')
            else:
                cells.append('<div class="maze-cell maze-open"></div>')
    st.markdown(
        f'<div class="maze-grid" style="grid-template-columns: repeat({cols}, minmax(40px, 62px));">{"".join(cells)}</div>',
        unsafe_allow_html=True,
    )


def _render_maze() -> None:
    run = st.session_state.get("maze_run")
    if not run:
        styles.child_card("Guide Rescue Pup through the maze. Use the big arrows.")
        if st.button("Start maze rescue"):
            _countdown()
            _start_maze()
        return

    if run.get("score"):
        if st.session_state.pop("maze_balloons", False):
            st.balloons()
        st.markdown("## Maze rescue complete!")
        gamify.reward_chest(run["stars"], run["score"], 5)
        st.markdown(styles.stars_html(run["stars"]), unsafe_allow_html=True)
        styles.child_card(f"You reached the goal in {run['moves']} moves.")
        if st.button("Try a new maze"):
            st.session_state.pop("maze_run", None)
            st.rerun()
        return

    gamify.mission_progress(min(run["moves"] + 1, 5), 5, max(0, 5 - run["moves"] // 4))
    _render_maze_grid(run)
    gamify.helper_tip(run["message"], "🐶")
    top = st.columns([1, 1, 1])
    with top[1]:
        if st.button("⬆️", key="maze-up"):
            _move_maze(run, -1, 0)
    middle = st.columns(3)
    with middle[0]:
        if st.button("⬅️", key="maze-left"):
            _move_maze(run, 0, -1)
    with middle[1]:
        st.button("🐶", key="maze-pup", disabled=True)
    with middle[2]:
        if st.button("➡️", key="maze-right"):
            _move_maze(run, 0, 1)
    bottom = st.columns([1, 1, 1])
    with bottom[1]:
        if st.button("⬇️", key="maze-down"):
            _move_maze(run, 1, 0)


def render() -> None:
    st.markdown("# Puzzle Rescue 🧩")
    gamify.adventure_header("Puzzle Rescue", "🧩", "Puzzle Bot and Rescue Pup need your brain power.")

    if st.session_state.get("puzzle_topic") == "Maze Rescue":
        _render_maze()
        if st.button("Back to puzzle missions"):
            st.session_state.pop("puzzle_topic", None)
            st.session_state.pop("maze_run", None)
            st.rerun()
        return

    run = st.session_state.get("puzzle_run")
    if run:
        _render_puzzle_question(run)
        return

    styles.child_card("Pick a puzzle mission. Patterns, memory, odd ones, or a maze.")
    for row_start in range(0, len(SUBTOPICS), 2):
        cols = st.columns(2)
        for offset, subtopic in enumerate(SUBTOPICS[row_start : row_start + 2]):
            with cols[offset]:
                if st.button(subtopic, key=f"puzzle-topic-{subtopic}"):
                    if subtopic == "Maze Rescue":
                        st.session_state.puzzle_topic = "Maze Rescue"
                        st.rerun()
                    else:
                        _start_puzzle(subtopic)
