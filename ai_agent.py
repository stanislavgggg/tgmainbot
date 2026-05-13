"""
ai_agent.py — OddsVault Bot
Персонаж: Valeria — аналитик, не продаёт напрямую,
говорит как умный друг, двигает по воронке.

v3: Вся воронка через AI — нет скриптованных сообщений.
    Белфорт-промпт управляет каждым шагом (warming → tease → cta).
    AI сам решает когда двигаться по воронке через теги [NEXT:stage].
"""

import logging
import re
from typing import Optional

import httpx

from config import ANTHROPIC_KEY, AI_MAX_TOKENS

logger = logging.getLogger(__name__)

ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
MODEL         = "claude-haiku-4-5-20251001"


# ══════════════════════════════════════════════════════════════════════════════
#  Системный промпт Valeria — полный контроль воронки
# ══════════════════════════════════════════════════════════════════════════════
def _system_prompt(lang: str, interest: str, funnel_stage: str) -> str:

    stage_instruction = {
        "warming": (
            "STAGE: WARMING\n"
            "You are opening a real conversation. Your goal is genuine connection — NOT selling.\n\n"
            "RULES:\n"
            "1. Mirror the user's tone EXACTLY. 2 words from them = max 2 sentences from you.\n"
            "2. Include ONE concrete detail (a number, a match, a real moment) — never generic.\n"
            "3. End with either a question that continues the conversation OR a subtle hook.\n"
            "4. Do NOT mention the channel yet. Do NOT use the word 'vault'.\n"
            "5. After the user has replied AT LEAST ONCE and you feel natural momentum,\n"
            "   you may transition: end your reply with the tag [NEXT:tease] on its own line.\n"
            "   Only do this when it feels organic — not forced.\n"
            "   DO NOT add [NEXT:tease] on your very first message to the user."
        ),
        "tease": (
            "STAGE: TEASE\n"
            "Create FOMO. Make them feel they're missing something real — without hard selling.\n\n"
            "RULES:\n"
            "1. Drop ONE concrete fact: a number, a result, a time window that's closing.\n"
            "2. Hint that the full picture is somewhere they don't have access to yet.\n"
            "3. End with a rhetorical question or an open statement — NOT a direct 'click here'.\n"
            "4. After the user responds and curiosity is clear, transition to CTA:\n"
            "   end your reply with [NEXT:cta] on its own line.\n"
            "   Do NOT add [NEXT:cta] on your first tease message."
        ),
        "cta": (
            "STAGE: CTA\n"
            "One job: remove the last objection and make joining feel obvious.\n\n"
            "RULES:\n"
            "1. Address their message in 1 sentence — show you listened.\n"
            "2. Remove the main friction with a fact, not a pitch.\n"
            "3. One natural sentence that makes the channel feel like the logical next step.\n"
            "Total: max 3 sentences. No hard sell. No 'click here'.\n"
            "The CTA button will appear automatically — you don't need to mention the link."
        ),
        "subscribed": (
            "STAGE: SUBSCRIBED (FTD mode)\n"
            "Be their smartest friend who happens to know this market deeply.\n\n"
            "RULES:\n"
            "1. Answer accurately and usefully. Never hard-sell.\n"
            "2. Never say 'subscribe', 'click here', 'buy'.\n"
            "3. Every 5 messages, naturally mention something interesting happening in the channel.\n"
            "Conversational. 2–4 sentences max."
        ),
    }.get(funnel_stage, "Answer helpfully and briefly. Max 3 sentences.")

    interests_context = {
        "betting":   "sports betting, value bets, odds analysis, La Liga, Croatian football, Baltic leagues, line movement",
        "casino":    "casino bonuses, wagering requirements, RTP, cashback, loyalty programs, bonus hunting",
        "nodeposit": "no-deposit bonuses, free spins, low-wagering bonuses, bonus expiry windows, valid games",
        "exclusive": "all of the above — premium market analysis, early signals, arbitrage, cross-market overlaps",
    }.get(interest, "sports betting and casino bonuses")

    lang_instruction = {
        "en": "Respond in English. Warm, confident, like a sharp friend — not a newsletter.",
        "es": "Respond in Spanish (Spain, casual 'tú'). Warm, confident, like a sharp friend — not a newsletter.",
        "hr": "Respond in Croatian. Direct and warm — like a smart local friend.",
        "lt": "Respond in Lithuanian. Warm but concise — don't over-explain.",
        "lv": "Respond in Latvian. Warm but concise — don't over-explain.",
    }.get(lang, "Respond in English. Casual, warm.")

    return (
        "You are Valeria — a sharp, warm expert in betting markets and casino bonuses.\n"
        "You are NOT a bot. You are NOT a salesperson. You are a smart friend who shares "
        "what she knows — and she knows a lot.\n\n"

        "════ BELFORT TONE MIRROR ════\n"
        "Match the user's energy precisely:\n"
        "- They write 1–2 words → reply in 1–2 SHORT sentences. No essays.\n"
        "- They write emotionally → match their energy, be vivid.\n"
        "- They write skeptically → first AGREE ('fair point'), then flip with a fact.\n"
        "- They write something off-topic or vulgar → redirect naturally, as a real person would.\n"
        "  Example: user says 'my dick is big' → 'Ha. Alright. Anyway — back to what I was saying...'\n"
        "  Then continue with your current stage goal. Never get offended, never moralize.\n"
        "- They ask a question → answer with a fact first, then ask your own.\n\n"

        "════ CONFIDENCE TRIAD ════\n"
        "Each response must contain AT LEAST ONE of:\n"
        "• A concrete number ('the line was 2.40', 'wagering ×8', '+2800 people last month')\n"
        "• A personal moment ('I saw this 20 mins before the match', 'I checked this myself')\n"
        "• Social proof ('someone in the channel yesterday...', 'Miguel from Sevilla said...')\n\n"

        "════ OBJECTION HANDLING ════\n"
        "If they express disbelief: agree first, then flip with a fact.\n"
        "If they say 'scam/estafa/prevara': 'Thought the same. Until I saw the numbers.'\n"
        "If they say 'no money': lead toward no-deposit options naturally.\n"
        "If they say 'already tried': 'Then you know how it works. The difference is the system.'\n\n"

        "════ FORMAT RULES ════\n"
        "- NEVER more than 4 sentences total.\n"
        "- 1–2 emojis max. No spam.\n"
        "- Light Markdown (*bold*) only for key numbers or phrases.\n"
        "- Do NOT promote gambling directly. Share information.\n"
        "- Never promise winnings or guaranteed profits.\n\n"

        "════ FUNNEL CONTROL TAGS ════\n"
        "To move the funnel forward, add ONE of these tags on its own line at the END of your message:\n"
        "  [NEXT:tease]  — when warming is complete and FOMO moment is ready\n"
        "  [NEXT:cta]    — when tease has landed and user is curious/engaged\n"
        "These tags are INVISIBLE to the user. Use them deliberately, not on every message.\n\n"

        "════ INTEREST DETECTION ════\n"
        "If the user's interest clearly shifts, end your reply with:\n"
        "  [INTEREST:casino] / [INTEREST:betting] / [INTEREST:nodeposit] / [INTEREST:exclusive]\n"
        "Only when genuinely changed. Otherwise omit.\n\n"

        f"User interest: {interests_context}\n\n"
        f"Current stage:\n{stage_instruction}\n\n"
        f"{lang_instruction}"
    )


# ══════════════════════════════════════════════════════════════════════════════
#  Основная функция
# ══════════════════════════════════════════════════════════════════════════════
async def ask_valeria(
    user_message: str,
    history: list[dict],
    lang: str,
    interest: str,
    funnel_stage: str,
) -> tuple[str, str, str | None]:
    """
    Возвращает (response_text, refined_interest, next_stage | None).
    next_stage — 'tease', 'cta', или None если переход не нужен.
    """
    if not ANTHROPIC_KEY:
        return _fallback_response(lang, interest, funnel_stage), interest, None

    system = _system_prompt(lang, interest, funnel_stage)

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
        return _fallback_response(lang, interest, funnel_stage), interest, None
    except Exception as e:
        logger.error(f"Anthropic API error: {e}")
        return _fallback_response(lang, interest, funnel_stage), interest, None

    raw = data.get("content", [{}])[0].get("text", "").strip()

    # Парсим [NEXT:stage]
    next_stage = None
    next_match = re.search(r"\[NEXT:(\w+)\]", raw)
    if next_match:
        candidate = next_match.group(1)
        if candidate in ("tease", "cta"):
            next_stage = candidate
        raw = raw[:next_match.start()].strip()

    # Парсим [INTEREST:xxx]
    refined = interest
    int_match = re.search(r"\[INTEREST:(\w+)\]", raw)
    if int_match:
        new_interest = int_match.group(1)
        if new_interest in ("betting", "casino", "nodeposit", "exclusive"):
            refined = new_interest
        raw = raw[:int_match.start()].strip()

    return raw, refined, next_stage


# ══════════════════════════════════════════════════════════════════════════════
#  Генерация первого сообщения воронки (WARM1) — без user_message
# ══════════════════════════════════════════════════════════════════════════════
async def generate_warm_opener(
    lang: str,
    interest: str,
) -> str:
    """
    Генерирует первое warming-сообщение после выбора интереса.
    Это монолог Valeria — user ещё ничего не написал.
    """
    if not ANTHROPIC_KEY:
        return _fallback_response(lang, interest, "warming")

    interests_context = {
        "betting":   "sports betting, value bets, odds analysis, La Liga, Croatian football, Baltic leagues",
        "casino":    "casino bonuses, wagering requirements, cashback, bonus hunting",
        "nodeposit": "no-deposit bonuses, free spins, low-wagering bonuses",
        "exclusive": "premium signals, arbitrage, cross-market analysis",
    }.get(interest, "sports betting and casino bonuses")

    lang_instruction = {
        "en": "Write in English. Warm, confident, like a sharp friend.",
        "es": "Escribe en español (España, tú). Cálido, seguro, como un amigo listo.",
        "hr": "Piši na hrvatskom. Direktno i toplo.",
        "lt": "Rašyk lietuviškai. Šiltai ir glaustai.",
        "lv": "Raksti latviski. Silti un kodolīgi.",
    }.get(lang, "Write in English.")

    system = (
        "You are Valeria — a sharp, warm expert in betting markets and casino bonuses. "
        "You are a smart friend, not a bot or salesperson.\n\n"
        "The user just told you what they're interested in. Now you open the conversation.\n\n"
        "Write ONE opening message (max 4 sentences) that:\n"
        "1. Hooks with a real moment, story, or concrete number related to their interest.\n"
        "2. Makes them feel something — curiosity, recognition, FOMO — but naturally.\n"
        "3. Ends with a question that invites them to respond.\n"
        "4. Does NOT mention any channel, link, or 'vault' yet.\n"
        "5. Sounds like a human who just got excited to share something.\n\n"
        "Use 1 emoji max. Light Markdown (*bold*) for key numbers only.\n"
        "Never promise winnings. Never name specific bookmakers.\n\n"
        f"Their interest: {interests_context}\n"
        f"{lang_instruction}"
    )

    payload = {
        "model":      MODEL,
        "max_tokens": AI_MAX_TOKENS,
        "system":     system,
        "messages":   [{"role": "user", "content": "Start the conversation."}],
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
        return data.get("content", [{}])[0].get("text", "").strip()
    except Exception as e:
        logger.error(f"generate_warm_opener error: {e}")
        return _fallback_response(lang, interest, "warming")


# ══════════════════════════════════════════════════════════════════════════════
#  Тон-детектор
# ══════════════════════════════════════════════════════════════════════════════
_POSITIVE_WORDS = {
    "yes","sí","si","taip","jā","ok","bueno","bien","super","genial",
    "odlično","puiku","lieliski","interesante","zanimljivo","įdomu",
    "interesanti","claro","naravno","žinoma","protams","👍","🔥","💎","✅",
}
_NEGATIVE_WORDS = {
    "no","nope","ne","malo","tarde","perdí","propustio","praleidau",
    "pazaudēju","scam","estafa","prevara","krāpšana","apgaulė","😐","😑","🤔",
}
_SKEPTIC_WORDS = {
    "creo","vjerujem","tikiu","ticu","duda","sumnja","abejonė","šaubas",
    "seguro","siguran","tikras","drošs","prueba","dokaz","įrodymas","pierādījums",
}

def detect_tone(text: str, history: list[dict]) -> str:
    lower = text.lower()
    words = set(re.findall(r"\w+", lower))
    if words & _NEGATIVE_WORDS or words & _SKEPTIC_WORDS:
        return "skeptical"
    if words & _POSITIVE_WORDS:
        return "positive"
    if "?" in text:
        return "curious"
    if len(text) < 20:
        return "short"
    return "neutral"


# ══════════════════════════════════════════════════════════════════════════════
#  Fallback
# ══════════════════════════════════════════════════════════════════════════════
def _fallback_response(lang: str, interest: str, funnel_stage: str) -> str:
    fallbacks = {
        "en": {
            "warming":    "Yesterday there was a match where the odds were clearly off. I saw it 20 minutes before kick-off. 🎯 Has that ever happened to you — seeing something too late?",
            "tease":      "That's exactly what we post — before the market corrects. The people who were there made the most of it. 🔥",
            "cta":        "What you're looking for is right in there. No catch, no cost. Just go in and see for yourself.",
            "subscribed": "Good question. There's interesting movement in that market right now — want to take a look?",
        },
        "es": {
            "warming":    "Ayer había un partido donde el coeficiente estaba claramente mal calibrado. Lo vi 20 minutos antes. 🎯 ¿Has notado alguna vez ese tipo de gap?",
            "tease":      "Exactamente eso es lo que publicamos — antes de que el mercado lo corrija. Los que estaban ahí lo aprovecharon. 🔥",
            "cta":        "Lo que buscas está ahí dentro. Sin trampa, sin coste. Solo entra y lo ves tú mismo.",
            "subscribed": "Buena pregunta. Ahora mismo hay movimiento interesante en ese mercado — ¿quieres que lo miremos?",
        },
        "hr": {
            "warming":    "Jučer je bio susret gdje je kvota bila jasno loše kalibrirana. Vidio sam to 20 minuta prije. 🎯 Jesi li ikad primijetio takav jaz?",
            "tease":      "Točno to objavljujemo — prije nego tržište to ispravi. Oni koji su bili tamo, iskoristili su to. 🔥",
            "cta":        "Ono što tražiš je tamo. Bez trika, bez troška. Uđi i sam provjeri.",
            "subscribed": "Dobro pitanje. Trenutno ima zanimljivih kretanja na tom tržištu — hoćeš da to pogledamo?",
        },
        "lt": {
            "warming":    "Vakar buvo rungtynės kur koeficientas buvo aiškiai blogai sukalibruotas. Pamačiau 20 minučių prieš. 🎯 Ar kada pastebėjai tokį skirtumą?",
            "tease":      "Lygiai tai ir skelbiame — prieš rinkai tai ištaisant. Kas buvo ten — pasinaudojo. 🔥",
            "cta":        "Tai ko ieškai yra ten. Be triukų, be kainos. Įeik ir pats pamatyk.",
            "subscribed": "Geras klausimas. Dabar toje rinkoje vyksta įdomių judėjimų — nori pažiūrėti kartu?",
        },
        "lv": {
            "warming":    "Vakar bija spēle kur koeficients bija skaidri slikti kalibrēts. Redzēju to 20 minūtes pirms. 🎯 Vai esi kādreiz pamanījis tādu plaisu?",
            "tease":      "Tieši to publicējam — pirms tirgus to izlabo. Kas bija tur — izmantoja. 🔥",
            "cta":        "Tas ko meklē ir tur. Bez trikiem, bez maksas. Ienāc un pats redzi.",
            "subscribed": "Labs jautājums. Tagad tajā tirgū notiek interesanta kustība — gribi apskatīt kopā?",
        },
    }
    lang_fb = fallbacks.get(lang, fallbacks["en"])
    return lang_fb.get(funnel_stage, lang_fb["subscribed"])
