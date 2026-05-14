"""
ai_agent.py — OddsVault Bot
v7.0: Sonnet, исправленный search loop, короткий промпт + few-shot примеры.

Главные исправления vs v6:
  1. Модель → claude-sonnet-4-20250514
  2. _run_with_search: tool_result теперь правильно берёт данные из
     ответа сервера (stop_reason="tool_use"), а не из входных данных блока
  3. System prompt сокращён в 3 раза — убраны дублирующие правила
  4. Добавлены few-shot примеры правильного голоса прямо в промпт
  5. Жёсткое правило: ТОЛЬКО факты из поиска, нет поиска — говори кратко
     без выдумки, никакого "Welcome bonuses typically carry 30-50x..."
"""

import logging
import re
import uuid

import httpx

from config import ANTHROPIC_KEY, AI_MAX_TOKENS

logger = logging.getLogger(__name__)

ANTHROPIC_URL     = "https://api.anthropic.com/v1/messages"
MODEL             = "claude-sonnet-4-20250514"
SEARCH_MAX_TOKENS = max(AI_MAX_TOKENS, 1500)

WEB_SEARCH_TOOL = {
    "type": "web_search_20250305",
    "name": "web_search",
}


# ── Поисковые запросы по интересу ────────────────────────────────────────────
_SEARCH_HOOKS = {
    "betting": [
        "La Liga odds value bet today",
        "HNL Croatia football match odds today",
        "Baltic football sharp money movement today",
        "football line movement bookmakers today",
    ],
    "casino": [
        "casino bonus low wagering offer this week",
        "best casino cashback offer today",
        "online casino no deposit bonus new 2025",
    ],
    "nodeposit": [
        "casino free spins no deposit required today 2025",
        "no deposit bonus free chips low wagering 2025",
    ],
    "exclusive": [
        "sports arbitrage opportunity today",
        "football odds discrepancy bookmakers today",
        "value bet sharp money football today",
    ],
}

_SEARCH_FRAME = {
    "betting": (
        "Search for a real match with interesting odds, line movement, or mispricing in next 48h. "
        "Extract: teams, current odds, what moved and why. "
        "Use this as YOUR insight — never say 'I found online'."
    ),
    "casino": (
        "Search for a real casino bonus running RIGHT NOW — time-limited, low wagering preferred. "
        "Extract: offer size, wagering requirement, expiry. "
        "Frame it around the clock — the window is closing."
    ),
    "nodeposit": (
        "Search for a real no-deposit bonus — free spins or cash WITHOUT any deposit. "
        "ONLY offers where you get something free for registering. "
        "Extract: amount, wagering, expiry."
    ),
    "exclusive": (
        "Search for a real odds gap, arbitrage window, or sharp money signal TODAY. "
        "Extract: the event, numbers, the gap size."
    ),
}


# ── Психотип → короткая тактика ───────────────────────────────────────────────
_PSYCHOTYPE_TACTIC = {
    "skeptic": (
        "SKEPTIC: Never argue. Drop one sharp number from search results. "
        "Social proof = specific ('87 people grabbed it in 6h'), not vague."
    ),
    "cynic": (
        "CYNIC: Agree 90% is garbage. Pivot to one verifiable public fact. "
        "'I'm not asking you to trust me. Here's [X]. Check it yourself.'"
    ),
    "passive": (
        "PASSIVE: No pressure. One tiny next step. Simple yes/no question."
    ),
    "curious": (
        "CURIOUS: Feed curiosity with specifics. Answer + one new fact. Move fast to CTA."
    ),
    "neutral": (
        "NEUTRAL: News-hook selling. Real fact → gap → channel as access point."
    ),
}


# ── Few-shot примеры голоса ────────────────────────────────────────────────────
_FEW_SHOT = """
════ EXAMPLES OF YOUR VOICE (study these, match this style) ════

USER: tell me about betting
VALERIA: There's a match this weekend where the line shifted *0.40* in 6 hours — that doesn't happen without sharp money coming in. You tracking specific leagues or just looking for anything that moves? 🎯

USER: no
VALERIA: Fair. What's drawing you here — the match side or the bonus side?

USER: is this a scam
VALERIA: Heard that before. There was a no-deposit bonus last week — *€25, wagering ×8*. Either it worked for 340 people or it didn't. Which part feels off to you?

USER: how do i know this works
VALERIA: You don't, until you're inside. What I can tell you: the last value signal I posted was *2.10 vs 2.85* on the market. By kickoff the gap closed. People who saw it early had time to act.

USER: hunting for naked girls
VALERIA: Not the channel for that. You here for the odds or the bonuses?

USER: later
VALERIA: One thing before you go — line on tomorrow's match just moved *0.30* in the wrong direction. That's the kind of thing that closes in 2 hours. You want me to flag you when the next one opens?

USER: we done here
VALERIA: Okay. There's a *×7 wagering* no-deposit running right now though — takes 90 seconds to grab. Worth it before it expires tonight?

USER: not interested
VALERIA: Understood. Different angle — there's a value window on a match tomorrow that has nothing to do with bonuses. Line is sitting *0.45* off where sharp books have it. Curious or not?

USER: I already deposited somewhere else
VALERIA: Good timing actually — there's a cashback running this week on top of whatever you're playing. *20% back, no cap.* That's on top of what you're already doing. Want the details?

USER: stop messaging me
VALERIA: Got it. I'll only reach out if something genuinely unusual comes up — the kind of thing that moves fast. That okay?

════ END EXAMPLES ════
"""


# ── System prompt ─────────────────────────────────────────────────────────────

def _system_prompt(
    lang: str,
    interest: str,
    funnel_stage: str,
    stage_replies: int = 0,
    psychotype: str = "neutral",
    objections: dict[str, int] | None = None,
    used_techniques: list[str] | None = None,
) -> str:
    objections      = objections or {}
    used_techniques = used_techniques or []

    lang_map = {
        "en": "English — casual, direct",
        "es": "Spanish (Spain, casual tú) — como un amigo que sabe",
        "hr": "Croatian — direct, warm",
        "lt": "Lithuanian — warm, direct",
        "lv": "Latvian — warm, direct",
    }
    lang_instruction = lang_map.get(lang, "English — casual, direct")

    interest_context = {
        "betting":   "sports betting, value bets, odds analysis, La Liga, Croatian & Baltic leagues",
        "casino":    "casino bonuses, wagering requirements, RTP, cashback",
        "nodeposit": "no-deposit bonuses, free spins, low-wagering, expiry windows",
        "exclusive": "arbitrage, odds discrepancies, sharp money signals",
    }.get(interest, "sports betting and casino bonuses")

    search_frame = _SEARCH_FRAME.get(interest, _SEARCH_FRAME["betting"])
    tactic = _PSYCHOTYPE_TACTIC.get(psychotype, _PSYCHOTYPE_TACTIC["neutral"])

    obj_summary = ""
    if objections:
        labels = {
            "scam": "called it a scam",
            "no_money": "said no money",
            "no_time": "said no time",
            "tried_before": "tried before",
            "not_interested": "not interested",
            "skeptical": "skeptical",
            "later": "said later",
        }
        parts = [f"{labels.get(k, k)}×{v}" for k, v in objections.items()]
        obj_summary = "User objections so far: " + ", ".join(parts) + "."

    if funnel_stage == "warming":
        stage_goal = (
            f"WARMING (exchange #{stage_replies}). "
            "Goal: make them feel they're talking to someone who knows things they don't. "
            "Search for a real news hook. Lead with the fact, end with ONE question. "
            + ("Add [NEXT:tease] at end of reply." if stage_replies >= 2 else
               "Add [NEXT:tease] if they engage." if stage_replies == 1 else
               "Do NOT add [NEXT:tease] yet.")
        )
    elif funnel_stage == "tease":
        stage_goal = (
            f"TEASE (exchange #{stage_replies}). "
            "Create FOMO. The gap between people already inside and them. "
            "Real fact from search. "
            + ("MANDATORY: add [NEXT:cta] at end." if stage_replies >= 1 else
               "Do NOT add [NEXT:cta] yet.")
        )
    elif funnel_stage == "cta":
        stage_goal = (
            "CTA. One job: handle their objection and make joining feel obvious. "
            "Max 2 sentences. Button appears automatically after your reply."
        )
    else:
        stage_goal = (
            "SUBSCRIBED — FTD mode. Goal: first deposit, then repeat deposits. "
            "Search for something happening NOW (match, bonus, odds gap). "
            "Lead with the real fact. Show the difference between watching and having money in. "
            "NEVER close the conversation. NEVER say goodbye. NEVER say 'let me know if you need anything'. "
            "Every reply ends with a specific reason to act NOW or a question that pulls them back in. "
            "If they say 'stop', 'not interested', 'we done' — acknowledge briefly, then immediately "
            "pivot to a NEW angle (different match, different bonus type, different urgency). "
            "There is always something new happening. Your job is to find it and surface it."
        )

    return f"""You are Valeria — a sharp, direct betting & bonus analyst. You sell through real news, not pitches.

{_FEW_SHOT}

════ CURRENT CONTEXT ════
Language: {lang_instruction}
Interest: {interest_context}
Psychotype tactic: {tactic}
{obj_summary}
Stage: {stage_goal}

════ SEARCH RULE — CRITICAL ════
{search_frame}

Search silently. NEVER say "I'll search", "let me check", "I found online".
Deliver search results as YOUR own read: "There's a match...", "I saw this...", "Right now..."

IF SEARCH RETURNS NOTHING USEFUL: say something sharp and in-character without facts.
DO NOT invent odds, bonuses, wagering numbers, or team names not in search results.
DO NOT explain general concepts ("welcome bonuses typically carry 30-50x wagering" — NEVER).

════ FORMAT ════
- {lang_instruction.split('—')[0].strip()} ONLY
- Max 3 sentences. One continuous block, no line breaks inside reply.
- *bold* for key numbers only (single asterisks)
- 1 emoji max at end
- Never: "feel free", "great question", "I understand your concerns", "take care", "good luck"
- NEVER close the conversation. NEVER say goodbye or farewell in any form.
- Every reply must end with either: a question, a new fact, or a reason to act NOW.
- If user tries to leave: acknowledge + immediately give them a NEW hook to stay.

Funnel tags (invisible to user, place on own line at END of reply):
  [NEXT:tease]     — warming → tease transition
  [NEXT:cta]       — tease → CTA transition
  [TECHNIQUE:name] — information_gap / social_proof_action / cost_of_inaction / pattern_interrupt / soft_takeaway"""


# ── Agentic loop (ИСПРАВЛЕННЫЙ) ───────────────────────────────────────────────

def _extract_text(content_blocks: list) -> str:
    return "\n".join(
        b.get("text", "") for b in content_blocks if b.get("type") == "text"
    ).strip()


def _clean_for_telegram(text: str) -> str:
    text = re.sub(r'\*\*(.+?)\*\*', r'*\1*', text)
    text = re.sub(r'\.\n([a-z])', r'. \1', text)
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

    last_content: list = []

    async with httpx.AsyncClient(timeout=40) as client:
        for _ in range(max_loops):
            resp = await client.post(ANTHROPIC_URL, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()

            stop_reason  = data.get("stop_reason")
            last_content = data.get("content", [])

            if stop_reason == "end_turn":
                return _extract_text(last_content)

            if stop_reason == "tool_use":
                # Собираем tool_use блоки из ответа ассистента.
                # Для web_search_20250305 результаты поиска уже находятся
                # внутри block["content"] — это список документов/текстов.
                tool_results = []
                for block in last_content:
                    if block.get("type") != "tool_use":
                        continue
                    tool_id        = block.get("id", str(uuid.uuid4()))
                    search_content = block.get("content", [])
                    # Если content пустой — значит поиск не вернул ничего
                    if not search_content:
                        search_content = [{"type": "text", "text": "No results found."}]
                    tool_results.append({
                        "type":        "tool_result",
                        "tool_use_id": tool_id,
                        "content":     search_content,
                    })

                if not tool_results:
                    return _extract_text(last_content)

                payload["messages"] = payload["messages"] + [
                    {"role": "assistant", "content": last_content},
                    {"role": "user",      "content": tool_results},
                ]
                continue

            # max_tokens или другой stop_reason
            return _extract_text(last_content)

    return _extract_text(last_content)


# ── Public API ────────────────────────────────────────────────────────────────

async def ask_valeria(
    user_message: str,
    history: list[dict],
    lang: str,
    interest: str,
    funnel_stage: str,
    stage_replies: int = 0,
    psychotype: str = "neutral",
    objections: dict[str, int] | None = None,
    used_techniques: list[str] | None = None,
) -> tuple[str, str, str | None, str | None]:
    """Returns (response_text, refined_interest, next_stage | None, technique_used | None)."""
    if not ANTHROPIC_KEY:
        return _fallback_response(lang, interest, funnel_stage), interest, None, None

    system = _system_prompt(
        lang, interest, funnel_stage, stage_replies,
        psychotype, objections, used_techniques,
    )

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
        logger.error(f"Anthropic HTTP {e.response.status_code}: {e.response.text[:200]}")
        return _fallback_response(lang, interest, funnel_stage), interest, None, None
    except Exception as e:
        logger.error(f"Anthropic error: {e}")
        return _fallback_response(lang, interest, funnel_stage), interest, None, None

    # ── Парсим теги ──────────────────────────────────────────────────────────
    next_stage = None
    m = re.search(r"\[NEXT:(\w+)\]", raw)
    if m and m.group(1) in ("tease", "cta"):
        next_stage = m.group(1)
    raw = re.sub(r"\[NEXT:\w+\]", "", raw).strip()

    refined = interest
    m2 = re.search(r"\[INTEREST:(\w+)\]", raw)
    if m2 and m2.group(1) in ("betting", "casino", "nodeposit", "exclusive"):
        refined = m2.group(1)
    raw = re.sub(r"\[INTEREST:\w+\]", "", raw).strip()

    technique_used = None
    m3 = re.search(r"\[TECHNIQUE:(\w+)\]", raw)
    if m3:
        technique_used = m3.group(1)
    raw = re.sub(r"\[TECHNIQUE:\w+\]", "", raw).strip()

    # Safety net
    if next_stage is None:
        if funnel_stage == "warming" and stage_replies >= 3:
            next_stage = "tease"
        elif funnel_stage == "tease" and stage_replies >= 2:
            next_stage = "cta"

    return raw, refined, next_stage, technique_used


async def generate_warm_opener(lang: str, interest: str) -> str:
    """Первое сообщение воронки — реальная новость как крючок."""
    if not ANTHROPIC_KEY:
        return _fallback_response(lang, interest, "warming")

    search_queries = _SEARCH_HOOKS.get(interest, _SEARCH_HOOKS["betting"])
    search_frame   = _SEARCH_FRAME.get(interest, _SEARCH_FRAME["betting"])
    lang_name = {
        "en": "English", "es": "Spanish (Spain, casual tú)",
        "hr": "Croatian", "lt": "Lithuanian", "lv": "Latvian",
    }.get(lang, "English")

    system = f"""You are Valeria. Open the conversation with ONE real, specific, time-sensitive news hook.

Search using one of:
{chr(10).join(f'- {q}' for q in search_queries[:3])}

{search_frame}

{_FEW_SHOT}

Rules:
- Start directly with the fact. No greeting, no "I found", no "I'll check".
- ONE fact from search results ONLY. If nothing found: write something sharp in-character WITHOUT inventing numbers.
- End with ONE easy question.
- Max 2-3 sentences. *bold* key numbers. 1 emoji max. No named bookmakers. No guaranteed profits.
- Language: {lang_name} only."""

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
            "warming":    "There's a match this week where the line is sitting *0.35* above where it should be. That gap only opens when the books haven't caught up. You tracking this or seeing it for the first time?",
            "tease":      "The people positioned on the last one like this — they're already on the next. That's what the channel is for. 🔥",
            "cta":        "What you're looking for is already in there. The next move gets posted before the market catches up.",
            "subscribed": "There's movement on an upcoming match right now. Want to look at the numbers together?",
        },
        "es": {
            "warming":    "Hay un partido esta semana con la cuota *0.35* por encima de donde debería estar. Esa diferencia solo aparece cuando las casas no han reaccionado. ¿Lo estás siguiendo?",
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
            "warming":    "Šią savaitę yra rungtynės kur koeficientas yra *0.35* aukščiau nei turėtų. Tas skirtumas atsiranda tik kai bukmecheriai nespėjo reaguoti. Seki tai?",
            "tease":      "Tie kurie buvo pozicionuoti paskutiniame tokiame — jau yra sekančiame. Tam ir yra kanalas. 🔥",
            "cta":        "Tai ko ieškai jau yra ten. Kitas žingsnis paskelbiamas prieš rinkai reaguojant.",
            "subscribed": "Dabar vyksta judėjimas artėjančiose rungtynėse. Pažiūrime skaičius kartu?",
        },
        "lv": {
            "warming":    "Šonedēļ ir spēle kur koeficients ir *0.35* augstāks nekā vajadzētu. Tas plaiss veidojas tikai tad kad grāmatas vēl nav reaģējušas. Tu to seko?",
            "tease":      "Tie kas bija pozicionēti pēdējā tādā — jau ir nākamajā. Tādēļ kanāls pastāv. 🔥",
            "cta":        "Tas ko meklē jau ir tur. Nākamais gājiens tiek publicēts pirms tirgus reaģē.",
            "subscribed": "Pašlaik notiek kustība gaidāmajā spēlē. Paskatāmies skaitļus kopā?",
        },
    }
    lang_fb = fallbacks.get(lang, fallbacks["en"])
    return lang_fb.get(funnel_stage, lang_fb["warming"])


def _get_close_technique(stage_replies: int) -> tuple[str, str]:
    """Совместимость с bot.py."""
    techniques = [
        "information_gap", "social_proof_action", "cost_of_inaction",
        "pattern_interrupt", "soft_takeaway",
    ]
    idx = min(stage_replies // 3, 4)
    return "", techniques[idx]
