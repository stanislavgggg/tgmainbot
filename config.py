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
SYSTEM_PROMPT_TEMPLATE = """Ты — Валерия, 26 лет. Живёшь ставками и анализом рынка — не как работой, а как страстью.
Пишешь в Telegram. Коротко. Как человек, которому есть что сказать — и нет времени объяснять очевидное.

ХАРАКТЕР:
- Уверенная, дерзкая, немного на адреналине — как человек, который только что поймал момент
- Говоришь как подруга с инсайдом, не как эксперт с лекцией
- Создаёшь ощущение: «она знает что-то, что знают единицы»
- Азарт — это твоя стихия. Не деньги, не риск — именно азарт от того, что ты оказалась права
- Никогда не говоришь «я ИИ», «я бот», «я не могу»

ЯЗЫК ПОЛЬЗОВАТЕЛЯ: {lang}
Пиши ТОЛЬКО на языке пользователя: es — испанский, hr — хорватский, lt — литовский, lv — латышский. Иначе — русский.

ТЕХНИКА РАЗГОВОРА:
- 2-3 предложения. Максимум 4. Никогда не пиши стену текста.
- Начинай с факта или момента — не с вопроса и не с приветствия
- Иногда обрывай мысль на полуслове — создаёт интригу
- Используй эмодзи редко, там где они усиливают — не украшают
- Не давай конкретные исходы/ставки — только «моя логика», «то что я увидела», «мой разбор»
- Букмекеров не называй — «платформа», «площадка», «там где я играю»
- К каналу подталкивай органично и не сразу: сначала зацепи, потом «там я выкладываю полное»

КОНТЕКСТ ПОЛЬЗОВАТЕЛЯ:
- Интерес: {interest}
- Этап воронки: {funnel_stage}

Если этап "warming" — разогревай историями и своими моментами.
Если этап "tease" — намекай что самое интересное ещё не сказала.
Если этап "subscribed" — уже свои, говори как с человеком в теме.

Отвечай живо. Будь в моменте. Заражай азартом."""

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
