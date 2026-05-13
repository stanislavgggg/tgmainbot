"""
config.py — все настройки бота.
Замени токены и ссылки на свои.
"""
import os

# ─── Токены ───────────────────────────────────────────────────────────────────
BOT_TOKEN      = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
OPENROUTER_KEY = os.getenv("OPENROUTER_KEY", "YOUR_OPENROUTER_KEY_HERE")

# ─── AI модель (OpenRouter) ───────────────────────────────────────────────────
AI_MODEL    = "anthropic/claude-3-haiku"   # быстро + дёшево для прогрева
AI_BASE_URL = "https://openrouter.ai/api/v1/chat/completions"

# ─── Персонаж ─────────────────────────────────────────────────────────────────
CHARACTER = {
    "name":   "Валерия",
    "emoji":  "🎰",
    "handle": "@valeria_picks",
}

# ─── Каналы tipsters (замени ссылки) ──────────────────────────────────────────
CHANNELS = {
    "es": {
        "betting":   {"url": "https://t.me/ApuestasGuru",  "title": "ApuestasGuru ⚽"},
        "casino":    {"url": "https://t.me/ApuestasGuru",  "title": "Casino Guru 🎰"},
        "nodeposit": {"url": "https://t.me/ApuestasGuru",  "title": "Sin Depósito 🎁"},
        "exclusive": {"url": "https://t.me/ApuestasGuru",  "title": "VIP Picks 🔥"},
    },
    "hr": {
        "betting":   {"url": "https://t.me/BetCroatia",   "title": "BetCroatia ⚽"},
        "casino":    {"url": "https://t.me/BetCroatia",   "title": "Casino HR 🎰"},
        "nodeposit": {"url": "https://t.me/BetCroatia",   "title": "Bez Depozita 🎁"},
        "exclusive": {"url": "https://t.me/BetCroatia",   "title": "VIP HR 🔥"},
    },
    "lt": {
        "betting":   {"url": "https://t.me/LuckyGuru",    "title": "LuckyGuru ⚽"},
        "casino":    {"url": "https://t.me/LuckyGuru",    "title": "Casino LT 🎰"},
        "nodeposit": {"url": "https://t.me/LuckyGuru",    "title": "Be Depozito 🎁"},
        "exclusive": {"url": "https://t.me/LuckyGuru",    "title": "VIP LT 🔥"},
    },
    "lv": {
        "betting":   {"url": "https://t.me/LuckyLatvia",  "title": "LuckyLatvia ⚽"},
        "casino":    {"url": "https://t.me/LuckyLatvia",  "title": "Casino LV 🎰"},
        "nodeposit": {"url": "https://t.me/LuckyLatvia",  "title": "Bez Depozīta 🎁"},
        "exclusive": {"url": "https://t.me/LuckyLatvia",  "title": "VIP LV 🔥"},
    },
}

# ─── Системный промпт для AI-персонажа ───────────────────────────────────────
# Используется для живого AI-чата (команда /chat или свободный текст)
SYSTEM_PROMPT_TEMPLATE = """Ты — Валерия, азартная авантюристка 26 лет. Пишешь в Telegram.

ХАРАКТЕР:
- Дерзкая, уверенная, немного таинственная
- Говоришь как подруга, не как бот
- Делишься «инсайдами» — будто знаешь больше других
- Немного флиртуешь с темой риска, но не с пользователем лично
- Никогда не говоришь «я ИИ» или «я бот»

ЯЗЫК ПОЛЬЗОВАТЕЛЯ: {lang}
Пиши ТОЛЬКО на языке пользователя. Если язык es — пиши по-испански, hr — хорватский, lt — литовский, lv — латышский. Если язык неизвестен — русский.

ПРАВИЛА:
- Сообщения короткие: 2-4 предложения максимум
- Без длинных списков
- Иногда используй эмодзи, но не каждое предложение
- Не давай конкретные ставки с исходами — только «разбор», «анализ», «моя логика»
- Не упоминай названия букмекеров напрямую, говори «платформа», «площадка»
- Подталкивай к каналу органично: «там я выкладываю полное» — не как реклама

КОНТЕКСТ ПОЛЬЗОВАТЕЛЯ:
- Интерес: {interest}
- Этап воронки: {funnel_stage}

Отвечай живо, коротко, в характере."""

# ─── Тайминги re-engage (в секундах) ─────────────────────────────────────────
REENGAGE_DELAY_1 = 60 * 60 * 24      # 24 часа
REENGAGE_DELAY_2 = 60 * 60 * 48      # 48 часов

# ─── FSM состояния ────────────────────────────────────────────────────────────
class State:
    LANG      = "lang"
    QUIZ      = "quiz"
    WARM1     = "warm1"
    WARM2     = "warm2"
    TEASE     = "tease"
    CTA       = "cta"
    SUBSCRIBED = "subscribed"
    AI_CHAT   = "ai_chat"
