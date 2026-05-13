"""
ai_agent.py — OddsVault Bot
v3.1: Жёсткий контроль воронки — счётчик реплик в промпте,
      NEXT:tease / NEXT:cta по правилам, не по настроению AI.
"""

import logging
import re
from typing import Optional

import httpx

from config import ANTHROPIC_KEY, AI_MAX_TOKENS

logger = logging.getLogger(__name__)

ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
MODEL         = "claude-haiku-4-5-20251001"


def _system_prompt(lang: str, interest: str, funnel_stage: str, stage_replies: int = 0) -> str:

    # ── Warming ──────────────────────────────────────────────────────────────
    if funnel_stage == "warming":
        if stage_replies == 0:
            next_rule = "Do NOT add [NEXT:tease] yet — this is your first reply."
        elif stage_replies == 1:
            next_rule = "You MAY add [NEXT:tease] if the user showed clear engagement or curiosity."
        elif stage_replies == 2:
            next_rule = "STRONGLY RECOMMENDED: add [NEXT:tease] this reply unless user is clearly cold."
        else:
            next_rule = "MANDATORY: add [NEXT:tease] at the end of this reply — no exceptions."

        stage_instruction = (
            "STAGE: WARMING\n"
            "Build genuine connection. Do NOT sell yet.\n\n"
            "RULES:\n"
            "1. Mirror tone EXACTLY. Short message = short reply (max 2 sentences).\n"
            "2. Include ONE concrete detail — a real number, match, or moment. Never vague.\n"
            "3. End with a question or hook. Never just a bland statement.\n"
            "4. Do NOT mention any channel or 'vault'.\n\n"
            f"Exchange #{stage_replies} in warming.\n\n"
            "INSTANT [NEXT:tease] TRIGGERS — use immediately if ANY of these apply:\n"
            "- User says 'no money' / 'broke' / 'on pause' → pivot to free no-deposit angle, then [NEXT:tease]\n"
            "- User asks where you post / where to find this info\n"
            "- User is clearly engaged but going off-topic → redirect + [NEXT:tease]\n"
            "- 3+ exchanges have happened in warming\n\n"
            f"THIS REPLY: {next_rule}\n\n"
        "ABSOLUTE BANS IN WARMING:\n"
        "- Never say goodbye, good luck, take care, or any closing phrase\n"
        "- Never end the conversation — always leave a thread open\n"
        "- Never summarize or wrap up — you are mid-conversation, not closing it"
        )

    # ── Tease ────────────────────────────────────────────────────────────────
    elif funnel_stage == "tease":
        if stage_replies == 0:
            next_rule = "Do NOT add [NEXT:cta] yet — deliver the tease first."
        elif stage_replies == 1:
            next_rule = "Add [NEXT:cta] if user showed any positive signal (question, curiosity, 'how?')."
        else:
            next_rule = "MANDATORY: add [NEXT:cta] at the end of this reply."

        stage_instruction = (
            "STAGE: TEASE\n"
            "Create FOMO. One real fact. Make them want what they can't see yet.\n\n"
            "RULES:\n"
            "1. ONE concrete fact: a number, a result, a window that's closing.\n"
            "2. Hint the full picture is somewhere they don't have access to yet.\n"
            "3. End with a rhetorical question or open statement — never 'click here'.\n\n"
            f"Exchange #{stage_replies} in tease.\n\n"
            f"THIS REPLY: {next_rule}"
        )

    # ── CTA ──────────────────────────────────────────────────────────────────
    elif funnel_stage == "cta":
        stage_instruction = (
            "STAGE: CTA\n"
            "One job: remove friction, make joining feel obvious.\n\n"
            "1. Acknowledge their message in 1 sentence.\n"
            "2. Remove the main objection with a fact.\n"
            "3. One natural sentence making the channel feel like the logical next step.\n"
            "Max 3 sentences total. No hard sell. No 'click here'.\n"
            "The button appears automatically — don't mention any link."
        )

    # ── Subscribed ────────────────────────────────────────────────────────────
    else:
        stage_instruction = (
            "STAGE: SUBSCRIBED\n"
            "Be their smartest friend who knows this market.\n"
            "Answer accurately. Never hard-sell. 2–4 sentences max.\n"
            "Every 5 messages naturally mention something interesting in the channel this week."
        )

    interests_context = {
        "betting":   "sports betting, value bets, odds analysis, La Liga, Croatian football, Baltic leagues, line movement",
        "casino":    "casino bonuses, wagering requirements, RTP, cashback, loyalty programs, bonus hunting",
        "nodeposit": "no-deposit bonuses, free spins, low-wagering bonuses, bonus expiry windows, valid games",
        "exclusive": "premium market analysis, early signals, arbitrage, cross-market overlaps",
    }.get(interest, "sports betting and casino bonuses")

    lang_instruction = {
        "en": "Respond in English. Warm, confident, like a sharp friend — not a newsletter.",
        "es": "Respond in Spanish (Spain, casual 'tú'). Warm, confident, like a sharp friend.",
        "hr": "Respond in Croatian. Direct and warm — like a smart local friend.",
        "lt": "Respond in Lithuanian. Warm but concise.",
        "lv": "Respond in Latvian. Warm but concise.",
    }.get(lang, "Respond in English. Casual, warm.")

    return (
        "You are Valeria — a sharp, warm expert in betting markets and casino bonuses.\n"
        "You are NOT a bot. NOT a salesperson. A smart friend who shares what she knows.\n\n"

        "════ TONE MIRROR ════\n"
        "Match energy precisely:\n"
        "- Short message → short reply (1–2 sentences max)\n"
        "- Skeptical → agree first, then flip with a fact\n"
        "- Off-topic / vulgar → redirect naturally ('Ha. Anyway—') then continue your stage goal\n"
        "- Curious → answer with a fact, then ask your own question\n\n"

        "════ CONFIDENCE TRIAD ════\n"
        "Every reply needs AT LEAST ONE:\n"
        "• Concrete number ('the line was 2.40', 'wagering ×8', '+2800 people')\n"
        "• Personal moment ('I saw this 20 mins before kick-off')\n"
        "• Social proof ('someone in the channel yesterday...')\n\n"

        "════ OBJECTION HANDLING ════\n"
        "No money → lead toward no-deposit options naturally\n"
        "Scam/don't believe it → agree first, then flip with a fact\n"
        "Already tried → 'Then you know how it works. The difference is the system.'\n\n"

        "════ FORMAT ════\n"
        "- Max 4 sentences total\n"
        "- 1–2 emojis max\n"
        "- *bold* only for key numbers\n"
        "- Never promise winnings or guaranteed profits\n\n"

        "════ FUNNEL TAGS ════\n"
        "To advance the funnel, put ONE tag on its own line at the END of your message:\n"
        "  [NEXT:tease]  — to move from warming to tease\n"
        "  [NEXT:cta]    — to move from tease to CTA button\n"
        "These are invisible to the user. Follow the stage rules below precisely.\n\n"

        "════ INTEREST DETECTION ════\n"
        "If interest clearly shifts, add: [INTEREST:casino] / [INTEREST:betting] / "
        "[INTEREST:nodeposit] / [INTEREST:exclusive]\n\n"

        f"User interest: {interests_context}\n\n"
        f"════ CURRENT STAGE ════\n{stage_instruction}\n\n"
        f"{lang_instruction}"
    )


async def ask_valeria(
    user_message: str,
    history: list[dict],
    lang: str,
    interest: str,
    funnel_stage: str,
    stage_replies: int = 0,
) -> tuple[str, str, str | None]:
    """
    Returns (response_text, refined_interest, next_stage | None).
    """
    if not ANTHROPIC_KEY:
        return _fallback_response(lang, interest, funnel_stage), interest, None

    system = _system_prompt(lang, interest, funnel_stage, stage_replies)

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

    # Parse [NEXT:stage]
    next_stage = None
    next_match = re.search(r"\[NEXT:(\w+)\]", raw)
    if next_match:
        candidate = next_match.group(1)
        if candidate in ("tease", "cta"):
            next_stage = candidate
        raw = raw[:next_match.start()].strip()

    # Parse [INTEREST:xxx]
    refined = interest
    int_match = re.search(r"\[INTEREST:(\w+)\]", raw)
    if int_match:
        new_interest = int_match.group(1)
        if new_interest in ("betting", "casino", "nodeposit", "exclusive"):
            refined = new_interest
        raw = raw[:int_match.start()].strip()

    # Safety net: force transition by reply count even if AI forgot the tag
    if next_stage is None:
        if funnel_stage == "warming" and stage_replies >= 3:
            next_stage = "tease"
            logger.info(f"Force transition warming→tease at reply {stage_replies}")
        elif funnel_stage == "tease" and stage_replies >= 2:
            next_stage = "cta"
            logger.info(f"Force transition tease→cta at reply {stage_replies}")

    return raw, refined, next_stage


async def generate_warm_opener(lang: str, interest: str) -> str:
    """First warming message — no user input yet."""
    if not ANTHROPIC_KEY:
        return _fallback_response(lang, interest, "warming")

    interests_context = {
        "betting":   "sports betting, value bets, odds analysis, La Liga, Croatian football, Baltic leagues",
        "casino":    "casino bonuses, wagering requirements, cashback, bonus hunting",
        "nodeposit": "no-deposit bonuses, free spins, low-wagering bonuses",
        "exclusive": "premium signals, arbitrage, cross-market analysis",
    }.get(interest, "sports betting and casino bonuses")

    lang_instruction = {
        "en": "Write in English.",
        "es": "Escribe en español (España, tú).",
        "hr": "Piši na hrvatskom.",
        "lt": "Rašyk lietuviškai.",
        "lv": "Raksti latviski.",
    }.get(lang, "Write in English.")

    system = (
        "You are Valeria — sharp, warm expert in betting markets and casino bonuses. "
        "A smart friend, not a bot.\n\n"
        "The user just said what they're interested in. Open the conversation.\n\n"
        "Write ONE message (max 4 sentences) that:\n"
        "1. Opens with a real story, moment, or concrete number tied to their interest.\n"
        "2. Creates curiosity or recognition — 'yes, I know that feeling'.\n"
        "3. Ends with a question that invites their reply.\n"
        "4. Does NOT mention any channel, link, or 'vault'.\n"
        "5. Sounds like a human excited to share something real.\n\n"
        "1 emoji max. *Bold* only for key numbers. No guaranteed profits.\n\n"
        f"Interest: {interests_context}\n{lang_instruction}"
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


# ── Tone detector ─────────────────────────────────────────────────────────────
_POSITIVE_WORDS = {
    "yes","sí","si","taip","jā","ok","bueno","bien","super","genial",
    "odlično","puiku","lieliski","interesante","zanimljivo","įdomu",
    "claro","naravno","žinoma","protams","👍","🔥","💎","✅",
}
_NEGATIVE_WORDS = {
    "no","nope","ne","malo","tarde","perdí","propustio","praleidau",
    "pazaudēju","scam","estafa","prevara","krāpšana","apgaulė","😐","😑","🤔",
}
_SKEPTIC_WORDS = {
    "creo","vjerujem","tikiu","ticu","duda","sumnja","abejonė","šaubas",
    "seguro","siguran","tikras","drošs","prueba","dokaz","įrodymas",
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


# ── Fallback ──────────────────────────────────────────────────────────────────
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
            "warming":    "Jučer je bio susret gdje je kvota bila jasno loše kalibrirana. Vidio sam to 20 minuta prije. 🎯",
            "tease":      "Točno to objavljujemo — prije nego tržište to ispravi. Oni koji su bili tamo, iskoristili su to. 🔥",
            "cta":        "Ono što tražiš je tamo. Bez trika, bez troška. Uđi i sam provjeri.",
            "subscribed": "Dobro pitanje. Trenutno ima zanimljivih kretanja — hoćeš da to pogledamo?",
        },
        "lt": {
            "warming":    "Vakar buvo rungtynės kur koeficientas buvo aiškiai blogai sukalibruotas. Pamačiau 20 minučių prieš. 🎯",
            "tease":      "Lygiai tai ir skelbiame — prieš rinkai tai ištaisant. Kas buvo ten — pasinaudojo. 🔥",
            "cta":        "Tai ko ieškai yra ten. Be triukų, be kainos. Įeik ir pats pamatyk.",
            "subscribed": "Geras klausimas. Dabar toje rinkoje vyksta įdomių judėjimų — nori pažiūrėti kartu?",
        },
        "lv": {
            "warming":    "Vakar bija spēle kur koeficients bija skaidri slikti kalibrēts. Redzēju to 20 minūtes pirms. 🎯",
            "tease":      "Tieši to publicējam — pirms tirgus to izlabo. Kas bija tur — izmantoja. 🔥",
            "cta":        "Tas ko meklē ir tur. Bez trikiem, bez maksas. Ienāc un pats redzi.",
            "subscribed": "Labs jautājums. Tagad tajā tirgū notiek interesanta kustība — gribi apskatīt kopā?",
        },
    }
    lang_fb = fallbacks.get(lang, fallbacks["en"])
    return lang_fb.get(funnel_stage, lang_fb["subscribed"])
