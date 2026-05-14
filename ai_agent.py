"""
ai_agent.py — OddsVault Bot v10
КЛЮЧЕВЫЕ ИЗМЕНЕНИЯ vs предыдущей версии:
  - Убран web-search из warming/tease/cta — они делали 2 API запроса на сообщение → 429
  - warming/tease/cta = 1 запрос (без поиска, с системным промптом)
  - subscribed = 1 запрос (без поиска, быстрее)
  - generate_warm_opener = 1 запрос с поиском (только при первом контакте)
  - Retry с exponential backoff при 429
  - Полное логирование ошибок API
"""
import asyncio, logging, re, json
from typing import Optional
from datetime import datetime, timezone
import httpx
from config import ANTHROPIC_KEY, AI_MAX_TOKENS

logger = logging.getLogger(__name__)

ANTHROPIC_URL     = "https://api.anthropic.com/v1/messages"
MODEL             = "claude-sonnet-4-20250514"
WEB_SEARCH_TOOL   = {"type":"web_search_20250305","name":"web_search","max_uses":1}

# ── Thinking filter ───────────────────────────────────────────────────────────
_THINKING_RE = re.compile(
    r"(let me (search|look|check|find|craft|create|try)|"
    r"i('ll| will) (search|look|check|find|craft|create|try)|"
    r"i('m| am) (looking|searching|checking)|"
    r"searching for|i need to (find|search|check)|"
    r"since (it'?s|today is|the date|we'?re in)|"
    r"the searches? (aren'?t|isn'?t|didn'?t|have(n'?)?)|"
    r"here'?s? (a|an|the|my) (message|opener|hook|response))",
    re.IGNORECASE)

def _strip_thinking(text: str) -> str:
    if not _THINKING_RE.search(text): return text
    lines = [l for l in text.split("\n") if not _THINKING_RE.search(l)]
    return " ".join(lines).strip()

def _clean_for_telegram(text: str) -> str:
    text = re.sub(r'\*\*(.+?)\*\*', r'*\1*', text)
    text = re.sub(r'\.\n([a-z])', r'. \1', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()

# ── HTTP helper with retry ────────────────────────────────────────────────────

async def _post_with_retry(url, payload, headers, timeout=30, max_retries=3) -> dict:
    """POST с exponential backoff при 429 Too Many Requests."""
    last_exc = None
    for attempt in range(max_retries):
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.post(url, json=payload, headers=headers)
                if resp.status_code == 429:
                    wait = 2 ** attempt  # 1s, 2s, 4s
                    logger.warning(f"429 Rate limit, retry in {wait}s (attempt {attempt+1}/{max_retries})")
                    await asyncio.sleep(wait)
                    continue
                if resp.status_code != 200:
                    logger.error(f"API error {resp.status_code}: {resp.text[:300]}")
                    resp.raise_for_status()
                return resp.json()
        except httpx.HTTPStatusError:
            raise
        except Exception as e:
            last_exc = e
            logger.warning(f"Request error (attempt {attempt+1}): {e}")
            await asyncio.sleep(1)
    if last_exc:
        raise last_exc
    raise RuntimeError("Max retries exceeded")

# ── Anti-hallucination search ─────────────────────────────────────────────────

def _is_valid_search_result(text: str) -> bool:
    if not text or len(text) < 80: return False
    lower = text.lower()
    if any(m in lower for m in ["no results","not found","couldn't find","nothing found","no_data_found"]): return False
    return bool(re.search(r'\d', text))

def _build_search_queries(interest: str, geo: str = "") -> list:
    today = datetime.now(timezone.utc).strftime("%B %Y")
    geo_league = {"ES":"La Liga","HR":"HNL Croatia","LT":"A lyga Lithuania","LV":"Virsliga Latvia"}.get(geo.upper() if geo else "", "European football")
    q = {
        "betting":   [f"{geo_league} football odds value bet {today}"],
        "casino":    [f"casino bonus low wagering {today} Europe"],
        "nodeposit": [f"no deposit casino bonus free spins {today}"],
        "exclusive": [f"sports arbitrage odds gap bookmakers {today}"],
    }
    return q.get(interest, q["betting"])

async def _safe_web_search(interest: str, geo: str = "") -> Optional[str]:
    """1 запрос. Returns real fact or None."""
    if not ANTHROPIC_KEY: return None
    query = _build_search_queries(interest, geo)[0]
    headers = {"x-api-key":ANTHROPIC_KEY,"anthropic-version":"2023-06-01",
               "anthropic-beta":"web-search-2025-03-05","content-type":"application/json"}
    payload = {
        "model": MODEL, "max_tokens": 400, "tools": [WEB_SEARCH_TOOL],
        "system": "Extract ONLY concrete facts from search: team names, odds, bonus amounts, dates. If nothing found reply: NO_DATA_FOUND. Never invent. Max 100 words.",
        "messages": [{"role":"user","content":query}]
    }
    try:
        data = await _post_with_retry(ANTHROPIC_URL, payload, headers, timeout=20, max_retries=2)
        for block in data.get("content", []):
            if block.get("type") == "text":
                result = block["text"].strip()
                if "NO_DATA_FOUND" in result: return None
                if _is_valid_search_result(result):
                    logger.info(f"Search hit ({len(result)} chars)")
                    return result[:500]
    except Exception as e:
        logger.warning(f"Search error: {e}")
    return None

# ── History sanitizer ─────────────────────────────────────────────────────────

def _sanitize_history(history: list) -> list:
    if not history: return []
    sanitized, last_role = [], None
    for msg in history:
        role, content = msg.get("role"), msg.get("content","")
        if role not in ("user","assistant"): continue
        if role == last_role:
            if sanitized: sanitized[-1]["content"] += "\n" + content
        else:
            sanitized.append({"role":role,"content":content})
            last_role = role
    while sanitized and sanitized[0]["role"] == "assistant": sanitized.pop(0)
    return sanitized

# ── Few-shot ──────────────────────────────────────────────────────────────────

_FEW_SHOT = """
VALERIA'S VOICE:
USER: tell me about betting
YOU: There's a match this weekend where the line shifted *0.40* in 6 hours — sharp money moved. You tracking specific leagues or just anything that moves? 🎯
USER: is this a scam
YOU: Heard that before. There was a no-deposit bonus — *€25, wagering ×8*. Either it worked for 340 people or it didn't. Which part feels off?
USER: later
YOU: One thing — a line just moved *0.30* in the wrong direction. That gap closes in 2 hours. Want me to flag you when the next one opens?
USER: not interested
YOU: Different angle — there's a value window that has nothing to do with bonuses. Line is *0.45* off where sharp books have it. Curious or not?
"""

_PSYCHOTYPE_TACTIC = {
    "skeptic":  "SKEPTIC: One sharp verifiable number. Social proof = specific.",
    "cynic":    "CYNIC: One verifiable public fact. 'Check it yourself.'",
    "passive":  "PASSIVE: One tiny next step. Simple yes/no question.",
    "curious":  "CURIOUS: Feed curiosity. Answer + one new fact. Move toward CTA.",
    "neutral":  "NEUTRAL: News-hook → gap → channel.",
}

def _build_profile_ctx(user_profile: dict) -> str:
    if not user_profile: return ""
    parts = [f"{k}={v}" for k,v in user_profile.items() if v]
    return ("Known: " + "; ".join(parts) + ".") if parts else ""

def _build_obj_summary(objections: dict) -> str:
    if not objections: return ""
    labels = {"scam":"scam","no_money":"no money","tried_before":"tried before",
              "not_interested":"not interested","skeptical":"skeptical","later":"said later"}
    parts = [f"{labels.get(k,k)}×{v}" for k,v in objections.items()]
    return "Objections: " + ", ".join(parts) + "."

# ── System prompts ────────────────────────────────────────────────────────────

def _system_prompt(lang, interest, funnel_stage, stage_replies=0, psychotype="neutral",
                   objections=None, used_techniques=None, user_profile=None) -> str:
    objections, used_techniques, user_profile = objections or {}, used_techniques or [], user_profile or {}
    lang_map = {"en":"English — casual","es":"Spanish (Spain, tú)","hr":"Croatian","lt":"Lithuanian","lv":"Latvian"}
    li = lang_map.get(lang, "English — casual")
    ic = {"betting":"sports betting, value bets, odds","casino":"casino bonuses, wagering, cashback",
          "nodeposit":"no-deposit bonuses, free spins","exclusive":"arbitrage, sharp signals, all of above"}.get(interest,"betting & bonuses")
    tactic = _PSYCHOTYPE_TACTIC.get(psychotype, _PSYCHOTYPE_TACTIC["neutral"])
    unused = [t for t in ["information_gap","social_proof","cost_of_inaction","pattern_interrupt","soft_takeaway"] if t not in used_techniques]
    tech_hint = f"Preferred technique: {unused[0]}" if unused else ""
    if funnel_stage == "warming":
        sg = (f"WARMING #{stage_replies}. Build curiosity. End with ONE question. "
              + ("Add [NEXT:tease] on own line." if stage_replies>=2 else "Add [NEXT:tease] if strong engagement." if stage_replies==1 else "Do NOT add [NEXT:tease]."))
    elif funnel_stage == "tease":
        sg = (f"TEASE #{stage_replies}. Create FOMO. "
              + ("MANDATORY: add [NEXT:cta] on own line." if stage_replies>=1 else "Build urgency, no CTA yet."))
    elif funnel_stage == "cta":
        sg = "CTA. Handle objection, make joining obvious. Max 2 sentences. Button appears automatically."
    else:
        sg = "SUBSCRIBED — FTD mode. Never close. End with question or reason to act NOW."

    return f"""You are Valeria — sharp betting & bonus analyst, private AI companion.

{_FEW_SHOT}

════ CONTEXT ════
Language: {li} — write ONLY in this language.
Interest: {ic}
Psychotype: {tactic}
{_build_obj_summary(objections)}
{_build_profile_ctx(user_profile)}
{tech_hint}
Stage: {sg}

════ RULES ════
NEVER invent: team names, match scores, odds, bonus amounts without real data.
NEVER show reasoning: no "Let me search", "Since today is".
NEVER close conversation. NEVER say goodbye.
Max 3 sentences. *bold* key numbers. 1 emoji max.
Every reply ends with: question, new fact, or reason to act NOW.
If no real data available: use general framing (line movements, market patterns) without specific numbers.

Tags (own line at END): [NEXT:tease]  [NEXT:cta]  [TECHNIQUE:name]"""

def _build_subscribed_prompt(lang, interest, psychotype, objections=None, user_profile=None) -> str:
    objections, user_profile = objections or {}, user_profile or {}
    lang_names = {"en":"English","es":"Spanish","hr":"Croatian","lt":"Lithuanian","lv":"Latvian"}
    language = lang_names.get(lang, "English")
    ic = {"betting":"sports betting, value bets","casino":"casino bonuses, wagering, cashback",
          "nodeposit":"no-deposit bonuses, free spins","exclusive":"value bets, bonuses, arbitrage"}.get(interest,"betting & bonuses")
    pi = {"cynic":"Lead with verifiable facts.","skeptic":"Specific numbers, social proof.",
          "passive":"Very short. One simple question.","curious":"Real depth. Pull toward FTD.",
          "neutral":"News-hook → gap → action."}.get(psychotype,"Direct and useful.")
    return f"""You are Valeria — insider analyst, private AI companion.
User is SUBSCRIBED. Goal: first deposit (FTD), then repeat.

LANGUAGE: {language} only. Never switch.
NEVER: show reasoning, mention being AI, promise profits, close conversation, invent specific numbers without real data.
PERSONALITY: Smart friend. Warm but direct. Max 4 sentences.
USER INTEREST: {ic}
PSYCHOTYPE: {pi}
{_build_obj_summary(objections)}
{_build_profile_ctx(user_profile)}

RULE: Max 150 words. End with question OR next step. NEVER close conversation.
If no real data: use general insight about {ic} — patterns, timing, what smart players do."""

# ── Interest shift ────────────────────────────────────────────────────────────

def _detect_interest_shift(text: str, current: str) -> Optional[str]:
    t = text.lower()
    if current!="casino"    and any(s in t for s in ["casino","slot","roulette","blackjack","bonus","free spins","bonos","kazino"]): return "casino"
    if current!="betting"   and any(s in t for s in ["bet","odds","match","football","soccer","sport","league","apuesta","cuota","klađenje","koeficient"]): return "betting"
    if current!="nodeposit" and any(s in t for s in ["no deposit","without deposit","sin depósito","bez depozita","be depozito","bez depozīta"]): return "nodeposit"
    return None

# ── Tone detector ─────────────────────────────────────────────────────────────

_POS = {"yes","sí","si","taip","jā","ok","bueno","bien","super","claro","naravno","👍","🔥","✅"}
_NEG = {"no","nope","ne","scam","estafa","prevara","😐","😑","🤔"}
_SKP = {"duda","sumnja","abejonė","šaubas","seguro","siguran","tikras","prueba","dokaz"}

def detect_tone(text: str, history: list) -> str:
    lower = text.lower()
    words = set(re.findall(r"\w+", lower))
    if words & _NEG or words & _SKP: return "skeptical"
    if words & _POS: return "positive"
    if "?" in text: return "curious"
    if len(text) < 20: return "short"
    return "neutral"

# ── Profile extractor ─────────────────────────────────────────────────────────

async def extract_profile_update(user_message: str, current_profile: dict, lang: str) -> dict:
    if not ANTHROPIC_KEY or len(user_message) < 5: return {}
    already = ", ".join(f"{k}={v}" for k,v in current_profile.items()) or "nothing yet"
    system = "Extract ONLY: name (first name if introduced), league (team/sport mentioned), experience (beginner/intermediate/experienced), budget (stake size). Return valid JSON with NEW fields only. If nothing new: {}. Never invent."
    try:
        data = await _post_with_retry(
            ANTHROPIC_URL,
            {"model":MODEL,"max_tokens":60,"system":system,
             "messages":[{"role":"user","content":f"Known: {already}\nMessage: {user_message}"}]},
            {"x-api-key":ANTHROPIC_KEY,"anthropic-version":"2023-06-01","content-type":"application/json"},
            timeout=8, max_retries=1)
        text = next((b["text"].strip() for b in data.get("content",[]) if b.get("type")=="text"), "")
        if not text or text=="{}": return {}
        text = re.sub(r"```json|```","",text).strip()
        updates = json.loads(text)
        return {k:v for k,v in updates.items() if k in {"name","league","experience","budget"} and isinstance(v,str) and v}
    except Exception as e:
        logger.debug(f"Profile skip: {e}"); return {}

# ── Micro-commitment questions ────────────────────────────────────────────────

_COMMITMENT_QUESTIONS = {
    "betting": {
        "en":{"text":"Quick one — when you bet, what usually drives you?","options":[{"label":"📊 The odds movement","data":"cm_odds"},{"label":"🏆 My gut on the team","data":"cm_gut"},{"label":"📰 Stats and form","data":"cm_stats"}]},
        "es":{"text":"Rápido — cuando apuestas, ¿qué te guía normalmente?","options":[{"label":"📊 El movimiento de cuotas","data":"cm_odds"},{"label":"🏆 Mi instinto sobre el equipo","data":"cm_gut"},{"label":"📰 Estadísticas y forma","data":"cm_stats"}]},
        "hr":{"text":"Brzo — kad se kladiš, što te obično vodi?","options":[{"label":"📊 Kretanje kvota","data":"cm_odds"},{"label":"🏆 Instinkt o momčadi","data":"cm_gut"},{"label":"📰 Statistike i forma","data":"cm_stats"}]},
        "lt":{"text":"Greitai — kai statai, kas tave paprastai veda?","options":[{"label":"📊 Koeficientų judėjimas","data":"cm_odds"},{"label":"🏆 Instinktas dėl komandos","data":"cm_gut"},{"label":"📰 Statistika ir forma","data":"cm_stats"}]},
        "lv":{"text":"Ātri — kad liec likmes, kas tevi parasti vada?","options":[{"label":"📊 Koeficientu kustība","data":"cm_odds"},{"label":"🏆 Instinkts par komandu","data":"cm_gut"},{"label":"📰 Statistika un forma","data":"cm_stats"}]},
    },
    "casino": {
        "en":{"text":"When you look at a bonus — what matters most?","options":[{"label":"💰 The bonus size","data":"cm_size"},{"label":"🔄 The wagering req.","data":"cm_wager"},{"label":"⏰ How long it's valid","data":"cm_time"}]},
        "es":{"text":"Al mirar un bono, ¿qué es lo más importante?","options":[{"label":"💰 El tamaño del bono","data":"cm_size"},{"label":"🔄 El wagering","data":"cm_wager"},{"label":"⏰ Tiempo de validez","data":"cm_time"}]},
        "hr":{"text":"Kad gledaš bonus — što je najvažnije?","options":[{"label":"💰 Veličina bonusa","data":"cm_size"},{"label":"🔄 Uvjet klađenja","data":"cm_wager"},{"label":"⏰ Trajanje","data":"cm_time"}]},
        "lt":{"text":"Žiūrint į bonusą — kas svarbiausia?","options":[{"label":"💰 Bonuso dydis","data":"cm_size"},{"label":"🔄 Wagering req.","data":"cm_wager"},{"label":"⏰ Galiojimo laikas","data":"cm_time"}]},
        "lv":{"text":"Skatoties uz bonusu — kas ir svarīgākais?","options":[{"label":"💰 Bonusa apmērs","data":"cm_size"},{"label":"🔄 Wagering req.","data":"cm_wager"},{"label":"⏰ Derīguma laiks","data":"cm_time"}]},
    },
    "nodeposit": {
        "en":{"text":"Have you used a no-deposit bonus before?","options":[{"label":"✅ Yes, a few times","data":"cm_yes_nd"},{"label":"🔰 Once, didn't work","data":"cm_bad_nd"},{"label":"❌ Never tried","data":"cm_never_nd"}]},
        "es":{"text":"¿Has usado alguna vez un bono sin depósito?","options":[{"label":"✅ Sí, varias veces","data":"cm_yes_nd"},{"label":"🔰 Una vez, no funcionó","data":"cm_bad_nd"},{"label":"❌ Nunca lo he probado","data":"cm_never_nd"}]},
        "hr":{"text":"Jesi li ikad koristio bonus bez depozita?","options":[{"label":"✅ Da, nekoliko puta","data":"cm_yes_nd"},{"label":"🔰 Jednom, nije radilo","data":"cm_bad_nd"},{"label":"❌ Nikad nisam probao","data":"cm_never_nd"}]},
        "lt":{"text":"Ar naudojai bonusą be depozito?","options":[{"label":"✅ Taip, kelis kartus","data":"cm_yes_nd"},{"label":"🔰 Kartą, neveikė","data":"cm_bad_nd"},{"label":"❌ Niekada nebandžiau","data":"cm_never_nd"}]},
        "lv":{"text":"Vai esi izmantojis bonusu bez depozīta?","options":[{"label":"✅ Jā, dažas reizes","data":"cm_yes_nd"},{"label":"🔰 Vienreiz, nedarbojās","data":"cm_bad_nd"},{"label":"❌ Nekad nemēģināju","data":"cm_never_nd"}]},
    },
    "exclusive": {
        "en":{"text":"What's your main goal right now?","options":[{"label":"📈 Consistent edge","data":"cm_edge"},{"label":"🎰 Best bonus value","data":"cm_bonus"},{"label":"⚡ The thrill of live","data":"cm_live"}]},
        "es":{"text":"¿Cuál es tu objetivo principal ahora mismo?","options":[{"label":"📈 Ventaja consistente","data":"cm_edge"},{"label":"🎰 Mejor bono","data":"cm_bonus"},{"label":"⚡ La emoción en vivo","data":"cm_live"}]},
        "hr":{"text":"Koji ti je glavni cilj sada?","options":[{"label":"📈 Dosljedna prednost","data":"cm_edge"},{"label":"🎰 Najbolji bonus","data":"cm_bonus"},{"label":"⚡ Uzbuđenje uživo","data":"cm_live"}]},
        "lt":{"text":"Koks dabar tavo pagrindinis tikslas?","options":[{"label":"📈 Pastovi pranašumas","data":"cm_edge"},{"label":"🎰 Geriausias bonusas","data":"cm_bonus"},{"label":"⚡ Gyvų rungtynių adrenalinas","data":"cm_live"}]},
        "lv":{"text":"Kāds ir tavs galvenais mērķis tagad?","options":[{"label":"📈 Stabils pārsvars","data":"cm_edge"},{"label":"🎰 Labākais bonuss","data":"cm_bonus"},{"label":"⚡ Dzīvo spēļu adrenalīns","data":"cm_live"}]},
    },
}

def get_commitment_question(lang: str, interest: str) -> Optional[dict]:
    q = _COMMITMENT_QUESTIONS.get(interest, _COMMITMENT_QUESTIONS["betting"])
    return q.get(lang, q.get("en"))

_CHOICE_MEANINGS = {
    "cm_odds":"tracks odds movement and sharp money","cm_gut":"follows intuition about teams",
    "cm_stats":"data-driven, follows statistics","cm_size":"cares about bonus size",
    "cm_wager":"cares about wagering requirements","cm_time":"cares about bonus validity",
    "cm_yes_nd":"used no-deposit bonuses before","cm_bad_nd":"tried no-deposit, bad experience",
    "cm_never_nd":"never tried no-deposit","cm_edge":"wants consistent betting edge",
    "cm_bonus":"wants best bonus value","cm_live":"loves live betting and adrenaline",
}

async def respond_to_commitment(choice_data: str, lang: str, interest: str, history: list,
                                 psychotype: str="neutral", user_profile: Optional[dict]=None) -> str:
    if not ANTHROPIC_KEY: return _fallback_response(lang, interest, "warming")
    lang_names = {"en":"English","es":"Spanish","hr":"Croatian","lt":"Lithuanian","lv":"Latvian"}
    language = lang_names.get(lang, "English")
    meaning = _CHOICE_MEANINGS.get(choice_data, "made a choice")
    profile_ctx = _build_profile_ctx(user_profile or {})
    system = f"""You are Valeria — private AI companion for betting and bonuses.
User clicked a choice button. Respond naturally, move conversation forward.
Language: {language} ONLY.
User's choice: {meaning}
{profile_ctx}
Rules:
- Acknowledge choice naturally (1 sentence)
- Add one relevant insight about what this reveals
- End with a teasing hint about what's in the channel matching this need
- Max 3 sentences. *bold* one key concept. 1 emoji max.
- NEVER invent specific match names, odds, or bonus amounts."""
    try:
        clean_history = _sanitize_history(history[-6:])
        data = await _post_with_retry(
            ANTHROPIC_URL,
            {"model":MODEL,"max_tokens":200,"system":system,
             "messages":clean_history+[{"role":"user","content":f"[CHOICE: {choice_data}]"}]},
            {"x-api-key":ANTHROPIC_KEY,"anthropic-version":"2023-06-01","content-type":"application/json"},
            timeout=20)
        for block in data.get("content",[]):
            if block.get("type")=="text": return _clean_for_telegram(block["text"].strip())
    except Exception as e:
        logger.error(f"respond_to_commitment error: {e}")
    return _fallback_response(lang, interest, "warming")

# ── Proactive post-subscription hook ─────────────────────────────────────────

async def generate_post_sub_hook(lang: str, interest: str, user_profile: Optional[dict]=None, geo: str="") -> str:
    if not ANTHROPIC_KEY: return _fallback_response(lang, interest, "subscribed")
    # Пробуем получить реальный факт (1 запрос)
    search_context = await _safe_web_search(interest, geo)
    lang_names = {"en":"English","es":"Spanish (Spain, tú)","hr":"Croatian","lt":"Lithuanian","lv":"Latvian"}
    language = lang_names.get(lang, "English")
    ic = {"betting":"sports betting, value bets","casino":"casino bonuses, cashback",
          "nodeposit":"no-deposit bonuses, free spins","exclusive":"arbitrage, value bets, exclusive bonuses"}.get(interest,"betting and bonuses")
    profile_ctx = _build_profile_ctx(user_profile or {})
    search_section = f"Real data: {search_context}" if search_context else f"No data found. Use general insight about {ic} WITHOUT inventing numbers."
    system = f"""You are Valeria — private AI companion. User just subscribed. Write a warm, personal opening — NOT a welcome message.
Language: {language} ONLY.
{profile_ctx}
{search_section}
Rules: Start personal and direct. If real data: lead with fact. If no data: question about their experience.
End with ONE easy question. Max 3 sentences. *bold* only if real data. 1 emoji max.
NEVER invent numbers, teams, or platforms without real data."""
    try:
        data = await _post_with_retry(
            ANTHROPIC_URL,
            {"model":MODEL,"max_tokens":200,"system":system,
             "messages":[{"role":"user","content":"Open the conversation."}]},
            {"x-api-key":ANTHROPIC_KEY,"anthropic-version":"2023-06-01","content-type":"application/json"},
            timeout=25)
        for block in data.get("content",[]):
            if block.get("type")=="text": return _clean_for_telegram(_strip_thinking(block["text"].strip()))
    except Exception as e:
        logger.error(f"generate_post_sub_hook error: {e}")
    return _fallback_response(lang, interest, "subscribed")

# ── Re-engage ─────────────────────────────────────────────────────────────────

async def generate_reengage_message(lang: str, interest: str, user_profile: Optional[dict]=None,
                                     geo: str="", attempt: int=1) -> Optional[str]:
    if not ANTHROPIC_KEY: return None
    search_context = await _safe_web_search(interest, geo)
    if not search_context: return None
    lang_names = {"en":"English","es":"Spanish","hr":"Croatian","lt":"Lithuanian","lv":"Latvian"}
    language = lang_names.get(lang, "English")
    profile_ctx = _build_profile_ctx(user_profile or {})
    tone = "last chance, final nudge" if attempt==2 else "casual, not pushy"
    system = f"""You are Valeria. Write a re-engagement message.
Language: {language} ONLY. Tone: {tone}
{profile_ctx}
Real data: {search_context}
Rules: Open with fact. Make it timely and personal. Soft CTA hint. Max 2-3 sentences. *bold* one key number. 1 emoji max.
DO NOT invent numbers beyond the real data above."""
    try:
        data = await _post_with_retry(
            ANTHROPIC_URL,
            {"model":MODEL,"max_tokens":180,"system":system,
             "messages":[{"role":"user","content":"Write the message."}]},
            {"x-api-key":ANTHROPIC_KEY,"anthropic-version":"2023-06-01","content-type":"application/json"},
            timeout=20)
        for block in data.get("content",[]):
            if block.get("type")=="text":
                result = _clean_for_telegram(_strip_thinking(block["text"].strip()))
                if len(result) > 30: return result
    except Exception as e:
        logger.error(f"generate_reengage_message error: {e}")
    return None

# ── generate_warm_opener — с web-search (только 1 раз при старте) ─────────────

async def generate_warm_opener(lang: str, interest: str, geo: str="",
                                user_profile: Optional[dict]=None) -> str:
    if not ANTHROPIC_KEY: return _fallback_response(lang, interest, "warming")
    # Поиск (1 запрос)
    search_context = await _safe_web_search(interest, geo)
    lang_names = {"en":"English","es":"Spanish (Spain, tú)","hr":"Croatian","lt":"Lithuanian","lv":"Latvian"}
    language = lang_names.get(lang, "English")
    profile_ctx = _build_profile_ctx(user_profile or {})
    if search_context:
        data_section = f"Real data (use as your own insight):\n{search_context}\nDo NOT say where it came from."
    else:
        data_section = f"No real data found. Open with a question about their experience — do NOT invent numbers."
    system = f"""You are Valeria — private AI companion for betting and bonuses.
Open conversation with a new user. One message. Natural. Direct.
{_FEW_SHOT}
Language: {language} ONLY.
{profile_ctx}
{data_section}
Rules:
- Start DIRECTLY with the hook or question
- If real data: lead with fact, end with ONE easy question
- If no data: open with genuine question about their experience
- Max 2-3 sentences. *bold* one key number (only if from real data). 1 emoji max.
- NEVER write "Let me search", "Since today is"
- NEVER invent specific numbers, teams, or bonus amounts."""
    try:
        data = await _post_with_retry(
            ANTHROPIC_URL,
            {"model":MODEL,"max_tokens":200,"system":system,
             "messages":[{"role":"user","content":"Open the conversation."}]},
            {"x-api-key":ANTHROPIC_KEY,"anthropic-version":"2023-06-01","content-type":"application/json"},
            timeout=30)
        for block in data.get("content",[]):
            if block.get("type")=="text":
                result = _clean_for_telegram(_strip_thinking(block["text"].strip()))
                if result: return result
    except Exception as e:
        logger.error(f"generate_warm_opener error: {e}")
    return _fallback_response(lang, interest, "warming")

# ── Fallback responses (safe, no invented data) ───────────────────────────────

def _fallback_response(lang: str, interest: str, funnel_stage: str) -> str:
    fb = {
        "en":{"warming":"There are patterns in how lines move before big matches — most people don't know what to look for. You tracking anything specific or starting fresh?",
              "tease":"The people positioned on the last one like this — they're already on the next. That's what the channel is for. 🔥",
              "cta":"What you're looking for is already in there. The next move gets shared before the market catches up.",
              "subscribed":"Something interesting is developing right now. Want to talk through what you're seeing?"},
        "es":{"warming":"Hay patrones en cómo se mueven las cuotas antes de los partidos — la mayoría no sabe qué buscar. ¿Sigues algo concreto o empiezas desde cero?",
              "tease":"Los que estaban posicionados en el último así — ya están en el siguiente. Para eso es el canal. 🔥",
              "cta":"Lo que buscas ya está ahí. El próximo movimiento se comparte antes de que el mercado reaccione.",
              "subscribed":"Ahora mismo hay algo interesante desarrollándose. ¿Quieres hablar de lo que estás viendo?"},
        "hr":{"warming":"Postoje obrasci u kretanju kvota — većina ne zna što tražiti. Pratiš li nešto konkretno ili počinješ iz nule?",
              "tease":"Oni koji su bili pozicionirani na zadnjem takvom — već su na sljedećem. Za to je kanal. 🔥",
              "cta":"Ono što tražiš već je tamo. Sljedeći potez se dijeli prije nego tržište reagira.",
              "subscribed":"Nešto zanimljivo se razvija upravo sada. Želiš li razgovarati o tome?"},
        "lt":{"warming":"Yra modeliai kaip koeficientai juda prieš svarbias rungtynes — dauguma nežino ko ieškoti. Seki ką nors konkretaus ar pradedi nuo nulio?",
              "tease":"Tie kurie buvo pozicionuoti paskutiniame — jau yra sekančiame. Tam ir yra kanalas. 🔥",
              "cta":"Tai ko ieškai jau yra ten. Kitas žingsnis pasidalijamas prieš rinkai reaguojant.",
              "subscribed":"Dabar kažkas įdomaus vystosi. Nori pakalbėti apie tai, ką matai?"},
        "lv":{"warming":"Ir modeļi kā koeficienti kustas pirms svarīgām spēlēm — lielākā daļa nezina ko meklēt. Tu seko kaut kam konkrētam vai sāc no nulles?",
              "tease":"Tie kas bija pozicionēti pēdējā tādā — jau ir nākamajā. Tādēļ kanāls pastāv. 🔥",
              "cta":"Tas ko meklē jau ir tur. Nākamais gājiens tiek dalīts pirms tirgus reaģē.",
              "subscribed":"Tagad kaut kas interesants attīstās. Gribi runāt par to, ko redzi?"},
    }
    lang_fb = fb.get(lang, fb["en"])
    return lang_fb.get(funnel_stage, lang_fb["warming"])

# ── PUBLIC: ask_valeria — 1 запрос, без web-search в основном цикле ──────────

async def ask_valeria(user_message, history, lang, interest, funnel_stage,
                      stage_replies=0, psychotype="neutral", objections=None,
                      used_techniques=None, geo="", user_profile=None) -> tuple:
    """
    Returns: (response_text, refined_interest, next_stage, technique_used)
    ВАЖНО: только 1 API запрос. Web-search убран из основного цикла.
    """
    objections, used_techniques, user_profile = objections or {}, used_techniques or [], user_profile or {}
    if not ANTHROPIC_KEY: return _fallback_response(lang, interest, funnel_stage), interest, None, None
    headers = {"x-api-key":ANTHROPIC_KEY,"anthropic-version":"2023-06-01","content-type":"application/json"}

    if funnel_stage == "subscribed":
        system = _build_subscribed_prompt(lang, interest, psychotype, objections, user_profile)
        messages_payload = _sanitize_history(history[-12:]) + [{"role":"user","content":user_message}]
        try:
            data  = await _post_with_retry(ANTHROPIC_URL,
                {"model":MODEL,"max_tokens":AI_MAX_TOKENS,"system":system,"messages":messages_payload},
                headers, timeout=25)
            reply = next((b["text"].strip() for b in data.get("content",[]) if b.get("type")=="text"), "")
        except Exception as e:
            logger.error(f"ask_valeria subscribed: {e}"); reply=""
        if not reply: reply = _fallback_response(lang, interest, funnel_stage)
        reply   = _clean_for_telegram(_strip_thinking(reply))
        refined = _detect_interest_shift(user_message, interest) or interest
        return reply, refined, None, None

    # warming / tease / cta — 1 чистый запрос без web-search
    system = _system_prompt(lang, interest, funnel_stage, stage_replies,
                            psychotype, objections, used_techniques, user_profile)
    api_messages = _sanitize_history(history[-10:]) + [{"role":"user","content":user_message}]
    try:
        data = await _post_with_retry(ANTHROPIC_URL,
            {"model":MODEL,"max_tokens":AI_MAX_TOKENS,"system":system,"messages":api_messages},
            headers, timeout=25)
        raw = next((b["text"].strip() for b in data.get("content",[]) if b.get("type")=="text"), "")
        raw = _clean_for_telegram(_strip_thinking(raw))
    except Exception as e:
        logger.error(f"ask_valeria {funnel_stage}: {e}")
        return _fallback_response(lang, interest, funnel_stage), interest, None, None

    if not raw:
        return _fallback_response(lang, interest, funnel_stage), interest, None, None

    # Parse tags
    next_stage = None
    if m := re.search(r"\[NEXT:(\w+)\]", raw):
        if m.group(1) in ("tease","cta"): next_stage = m.group(1)
    raw = re.sub(r"\[NEXT:\w+\]","",raw).strip()
    technique_used = None
    if m3 := re.search(r"\[TECHNIQUE:(\w+)\]", raw):
        technique_used = m3.group(1)
    raw = re.sub(r"\[TECHNIQUE:\w+\]","",raw).strip()
    refined = interest
    if shifted := _detect_interest_shift(user_message, refined): refined = shifted
    if next_stage is None:
        if funnel_stage=="warming" and stage_replies>=3: next_stage="tease"
        elif funnel_stage=="tease" and stage_replies>=2: next_stage="cta"
    return raw, refined, next_stage, technique_used
