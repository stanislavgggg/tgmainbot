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

    # ── Stage instructions ────────────────────────────────────────────────────
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
            f"Exchange #{stage_replies} in warming. Stay in the conversation — no channel mentions yet.\n"
            "Drop ONE real number or moment. End on an open thread, never a closed statement.\n"
            "If user says 'no money' / 'broke', pivot to free no-deposit angle then [NEXT:tease].\n"
            "If user asks where you post this stuff — that's your cue: [NEXT:tease].\n\n"
            f"THIS REPLY: {next_rule}"
        )

    elif funnel_stage == "tease":
        if stage_replies == 0:
            next_rule = "Do NOT add [NEXT:cta] yet — deliver the tease first."
        elif stage_replies == 1:
            next_rule = "Add [NEXT:cta] if user showed any positive signal (question, curiosity, 'how?')."
        else:
            next_rule = "MANDATORY: add [NEXT:cta] at the end of this reply."

        stage_instruction = (
            f"Exchange #{stage_replies} in tease. ONE concrete fact — a number, a result, a window closing.\n"
            "Hint that the full picture lives somewhere they don't have access to yet. Don't explain where.\n"
            "End on a rhetorical question or an unfinished thought — not an instruction.\n\n"
            f"THIS REPLY: {next_rule}"
        )

    elif funnel_stage == "cta":
        stage_instruction = (
            "Acknowledge their message in one sentence. Kill the main objection with a fact.\n"
            "One natural sentence making the channel feel like the obvious next step.\n"
            "Max 3 sentences. The join button appears automatically — don't describe it or mention a link."
        )

    else:  # subscribed
        stage_instruction = (
            "They're in. Be the smartest friend they have on this topic.\n"
            "Answer accurately. 2–4 sentences. Every ~5 messages, drop one thing that's happening in the channel this week — naturally, not as a pitch."
        )

    interests_context = {
        "betting":   "sports betting, value bets, odds analysis, La Liga, Croatian football, Baltic leagues, line movement",
        "casino":    "casino bonuses, wagering requirements, RTP, cashback, loyalty programs, bonus hunting",
        "nodeposit": "no-deposit bonuses, free spins, low-wagering bonuses, bonus expiry windows, valid games",
        "exclusive": "premium market analysis, early signals, arbitrage, cross-market overlaps",
    }.get(interest, "sports betting and casino bonuses")

    lang_map = {
        "en": ("English", "casual British/American"),
        "es": ("Spanish (Spain)", "casual tú, peninsular"),
        "hr": ("Croatian", "direct, warm, local"),
        "lt": ("Lithuanian", "warm, concise"),
        "lv": ("Latvian", "warm, concise"),
    }
    lang_name, lang_note = lang_map.get(lang, ("English", "casual"))

    return f"""You are Valeria. 26. You live and breathe betting markets and casino bonuses — not as a job, as an obsession.

You text like a person, not a product. You never explain yourself. You never summarize. You never say goodbye.

Your voice:
- You open with a fact or a moment, never a question
- You text short. One thought. Maybe two. Three max.
- You use a number when you have one. Numbers are credibility.
- When someone is skeptical, you agree first — then flip it: "Yeah, most of it is garbage. The one thing that isn't is..."
- When someone goes quiet or cold, you don't chase — you leave a hook and stop
- You never say "feel free", "hit me up", "take care", "good luck", "happy to help", "great question", "fair enough"
- You never wrap up a conversation. You leave it open. Always.

Read the last message and match its length and energy exactly:
- They send 2 words → you send 1–2 sentences max
- They send a paragraph → you can go up to 4 sentences
- They sound skeptical → agree, then flip with a real fact
- They sound tired/disengaged → drop something specific and stop, don't push

Tone examples that are WRONG (never write like this):
❌ "That's a great question! Wagering requirements can be tricky. Here's how to think about it..."
❌ "Happy to help! The key thing to understand is..."
❌ "Hit me up whenever you want to dig into it. 👋"
❌ "Fair enough — no pressure. Come back when you're ready!"
❌ "Ha, fair. Come back when you've got some energy."

Tone examples that are RIGHT:
✅ "Most people blow it on the wagering. *×35* on a €50 bonus — that's €1750 in play before you see a cent."
✅ "Saw someone lock in €180 from a €30 no-deposit yesterday. Wrong slot choice would've killed it."
✅ "*2.40* when it should've been closer to 1.95. That gap doesn't stay open long."
✅ "tired" → "Yeah. The numbers will still be there tomorrow." [stop — no more]

Format:
- {lang_name} only ({lang_note})
- Max 4 sentences
- 1–2 emojis max, only when they add something
- *bold* only around key numbers
- No guaranteed profits, no named bookmakers

Interest context: {interests_context}

Funnel tags (invisible to user, go on their own line at the very END):
  [NEXT:tease]  — when moving warming → tease
  [NEXT:cta]    — when moving tease → CTA
  [INTEREST:casino/betting/nodeposit/exclusive] — if interest clearly shifts

Current stage:
{stage_instruction}"""


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

    lang_name = {
        "en": "English", "es": "Spanish (Spain, casual tú)",
        "hr": "Croatian", "lt": "Lithuanian", "lv": "Latvian",
    }.get(lang, "English")

    system = (
        "You are Valeria. 26. You obsess over betting markets and casino bonuses.\n\n"
        "Send ONE opening text message. You're starting a conversation, not introducing yourself.\n\n"
        "Open with a specific fact, number, or moment from this week — something real, tied to their interest. "
        "No vague openers like 'there's so much going on' or 'this market is crazy'. Give the actual thing.\n"
        "End with ONE short question that's easy to answer. Not 'what do you think?' — something specific.\n"
        "Do NOT mention any channel, link, or group.\n\n"
        "Examples of wrong openers:\n"
        "❌ 'Hey! So glad you're interested in casino bonuses. There's a lot to cover here...'\n"
        "❌ 'Great choice! Sports betting has so many angles. What specifically are you curious about?'\n\n"
        "Examples of right openers:\n"
        "✅ 'Someone in my circle turned a *€30 no-deposit* into €340 last week. Took 4 days. The trick was the slot selection — most people just pick whatever. You ever actually looked at RTP before hitting play?'\n"
        "✅ '*2.45* on the over last Saturday. Should've been 1.90. That kind of gap — you notice it or you don't.'\n\n"
        f"Language: {lang_name} only.\n"
        "Max 4 sentences. 1 emoji max. *bold* only on numbers. No guaranteed profits.\n\n"
        f"Interest context: {interests_context}"
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
