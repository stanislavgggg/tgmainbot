"""
config.py — OddsVault Bot
Все env-переменные, каналы, State FSM, константы.
"""

import os
from enum import Enum


# ── Токены ──────────────────────────────────────────────────────────────────
BOT_TOKEN      = os.getenv("BOT_TOKEN",      "8840016683:AAFRXj04QarjrC0OfVefeCTCaTWz4HnO6Sk")
ANTHROPIC_KEY  = os.getenv("ANTHROPIC_API_KEY", "")   # ← обязателен для AI-чата


# ── FSM States ───────────────────────────────────────────────────────────────
class State(str, Enum):
    LANG       = "lang"        # выбор языка
    QUIZ       = "quiz"        # выбор интереса
    WARM1      = "warm1"       # прогрев 1 — ждём реакции
    WARM2      = "warm2"       # прогрев 2 — ждём реакции
    TEASE      = "tease"       # тизер    — ждём реакции
    CTA        = "cta"         # кнопка канала
    SUBSCRIBED = "subscribed"  # «Уже вступил»
    AI_CHAT    = "ai_chat"     # свободный AI-чат (FTD-режим)


# ── Каналы ───────────────────────────────────────────────────────────────────
# url — основной, extra_url — опциональный второй
CHANNELS: dict[str, dict[str, dict]] = {
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
REENGAGE_DELAY_1 = 24 * 3600    # 24 ч
REENGAGE_DELAY_2 = 48 * 3600    # 48 ч


# ── Картинки по интересам (добавь свои файлы в папку images/) ────────────────
INTEREST_IMAGES: dict[str, list[str]] = {
    "betting":   [],
    "casino":    [],
    "nodeposit": [],
    "exclusive": [],
}


# ── AI-чат: FTD пуш каждые N сообщений ─────────────────────────────────────
FTD_PUSH_EVERY  = 5
IMAGE_EVERY_N   = 4
AI_MAX_HISTORY  = 20     # сколько сообщений хранить в истории
AI_MAX_TOKENS   = 350    # max tokens в ответе Valeria
