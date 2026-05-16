"""config.py — OddsVault Bot v14 (cleaned)

УДАЛЕНО (мёртвый код):
  - CHANNELS dict — routing перенесён в membership.py
  - REENGAGE_DELAY_1/2 — заменены логикой в reengage_job
  - IMAGE_EVERY_N — нет handler-а для картинок
  - FTD_PUSH_EVERY — нет handler-а
"""
import os, glob
from enum import Enum

BOT_TOKEN     = os.getenv("BOT_TOKEN", "")
ANTHROPIC_KEY = os.getenv("ANTHROPIC_API_KEY", "")

class State(str, Enum):
    LANG="lang"; QUIZ="quiz"; WARM1="warm1"; WARM2="warm2"
    TEASE="tease"; CTA="cta"; SUBSCRIBED="subscribed"; AI_CHAT="ai_chat"

def _load_images(base="assets/images"):
    result = {}
    for cat in ("betting", "casino", "nodeposit", "exclusive"):
        folder = os.path.join(base, cat)
        if os.path.exists(folder):
            files = sorted(
                glob.glob(os.path.join(folder, "*.jpg")) +
                glob.glob(os.path.join(folder, "*.jpeg")) +
                glob.glob(os.path.join(folder, "*.png"))
            )
            result[cat] = files
        else:
            result[cat] = []
    return result

INTEREST_IMAGES: dict[str, list[str]] = _load_images()

AI_MAX_HISTORY = 20
AI_MAX_TOKENS  = 400
