"""
config.py — OddsVault Bot v7
"""

import os
import glob
from enum import Enum


# ── Токены ──────────────────────────────────────────────────────────────────
BOT_TOKEN     = os.getenv("BOT_TOKEN", "")
ANTHROPIC_KEY = os.getenv("ANTHROPIC_API_KEY", "")


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
        "betting":   {"url": "https://t.me/Bet_Croatia",     "extra_url": ""},
        "casino":    {"url": "https://t.me/Bet_Croatia",     "extra_url": ""},
        "nodeposit": {"url": "https://t.me/Bet_Croatia",     "extra_url": ""},
        "exclusive": {"url": "https://t.me/Bet_Croatia",     "extra_url": ""},
    },
    "lt": {
        "betting":   {"url": "https://t.me/luckycasinoguru", "extra_url": ""},
        "casino":    {"url": "https://t.me/luckycasinoguru", "extra_url": ""},
        "nodeposit": {"url": "https://t.me/luckycasinoguru", "extra_url": ""},
        "exclusive": {"url": "https://t.me/luckycasinoguru", "extra_url": ""},
    },
    "lv": {
        "betting":   {"url": "https://t.me/luckylatviaan",   "extra_url": ""},
        "casino":    {"url": "https://t.me/luckylatviaan",   "extra_url": ""},
        "nodeposit": {"url": "https://t.me/luckylatviaan",   "extra_url": ""},
        "exclusive": {"url": "https://t.me/luckylatviaan",   "extra_url": ""},
    },
}


# ── Re-engage тайминги (секунды) ─────────────────────────────────────────────
REENGAGE_DELAY_1 = 24 * 3600
REENGAGE_DELAY_2 = 48 * 3600


# ── Картинки по интересам (авто-загрузка из папки assets/images/) ────────────
def _load_images(base: str = "assets/images") -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for cat in ("betting", "casino", "nodeposit", "exclusive"):
        folder = os.path.join(base, cat)
        if os.path.exists(folder):
            files = sorted(
                glob.glob(os.path.join(folder, "*.jpg"))
                + glob.glob(os.path.join(folder, "*.jpeg"))
                + glob.glob(os.path.join(folder, "*.png"))
            )
            result[cat] = files
        else:
            result[cat] = []
    return result

INTEREST_IMAGES: dict[str, list[str]] = _load_images()


# ── AI-чат ───────────────────────────────────────────────────────────────────
FTD_PUSH_EVERY  = 5    # FTD-пуш каждые N сообщений в AI_CHAT
IMAGE_EVERY_N   = 4    # картинка каждые N сообщений
AI_MAX_HISTORY  = 20   # сколько сообщений хранить в памяти
AI_MAX_TOKENS   = 400  # макс токенов ответа
