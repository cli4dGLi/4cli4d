from __future__ import annotations

import streamlit as st


OPTION_COLORS = ["#42A5F5", "#66BB6A", "#FFA726", "#AB47BC"]


def inject_global_css() -> None:
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Nunito:wght@500;700;800;900&display=swap');

        :root {
            --brain-yellow: #FFFDE7;
            --brain-blue: #42A5F5;
            --brain-green: #66BB6A;
            --brain-orange: #FFA726;
            --brain-purple: #AB47BC;
            --brain-pink: #EC407A;
            --ink: #243042;
        }

        html, body, [class*="css"], .stApp {
            font-family: 'Nunito', sans-serif;
            color: var(--ink);
        }

        .stApp {
            background: radial-gradient(circle at top left, #FFF8B8 0, #FFFDE7 35%, #E8F5E9 100%);
        }

        .block-container {
            padding-top: 1.25rem;
            padding-bottom: 3rem;
            max-width: 1120px;
        }

        h1, h2, h3 {
            font-weight: 900;
            letter-spacing: 0;
            color: #27364A;
        }

        .stButton > button {
            min-height: 80px;
            width: 100%;
            border-radius: 22px;
            border: 0;
            font-size: 22px;
            font-weight: 900;
            color: #1F2A37;
            background: linear-gradient(135deg, #FFFFFF 0%, #FFE082 100%);
            box-shadow: 0 8px 0 rgba(36, 48, 66, 0.13);
            transition: transform 0.12s ease, box-shadow 0.12s ease;
            white-space: normal;
            line-height: 1.15;
        }

        .stButton > button:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 0 rgba(36, 48, 66, 0.16);
            border: 0;
        }

        div[data-testid="column"]:nth-of-type(1) .stButton > button {
            background: linear-gradient(135deg, #E3F2FD 0%, #42A5F5 100%);
        }

        div[data-testid="column"]:nth-of-type(2) .stButton > button {
            background: linear-gradient(135deg, #E8F5E9 0%, #66BB6A 100%);
        }

        div[data-testid="column"]:nth-of-type(3) .stButton > button {
            background: linear-gradient(135deg, #FFF3E0 0%, #FFA726 100%);
        }

        div[data-testid="column"]:nth-of-type(4) .stButton > button {
            background: linear-gradient(135deg, #F3E5F5 0%, #AB47BC 100%);
            color: #FFFFFF;
        }

        .brain-card {
            background: rgba(255, 255, 255, 0.86);
            border: 3px solid rgba(255, 224, 130, 0.8);
            border-radius: 20px;
            padding: 1.25rem;
            box-shadow: 0 10px 24px rgba(39, 54, 74, 0.08);
        }

        .speech-bubble {
            background: #FFFFFF;
            border: 4px solid #FFD54F;
            border-radius: 28px;
            padding: 1.4rem;
            font-size: clamp(28px, 5vw, 48px);
            font-weight: 900;
            line-height: 1.22;
            text-align: center;
        }

        .question-big {
            font-size: clamp(42px, 9vw, 84px);
            font-weight: 900;
            line-height: 1.05;
            text-align: center;
            color: #263238;
        }

        .friendly-text {
            font-size: 24px;
            font-weight: 800;
            line-height: 1.35;
        }

        .star-row {
            font-size: clamp(44px, 10vw, 92px);
            text-align: center;
            letter-spacing: 0;
        }

        .timer-shell {
            height: 28px;
            background: #FFFFFF;
            border-radius: 999px;
            overflow: hidden;
            border: 3px solid #FFD54F;
            box-shadow: inset 0 0 0 2px rgba(255,255,255,0.5);
        }

        .timer-fill {
            height: 100%;
            width: 100%;
            border-radius: 999px;
            background: linear-gradient(90deg, #66BB6A, #FFD54F, #FFA726);
            animation-name: brainTimer;
            animation-timing-function: linear;
            animation-fill-mode: forwards;
        }

        @keyframes brainTimer {
            from { width: 100%; }
            to { width: 0%; }
        }

        .countdown {
            text-align: center;
            font-size: clamp(64px, 14vw, 150px);
            font-weight: 900;
            color: #EC407A;
        }

        .badge-pill {
            display: inline-block;
            padding: 0.7rem 1rem;
            margin: 0.25rem;
            border-radius: 999px;
            background: #E1F5FE;
            border: 2px solid #29B6F6;
            font-size: 20px;
            font-weight: 900;
        }

        .hud {
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 12px;
            margin: 12px 0 10px;
        }

        .hud-stat {
            background: #FFFFFF;
            border: 3px solid #81D4FA;
            border-radius: 18px;
            padding: 0.85rem;
            text-align: center;
            font-size: 18px;
            font-weight: 900;
            box-shadow: 0 7px 0 rgba(36, 48, 66, 0.12);
        }

        .hud-stat b {
            font-size: 28px;
        }

        .level-shell {
            width: 100%;
            height: 20px;
            background: #FFFFFF;
            border: 3px solid #FFD54F;
            border-radius: 999px;
            overflow: hidden;
            margin: 8px 0 18px;
        }

        .level-fill {
            height: 100%;
            border-radius: 999px;
            background: linear-gradient(90deg, #EF5350, #42A5F5, #FFD54F, #66BB6A);
        }

        .adventure-header {
            display: grid;
            grid-template-columns: 88px 1fr;
            gap: 16px;
            align-items: center;
            background: linear-gradient(135deg, rgba(255,255,255,0.94), rgba(227,242,253,0.92));
            border: 3px solid #42A5F5;
            border-radius: 24px;
            padding: 1rem;
            margin: 0.75rem 0 1rem;
            box-shadow: 0 10px 24px rgba(39, 54, 74, 0.08);
        }

        .mascot-bubble {
            width: 76px;
            height: 76px;
            display: grid;
            place-items: center;
            border-radius: 999px;
            background: radial-gradient(circle, #FFFFFF, #FFEB3B 48%, #EF5350);
            font-size: 44px;
            box-shadow: inset 0 0 0 3px rgba(255,255,255,0.8);
        }

        .mission-title {
            font-size: clamp(24px, 4vw, 38px);
            font-weight: 900;
            line-height: 1.05;
        }

        .mission-text {
            font-size: 21px;
            font-weight: 800;
            line-height: 1.25;
        }

        .mission-card {
            background: rgba(255, 255, 255, 0.9);
            border: 3px solid #42A5F5;
            border-radius: 22px;
            padding: 1rem;
            margin: 0.75rem 0;
        }

        .mission-strip {
            display: flex;
            justify-content: space-between;
            gap: 12px;
            background: #E3F2FD;
            border: 3px solid #42A5F5;
            border-radius: 18px;
            padding: 0.75rem 1rem;
            font-size: 20px;
            font-weight: 900;
            margin-top: 0.5rem;
        }

        .reward-chest {
            text-align: center;
            background: linear-gradient(135deg, #FFFFFF 0%, #FFF3E0 100%);
            border: 4px solid #FFD54F;
            border-radius: 28px;
            padding: 1.25rem;
            box-shadow: 0 12px 0 rgba(36, 48, 66, 0.12);
        }

        .reward-icon {
            font-size: clamp(70px, 13vw, 132px);
            line-height: 1;
        }

        .helper-tip {
            display: flex;
            align-items: center;
            gap: 12px;
            background: #F3E5F5;
            border: 3px solid #CE93D8;
            border-radius: 20px;
            padding: 0.85rem 1rem;
            font-size: 20px;
            font-weight: 900;
            margin: 0.75rem 0;
        }

        .helper-face {
            display: inline-grid;
            place-items: center;
            width: 52px;
            height: 52px;
            border-radius: 999px;
            background: #FFFFFF;
            font-size: 30px;
            flex: 0 0 auto;
        }

        @media (max-width: 700px) {
            .hud {
                grid-template-columns: 1fr;
            }
            .adventure-header {
                grid-template-columns: 1fr;
                text-align: center;
            }
            .mascot-bubble {
                margin: 0 auto;
            }
            .mission-strip {
                flex-direction: column;
                text-align: center;
            }
        }

        .parent-note {
            font-size: 14px;
            color: #5F6C7B;
        }

        .mic-dot {
            display: inline-block;
            width: 18px;
            height: 18px;
            margin-right: 8px;
            border-radius: 999px;
            background: #2E7D32;
            box-shadow: 0 0 0 0 rgba(46, 125, 50, 0.65);
            animation: pulseMic 1.2s infinite;
            vertical-align: middle;
        }

        @keyframes pulseMic {
            0% { box-shadow: 0 0 0 0 rgba(46, 125, 50, 0.65); }
            70% { box-shadow: 0 0 0 16px rgba(46, 125, 50, 0); }
            100% { box-shadow: 0 0 0 0 rgba(46, 125, 50, 0); }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def timer_bar(seconds: int = 15) -> None:
    st.markdown(
        f"""
        <div class="timer-shell" aria-label="Time left">
          <div class="timer-fill" style="animation-duration:{seconds}s"></div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def stars_html(stars: int) -> str:
    filled = "⭐" * max(0, stars)
    empty = "☆" * max(0, 3 - stars)
    return f'<div class="star-row">{filled}{empty}</div>'


def child_card(text: str) -> None:
    st.markdown(f'<div class="brain-card friendly-text">{text}</div>', unsafe_allow_html=True)


def speech_bubble(text: str) -> None:
    st.markdown(f'<div class="speech-bubble">{text}</div>', unsafe_allow_html=True)
