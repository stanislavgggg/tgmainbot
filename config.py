"""
config.py — OddsVault Bot
Все env-переменные, каналы, State FSM, константы.
"""

import os
from enum import Enum


# ── Токены ──────────────────────────────────────────────────────────────────
BOT_TOKEN      = os.getenv("BOT_TOKEN",      "")
ANTHROPIC_KEY  = os.getenv("ANTHROPIC_API_KEY", "")


# ── FSM States ───────────────────────────────────────────────────────────────
class State(str, Enum):
    LANG       = "lang"
    QUIZ       = "quiz"
    WARM1      = "warm1"
    WARM2      = "warm2"
    TEASE      = "tease"
    CTA        = "cta"
    SUBSCRIBED = "subscribed"
    AI_CHAT    = "ai_chat"


# ── Каналы ───────────────────────────────────────────────────────────────────
# FIX: добавлен "en" — без него KeyError при CTA у англоязычных юзеров
CHANNELS: dict[str, dict[str, dict]] = {
    "en": {
        "betting":   {"url": "https://t.me/ApuestasGuruES",  "extra_url": ""},
        "casino":    {"url": "https://t.me/ApuestasGuruES",  "extra_url": ""},
        "nodeposit": {"url": "https://t.me/ApuestasGuruES",  "extra_url": ""},
        "exclusive": {"url": "https://t.me/ApuestasGuruES",  "extra_url": ""},
    },
    "es": {
        "betting":   {"url": "https://t.me/ApuestasGuruES",  "extra_url": ""},
        "casino":    {"url": "https://t.me/ApuestasGuruES",  "extra_url": ""},
        "nodeposit": {"url": "https://t.me/ApuestasGuruES",  "extra_url": ""},
        "exclusive": {"url": "https://t.me/ApuestasGuruES",  "extra_url": ""},
    },
    "hr": {
        "betting":   {"url": "https://t.me/Bet_Croatia",   "extra_url": ""},
        "casino":    {"url": "https://t.me/Bet_Croatia",   "extra_url": ""},
        "nodeposit": {"url": "https://t.me/Bet_Croatia",   "extra_url": ""},
        "exclusive": {"url": "https://t.me/Bet_Croatia",   "extra_url": ""},
    },
    "lt": {
        "betting":   {"url": "https://t.me/luckycasinoguru",    "extra_url": ""},
        "casino":    {"url": "https://t.me/luckycasinoguru",    "extra_url": ""},
        "nodeposit": {"url": "https://t.me/luckycasinoguru",    "extra_url": ""},
        "exclusive": {"url": "https://t.me/luckycasinoguru",    "extra_url": ""},
    },
    "lv": {
        "betting":   {"url": "https://t.me/luckylatviaan",  "extra_url": ""},
        "casino":    {"url": "https://t.me/luckylatviaan",  "extra_url": ""},
        "nodeposit": {"url": "https://t.me/luckylatviaan",  "extra_url": ""},
        "exclusive": {"url": "https://t.me/luckylatviaan",  "extra_url": ""},
    },
}


# ── Re-engage тайминги (секунды) ─────────────────────────────────────────────
REENGAGE_DELAY_1 = 24 * 3600
REENGAGE_DELAY_2 = 48 * 3600


# ── Картинки по интересам ────────────────────────────────────────────────────
INTEREST_IMAGES: dict[str, list[str]] = {
    "betting":   [],
    "casino":    [],
    "nodeposit": [],
    "exclusive": [],
}


# ── AI-чат ───────────────────────────────────────────────────────────────────
FTD_PUSH_EVERY  = 5
IMAGE_EVERY_N   = 4
AI_MAX_HISTORY  = 20
AI_MAX_TOKENS   = 350
