"""
ai_agent.py — OddsVault Bot
v4.0: web_search tool use — Valeria ищет реальные данные перед ответом.
      Agentic loop: model decides when to search, we handle tool_use → tool_result.
"""

import json
import logging
import re
import uuid
from typing import Optional

import httpx

from config import ANTHROPIC_KEY, AI_MAX_TOKENS

logger = logging.getLogger(__name__)

ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
MODEL         = "claude-haiku-4-5-20251001"

# web_search даёт реальные данные — нужно больше токенов (поиск + reasoning + ответ)
SEARCH_MAX_TOKENS = max(AI_MAX_TOKENS, 1500)

WEB_SEARCH_TOOL = {
    "type": "web_search_20250305",
    "name": "web_search",
}


# ── Search guidance в системном промпте ──────────────────────────────────────
_SEARCH_GUIDANCE = {
    "betting": (
        "You have web_search. Use it when you need REAL data to sound credible:\n"
        "- Current odds or line movements on upcoming matches (search: 'odds [match] today' or '[league] betting lines')\n"
        "- Recent results that moved a market ('Dinamo Zagreb result', 'La Liga weekend results')\n"
        "- Injury/suspension news that affects lines ('[team] injury news')\n"
        "Search once, extract ONE sharp number or fact, then reply.\n"
        "If search returns nothing useful — use your knowledge of patterns, don't invent specific scores."
    ),
    "casino": (
        "You have web_search. Use it when you need REAL data:\n"
        "- Current no-deposit bonus offers ('no deposit bonus [country] 2025')\n"
        "- RTP figures for specific slots ('[slot name] RTP')\n"
        "- Wagering requirement norms ('casino bonus wagering requirements average 2025')\n"
        "Search once, extract ONE sharp number or fact, then reply.\n"
        "If search returns nothing useful — use your knowledge, don't invent specific offers."
    ),
    "nodeposit": (
        "You have web_search. Use it to find REAL current no-deposit offers:\n"
        "- 'no deposit free spins [country] 2025'\n"
        "- 'casino no deposit bonus codes May 2025'\n"
        "Search once, extract a real offer with its wagering terms if visible, then reply.\n"
        "If search returns nothing useful — use your knowledge of typical offers."
    ),
    "exclusive": (
        "You have web_search. Use it for REAL market intelligence:\n"
        "- Arbitrage opportunities or line discrepancies ('odds comparison [event]')\n"
        "- Sharp money signals ('betting market [match] line movement')\n"
        "Search once, extract ONE sharp insight, then reply.\n"
        "If nothing useful — use your knowledge of patterns."
    ),
}


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

    search_guidance = _SEARCH_GUIDANCE.get(interest, _SEARCH_GUIDANCE["betting"])

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

Web search:
{search_guidance}

Format:
- {lang_name} only ({lang_note})
- Max 4 sentences in your final reply
- 1–2 emojis max, only when they add something
- *bold* only around key numbers
- No guaranteed profits, no named bookmakers

Interest context: {interests_context}

Funnel tags (invisible to user, go on their own line at the very END of your final reply):
  [NEXT:tease]  — when moving warming → tease
  [NEXT:cta]    — when moving tease → CTA
  [INTEREST:casino/betting/nodeposit/exclusive] — if interest clearly shifts

Current stage:
{stage_instruction}"""


# ── Agentic loop helper ───────────────────────────────────────────────────────

def _extract_text(content_blocks: list) -> str:
    """Pull all text blocks from a content list into one string."""
    return "\n".join(
        b.get("text", "") for b in content_blocks if b.get("type") == "text"
    ).strip()


async def _run_with_search(
    system: str,
    messages: list[dict],
    headers: dict,
    max_loops: int = 4,
) -> str:
    """
    Agentic loop: send request, handle tool_use (web_search) calls,
    feed tool_result back, repeat until stop_reason == 'end_turn'.
    Returns final text response.
    """
    payload = {
        "model":      MODEL,
        "max_tokens": SEARCH_MAX_TOKENS,
        "system":     system,
        "tools":      [WEB_SEARCH_TOOL],
        "messages":   messages,
    }

    async with httpx.AsyncClient(timeout=30) as client:
        for loop in range(max_loops):
            resp = await client.post(ANTHROPIC_URL, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()

            stop_reason = data.get("stop_reason")
            content     = data.get("content", [])

            # Done — return text
            if stop_reason == "end_turn":
                return _extract_text(content)

            # Model wants to search
            if stop_reason == "tool_use":
                tool_results = []
                for block in content:
                    if block.get("type") != "tool_use":
                        continue
                    tool_id   = block.get("id", str(uuid.uuid4()))
                    tool_name = block.get("name")
                    tool_input = block.get("input", {})

                    if tool_name == "web_search":
                        # The API handles the actual search — we just pass back
                        # the tool_result with the content it returned.
                        # The content blocks from the search are in block["content"]
                        # for web_search_20250305 — pass them through verbatim.
                        search_content = block.get("content", [])
                        tool_results.append({
                            "type":       "tool_result",
                            "tool_use_id": tool_id,
                            "content":    search_content,
                        })
                    else:
                        # Unknown tool — return empty result to unblock
                        tool_results.append({
                            "type":       "tool_result",
                            "tool_use_id": tool_id,
                            "content":    [],
                        })

                # Append assistant turn + tool results to messages
                payload["messages"] = payload["messages"] + [
                    {"role": "assistant", "content": content},
                    {"role": "user",      "content": tool_results},
                ]
                continue  # next loop iteration

            # Unexpected stop reason — return whatever text we have
            return _extract_text(content)

    # Max loops exceeded — return whatever was in last response
    return _extract_text(content)


# ── Public API ────────────────────────────────────────────────────────────────

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

    headers = {
        "x-api-key":         ANTHROPIC_KEY,
        "anthropic-version": "2023-06-01",
        "content-type":      "application/json",
    }

    try:
        raw = await _run_with_search(system, api_messages, headers)
    except httpx.HTTPStatusError as e:
        logger.error(f"Anthropic API HTTP error: {e.response.status_code} — {e.response.text}")
        return _fallback_response(lang, interest, funnel_stage), interest, None
    except Exception as e:
        logger.error(f"Anthropic API error: {e}")
        return _fallback_response(lang, interest, funnel_stage), interest, None

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
    """First warming message — searches for real data before opening."""
    if not ANTHROPIC_KEY:
        return _fallback_response(lang, interest, "warming")

    interests_context = {
        "betting":   "sports betting, value bets, odds analysis, La Liga, Croatian football, Baltic leagues",
        "casino":    "casino bonuses, wagering requirements, cashback, bonus hunting",
        "nodeposit": "no-deposit bonuses, free spins, low-wagering bonuses",
        "exclusive": "premium signals, arbitrage, cross-market analysis",
    }.get(interest, "sports betting and casino bonuses")

    search_guidance = _SEARCH_GUIDANCE.get(interest, _SEARCH_GUIDANCE["betting"])

    lang_name = {
        "en": "English", "es": "Spanish (Spain, casual tú)",
        "hr": "Croatian", "lt": "Lithuanian", "lv": "Latvian",
    }.get(lang, "English")

    system = (
        "You are Valeria. 26. You obsess over betting markets and casino bonuses.\n\n"
        "Send ONE opening text message. You're starting a conversation, not introducing yourself.\n\n"
        "Before writing, use web_search to find ONE real, current, specific fact tied to the user's interest "
        "(a real line, a real offer, a real movement from today or this week). "
        "That fact becomes the hook of your opener.\n\n"
        "Open with that fact. End with ONE short, specific question.\n"
        "Do NOT mention any channel, link, or group.\n\n"
        "Examples of wrong openers:\n"
        "❌ 'Hey! So glad you're interested in casino bonuses. There's a lot to cover here...'\n"
        "❌ 'Great choice! Sports betting has so many angles. What specifically are you curious about?'\n\n"
        "Examples of right openers:\n"
        "✅ 'Someone in my circle turned a *€30 no-deposit* into €340 last week. Took 4 days. The trick was slot selection — most people just pick whatever. You ever actually looked at RTP before hitting play?'\n"
        "✅ '*2.45* on the over last Saturday. Should've been 1.90. That kind of gap — you notice it or you don't.'\n\n"
        f"Web search guidance:\n{search_guidance}\n\n"
        f"Language: {lang_name} only.\n"
        "Max 4 sentences in your reply. 1 emoji max. *bold* only on numbers. No guaranteed profits. No named bookmakers.\n\n"
        f"Interest context: {interests_context}"
    )

    headers = {
        "x-api-key":         ANTHROPIC_KEY,
        "anthropic-version": "2023-06-01",
        "content-type":      "application/json",
    }

    try:
        return await _run_with_search(
            system,
            [{"role": "user", "content": "Start the conversation."}],
            headers,
        )
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
