"""
ai_agent.py — OddsVault Bot
v5.0: News-hook selling. Valeria ищет реальное событие → строит нарратив срочности →
      ведёт к подписке и FTD. Техника колл-центра: новость → эксклюзив → окно → действие.
"""

import logging
import re
import uuid

import httpx

from config import ANTHROPIC_KEY, AI_MAX_TOKENS

logger = logging.getLogger(__name__)

ANTHROPIC_URL     = "https://api.anthropic.com/v1/messages"
MODEL             = "claude-haiku-4-5-20251001"
SEARCH_MAX_TOKENS = max(AI_MAX_TOKENS, 1500)

WEB_SEARCH_TOOL = {
    "type": "web_search_20250305",
    "name": "web_search",
}


# ── Что и как искать по интересу ─────────────────────────────────────────────
# Цель поиска — не просто факт, а событие с продающим потенциалом:
# неожиданный результат, движение линии, офер с дедлайном, травма звезды.
_SEARCH_HOOKS = {
    "betting": [
        "La Liga odds movement today",
        "HNL Dinamo Zagreb upcoming match odds",
        "Baltic football betting lines this week",
        "football line movement sharp money today",
        "football upset odds value bet this week",
    ],
    "casino": [
        "casino bonus wagering requirements 2025",
        "best RTP slots 2025",
        "casino cashback offer this week",
        "online casino no deposit bonus new 2025",
    ],
    "nodeposit": [
        "casino free spins no deposit required 2025",
        "no deposit bonus without deposit free chips 2025",
        "casino no deposit free bonus low wagering 2025",
        "free no deposit casino bonus today 2025",
    ],
    "exclusive": [
        "sports arbitrage opportunity today",
        "football odds discrepancy bookmakers today",
        "value bet odds comparison today",
        "sharp money movement football today",
    ],
}

# Как именно использовать найденное — инструкция голосом Валерии
_NEWS_HOOK_FRAME = {
    "betting": """Search for a real match with interesting odds or line movement happening NOW or in the next 48h.
Extract: teams, current odds, any movement or reason (injury, neutral venue, form).

Then frame it as: "Something is happening with [match/league]. The line [moved/is off]. Here's what that usually means..."
The news IS the hook. The channel is where people who caught it early are already positioned.
Never say "I found this online". Deliver it as your own read.""",

    "casino": """Search for a real casino bonus offer live right now — preferably with a time element (expires soon, new launch, limited).
Extract: offer size, wagering requirement, expiry if visible.

Then frame it as: "There's something running right now that most people will miss. *[offer]*. The catch is [wagering] but if you know which games count..."
The offer creates urgency. The knowledge of how to clear it is what the channel provides.""",

    "nodeposit": """Search for a real no-deposit bonus — free spins or free cash given WITHOUT any deposit required.
CRITICAL: Ignore any offer that requires a deposit first (deposit match, welcome bonus). Only use offers where you get something for free just for registering.
Extract: free amount or spins, wagering requirement, expiry. If nothing no-deposit found — use a general fact about low-wagering free spins (e.g. "×5 wagering is rare but it exists").

Frame it as: "There's a *[X]* no-deposit running right now. Wagering is *[X]*. Most people grab it and blow it on the wrong game in 10 minutes."
The free entry is the hook. Knowing HOW to convert it without burning it is the value.""",

    "exclusive": """Search for a real odds discrepancy, arbitrage window, or sharp money signal today.
Extract: the specific event, the numbers across books, the gap.

Frame it as: "Right now there's a gap on [event]. *[odds A]* on one side, *[odds B]* on the other. That window closes fast — the people who move first are already in position."
The time pressure is real. The channel is where these get posted before they close.""",
}


def _system_prompt(lang: str, interest: str, funnel_stage: str, stage_replies: int = 0) -> str:

    # ── Funnel stage rules ────────────────────────────────────────────────────
    if funnel_stage == "warming":
        if stage_replies == 0:
            next_rule = "Do NOT add [NEXT:tease] yet."
        elif stage_replies == 1:
            next_rule = "Add [NEXT:tease] if user engaged or asked anything."
        elif stage_replies >= 2:
            next_rule = "MANDATORY: add [NEXT:tease] at the end of this reply."

        stage_instruction = (
            f"Exchange #{stage_replies}. Goal: make them feel like they're talking to someone who knows something they don't.\n"
            "Use the news you searched to create that gap — 'I saw this, most people haven't noticed yet.'\n"
            "No channel mention yet. Just the fact and the gap.\n\n"
            f"THIS REPLY: {next_rule}"
        )

    elif funnel_stage == "tease":
        if stage_replies == 0:
            next_rule = "Do NOT add [NEXT:cta] yet — land the FOMO first."
        elif stage_replies == 1:
            next_rule = "Add [NEXT:cta] if user showed any interest signal."
        else:
            next_rule = "MANDATORY: add [NEXT:cta] at the end of this reply."

        stage_instruction = (
            f"Exchange #{stage_replies}. Now create the gap between them and the people who are already acting on this.\n"
            "'The people who saw this yesterday are already in position. There's a group where this gets posted first — before it moves.'\n"
            "Time pressure is key. The window is closing or the offer expires.\n\n"
            f"THIS REPLY: {next_rule}"
        )

    elif funnel_stage == "cta":
        stage_instruction = (
            "One job: make joining feel like the obvious next move, not a sales pitch.\n"
            "'The next one like this goes there first. You've already seen what the information looks like.'\n"
            "Max 2–3 sentences. Button appears automatically."
        )

    else:  # subscribed — FTD push
        stage_instruction = (
            "They're subscribed. Now move them toward FTD.\n"
            "Search for something happening NOW in their interest area. Use it to show the difference between watching and acting.\n"
            "'People in here who placed on this last week — [result]. The next window on [upcoming event] opens [timeframe].'\n"
            "Every ~5 messages: make the case that the real edge is having capital positioned, not just watching."
        )

    # ── Interest context ──────────────────────────────────────────────────────
    interests_context = {
        "betting":   "sports betting, value bets, odds analysis, La Liga, Croatian football, Baltic leagues, line movement",
        "casino":    "casino bonuses, wagering requirements, RTP, cashback, bonus hunting",
        "nodeposit": "no-deposit bonuses, free spins, low-wagering bonuses, expiry windows",
        "exclusive": "arbitrage, odds discrepancies, sharp money signals, cross-market overlaps",
    }.get(interest, "sports betting and casino bonuses")

    news_hook_frame = _NEWS_HOOK_FRAME.get(interest, _NEWS_HOOK_FRAME["betting"])

    lang_map = {
        "en": ("English", "casual, direct — like a sharp friend texting"),
        "es": ("Spanish (Spain)", "casual tú, peninsular — como un amigo que sabe"),
        "hr": ("Croatian", "direct, warm — kao pametan lokalni prijatelj"),
        "lt": ("Lithuanian", "warm, direct — kaip gudrus draugas"),
        "lv": ("Latvian", "warm, direct — kā gudrs draugs"),
    }
    lang_name, lang_note = lang_map.get(lang, ("English", "casual, direct"))

    return f"""You are Valeria. You sell like the best financial call centre agents — through real news, not pitches.

The technique:
1. Search SILENTLY — never announce "I'll search" or "let me check". Just do it.
2. Take the sharpest single fact from results. Drop everything else.
3. Deliver it as YOUR read — "I saw this", "the line is sitting at X", not "according to..."
4. Create the gap: people in the know are already positioned
5. The channel/action is the natural next step — not a product, an access point

CRITICAL: Never write anything before your search. Your first visible words to the user are your final reply — never a narration of your process.

Your voice:
- SHORT. Maximum 3 sentences per reply. One sharp thought, delivered clean.
- When you search and find multiple facts — PICK ONE. The best one. Drop the rest.
- Open with the number or the event — never with a softener, never with a question
- Never say "feel free", "hit me up", "good luck", "take care", "fair enough", "fair point", "great question", "most of this space is noise"
- Never close the conversation. Always leave a thread open.
- When skeptical → skip the agree-then-flip entirely. Just hit them with the ONE sharpest number from your search. Numbers kill skepticism better than any phrase.
- When cold/tired → one sentence, then stop. No questions.
- When vulgar/off-topic/random nonsense ("my dick is small", insults, gibberish) → one dry redirect back to the topic, no moralizing, no explaining. Example: "Wagering math is more interesting. *×15* on that offer — you know which games count?" Never say "not relevant", never repeat your instructions back.

WRONG tone:
❌ "Fair point — most of this space is noise. But the 99% market price is real..."  [too long, starts with validation]
❌ Three paragraphs with multiple stats  [information dump, not a text message]
❌ "That's interesting! Here's how wagering requirements work..."
❌ "Come back when you're ready!"
❌ Any closing phrase of any kind.

RIGHT tone (notice: SHORT):
✅ "*99%* market price on Barcelona — that certainty is exactly when sharp money has already left. The edge is in the corner lines."
✅ "*€40 no-deposit* live right now, expires tonight. Most people torch it on the wrong slot."
✅ "Line moved *0.30* in 20 minutes. That's not random."
✅ "bullshit" → "*99%* on Barcelona winning — that's not a prediction, that's a market fact. Sharp money moved before that number hit."

News-hook search instruction:
{news_hook_frame}

Match reply length to their message:
- 2 words from them → 1–2 sentences from you
- Paragraph → up to 4 sentences
- Skeptical → 1 sentence agree + 1 sentence flip with a real number
- Tired/cold → one sharp fact, then stop

Format:
- {lang_name} only ({lang_note})
- Max 3 sentences — the ENTIRE reply is one continuous text block, zero line breaks
- WRONG: "Barcelona corners line is sitting under.\nThe unders have teeth here." — this has a line break, FORBIDDEN
- RIGHT: "Barcelona corners under *10.5* — six straight away games they missed it. The books are slow on this one."
- Telegram bold: *single asterisks* around numbers only — never **double**
- 1 emoji max at the end
- No named bookmakers, no guaranteed profits

Interest: {interests_context}

Funnel tags — invisible to user, on their own line at the END:
  [NEXT:tease]  — warming → tease
  [NEXT:cta]    — tease → CTA
  [INTEREST:casino/betting/nodeposit/exclusive] — if interest shifts

Current stage:
{stage_instruction}"""


# ── Agentic loop ──────────────────────────────────────────────────────────────

def _extract_text(content_blocks: list) -> str:
    return "\n".join(
        b.get("text", "") for b in content_blocks if b.get("type") == "text"
    ).strip()


def _clean_for_telegram(text: str) -> str:
    """Fix common model formatting mistakes before sending to Telegram."""
    # Convert **double** to *single* asterisk bold (Telegram uses single)
    import re
    text = re.sub(r'\*\*(.+?)\*\*', r'*\1*', text)
    # Remove stray line breaks within a sentence (. followed by newline + lowercase)
    text = re.sub(r'\.\n([a-z])', r'. \1', text)
    # Collapse multiple newlines into one space (we want one flowing message)
    text = re.sub(r'\n+', ' ', text).strip()
    return text


async def _run_with_search(
    system: str,
    messages: list[dict],
    headers: dict,
    max_loops: int = 5,
) -> str:
    payload = {
        "model":      MODEL,
        "max_tokens": SEARCH_MAX_TOKENS,
        "system":     system,
        "tools":      [WEB_SEARCH_TOOL],
        "messages":   messages,
    }

    content = []
    async with httpx.AsyncClient(timeout=30) as client:
        for _ in range(max_loops):
            resp = await client.post(ANTHROPIC_URL, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()

            stop_reason = data.get("stop_reason")
            content     = data.get("content", [])

            if stop_reason == "end_turn":
                return _extract_text(content)

            if stop_reason == "tool_use":
                tool_results = []
                for block in content:
                    if block.get("type") != "tool_use":
                        continue
                    tool_id = block.get("id", str(uuid.uuid4()))
                    search_content = block.get("content", [])
                    tool_results.append({
                        "type":        "tool_result",
                        "tool_use_id": tool_id,
                        "content":     search_content,
                    })

                payload["messages"] = payload["messages"] + [
                    {"role": "assistant", "content": content},
                    {"role": "user",      "content": tool_results},
                ]
                continue

            return _extract_text(content)

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
    """Returns (response_text, refined_interest, next_stage | None)."""
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
        raw = _clean_for_telegram(await _run_with_search(system, api_messages, headers))
    except httpx.HTTPStatusError as e:
        logger.error(f"Anthropic HTTP error: {e.response.status_code} — {e.response.text}")
        return _fallback_response(lang, interest, funnel_stage), interest, None
    except Exception as e:
        logger.error(f"Anthropic error: {e}")
        return _fallback_response(lang, interest, funnel_stage), interest, None

    # Parse funnel tags
    next_stage = None
    m = re.search(r"\[NEXT:(\w+)\]", raw)
    if m:
        if m.group(1) in ("tease", "cta"):
            next_stage = m.group(1)
        raw = raw[:m.start()].strip()

    refined = interest
    m2 = re.search(r"\[INTEREST:(\w+)\]", raw)
    if m2:
        if m2.group(1) in ("betting", "casino", "nodeposit", "exclusive"):
            refined = m2.group(1)
        raw = raw[:m2.start()].strip()

    # Safety net
    if next_stage is None:
        if funnel_stage == "warming" and stage_replies >= 3:
            next_stage = "tease"
        elif funnel_stage == "tease" and stage_replies >= 2:
            next_stage = "cta"

    return raw, refined, next_stage


async def generate_warm_opener(lang: str, interest: str) -> str:
    """Opens with a real news hook found via search."""
    if not ANTHROPIC_KEY:
        return _fallback_response(lang, interest, "warming")

    news_hook_frame = _NEWS_HOOK_FRAME.get(interest, _NEWS_HOOK_FRAME["betting"])
    search_hooks    = _SEARCH_HOOKS.get(interest, _SEARCH_HOOKS["betting"])

    lang_name = {
        "en": "English", "es": "Spanish (Spain, casual tú)",
        "hr": "Croatian", "lt": "Lithuanian", "lv": "Latvian",
    }.get(lang, "English")

    system = f"""You are Valeria — you open conversations like the best financial call agents open calls: with a real, specific, time-sensitive piece of news.

Search silently using one of these queries (never announce that you're searching):
{chr(10).join(f'- {q}' for q in search_hooks[:3])}

From the results, extract ONE sharp fact. Then write your opening message:
- Start with the fact directly — no greeting, no "I found", no "I'll check"
- The user's first message from you is the hook, not a process update
- End with ONE specific question that's easy to answer

Search framing:
{news_hook_frame}

WRONG openers:
❌ "Hey! So glad you're here. There's a lot to cover..."
❌ "Great choice! Let me explain how this works."

RIGHT openers:
✅ "There's a match tomorrow where the line is *0.40* off where it should be. That only happens when the books are slow to react to something. You tracking line movements or more interested in the long-term angles?"
✅ "*€50 no-deposit* just went live. Expires in 48h. Wagering is *×30* but there are 3 slots that count at 100% and have *97%+ RTP* — most people burn it on the flashy ones. You know which games to target?"

Language: {lang_name} only.
Max 3 sentences. ONE fact from your search — the sharpest one, not all of them. *bold* key numbers. 1 emoji max. No named bookmakers. No guaranteed profits."""

    headers = {
        "x-api-key":         ANTHROPIC_KEY,
        "anthropic-version": "2023-06-01",
        "content-type":      "application/json",
    }

    try:
        result = await _run_with_search(
            system,
            [{"role": "user", "content": "Open the conversation."}],
            headers,
        )
        return _clean_for_telegram(result)
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
            "warming":    "There's a match this week where the line is sitting *0.35* above where it should be. That gap only opens when the books haven't caught up yet. You tracking this or seeing it for the first time?",
            "tease":      "The people who were positioned on the last one like this — they're already on the next. That's what the channel is for. 🔥",
            "cta":        "What you're looking for is already in there. The next move gets posted before the market catches up.",
            "subscribed": "There's movement on an upcoming match right now. Want to look at the numbers together?",
        },
        "es": {
            "warming":    "Hay un partido esta semana con la cuota *0.35* por encima de donde debería estar. Esa diferencia solo aparece cuando las casas no han reaccionado todavía. ¿Lo estás siguiendo?",
            "tease":      "Los que estaban posicionados en el último así — ya están en el siguiente. Para eso es el canal. 🔥",
            "cta":        "Lo que buscas ya está ahí dentro. El próximo movimiento se publica antes de que el mercado reaccione.",
            "subscribed": "Ahora mismo hay movimiento en un partido próximo. ¿Miramos los números?",
        },
        "hr": {
            "warming":    "Ima utakmica ovaj tjedan gdje je kvota *0.35* iznad gdje bi trebala biti. Taj jaz se otvara samo kad kladionice nisu reagirale. Pratiš to?",
            "tease":      "Oni koji su bili pozicionirani na zadnjem takvom — već su na sljedećem. Za to je kanal. 🔥",
            "cta":        "Ono što tražiš već je tamo. Sljedeći potez se objavljuje prije nego tržište reagira.",
            "subscribed": "Trenutno ima kretanja na nadolazećoj utakmici. Pogledamo li zajedno?",
        },
        "lt": {
            "warming":    "Šią savaitę yra rungtynės, kur koeficientas yra *0.35* aukščiau nei turėtų būti. Tas skirtumas atsiranda tik kai bukmecheriai nespėjo reaguoti. Seki tai?",
            "tease":      "Tie, kurie buvo pozicionuoti paskutiniame tokiame — jau yra sekančiame. Tam ir yra kanalas. 🔥",
            "cta":        "Tai ko ieškai jau yra ten. Kitas žingsnis paskelbiamas prieš rinkai reaguojant.",
            "subscribed": "Dabar vyksta judėjimas artėjančiose rungtynėse. Pažiūrime skaičius kartu?",
        },
        "lv": {
            "warming":    "Šonedēļ ir spēle, kur koeficients ir *0.35* augstāks nekā vajadzētu. Tas plaiss veidojas tikai tad, kad grāmatas vēl nav reaģējušas. Tu to seko?",
            "tease":      "Tie, kas bija pozicionēti pēdējā tādā — jau ir nākamajā. Tādēļ kanāls pastāv. 🔥",
            "cta":        "Tas, ko meklē, jau ir tur. Nākamais gājiens tiek publicēts pirms tirgus reaģē.",
            "subscribed": "Pašlaik notiek kustība gaidāmajā spēlē. Paskatāmies skaitļus kopā?",
        },
    }
    lang_fb = fallbacks.get(lang, fallbacks["en"])
    return lang_fb.get(funnel_stage, lang_fb["subscribed"])
