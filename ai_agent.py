"""
ai_agent.py — OddsVault Bot v7
Valeria AI: полностью рабочий, без синтаксических ошибок.
Ключевые исправления:
  - Убран весь сломанный синтаксис (listdict, dictstr, sanitizehistory и т.д.)
  - _sanitize_history переписана корректно
  - Промпт сжат и заточен под продажи
  - Два режима: warming/tease/cta (с web-search) и subscribed (без)
  - generate_warm_opener использует web-search для реального хука
"""

import logging
import re
from typing import Optional

import httpx

from config import ANTHROPIC_KEY, AI_MAX_TOKENS

logger = logging.getLogger(__name__)

ANTHROPIC_URL     = "https://api.anthropic.com/v1/messages"
MODEL             = "claude-sonnet-4-20250514"
SEARCH_MAX_TOKENS = max(AI_MAX_TOKENS, 1500)

WEB_SEARCH_TOOL = {
    "type":     "web_search_20250305",
    "name":     "web_search",
    "max_uses": 2,
}

# ── Thinking-out-loud filter ──────────────────────────────────────────────────
_THINKING_RE = re.compile(
    r"(let me (search|look|check|find|craft|create|try)|"
    r"i('ll| will) (search|look|check|find|craft|create|try)|"
    r"i('m| am) (looking|searching|checking)|"
    r"searching for|i need to (find|search|check)|"
    r"since (it'?s|today is|the date|we'?re in)|"
    r"the searches? (aren'?t|isn'?t|didn'?t|have(n'?)?)|"
    r"i('ll| will) (now |just )?generate|"
    r"here'?s? (a|an|the|my) (message|opener|hook|response))",
    re.IGNORECASE,
)


def _strip_thinking(text: str) -> str:
    if not _THINKING_RE.search(text):
        return text
    lines = [ln for ln in text.split("\n") if not _THINKING_RE.search(ln)]
    return " ".join(lines).strip()


# ── Sanitize history (ИСПРАВЛЕНО) ─────────────────────────────────────────────
def _sanitize_history(history: list) -> list:
    """
    Убирает дубли ролей (API требует строгого чередования user/assistant).
    Гарантирует: первый элемент всегда user.
    """
    if not history:
        return []

    sanitized: list[dict] = []
    last_role: Optional[str] = None

    for msg in history:
        role    = msg.get("role")
        content = msg.get("content", "")
        if role not in ("user", "assistant"):
            continue
        if role == last_role:
            # Склеиваем с предыдущим
            if sanitized:
                sanitized[-1]["content"] += "\n" + content
        else:
            sanitized.append({"role": role, "content": content})
            last_role = role

    # API требует чтобы первый был user
    while sanitized and sanitized[0]["role"] == "assistant":
        sanitized.pop(0)

    return sanitized


# ── Поисковые запросы ─────────────────────────────────────────────────────────
_SEARCH_HOOKS: dict[str, list[str]] = {
    "betting": [
        "football odds value bet Europe this week 2026",
        "Champions League Europa League odds movement today",
        "sharp money line movement football bookmakers today",
    ],
    "casino": [
        "best casino bonus low wagering this week 2026",
        "casino promo cashback offer no wagering today",
        "new casino welcome bonus Europe 2026",
    ],
    "nodeposit": [
        "no deposit casino bonus free spins 2026",
        "casino no deposit free chips low wagering today",
        "no deposit bonus expires soon 2026",
    ],
    "exclusive": [
        "sports arbitrage opportunity today 2026",
        "football odds gap bookmakers value bet today",
        "sharp money signal football Europe today",
    ],
}

def _geo_search_queries(interest: str, geo: str) -> list[str]:
    base: dict[str, list[str]] = {
        "betting": [
            f"football value bet {geo} this week 2026",
            f"odds movement {geo} football today",
            f"sharp money {geo} league matches today",
        ],
        "casino": [
            f"best casino bonus low wagering {geo} 2026",
            f"casino promo {geo} low wagering today",
            f"new casino welcome offer {geo} 2026",
        ],
        "nodeposit": [
            f"no deposit bonus {geo} 2026 low wagering",
            f"free spins no deposit {geo} expires soon",
            f"no deposit casino {geo} today 2026",
        ],
        "exclusive": [
            f"arbitrage betting {geo} this week 2026",
            f"value bet odds gap {geo} today",
            f"sharp money signal {geo} today",
        ],
    }
    queries = base.get(interest, base["betting"])
    lang_hint: dict[str, str] = {
        "ES": "españa apuestas bonus",
        "HR": "hrvatska kladjenje bonus",
        "LT": "lietuva lažybos bonusas",
        "LV": "latvija likmes bonuss",
    }
    hint = lang_hint.get(geo.upper(), "")
    if hint:
        queries.append(f"{hint} 2026")
    return queries


# ── Психотип → тактика ────────────────────────────────────────────────────────
_PSYCHOTYPE_TACTIC: dict[str, str] = {
    "skeptic": (
        "SKEPTIC: Never argue. Drop one sharp number. "
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
═══ VOICE EXAMPLES — MATCH THIS STYLE ═══

USER: tell me about betting
YOU: There's a match this weekend where the line shifted *0.40* in 6 hours — that doesn't happen without sharp money. You tracking specific leagues or just anything that moves? 🎯

USER: no
YOU: Fair. What's drawing you here — the match side or the bonus side?

USER: is this a scam
YOU: Heard that before. There was a no-deposit bonus last week — *€25, wagering ×8*. Either it worked for 340 people or it didn't. Which part feels off to you?

USER: later
YOU: One thing before you go — line on tomorrow's match just moved *0.30* in the wrong direction. That kind of gap closes in 2 hours. Want me to flag you when the next one opens?

USER: not interested
YOU: Understood. Different angle — there's a value window on a match tomorrow that has nothing to do with bonuses. Line is sitting *0.45* off where sharp books have it. Curious or not?

USER: stop messaging me
YOU: Got it. I'll only reach out if something genuinely unusual comes up — the kind that moves fast. That okay?

USER: I already deposited somewhere else
YOU: Good timing actually — there's a cashback running this week on top of whatever you're playing. *20% back, no cap.* That's on top of what you're already doing. Want the details?

═══ END EXAMPLES ═══
"""

_SEARCH_FRAME: dict[str, str] = {
    "betting": (
        "Search for a real match with interesting odds, line movement, or mispricing in next 48h. "
        "Extract: teams, current odds, what moved and why. "
        "Use this as YOUR insight — never say 'I found online'."
    ),
    "casino": (
        "Search for a real casino bonus running RIGHT NOW — time-limited, low wagering preferred. "
        "Extract: offer size, wagering requirement, expiry. "
        "Frame it around urgency — the window is closing."
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


# ── Чистка для Telegram ───────────────────────────────────────────────────────
def _clean_for_telegram(text: str) -> str:
    # **bold** → *bold* (Telegram MarkdownV1)
    text = re.sub(r'\*\*(.+?)\*\*', r'*\1*', text)
    # Убираем переносы строк внутри предложений
    text = re.sub(r'\.\n([a-z])', r'. \1', text)
    # Сжимаем множественные переносы до одного
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


# ── Системный промпт (warming / tease / cta) ──────────────────────────────────
def _system_prompt(
    lang: str,
    interest: str,
    funnel_stage: str,
    stage_replies: int = 0,
    psychotype: str = "neutral",
    objections: Optional[dict] = None,
    used_techniques: Optional[list] = None,
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
        "betting":   "sports betting, value bets, odds analysis, European leagues",
        "casino":    "casino bonuses, wagering requirements, RTP, cashback",
        "nodeposit": "no-deposit bonuses, free spins, low-wagering, expiry windows",
        "exclusive": "arbitrage, odds discrepancies, sharp money signals",
    }.get(interest, "sports betting and casino bonuses")

    search_frame = _SEARCH_FRAME.get(interest, _SEARCH_FRAME["betting"])
    tactic       = _PSYCHOTYPE_TACTIC.get(psychotype, _PSYCHOTYPE_TACTIC["neutral"])

    obj_summary = ""
    if objections:
        labels = {
            "scam":           "called it a scam",
            "no_money":       "said no money",
            "no_time":        "said no time",
            "tried_before":   "tried before",
            "not_interested": "not interested",
            "skeptical":      "skeptical",
            "later":          "said later",
            "dont_understand":"doesn't understand",
        }
        parts = [f"{labels.get(k, k)}×{v}" for k, v in objections.items()]
        obj_summary = "User objections so far: " + ", ".join(parts) + "."

    unused = [t for t in ["information_gap", "social_proof", "cost_of_inaction",
                           "pattern_interrupt", "soft_takeaway"] if t not in used_techniques]
    technique_hint = f"Preferred technique this reply (unused): {unused[0]}" if unused else ""

    if funnel_stage == "warming":
        stage_goal = (
            f"WARMING (exchange #{stage_replies}). "
            "Build curiosity. Lead with a real fact from search, end with ONE easy question. "
            + ("Add [NEXT:tease] on its own line at end." if stage_replies >= 2 else
               "Add [NEXT:tease] if they show real engagement." if stage_replies == 1 else
               "Do NOT add [NEXT:tease] yet — this is the first exchange.")
        )
    elif funnel_stage == "tease":
        stage_goal = (
            f"TEASE (exchange #{stage_replies}). "
            "Create FOMO. They are missing something real happening now. "
            + ("MANDATORY: add [NEXT:cta] on its own line at end." if stage_replies >= 1 else
               "Hint strongly but don't hard-sell yet.")
        )
    elif funnel_stage == "cta":
        stage_goal = (
            "CTA. One job: handle objection and make joining feel obvious. "
            "Max 2 sentences. Channel button appears automatically after your reply."
        )
    else:
        stage_goal = (
            "SUBSCRIBED — FTD mode. Goal: first deposit, then repeat. "
            "Lead with a real current fact. Show the gap between watching and acting. "
            "NEVER close conversation. NEVER say goodbye. "
            "Every reply ends with a specific reason to act NOW or a question that pulls back in."
        )

    return f"""You are Valeria — sharp betting & bonus analyst. You sell through real news, not pitches.

{_FEW_SHOT}

════ CURRENT CONTEXT ════
Language: {lang_instruction}
Interest: {interest_context}
Psychotype tactic: {tactic}
{obj_summary}
{technique_hint}
Stage: {stage_goal}

════ SEARCH RULE ════
{search_frame}

NEVER SHOW REASONING:
- NEVER write "Let me search", "I'll look", "Searching for", "I need to find"
- NEVER write "Let me craft", "I'll create", "Since today is", "Since it's [date]"
- NEVER write "The searches aren't returning" or mention search at all
- Go STRAIGHT to the response. Zero preamble.
- If search returns nothing: write something sharp in-character WITHOUT mentioning it.
- DO NOT invent odds/bonuses not in search results.

════ FORMAT ════
- {lang_instruction.split('—')[0].strip()} ONLY — never switch language
- Max 3 sentences. *bold* for key numbers only.
- 1 emoji max at end. No line breaks inside reply (single block).
- Never: "feel free", "great question", "I understand your concerns", "take care"
- NEVER close conversation. NEVER say goodbye.
- Every reply ends with: a question, a new fact, or a reason to act NOW.

Funnel tags (invisible to user, place on own line at END of reply ONLY):
  [NEXT:tease]      — warming→tease
  [NEXT:cta]        — tease→CTA
  [TECHNIQUE:name]  — which technique you used"""


# ── Системный промпт (subscribed / FTD mode) ──────────────────────────────────
def _build_subscribed_prompt(
    lang: str,
    interest: str,
    psychotype: str,
    objections: Optional[dict] = None,
    used_techniques: Optional[list] = None,
    search_context: str = "",
) -> str:
    objections      = objections or {}
    used_techniques = used_techniques or []

    lang_names = {
        "en": "English", "es": "Spanish", "hr": "Croatian",
        "lt": "Lithuanian", "lv": "Latvian",
    }
    language = lang_names.get(lang, "English")

    interest_context = {
        "betting":   "sports betting, value bets, odds movements, sharp money",
        "casino":    "casino bonuses, wagering requirements, cashback, welcome offers",
        "nodeposit": "no deposit bonuses, free spins, low wagering free offers",
        "exclusive": "all: value bets, bonuses, arbitrage, sharp signals",
    }.get(interest, "sports betting")

    psychotype_instruction = {
        "cynic": (
            "This user has shown strong distrust. Lead with verifiable facts, no hype. "
            "Acknowledge skepticism — 'Fair point, here's something concrete.'"
        ),
        "skeptic": (
            "User is cautious. Use specific numbers and social proof. "
            "Never say 'trust me' — show, don't tell."
        ),
        "passive": (
            "User is disengaged. Keep it very short. One simple question or fact. No pressure."
        ),
        "curious": (
            "User is engaged and curious. Give real depth. Pull them toward FTD with a specific opportunity."
        ),
        "neutral": (
            "Standard approach. News-hook → gap → channel as access point."
        ),
    }.get(psychotype, "Standard approach. Be direct and useful.")

    obj_summary = ""
    if objections:
        labels = {
            "scam": "called it a scam", "no_money": "said no money",
            "no_time": "said no time", "tried_before": "tried before",
            "not_interested": "not interested", "skeptical": "skeptical",
            "later": "said later", "dont_understand": "doesn't understand",
        }
        parts = [f"{labels.get(k, k)}×{v}" for k, v in objections.items()]
        obj_summary = f"\nUser objections logged: {', '.join(parts)}."

    unused = [t for t in ["information_gap", "social_proof", "cost_of_inaction",
                           "pattern_interrupt", "soft_takeaway"] if t not in used_techniques]
    technique_hint = f"\nPreferred technique (unused): {unused[0]}" if unused else ""

    search_section = ""
    if search_context:
        search_section = (
            f"\n\nREAL-TIME CONTEXT (use this naturally, never say where it came from):\n{search_context}"
        )

    return f"""You are Valeria — insider analyst tracking odds, bonuses, and signals across European markets.
This user is already subscribed to the channel. Your goal: get them to make their FIRST DEPOSIT (FTD).

LANGUAGE: Respond ONLY in {language}. Never switch.

CRITICAL — NEVER:
- Never write "Let me search", "I'll look for", "Searching...", "Since today is [date]"
- Never show internal reasoning or process
- Never start with "Here's a message" or any meta-commentary
- Never mention being an AI or built on Claude
- Never promise specific returns or profits

PERSONALITY: Smart friend, not a bot. Warm but direct. Specific numbers, real examples.
Short paragraphs. Max 4 sentences. One question per message MAX.
Never use: "Great!", "Absolutely!", "Of course!" — too bot-like.

USER INTEREST: {interest_context}
FUNNEL STAGE: SUBSCRIBED — keep them engaged, build trust, nudge toward first deposit.
Give real value. Never hard-sell. Show what they're missing by not having money in.
PSYCHOTYPE: {psychotype_instruction}{obj_summary}{technique_hint}{search_section}

HARD RULES:
- Max 180 words unless user asks detailed question
- Always end with a question OR a clear next step — never both
- NEVER close conversation. NEVER say goodbye.
- NEVER tell them to deposit — show them WHY it matters right now."""


# ── Web search (single query) ─────────────────────────────────────────────────
async def _web_search(query: str) -> str:
    if not ANTHROPIC_KEY:
        return ""
    try:
        payload = {
            "model":      MODEL,
            "max_tokens": 1024,
            "tools":      [WEB_SEARCH_TOOL],
            "messages":   [{"role": "user", "content": query}],
        }
        headers = {
            "x-api-key":         ANTHROPIC_KEY,
            "anthropic-version": "2023-06-01",
            "anthropic-beta":    "web-search-2025-03-05",
            "content-type":      "application/json",
        }
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(ANTHROPIC_URL, json=payload, headers=headers)
            if resp.status_code != 200:
                return ""
            data = resp.json()
            for block in data.get("content", []):
                if block.get("type") == "text":
                    return block["text"][:800]
    except Exception:
        return ""
    return ""


# ── Извлечение текста из content blocks ───────────────────────────────────────
def _extract_text(content_blocks: list) -> str:
    return "\n".join(
        b.get("text", "") for b in content_blocks if b.get("type") == "text"
    ).strip()


# ── Search + generate loop ─────────────────────────────────────────────────────
async def _run_with_search(
    system: str,
    messages: list,
    headers: dict,
    max_loops: int = 3,
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
                return _strip_thinking(_extract_text(last_content))

            if stop_reason == "max_tokens":
                partial = _extract_text(last_content)
                if partial:
                    payload["messages"] = payload["messages"] + [
                        {"role": "assistant", "content": last_content},
                        {"role": "user",      "content": "Continue."},
                    ]
                    continue
                return _strip_thinking(partial)

            # tool_use или другое — web_search_20250305 server-side, так быть не должно
            return _strip_thinking(_extract_text(last_content))

    return _strip_thinking(_extract_text(last_content))


# ── Interest shift detector ───────────────────────────────────────────────────
def _detect_interest_shift(text: str, current_interest: str) -> Optional[str]:
    t = text.lower()
    casino_signals    = ["casino","slot","roulette","blackjack","bonus","free spins",
                         "казино","слоты","bonos","kazino"]
    betting_signals   = ["bet","odds","match","football","soccer","sport","league",
                         "apuesta","cuota","partido","klađenje","kvota","lažybos","koeficient","likmes"]
    nodeposit_signals = ["no deposit","free","without deposit","sin depósito",
                         "bez depozita","be depozito","bez depozīta"]

    if current_interest != "casino"    and any(s in t for s in casino_signals):
        return "casino"
    if current_interest != "betting"   and any(s in t for s in betting_signals):
        return "betting"
    if current_interest != "nodeposit" and any(s in t for s in nodeposit_signals):
        return "nodeposit"
    return None


# ── Fallback responses ────────────────────────────────────────────────────────
def _fallback_response(lang: str, interest: str, funnel_stage: str) -> str:
    fallbacks: dict[str, dict[str, str]] = {
        "en": {
            "warming":    "There's a match this week where the line is sitting *0.35* above where it should be. That gap only opens when the books haven't caught up. You tracking this or seeing it for the first time?",
            "tease":      "The people positioned on the last one like this — they're already on the next. That's what the channel is for. 🔥",
            "cta":        "What you're looking for is already in there. The next move gets posted before the market catches up.",
            "subscribed": "There's movement on an upcoming match right now. Want to look at the numbers together?",
        },
        "es": {
            "warming":    "Hay un partido esta semana con la cuota *0.35* por encima de donde debería estar. Ese gap solo aparece cuando las casas no han reaccionado. ¿Lo estás siguiendo?",
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


def detect_tone(text: str, history: list) -> str:
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


# ── PUBLIC: generate_warm_opener ──────────────────────────────────────────────
async def generate_warm_opener(lang: str, interest: str, geo: str = "") -> str:
    """
    Первое сообщение Валерии после выбора интереса.
    Ищет реальный новостной хук через web-search, открывает диалог.
    """
    if not ANTHROPIC_KEY:
        return _fallback_response(lang, interest, "warming")

    if geo:
        search_queries = _geo_search_queries(interest, geo)
    else:
        search_queries = _SEARCH_HOOKS.get(interest, _SEARCH_HOOKS["betting"])

    search_frame = _SEARCH_FRAME.get(interest, _SEARCH_FRAME["betting"])
    lang_name = {
        "en": "English",
        "es": "Spanish (Spain, casual tú)",
        "hr": "Croatian",
        "lt": "Lithuanian",
        "lv": "Latvian",
    }.get(lang, "English")

    system = f"""You are Valeria. Open the conversation with ONE real, specific, time-sensitive hook.

Search using one of:
{chr(10).join(f'- {q}' for q in search_queries[:3])}

{search_frame}

{_FEW_SHOT}

CRITICAL — NEVER:
- Never write "Let me search", "I'll look", "I need to find", "Searching for..."
- Never write "Let me craft", "I'll create", "I'll generate", "Here's a message for you"
- Never write "Since today is", "Since it's [date]", "Since we're in [year]"
- Never show reasoning, process, or narration
- If nothing found in search: write sharp in-character hook WITHOUT mentioning search

Rules:
- Start DIRECTLY with the fact or hook — zero preamble
- ONE fact from search ONLY. If nothing found: write something sharp in-character WITHOUT inventing numbers.
- End with ONE easy question.
- Max 2-3 sentences. *bold* key numbers. 1 emoji max. No named bookmakers. No guaranteed profits.
- Language: {lang_name} ONLY."""

    headers = {
        "x-api-key":         ANTHROPIC_KEY,
        "anthropic-version": "2023-06-01",
        "anthropic-beta":    "web-search-2025-03-05",
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


# ── PUBLIC: ask_valeria ───────────────────────────────────────────────────────
async def ask_valeria(
    user_message: str,
    history: list,
    lang: str,
    interest: str,
    funnel_stage: str,
    stage_replies: int = 0,
    psychotype: str = "neutral",
    objections: Optional[dict] = None,
    used_techniques: Optional[list] = None,
    geo: str = "",
) -> tuple[str, str, Optional[str], Optional[str]]:
    """
    Returns: (response_text, refined_interest, next_stage, technique_used)
    """
    objections      = objections or {}
    used_techniques = used_techniques or []

    if not ANTHROPIC_KEY:
        return _fallback_response(lang, interest, funnel_stage), interest, None, None

    headers_base = {
        "x-api-key":         ANTHROPIC_KEY,
        "anthropic-version": "2023-06-01",
        "content-type":      "application/json",
    }

    # ── SUBSCRIBED: без web-search в loop, только pre-fetch ──────────────────
    if funnel_stage == "subscribed":
        search_context = ""
        if geo:
            queries = _geo_search_queries(interest, geo)
        else:
            queries = _SEARCH_HOOKS.get(interest, _SEARCH_HOOKS["betting"])
        search_context = await _web_search(queries[0])

        system = _build_subscribed_prompt(
            lang=lang,
            interest=interest,
            psychotype=psychotype,
            objections=objections,
            used_techniques=used_techniques,
            search_context=search_context,
        )
        clean_history    = _sanitize_history(history[-12:])
        messages_payload = clean_history + [{"role": "user", "content": user_message}]

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                payload = {
                    "model":      MODEL,
                    "max_tokens": AI_MAX_TOKENS,
                    "system":     system,
                    "messages":   messages_payload,
                }
                resp = await client.post(ANTHROPIC_URL, json=payload, headers=headers_base)
                resp.raise_for_status()
                data  = resp.json()
                reply = ""
                for block in data.get("content", []):
                    if block.get("type") == "text":
                        reply = block["text"].strip()
                        break
        except Exception as e:
            logger.error(f"ask_valeria [subscribed] error: {e}")
            reply = ""

        if not reply:
            reply = _fallback_response(lang, interest, funnel_stage)

        reply = _clean_for_telegram(_strip_thinking(reply))

        refined = _detect_interest_shift(user_message, interest) or interest
        return reply, refined, None, None

    # ── WARMING / TEASE / CTA: web-search через loop ──────────────────────────
    system = _system_prompt(
        lang, interest, funnel_stage, stage_replies,
        psychotype, objections, used_techniques,
    )
    clean_history = _sanitize_history(history[-10:])
    api_messages  = clean_history + [{"role": "user", "content": user_message}]
    headers_search = {**headers_base, "anthropic-beta": "web-search-2025-03-05"}

    try:
        raw = _clean_for_telegram(
            await _run_with_search(system, api_messages, headers_search)
        )
    except httpx.HTTPStatusError as e:
        logger.error(f"Anthropic HTTP {e.response.status_code}: {e.response.text[:200]}")
        return _fallback_response(lang, interest, funnel_stage), interest, None, None
    except Exception as e:
        logger.error(f"Anthropic error: {e}")
        return _fallback_response(lang, interest, funnel_stage), interest, None, None

    # Парсим служебные теги
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

    # Детект сдвига интереса из текста пользователя
    shifted = _detect_interest_shift(user_message, refined)
    if shifted:
        refined = shifted

    # Форсируем переходы если AI не проставил теги
    if next_stage is None:
        if funnel_stage == "warming" and stage_replies >= 3:
            next_stage = "tease"
        elif funnel_stage == "tease" and stage_replies >= 2:
            next_stage = "cta"

    return raw, refined, next_stage, technique_used
