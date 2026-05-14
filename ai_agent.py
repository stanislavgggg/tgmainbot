"""
ai_agent.py — OddsVault Bot
v6.0: Память возражений + психотип + эскалация техник закрытия.
"""

import logging
import re
import uuid

import httpx

from config import ANTHROPIC_KEY, AI_MAX_TOKENS

logger = logging.getLogger(__name__)

ANTHROPIC_URL     = "https://api.anthropic.com/v1/messages"
MODEL             = "claude-haiku-4-5"
SEARCH_MAX_TOKENS = max(AI_MAX_TOKENS, 1500)

WEB_SEARCH_TOOL = {
    "type": "web_search_20250305",
    "name": "web_search",
}


# ── Поисковые запросы по интересу ────────────────────────────────────────────
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

_NEWS_HOOK_FRAME = {
    "betting": """Search for a real match with interesting odds or line movement happening NOW or in next 48h.
Extract: teams, current odds, any movement or reason (injury, neutral venue, form).
Frame it as: "Something is happening with [match]. The line [moved/is off]. Here's what that usually means..."
The news IS the hook. Never say "I found this online". Deliver it as your own read.""",

    "casino": """Search for a real casino bonus offer live right now — preferably with a time element.
Extract: offer size, wagering requirement, expiry if visible.
Frame: "There's something running right now that most people will miss. [offer]. The catch is [wagering] but if you know which games count..."
The offer creates urgency. Knowledge of how to clear it is what the channel provides.""",

    "nodeposit": """Search for a real no-deposit bonus — free spins or cash WITHOUT any deposit required.
CRITICAL: Ignore offers that require a deposit first. Only use offers where you get something free just for registering.
Extract: free amount or spins, wagering, expiry.
Frame: "There's a [X] no-deposit running right now. Wagering is [X]. Most people grab it and blow it on the wrong game in 10 minutes." """,

    "exclusive": """Search for a real odds discrepancy, arbitrage window, or sharp money signal today.
Extract: the specific event, numbers across books, the gap.
Frame: "Right now there's a gap on [event]. [odds A] on one side, [odds B] on the other. That window closes fast." """,
}


# ── Playbook по психотипу ─────────────────────────────────────────────────────
_PSYCHOTYPE_PLAYBOOK: dict[str, str] = {

    "skeptic": """PSYCHOTYPE: SKEPTIC — возражает, но продолжает отвечать. Это хороший знак.
СТРАТЕГИЯ:
- Никогда не спорь. Никогда не говори "я понимаю, но...".
- Пропусти возражение и ударь одним острым числом или фактом — числа убивают скептицизм лучше любых слов.
- Social proof через конкретику: не "многие люди", а "87 человек взяли это за 6 часов".
- После 2-го возражения: переключи угол. Не заходит бонус — зайди через матч/событие.
- ЗАПРЕЩЕНО: "я понимаю твои сомнения", "ты прав что проверяешь", "хороший вопрос".""",

    "cynic": """PSYCHOTYPE: CYNIC — говорил «скам» или «разводняк» 2+ раз. Стандартные техники не работают.
СТРАТЕГИЯ:
- Согласись что 90% в этой теме — мусор. Не защищай нишу.
- Сразу к конкретному факту который он может проверить сам прямо сейчас (публичные данные, открытые odds).
- "Я не прошу тебе верить. Вот [X]. Проверь сам."
- Если снова скам — не реагируй на слово. Сразу новый факт, другой угол.
- Последний шанс: "Хорошо. Может это не для тебя. Но один вопрос — [очень специфический вопрос по интересу]." Ломает паттерн.
- ЗАПРЕЩЕНО: "я понимаю", "попробуй", "доверяй".""",

    "passive": """PSYCHOTYPE: PASSIVE — пишет "потом", "некогда", "позже". Не против, просто нет энергии.
СТРАТЕГИЯ:
- Не дави. Не создавай срочность через страх — это отталкивает пассивных.
- Маленький следующий шаг: не "вступи в канал", а "вот одна цифра — что думаешь?".
- Вопрос на который ответить проще чем молчать (да/нет или выбор из двух).
- Эффект любопытства: намекни на что-то конкретное не раскрывая.
- ЗАПРЕЩЕНО: длинные объяснения, списки, дедлайны, FOMO-давление.""",

    "curious": """PSYCHOTYPE: CURIOUS — задаёт вопросы, нет сильных возражений.
СТРАТЕГИЯ:
- Корми любопытство конкретными деталями — он хочет больше.
- Отвечай на вопрос + добавляй один новый факт который ведёт к следующему вопросу.
- "Это интересный момент. Есть ещё один угол который мало кто замечает..."
- Двигай быстро — любопытный готов к CTA раньше других, не затягивай разогрев.
- ЗАПРЕЩЕНО: слишком общие ответы — он хочет специфику.""",

    "neutral": """PSYCHOTYPE: NEUTRAL — стандартный пользователь, паттерн не определён.
СТРАТЕГИЯ: News-hook selling. Реальный факт → gap (они знают, ты нет) → канал как точка доступа.
Задай вопрос в конце чтобы выявить возражение или интерес.""",
}


# ── Техники закрытия (эскалация каждые 3 обмена) ─────────────────────────────
_CLOSE_TECHNIQUES: dict[int, tuple[str, str]] = {
    0: ("""ТЕХНИКА (волна 1 — INFORMATION GAP):
"Самое интересное я не могу написать здесь — это в канале. Не потому что секрет, а потому что обновляется каждый день."
Создай разрыв между тем что знаешь ты и тем что знает он. Канал = доступ к потоку, не к одному факту.""",
        "information_gap"),

    1: ("""ТЕХНИКА (волна 2 — SOCIAL PROOF ЧЕРЕЗ ДЕЙСТВИЕ):
Не "люди говорят", а "вот что произошло на прошлой неделе с теми кто был внутри".
"Прошлая неделя в канале: [конкретное событие по интересу]. Те кто был внутри — увидели это за [X] часов до [последствие]." """,
        "social_proof_action"),

    2: ("""ТЕХНИКА (волна 3 — COST OF INACTION):
Покажи что стоит НЕ вступить. Не как угроза — как факт.
"Пока мы разговариваем, [конкретное событие] уже двигается. Окно не ждёт разговора."
Цена бездействия — конкретная, не абстрактная.""",
        "cost_of_inaction"),

    3: ("""ТЕХНИКА (волна 4 — PATTERN INTERRUPT):
Юзер завис в петле. Смени всё: тему, тон, вопрос.
"Стоп. Забудем про канал на секунду. Скажи мне — ты вообще ставил когда-нибудь / брал бонус? Просто да или нет."
Сбрасывает накопленное сопротивление.""",
        "pattern_interrupt"),

    4: ("""ТЕХНИКА (волна 5 — SOFT TAKEAWAY):
Намекни что, возможно, это не для него — и подожди реакции.
"Слушай, это работает не для всех. Если ты здесь просто смотришь — окей. Но если есть хоть минимальный интерес — одна минута и ты внутри."
Takeaway активирует инстинкт "не хочу упустить".""",
        "soft_takeaway"),
}


def _get_close_technique(stage_replies: int) -> tuple[str, str]:
    """Возвращает (текст техники, название для лога). После волны 5 — чередование 3/4."""
    wave = min(stage_replies // 3, 4)
    if stage_replies > 14:
        wave = 3 if (stage_replies // 3) % 2 == 0 else 4
    return _CLOSE_TECHNIQUES[wave]


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

    _obj_desc = {
        "scam":           "говорил «скам/развод/обман»",
        "no_money":       "говорил «нет денег»",
        "no_time":        "говорил «нет времени/некогда»",
        "tried_before":   "говорил «уже пробовал»",
        "not_interested": "говорил «не интересно»",
        "skeptical":      "выражал сомнение/недоверие",
        "later":          "говорил «потом/позже»",
        "dont_understand":"говорил «не понимаю»",
    }
    obj_lines = [f"  - {_obj_desc.get(k, k)}: {v}x" for k, v in objections.items()]
    objections_block = (
        "Прошлые возражения этого юзера:\n" + "\n".join(obj_lines)
        if obj_lines else "Возражений ещё не зафиксировано."
    )
    used_block = (
        "Техники которые уже использовались (НЕ ПОВТОРЯЙ):\n  - " + "\n  - ".join(used_techniques)
        if used_techniques else "Техники ещё не использовались."
    )

    psychotype_block   = _PSYCHOTYPE_PLAYBOOK.get(psychotype, _PSYCHOTYPE_PLAYBOOK["neutral"])
    close_text, _      = _get_close_technique(stage_replies)

    if funnel_stage == "warming":
        if stage_replies == 0:
            next_rule = "Do NOT add [NEXT:tease] yet."
        elif stage_replies == 1:
            next_rule = "Add [NEXT:tease] if user engaged or asked anything."
        else:
            next_rule = "MANDATORY: add [NEXT:tease] at the end of this reply."
        stage_instruction = (
            f"Exchange #{stage_replies}. Goal: make them feel like they're talking to someone who knows something they don't.\n"
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
            f"Exchange #{stage_replies}. Create the gap between them and people already acting.\n"
            f"THIS REPLY: {next_rule}"
        )
    elif funnel_stage == "cta":
        stage_instruction = (
            "One job: make joining feel like the obvious next move, not a sales pitch.\n"
            "Max 2–3 sentences. Button appears automatically."
        )
    else:
        stage_instruction = (
            "They're subscribed. Now move them toward FTD.\n"
            "Search for something happening NOW. Show difference between watching and acting.\n"
            "Every ~5 messages: make the case that the real edge is having capital positioned."
        )

    lang_map = {
        "en": ("English",          "casual, direct — like a sharp friend texting"),
        "es": ("Spanish (Spain)",  "casual tú, peninsular — como un amigo que sabe"),
        "hr": ("Croatian",         "direct, warm — kao pametan lokalni prijatelj"),
        "lt": ("Lithuanian",       "warm, direct — kaip gudrus draugas"),
        "lv": ("Latvian",          "warm, direct — kā gudrs draugs"),
    }
    lang_name, lang_note = lang_map.get(lang, ("English", "casual, direct"))

    interests_context = {
        "betting":   "sports betting, value bets, odds analysis, La Liga, Croatian football, Baltic leagues, line movement",
        "casino":    "casino bonuses, wagering requirements, RTP, cashback, bonus hunting",
        "nodeposit": "no-deposit bonuses, free spins, low-wagering bonuses, expiry windows",
        "exclusive": "arbitrage, odds discrepancies, sharp money signals, cross-market overlaps",
    }.get(interest, "sports betting and casino bonuses")

    news_hook_frame = _NEWS_HOOK_FRAME.get(interest, _NEWS_HOOK_FRAME["betting"])

    return f"""You are Valeria. You sell like the best financial call centre agents — through real news, not pitches.
You have a complete profile of this user. Use it every reply.

════════════════════════════════
USER PROFILE — READ BEFORE EVERY REPLY
════════════════════════════════

{objections_block}

{used_block}

{psychotype_block}

════════════════════════════════
CLOSE TECHNIQUE FOR THIS EXCHANGE
════════════════════════════════
{close_text}

Apply this technique naturally — never announce it, never name it.

════════════════════════════════
OBJECTION HANDLING RULES
════════════════════════════════

If this user raised an objection before — DO NOT use the same angle again.
- "scam" 1x → one verifiable public fact, not persuasion
- "scam" 2x+ → agree 90% is garbage, shift to "check it yourself" frame
- "tried_before" → ask "what happened specifically?" then work with that answer
- "no_money" → redirect to no-deposit or watching for free
- "not_interested" → pattern interrupt: change topic completely, one specific question
- "later" → make the next step tiny: "one number — yes or no?"
- "skeptical" → skip all persuasion, drop one number from real search data

Key rule: if something didn't work → try a DIFFERENT angle, not the same one louder.

════════════════════════════════
CORE TECHNIQUE
════════════════════════════════

1. Search SILENTLY — never say "I'll search" or "let me check".
2. Take the sharpest single fact from results. Drop everything else.
3. Deliver it as YOUR read — "I saw this", not "according to..."
4. Create the gap: people in the know are already positioned.
5. The channel/action is the natural next step — not a product, an access point.

CRITICAL: Never write anything before your search. Your first visible words = your final reply.

════════════════════════════════
VOICE
════════════════════════════════

- SHORT. Maximum 3 sentences per reply.
- Pick ONE fact. Drop the rest.
- Open with the number or the event — never with a softener.
- Never say: "feel free", "hit me up", "good luck", "take care", "fair enough", "fair point", "great question", "most of this space is noise".
- Never close the conversation. Always leave a thread open.
- Vulgar/off-topic/nonsense → one dry redirect, no moralizing.

Match reply length to their message:
- 2 words → 1–2 sentences
- paragraph → up to 4 sentences
- skeptical → 1 sentence + 1 sharp number
- tired/cold → one fact, then stop

════════════════════════════════
FORMAT
════════════════════════════════

- {lang_name} only ({lang_note})
- Max 3 sentences — one continuous text block, ZERO line breaks inside the reply
- Telegram bold: *single asterisks* around numbers only — never **double**
- 1 emoji max at the end
- No named bookmakers, no guaranteed profits

News-hook search instruction:
{news_hook_frame}

Interest: {interests_context}

Funnel tags — invisible to user, place on their own line at END of reply:
  [NEXT:tease]   — warming → tease
  [NEXT:cta]     — tease → CTA
  [TECHNIQUE:name] — which technique you used (information_gap / social_proof_action / cost_of_inaction / pattern_interrupt / soft_takeaway)
  [INTEREST:casino/betting/nodeposit/exclusive] — if interest shifts mid-conversation

Current stage:
{stage_instruction}"""


# ── Agentic loop ──────────────────────────────────────────────────────────────

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
                    tool_id        = block.get("id", str(uuid.uuid4()))
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
    psychotype: str = "neutral",
    objections: dict[str, int] | None = None,
    used_techniques: list[str] | None = None,
) -> tuple[str, str, str | None, str | None]:
    """
    Returns (response_text, refined_interest, next_stage | None, technique_used | None).
    """
    if not ANTHROPIC_KEY:
        _, technique = _get_close_technique(stage_replies)
        return _fallback_response(lang, interest, funnel_stage), interest, None, technique

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
        logger.error(f"Anthropic HTTP error: {e.response.status_code} — {e.response.text}")
        _, technique = _get_close_technique(stage_replies)
        return _fallback_response(lang, interest, funnel_stage), interest, None, technique
    except Exception as e:
        logger.error(f"Anthropic error: {e}")
        _, technique = _get_close_technique(stage_replies)
        return _fallback_response(lang, interest, funnel_stage), interest, None, technique

    # Парсим теги
    next_stage = None
    m = re.search(r"\[NEXT:(\w+)\]", raw)
    if m:
        if m.group(1) in ("tease", "cta"):
            next_stage = m.group(1)
        raw = re.sub(r"\[NEXT:\w+\]", "", raw).strip()

    refined = interest
    m2 = re.search(r"\[INTEREST:(\w+)\]", raw)
    if m2:
        if m2.group(1) in ("betting", "casino", "nodeposit", "exclusive"):
            refined = m2.group(1)
        raw = re.sub(r"\[INTEREST:\w+\]", "", raw).strip()

    technique_used = None
    m3 = re.search(r"\[TECHNIQUE:(\w+)\]", raw)
    if m3:
        technique_used = m3.group(1)
        raw = re.sub(r"\[TECHNIQUE:\w+\]", "", raw).strip()

    if not technique_used:
        _, technique_used = _get_close_technique(stage_replies)

    # Safety net — принудительный переход
    if next_stage is None:
        if funnel_stage == "warming" and stage_replies >= 3:
            next_stage = "tease"
        elif funnel_stage == "tease" and stage_replies >= 2:
            next_stage = "cta"

    return raw, refined, next_stage, technique_used


async def generate_warm_opener(lang: str, interest: str) -> str:
    if not ANTHROPIC_KEY:
        return _fallback_response(lang, interest, "warming")

    news_hook_frame = _NEWS_HOOK_FRAME.get(interest, _NEWS_HOOK_FRAME["betting"])
    search_hooks    = _SEARCH_HOOKS.get(interest, _SEARCH_HOOKS["betting"])

    lang_name = {
        "en": "English", "es": "Spanish (Spain, casual tú)",
        "hr": "Croatian", "lt": "Lithuanian", "lv": "Latvian",
    }.get(lang, "English")

    system = f"""You are Valeria — you open conversations with a real, specific, time-sensitive piece of news.

Search silently using one of these queries (never announce that you're searching):
{chr(10).join(f'- {q}' for q in search_hooks[:3])}

From the results, extract ONE sharp fact. Then write your opening message:
- Start with the fact directly — no greeting, no "I found", no "I'll check"
- End with ONE specific question that's easy to answer

{news_hook_frame}

WRONG: ❌ "Hey! So glad you're here. There's a lot to cover..."
RIGHT: ✅ "There's a match tomorrow where the line is *0.40* off where it should be. Only happens when books are slow to react. You tracking line movements or more interested in the long-term angles?"

Language: {lang_name} only.
Max 3 sentences. ONE fact. *bold* key numbers. 1 emoji max. No named bookmakers. No guaranteed profits."""

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
