"""config.py — OddsVault Bot v8"""
import os, glob
from enum import Enum

BOT_TOKEN     = os.getenv("BOT_TOKEN", "")
ANTHROPIC_KEY = os.getenv("ANTHROPIC_API_KEY", "")

class State(str, Enum):
    LANG="lang"; QUIZ="quiz"; WARM1="warm1"; WARM2="warm2"
    TEASE="tease"; CTA="cta"; SUBSCRIBED="subscribed"; AI_CHAT="ai_chat"

CHANNELS: dict[str, dict[str, dict]] = {
    "en": {"betting":{"url":"https://t.me/ApuestasGuruES","extra_url":""},"casino":{"url":"https://t.me/ApuestasGuruES","extra_url":""},"nodeposit":{"url":"https://t.me/ApuestasGuruES","extra_url":""},"exclusive":{"url":"https://t.me/ApuestasGuruES","extra_url":""}},
    "es": {"betting":{"url":"https://t.me/ApuestasGuruES","extra_url":""},"casino":{"url":"https://t.me/ApuestasGuruES","extra_url":""},"nodeposit":{"url":"https://t.me/ApuestasGuruES","extra_url":""},"exclusive":{"url":"https://t.me/ApuestasGuruES","extra_url":""}},
    "hr": {"betting":{"url":"https://t.me/Bet_Croatia","extra_url":""},"casino":{"url":"https://t.me/Bet_Croatia","extra_url":""},"nodeposit":{"url":"https://t.me/Bet_Croatia","extra_url":""},"exclusive":{"url":"https://t.me/Bet_Croatia","extra_url":""}},
    "lt": {"betting":{"url":"https://t.me/luckycasinoguru","extra_url":""},"casino":{"url":"https://t.me/luckycasinoguru","extra_url":""},"nodeposit":{"url":"https://t.me/luckycasinoguru","extra_url":""},"exclusive":{"url":"https://t.me/luckycasinoguru","extra_url":""}},
    "lv": {"betting":{"url":"https://t.me/luckylatviaan","extra_url":""},"casino":{"url":"https://t.me/luckylatviaan","extra_url":""},"nodeposit":{"url":"https://t.me/luckylatviaan","extra_url":""},"exclusive":{"url":"https://t.me/luckylatviaan","extra_url":""}},
}

REENGAGE_DELAY_1 = 24*3600
REENGAGE_DELAY_2 = 48*3600

def _load_images(base="assets/images"):
    result = {}
    for cat in ("betting","casino","nodeposit","exclusive"):
        folder = os.path.join(base, cat)
        if os.path.exists(folder):
            files = sorted(glob.glob(os.path.join(folder,"*.jpg")) + glob.glob(os.path.join(folder,"*.jpeg")) + glob.glob(os.path.join(folder,"*.png")))
            result[cat] = files
        else:
            result[cat] = []
    return result

INTEREST_IMAGES: dict[str, list[str]] = _load_images()

FTD_PUSH_EVERY = 5
IMAGE_EVERY_N  = 4
AI_MAX_HISTORY = 20
AI_MAX_TOKENS  = 400
