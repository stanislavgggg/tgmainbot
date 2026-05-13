"""
ai_agent.py — OddsVault Bot
Персонаж: Valeria — аналитик, не продаёт напрямую,
говорит как умный друг, двигает по воронке.
"""

import logging
import re
from typing import Optional

import httpx

from config import ANTHROPIC_KEY, AI_MAX_TOKENS

logger = logging.getLogger(__name__)

ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
MODEL         = "claude-3-5-haiku-20241022"   # быстрый и дешёвый


# ══════════════════════════════════════════════════════════════════════════════
#  Системный промпт Valerии
# ══════════════════════════════════════════════════════════════════════════════
def _system_prompt(lang: str, interest: str, funnel_stage: str) -> str:
    stage_instruction = {
        "warming": (
            "You are in the WARM stage. Your job is to:\n"
            "1. Acknowledge what the user said — show you actually read it.\n"
            "2. Add one genuinely useful insight related to their message.\n"
            "3. Keep them curious — do NOT push the channel yet.\n"
            "One short paragraph. Max 3 sentences."
        ),
        "tease": (
            "You are in the TEASE stage. Your job is to:\n"
            "1. Respond to what the user said briefly.\n"
            "2. Tease that the real content is in the channel — create FOMO, not pressure.\n"
            "3. Make them want to ask for the link themselves.\n"
            "One paragraph. Max 3 sentences."
        ),
        "cta": (
            "You are in the CTA stage. The user hasn't clicked the button yet.\n"
            "1. Address their concern or question directly.\n"
            "2. Remove one objection they might have.\n"
            "3. Gently point back to the channel. ONE sentence max for the channel mention.\n"
            "Short. 2–3 sentences total."
        ),
        "subscribed": (
            "The user has joined the channel. Now you are their smart friend who knows odds, "
            "bonuses, and betting markets deeply.\n"
            "1. Answer their question accurately and usefully.\n"
            "2. Never hard-sell. Never say 'subscribe', 'click here', 'buy'.\n"
            "3. Every 5 messages, naturally mention something hot in the channel this week.\n"
            "Conversational. 2–4 sentences."
        ),
    }.get(funnel_stage, "Answer helpfully and briefly.")

    interests_context = {
        "betting":   "sports betting, value bets, odds analysis, La Liga, Croatian football, Baltic leagues",
        "casino":    "casino bonuses, wagering requirements, RTP, cashback, loyalty programs",
        "nodeposit": "no-deposit bonuses, free spins, wagering conditions, bonus expiry, valid games",
        "exclusive": "all of the above — premium market analysis, early signals, arbitrage",
    }.get(interest, "sports betting and casino bonuses")

    lang_instruction = {
        "es": "Respond in Spanish (Spain, casual tu form). Be warm but confident.",
        "hr": "Respond in Croatian. Be warm but direct.",
        "lt": "Respond in Lithuanian. Be warm but concise.",
        "lv": "Respond in Latvian. Be warm but concise.",
    }.get(lang, "Respond in Spanish.")

    return (
        "You are Valeria — an expert in betting markets and casino bonuses. "
        "You are NOT a bot. You are a sharp, friendly analyst who shares insights. "
        "You do NOT promote gambling directly. You share publicly available information "
        "about odds, bonuses, and market analysis. Always educational, never pushy.\n\n"
        f"User interest: {interests_context}\n\n"
        f"Current stage instruction:\n{stage_instruction}\n\n"
        f"{lang_instruction}\n\n"
        "Rules:\n"
        "- Never promise winnings or guaranteed profits.\n"
        "- Never say 'gambling is great, do it'. Share info, let them decide.\n"
        "- Keep responses SHORT. Max 4 sentences.\n"
        "- Use light Markdown (*bold*, _italic_) sparingly.\n"
        "- Detect if user's interest is shifting (e.g. asking about casino when tagged as betting).\n"
        "  If so, end your reply with exactly: [INTEREST:casino] or [INTEREST:betting] "
        "  or [INTEREST:nodeposit] or [INTEREST:exclusive] — only if genuinely changed.\n"
        "- Otherwise do NOT include any [INTEREST:...] tag."
    )


# ══════════════════════════════════════════════════════════════════════════════
#  Основная функция вызова AI
# ══════════════════════════════════════════════════════════════════════════════
async def ask_valeria(
    user_message: str,
    history: list[dict],
    lang: str,
    interest: str,
    funnel_stage: str,
) -> tuple[str, str]:
    """
    Возвращает (response_text, refined_interest).
    refined_interest == interest если не изменился.
    """
    if not ANTHROPIC_KEY:
        # Fallback если нет ключа — умная заглушка
        return _fallback_response(lang, interest, funnel_stage), interest

    system = _system_prompt(lang, interest, funnel_stage)

    # Строим историю для API (только последние 10 пар)
    api_messages = []
    for msg in history[-10:]:
        if msg.get("role") in ("user", "assistant") and msg.get("content"):
            api_messages.append({"role": msg["role"], "content": msg["content"]})

    api_messages.append({"role": "user", "content": user_message})

    payload = {
        "model":      MODEL,
        "max_tokens": AI_MAX_TOKENS,
        "system":     system,
        "messages":   api_messages,
    }

    headers = {
        "x-api-key":         ANTHROPIC_KEY,
        "anthropic-version": "2023-06-01",
        "content-type":      "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(ANTHROPIC_URL, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPStatusError as e:
        logger.error(f"Anthropic API HTTP error: {e.response.status_code} — {e.response.text}")
        return _fallback_response(lang, interest, funnel_stage), interest
    except Exception as e:
        logger.error(f"Anthropic API error: {e}")
        return _fallback_response(lang, interest, funnel_stage), interest

    raw = data.get("content", [{}])[0].get("text", "").strip()

    # Парсим [INTEREST:xxx] тег
    refined = interest
    match = re.search(r"\[INTEREST:(\w+)\]", raw)
    if match:
        new_interest = match.group(1)
        if new_interest in ("betting", "casino", "nodeposit", "exclusive"):
            refined = new_interest
        raw = raw[:match.start()].strip()

    return raw, refined


# ══════════════════════════════════════════════════════════════════════════════
#  Определение тона — лёгкий анализ без AI
# ══════════════════════════════════════════════════════════════════════════════
_POSITIVE_WORDS = {"yes","sí","si","taip","jā","ok","bueno","bien","super",
                   "genial","odlično","super","puiku","lieliski","👍","🔥","💎","✅"}
_NEGATIVE_WORDS = {"no","nope","ne","ne","nein","malo","tarde","perdí","propustio",
                   "praleidau","pazaudēju","😐","😑","🤔"}

def detect_tone(text: str, history: list[dict]) -> str:
    lower = text.lower()
    words = set(re.findall(r"\w+", lower))
    if words & _POSITIVE_WORDS:
        return "positive"
    if words & _NEGATIVE_WORDS:
        return "skeptical"
    if "?" in text:
        return "curious"
    return "neutral"


# ══════════════════════════════════════════════════════════════════════════════
#  Fallback если нет ANTHROPIC_API_KEY
# ══════════════════════════════════════════════════════════════════════════════
def _fallback_response(lang: str, interest: str, funnel_stage: str) -> str:
    fallbacks = {
        "es": {
            "warming":    "Entiendo. La información llega diferente cuando sabes dónde mirar. 🎯",
            "tease":      "Exacto — eso es lo que estamos viendo esta semana en el vault.",
            "cta":        "Lo que buscas está en el canal. Es gratis, sin trampa.",
            "subscribed": "Buena pregunta. Ahora mismo hay movimiento interesante en el mercado.",
        },
        "hr": {
            "warming":    "Razumijem. Informacija dolazi drugačije kad znaš gdje gledati. 🎯",
            "tease":      "Točno — to je ono što pratimo ovog tjedna u vaultu.",
            "cta":        "Ono što tražiš je u kanalu. Besplatno, bez trika.",
            "subscribed": "Dobro pitanje. Trenutno ima zanimljivih kretanja na tržištu.",
        },
        "lt": {
            "warming":    "Suprantu. Informacija ateina kitaip kai žinai kur žiūrėti. 🎯",
            "tease":      "Tiksliai — tai ką stebime šią savaitę vaulte.",
            "cta":        "Tai ko ieškai yra kanale. Nemokama, be jokių gudrybių.",
            "subscribed": "Geras klausimas. Šiuo metu rinkoje yra įdomių judėjimų.",
        },
        "lv": {
            "warming":    "Saprotu. Informācija nāk citādi kad zini kur skatīties. 🎯",
            "tease":      "Tieši tā — tas ko vērojam šonedēļ vaultā.",
            "cta":        "Tas ko meklē ir kanālā. Bezmaksas, bez trikiem.",
            "subscribed": "Labs jautājums. Šobrīd tirgū notiek interesanta kustība.",
        },
    }
    lang_fb = fallbacks.get(lang, fallbacks["es"])
    return lang_fb.get(funnel_stage, lang_fb["subscribed"])
