"""
ai_agent.py — OddsVault Bot v8
ANTI-HALLUCINATION ARCHITECTURE:
  - _safe_web_search: возвращает реальный факт или None, НИКОГДА не выдумывает
  - Если search = None — fallback без цифр и названий
  - AI получает search_context и явную инструкцию: только то что там есть
  - Профиль пользователя, micro-commitment, proactive hook, re-engage с инфоповодом
"""
import logging, re, json
from typing import Optional
from datetime import datetime, timezone
import httpx
from config import ANTHROPIC_KEY, AI_MAX_TOKENS

logger = logging.getLogger(__name__)
ANTHROPIC_URL     = "https://api.anthropic.com/v1/messages"
MODEL             = "claude-sonnet-4-20250514"
SEARCH_MAX_TOKENS = max(AI_MAX_TOKENS, 1500)
WEB_SEARCH_TOOL   = {"type":"web_search_20250305","name":"web_search","max_uses":2}

_THINKING_RE = re.compile(
    r"(let me (search|look|check|find|craft|create|try)|"
    r"i('ll| will) (search|look|check|find|craft|create|try)|"
    r"i('m| am) (looking|searching|checking)|"
    r"searching for|i need to (find|search|check)|"
    r"since (it'?s|today is|the date|we'?re in)|"
    r"the searches? (aren'?t|isn'?t|didn'?t|have(n'?)?)|"
    r"i('ll| will) (now |just )?generate|"
    r"here'?s? (a|an|the|my) (message|opener|hook|response))",
    re.IGNORECASE)

def _strip_thinking(text: str) -> str:
    if not _THINKING_RE.search(text): return text
    lines = [l for l in text.split("\n") if not _THINKING_RE.search(l)]
    return " ".join(lines).strip()

# ── Anti-hallucination search layer ──────────────────────────────────────────

def _is_valid_search_result(text: str) -> bool:
    if not text or len(text) < 80: return False
    lower = text.lower()
    if any(m in lower for m in ["no results","not found","couldn't find","nothing found"]): return False
    return bool(re.search(r'\d', text))

def _build_search_queries(interest: str, geo: str = "") -> list:
    today = datetime.now(timezone.utc).strftime("%B %Y")
    geo_league = {"ES":"La Liga Primera Division","HR":"HNL Croatia Prva HNL","LT":"A lyga Lithuania","LV":"Virsliga Latvia","EU":"Champions League Europa League"}.get(geo.upper() if geo else "", "European football")
    q = {
        "betting":   [f"{geo_league} football match odds movement {today}", f"value bet odds discrepancy football today {today}"],
        "casino":    [f"casino bonus low wagering offer {today} Europe", f"online casino cashback promo active {today}"],
        "nodeposit": [f"no deposit casino bonus free spins {today}", f"casino free bonus without deposit low wagering {today}"],
        "exclusive": [f"sports arbitrage opportunity odds gap bookmakers {today}", f"football value bet sharp money signal {today}"],
    }
    return q.get(interest, q["betting"])

async def _safe_web_search(interest: str, geo: str = "") -> Optional[str]:
    """Returns real fact string or None. NEVER invents data."""
    if not ANTHROPIC_KEY: return None
    queries = _build_search_queries(interest, geo)
    headers = {"x-api-key":ANTHROPIC_KEY,"anthropic-version":"2023-06-01","anthropic-beta":"web-search-2025-03-05","content-type":"application/json"}
    for query in queries[:2]:
        try:
            payload = {
                "model": MODEL, "max_tokens": 600, "tools": [WEB_SEARCH_TOOL],
                "system": ("You are a data extraction assistant. Search and return ONLY concrete facts: "
                           "team names, odds numbers, bonus amounts, wagering requirements, dates. "
                           "If nothing concrete found, reply exactly: NO_DATA_FOUND. Never invent. Max 150 words."),
                "messages": [{"role":"user","content":query}]
            }
            async with httpx.AsyncClient(timeout=20) as client:
                resp = await client.post(ANTHROPIC_URL, json=payload, headers=headers)
                if resp.status_code != 200: continue
                data = resp.json()
                for block in data.get("content", []):
                    if block.get("type") == "text":
                        result = block["text"].strip()
                        if "NO_DATA_FOUND" in result: break
                        if _is_valid_search_result(result):
                            logger.info(f"Search hit ({len(result)} chars)")
                            return result[:600]
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
VALERIA'S VOICE — STUDY AND MATCH:
USER: tell me about betting
YOU: There's a match this weekend where the line shifted *0.40* in 6 hours — that doesn't happen without sharp money. You tracking specific leagues or just anything that moves? 🎯
USER: is this a scam
YOU: Heard that before. There was a no-deposit bonus last week — *€25, wagering ×8*. Either it worked for 340 people or it didn't. Which part feels off to you?
USER: later
YOU: One thing before you go — line on tomorrow's match just moved *0.30* in the wrong direction. That kind of gap closes in 2 hours. Want me to flag you when the next one opens?
USER: not interested
YOU: Understood. Different angle — there's a value window on a match tomorrow that has nothing to do with bonuses. Line is sitting *0.45* off where sharp books have it. Curious or not?
USER: stop messaging me
YOU: Got it. I'll only reach out if something genuinely unusual comes up. That okay?
"""

_PSYCHOTYPE_TACTIC = {
    "skeptic":  "SKEPTIC: Never argue. One sharp verifiable number. Social proof = specific.",
    "cynic":    "CYNIC: Agree 90% is garbage. One verifiable public fact. 'Check it yourself.'",
    "passive":  "PASSIVE: No pressure. One tiny next step. Simple yes/no question.",
    "curious":  "CURIOUS: Feed curiosity with specifics. Answer + one new fact. Move toward CTA.",
    "neutral":  "NEUTRAL: News-hook. Real fact → gap → channel as access point.",
}

_SEARCH_FRAME = {
    "betting":   "If SEARCH CONTEXT provided: use specific match/odds from it. If NO_DATA: general framing about line movements WITHOUT inventing teams/odds.",
    "casino":    "If SEARCH CONTEXT provided: use specific bonus/wagering from it. If NO_DATA: mention promo this week WITHOUT inventing platform names or amounts.",
    "nodeposit": "If SEARCH CONTEXT provided: use specific free offer from it. If NO_DATA: mention free bonus windows WITHOUT inventing amounts or platform names.",
    "exclusive": "If SEARCH CONTEXT provided: use specific odds gap from it. If NO_DATA: describe general arbitrage concept WITHOUT inventing teams or ROI numbers.",
}

# ── System prompts ────────────────────────────────────────────────────────────

def _build_profile_ctx(user_profile: dict) -> str:
    if not user_profile: return ""
    parts = [f"{k}={v}" for k,v in user_profile.items() if v]
    return ("Known about user: " + "; ".join(parts) + ".") if parts else ""

def _build_obj_summary(objections: dict) -> str:
    if not objections: return ""
    labels = {"scam":"called scam","no_money":"no money","no_time":"no time","tried_before":"tried before","not_interested":"not interested","skeptical":"skeptical","later":"said later"}
    parts = [f"{labels.get(k,k)}×{v}" for k,v in objections.items()]
    return "User objections: " + ", ".join(parts) + "."

def _build_search_section(interest: str, search_context: Optional[str]) -> str:
    rule = _SEARCH_FRAME.get(interest, _SEARCH_FRAME["betting"])
    if search_context:
        return (f"\n\nSEARCH CONTEXT (real data — use it, never reveal source):\n{search_context}\n"
                f"GROUNDING RULE: {rule}")
    return (f"\n\nSEARCH CONTEXT: NO_DATA — nothing found.\n"
            f"GROUNDING RULE: {rule}\n"
            f"CRITICAL: Do NOT invent team names, match scores, odds, or bonus amounts.")

def _system_prompt(lang, interest, funnel_stage, stage_replies=0, psychotype="neutral",
                   objections=None, used_techniques=None, search_context=None, user_profile=None) -> str:
    objections, used_techniques, user_profile = objections or {}, used_techniques or [], user_profile or {}
    lang_map = {"en":"English — casual, direct","es":"Spanish (Spain, casual tú)","hr":"Croatian — direct, warm","lt":"Lithuanian — warm, direct","lv":"Latvian — warm, direct"}
    li = lang_map.get(lang, "English — casual, direct")
    ic = {"betting":"sports betting, value bets, odds analysis","casino":"casino bonuses, wagering, cashback","nodeposit":"no-deposit bonuses, free spins, low-wagering","exclusive":"arbitrage, odds discrepancies, sharp signals"}.get(interest,"betting & bonuses")
    tactic = _PSYCHOTYPE_TACTIC.get(psychotype, _PSYCHOTYPE_TACTIC["neutral"])
    unused = [t for t in ["information_gap","social_proof","cost_of_inaction","pattern_interrupt","soft_takeaway"] if t not in used_techniques]
    tech_hint = f"Preferred technique: {unused[0]}" if unused else ""
    if funnel_stage == "warming":
        sg = (f"WARMING #{stage_replies}. Build curiosity. Lead with real fact (if available), end with ONE question. "
              + ("Add [NEXT:tease] on own line." if stage_replies>=2 else "Add [NEXT:tease] if strong engagement." if stage_replies==1 else "Do NOT add [NEXT:tease]."))
    elif funnel_stage == "tease":
        sg = (f"TEASE #{stage_replies}. Create FOMO. "
              + ("MANDATORY: add [NEXT:cta] on own line." if stage_replies>=1 else "Build urgency, no CTA yet."))
    elif funnel_stage == "cta":
        sg = "CTA. Handle objection, make joining obvious. Max 2 sentences. Button appears automatically."
    else:
        sg = "SUBSCRIBED — FTD mode. Never close conversation. Every reply ends with question or reason to act NOW."
    return f"""You are Valeria — sharp betting & bonus analyst, private AI companion. Real news, not pitches.

{_FEW_SHOT}

════ CONTEXT ════
Language: {li} — write ONLY in this language.
Interest: {ic}
Psychotype: {tactic}
{_build_obj_summary(objections)}
{_build_profile_ctx(user_profile)}
{tech_hint}
Stage: {sg}
{_build_search_section(interest, search_context)}

════ HARD RULES ════
NEVER invent: team names, match scores, odds, bonus amounts, wagering numbers, platform names.
NEVER show reasoning: no "Let me search", "I'll look", "Since today is".
NEVER close conversation. NEVER say goodbye.
Max 3 sentences. *bold* key numbers (only from real data). 1 emoji max.
Every reply ends with: question, new fact, or reason to act NOW.

Funnel tags (own line at END only):
  [NEXT:tease]  [NEXT:cta]  [TECHNIQUE:name]"""

def _build_subscribed_prompt(lang, interest, psychotype, objections=None, used_techniques=None, search_context=None, user_profile=None) -> str:
    objections, user_profile = objections or {}, user_profile or {}
    lang_names = {"en":"English","es":"Spanish","hr":"Croatian","lt":"Lithuanian","lv":"Latvian"}
    language = lang_names.get(lang, "English")
    ic = {"betting":"sports betting, value bets, odds movements","casino":"casino bonuses, wagering, cashback","nodeposit":"no-deposit bonuses, free spins","exclusive":"value bets, bonuses, arbitrage"}.get(interest,"betting & bonuses")
    pi = {"cynic":"Lead with verifiable facts. Acknowledge skepticism.","skeptic":"Specific numbers, social proof. Show don't tell.","passive":"Very short. One simple question. No pressure.","curious":"Real depth. Pull toward FTD with specific opportunity.","neutral":"News-hook → gap → action."}.get(psychotype,"Direct and useful.")
    return f"""You are Valeria — insider analyst, private AI companion.
User is SUBSCRIBED. Goal: first deposit (FTD), then repeat.

LANGUAGE: {language} only. Never switch.
NEVER: write "Let me search", show reasoning, mention being AI, promise profits, close conversation, invent team names/odds/amounts.
PERSONALITY: Smart friend, not a bot. Warm but direct. Max 4 sentences.
USER INTEREST: {ic}
PSYCHOTYPE: {pi}
{_build_obj_summary(objections)}
{_build_profile_ctx(user_profile)}
{_build_search_section(interest, search_context)}

RULE: Max 180 words. End with question OR next step. NEVER close conversation."""

# ── Extract text / clean ──────────────────────────────────────────────────────

def _extract_text(blocks: list) -> str:
    return "\n".join(b.get("text","") for b in blocks if b.get("type")=="text").strip()

def _clean_for_telegram(text: str) -> str:
    text = re.sub(r'\*\*(.+?)\*\*', r'*\1*', text)
    text = re.sub(r'\.\n([a-z])', r'. \1', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()

# ── Search loop ───────────────────────────────────────────────────────────────

async def _run_with_search(system, messages, headers, max_loops=3) -> str:
    payload = {"model":MODEL,"max_tokens":SEARCH_MAX_TOKENS,"system":system,"tools":[WEB_SEARCH_TOOL],"messages":messages}
    last_content = []
    async with httpx.AsyncClient(timeout=40) as client:
        for _ in range(max_loops):
            resp = await client.post(ANTHROPIC_URL, json=payload, headers=headers)
            if resp.status_code != 200:
                logger.error(f"Anthropic API error {resp.status_code}: {resp.text[:300]}")
                resp.raise_for_status()
            data = resp.json()
            stop_reason, last_content = data.get("stop_reason"), data.get("content",[])
            if stop_reason == "end_turn": return _strip_thinking(_extract_text(last_content))
            if stop_reason == "max_tokens":
                partial = _extract_text(last_content)
                if partial:
                    payload["messages"] = payload["messages"] + [{"role":"assistant","content":last_content},{"role":"user","content":"Continue."}]
                    continue
                return _strip_thinking(partial)
            return _strip_thinking(_extract_text(last_content))
    return _strip_thinking(_extract_text(last_content))

# ── Interest shift ────────────────────────────────────────────────────────────

def _detect_interest_shift(text: str, current: str) -> Optional[str]:
    t = text.lower()
    if current!="casino"    and any(s in t for s in ["casino","slot","roulette","blackjack","bonus","free spins","bonos","kazino"]): return "casino"
    if current!="betting"   and any(s in t for s in ["bet","odds","match","football","soccer","sport","league","apuesta","cuota","klađenje","kvota","lažybos"]): return "betting"
    if current!="nodeposit" and any(s in t for s in ["no deposit","free","without deposit","sin depósito","bez depozita","be depozito","bez depozīta"]): return "nodeposit"
    return None

# ── Tone detector ─────────────────────────────────────────────────────────────

_POS = {"yes","sí","si","taip","jā","ok","bueno","bien","super","genial","odlično","puiku","lieliski","interesante","claro","naravno","žinoma","protams","👍","🔥","💎","✅"}
_NEG = {"no","nope","ne","scam","estafa","prevara","krāpšana","apgaulė","😐","😑","🤔"}
_SKP = {"duda","sumnja","abejonė","šaubas","seguro","siguran","tikras","drošs","prueba","dokaz"}

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
    """Silent profile extraction. Returns only new/changed fields."""
    if not ANTHROPIC_KEY or len(user_message) < 5: return {}
    already = ", ".join(f"{k}={v}" for k,v in current_profile.items()) or "nothing yet"
    system = """Extract from user message ONLY these fields if explicitly mentioned:
- name: their first name (if they introduce themselves)
- league: favourite football league, team, or sport
- experience: "beginner", "intermediate", or "experienced" based on knowledge shown
- budget: stake size if mentioned (e.g. "€10-50", "small", "€100+")
Respond ONLY with valid JSON. Only NEW or CHANGED fields vs already known.
If nothing new: respond exactly {}. Never invent data."""
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            resp = await client.post(ANTHROPIC_URL,
                json={"model":MODEL,"max_tokens":80,"system":system,
                      "messages":[{"role":"user","content":f"Already known: {already}\nMessage: {user_message}"}]},
                headers={"x-api-key":ANTHROPIC_KEY,"anthropic-version":"2023-06-01","content-type":"application/json"})
        if resp.status_code != 200: return {}
        text = ""
        for block in resp.json().get("content",[]):
            if block.get("type")=="text": text=block["text"].strip(); break
        if not text or text=="{}": return {}
        text = re.sub(r"```json|```","",text).strip()
        updates = json.loads(text)
        allowed = {"name","league","experience","budget"}
        return {k:v for k,v in updates.items() if k in allowed and isinstance(v,str) and v}
    except Exception as e:
        logger.debug(f"Profile extraction skipped: {e}")
        return {}

# ── Micro-commitment questions (safe — no real data needed) ───────────────────

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
        "en":{"text":"Have you ever used a no-deposit bonus before?","options":[{"label":"✅ Yes, a few times","data":"cm_yes_nd"},{"label":"🔰 Once, didn't work","data":"cm_bad_nd"},{"label":"❌ Never tried","data":"cm_never_nd"}]},
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

# ── Respond to commitment choice ──────────────────────────────────────────────

_CHOICE_MEANINGS = {
    "cm_odds":"tracks odds movement and sharp money signals","cm_gut":"follows intuition about teams",
    "cm_stats":"data-driven, follows statistics and form","cm_size":"cares most about bonus size",
    "cm_wager":"cares most about wagering requirements","cm_time":"cares about bonus validity period",
    "cm_yes_nd":"has used no-deposit bonuses, some experience","cm_bad_nd":"tried no-deposit once, bad experience (probably high wagering)",
    "cm_never_nd":"never tried no-deposit, curious but new to it","cm_edge":"wants consistent betting edge",
    "cm_bonus":"wants best bonus value","cm_live":"loves live betting and adrenaline",
}

async def respond_to_commitment(choice_data: str, lang: str, interest: str, history: list, psychotype: str="neutral", user_profile: Optional[dict]=None) -> str:
    if not ANTHROPIC_KEY: return _fallback_response(lang, interest, "warming")
    lang_names = {"en":"English","es":"Spanish","hr":"Croatian","lt":"Lithuanian","lv":"Latvian"}
    language = lang_names.get(lang, "English")
    meaning = _CHOICE_MEANINGS.get(choice_data, "made a choice")
    profile_ctx = _build_profile_ctx(user_profile or {})
    system = f"""You are Valeria — private AI companion for betting and bonuses.
User just clicked a choice. Respond naturally and move conversation forward (warming stage).
Language: {language} ONLY.
User's choice means: {meaning}
{profile_ctx}
Rules:
- Acknowledge choice naturally (1 sentence) — don't just repeat it back
- Add one relevant insight about what this reveals or what it means for them
- End with a teasing hint about what's in the channel that matches this need exactly
- Max 3 sentences. *bold* one key concept. 1 emoji max.
- NEVER invent specific match names, odds numbers, or bonus amounts without real data.
- Do NOT add [NEXT:...] tags."""
    try:
        clean_history = _sanitize_history(history[-6:])
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(ANTHROPIC_URL,
                json={"model":MODEL,"max_tokens":200,"system":system,
                      "messages":clean_history+[{"role":"user","content":f"[CHOICE: {choice_data}]"}]},
                headers={"x-api-key":ANTHROPIC_KEY,"anthropic-version":"2023-06-01","content-type":"application/json"})
        if resp.status_code == 200:
            for block in resp.json().get("content",[]):
                if block.get("type")=="text": return _clean_for_telegram(block["text"].strip())
    except Exception as e:
        logger.error(f"respond_to_commitment error: {e}")
    return _fallback_response(lang, interest, "warming")

# ── Proactive post-subscription hook ─────────────────────────────────────────

async def generate_post_sub_hook(lang: str, interest: str, user_profile: Optional[dict]=None, geo: str="") -> str:
    if not ANTHROPIC_KEY: return _fallback_response(lang, interest, "subscribed")
    search_context = await _safe_web_search(interest, geo)
    lang_names = {"en":"English","es":"Spanish","hr":"Croatian","lt":"Lithuanian","lv":"Latvian"}
    language = lang_names.get(lang, "English")
    ic = {"betting":"sports betting, value bets","casino":"casino bonuses, cashback","nodeposit":"no-deposit bonuses, free spins","exclusive":"arbitrage, value bets, exclusive bonuses"}.get(interest,"betting and bonuses")
    profile_ctx = _build_profile_ctx(user_profile or {})
    search_section = _build_search_section(interest, search_context)
    system = f"""You are Valeria — private AI companion. User just subscribed to the channel.
Write a warm, personal opening message — NOT a welcome. Valeria is reaching out proactively after 2 minutes.
Language: {language} ONLY.
User interest: {ic}
{profile_ctx}
{search_section}
Rules:
- Start personal and direct — NOT "welcome" or "congratulations"
- If real search data: lead with one specific fact as a hook
- If NO_DATA: open with a question about THEIR experience or preference
- End with ONE easy question that invites reply
- Max 3 sentences. *bold* key numbers (only if from real data). 1 emoji max.
- NEVER invent specific match names, odds, or exact bonus amounts without real data."""
    try:
        async with httpx.AsyncClient(timeout=25) as client:
            resp = await client.post(ANTHROPIC_URL,
                json={"model":MODEL,"max_tokens":250,"system":system,"messages":[{"role":"user","content":"Open the conversation."}]},
                headers={"x-api-key":ANTHROPIC_KEY,"anthropic-version":"2023-06-01","content-type":"application/json"})
        if resp.status_code == 200:
            for block in resp.json().get("content",[]):
                if block.get("type")=="text": return _clean_for_telegram(_strip_thinking(block["text"].strip()))
    except Exception as e:
        logger.error(f"generate_post_sub_hook error: {e}")
    return _fallback_response(lang, interest, "subscribed")

# ── Re-engage with real news hook ─────────────────────────────────────────────

async def generate_reengage_message(lang: str, interest: str, user_profile: Optional[dict]=None, geo: str="", attempt: int=1) -> Optional[str]:
    """Returns message with real fact, or None if no real data found."""
    if not ANTHROPIC_KEY: return None
    search_context = await _safe_web_search(interest, geo)
    if not search_context: return None  # no data → use static fallback
    lang_names = {"en":"English","es":"Spanish","hr":"Croatian","lt":"Lithuanian","lv":"Latvian"}
    language = lang_names.get(lang, "English")
    profile_ctx = _build_profile_ctx(user_profile or {})
    tone = "last chance, final nudge" if attempt==2 else "casual, not pushy"
    system = f"""You are Valeria — private AI companion. Write a re-engagement message.
User hasn't joined the channel yet. Make them want to come back.
Language: {language} ONLY. Tone: {tone}
{profile_ctx}
Real data to use as hook (use naturally, never mention source):
{search_context}
Rules:
- Open with the real fact — NOT "hey" or "hi"
- Make it feel timely and personal, not broadcast
- End with softest possible CTA — hint, not push
- Max 2-3 sentences. *bold* one key number from real data. 1 emoji max.
- DO NOT invent any numbers or names beyond what's in the real data above."""
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(ANTHROPIC_URL,
                json={"model":MODEL,"max_tokens":200,"system":system,"messages":[{"role":"user","content":"Write the message."}]},
                headers={"x-api-key":ANTHROPIC_KEY,"anthropic-version":"2023-06-01","content-type":"application/json"})
        if resp.status_code == 200:
            for block in resp.json().get("content",[]):
                if block.get("type")=="text":
                    result = _clean_for_telegram(_strip_thinking(block["text"].strip()))
                    if len(result) > 30: return result
    except Exception as e:
        logger.error(f"generate_reengage_message error: {e}")
    return None

# ── generate_warm_opener ──────────────────────────────────────────────────────

async def generate_warm_opener(lang: str, interest: str, geo: str="", user_profile: Optional[dict]=None) -> str:
    if not ANTHROPIC_KEY: return _fallback_response(lang, interest, "warming")
    search_context = await _safe_web_search(interest, geo)
    lang_names = {"en":"English","es":"Spanish (Spain, casual tú)","hr":"Croatian","lt":"Lithuanian","lv":"Latvian"}
    language = lang_names.get(lang, "English")
    profile_ctx = _build_profile_ctx(user_profile or {})
    search_section = _build_search_section(interest, search_context)
    system = f"""You are Valeria — private AI companion for betting and bonuses.
Open conversation with a new user. One message. Natural. Direct.
{_FEW_SHOT}
Language: {language} ONLY.
{profile_ctx}
{search_section}
Rules:
- If real data: lead with fact as your own insight, end with ONE easy question
- If NO_DATA: open with genuine question about their experience (no invented facts)
- Max 2-3 sentences. *bold* one key number (only if from real data). 1 emoji max.
- NEVER write "Let me search", "I'll look", "Since today is", "Here's a message"
- NEVER invent specific match names, scores, odds, or bonus amounts."""
    headers = {"x-api-key":ANTHROPIC_KEY,"anthropic-version":"2023-06-01","anthropic-beta":"web-search-2025-03-05","content-type":"application/json"}
    try:
        result = await _run_with_search(system, [{"role":"user","content":"Open the conversation."}], headers)
        cleaned = _clean_for_telegram(result)
        return cleaned if cleaned else _fallback_response(lang, interest, "warming")
    except Exception as e:
        logger.error(f"generate_warm_opener error: {e}")
        return _fallback_response(lang, interest, "warming")

# ── Fallback (safe — no invented data) ───────────────────────────────────────

def _fallback_response(lang: str, interest: str, funnel_stage: str) -> str:
    fb = {
        "en":{"warming":"There are patterns in how lines move before big matches — most people don't know what to look for. You tracking anything specific or starting fresh?","tease":"The people positioned on the last one like this — they're already on the next. That's what the channel is for. 🔥","cta":"What you're looking for is already in there. The next move gets shared before the market catches up.","subscribed":"Something interesting is developing right now. Want to talk through what you're seeing?"},
        "es":{"warming":"Hay patrones en cómo se mueven las cuotas antes de los partidos — la mayoría no sabe qué buscar. ¿Sigues algo concreto o empiezas desde cero?","tease":"Los que estaban posicionados en el último así — ya están en el siguiente. Para eso es el canal. 🔥","cta":"Lo que buscas ya está ahí. El próximo movimiento se comparte antes de que el mercado reaccione.","subscribed":"Ahora mismo hay algo interesante desarrollándose. ¿Quieres hablar de lo que estás viendo?"},
        "hr":{"warming":"Postoje obrasci u kretanju kvota prije velikih utakmica — većina ne zna što tražiti. Pratiš li nešto konkretno ili počinješ iz nule?","tease":"Oni koji su bili pozicionirani na zadnjem takvom — već su na sljedećem. Za to je kanal. 🔥","cta":"Ono što tražiš već je tamo. Sljedeći potez se dijeli prije nego tržište reagira.","subscribed":"Nešto zanimljivo se razvija upravo sada. Želiš li razgovarati o tome?"},
        "lt":{"warming":"Yra modeliai kaip koeficientai juda prieš svarbias rungtynes — dauguma nežino ko ieškoti. Seki ką nors konkretaus ar pradedi nuo nulio?","tease":"Tie kurie buvo pozicionuoti paskutiniame tokiame — jau yra sekančiame. Tam ir yra kanalas. 🔥","cta":"Tai ko ieškai jau yra ten. Kitas žingsnis pasidalijamas prieš rinkai reaguojant.","subscribed":"Dabar kažkas įdomaus vystosi. Nori pakalbėti apie tai, ką matai?"},
        "lv":{"warming":"Ir modeļi kā koeficienti kustas pirms svarīgām spēlēm — lielākā daļa nezina ko meklēt. Tu seko kaut kam konkrētam vai sāc no nulles?","tease":"Tie kas bija pozicionēti pēdējā tādā — jau ir nākamajā. Tādēļ kanāls pastāv. 🔥","cta":"Tas ko meklē jau ir tur. Nākamais gājiens tiek dalīts pirms tirgus reaģē.","subscribed":"Tagad kaut kas interesants attīstās. Gribi runāt par to, ko redzi?"},
    }
    lang_fb = fb.get(lang, fb["en"])
    return lang_fb.get(funnel_stage, lang_fb["warming"])

# ── PUBLIC: ask_valeria ───────────────────────────────────────────────────────

async def ask_valeria(user_message, history, lang, interest, funnel_stage,
                      stage_replies=0, psychotype="neutral", objections=None,
                      used_techniques=None, geo="", user_profile=None) -> tuple:
    objections, used_techniques, user_profile = objections or {}, used_techniques or [], user_profile or {}
    if not ANTHROPIC_KEY: return _fallback_response(lang, interest, funnel_stage), interest, None, None
    headers_base = {"x-api-key":ANTHROPIC_KEY,"anthropic-version":"2023-06-01","content-type":"application/json"}

    if funnel_stage == "subscribed":
        search_context = await _safe_web_search(interest, geo)
        system = _build_subscribed_prompt(lang, interest, psychotype, objections, used_techniques, search_context, user_profile)
        messages_payload = _sanitize_history(history[-12:]) + [{"role":"user","content":user_message}]
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(ANTHROPIC_URL, json={"model":MODEL,"max_tokens":AI_MAX_TOKENS,"system":system,"messages":messages_payload}, headers=headers_base)
                resp.raise_for_status()
                reply = ""
                for block in resp.json().get("content",[]):
                    if block.get("type")=="text": reply=block["text"].strip(); break
        except Exception as e:
            logger.error(f"ask_valeria subscribed error: {e}"); reply=""
        if not reply: reply = _fallback_response(lang, interest, funnel_stage)
        reply = _clean_for_telegram(_strip_thinking(reply))
        refined = _detect_interest_shift(user_message, interest) or interest
        return reply, refined, None, None

    # warming / tease / cta
    search_context = await _safe_web_search(interest, geo)
    system = _system_prompt(lang, interest, funnel_stage, stage_replies, psychotype, objections, used_techniques, search_context, user_profile)
    api_messages   = _sanitize_history(history[-10:]) + [{"role":"user","content":user_message}]
    headers_search = {**headers_base,"anthropic-beta":"web-search-2025-03-05"}
    try:
        raw = _clean_for_telegram(await _run_with_search(system, api_messages, headers_search))
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP {e.response.status_code}"); return _fallback_response(lang, interest, funnel_stage), interest, None, None
    except Exception as e:
        logger.error(f"ask_valeria error: {e}"); return _fallback_response(lang, interest, funnel_stage), interest, None, None

    next_stage = None
    if m := re.search(r"\[NEXT:(\w+)\]", raw):
        if m.group(1) in ("tease","cta"): next_stage = m.group(1)
    raw = re.sub(r"\[NEXT:\w+\]","",raw).strip()
    refined = interest
    if m2 := re.search(r"\[INTEREST:(\w+)\]", raw):
        if m2.group(1) in ("betting","casino","nodeposit","exclusive"): refined = m2.group(1)
    raw = re.sub(r"\[INTEREST:\w+\]","",raw).strip()
    technique_used = None
    if m3 := re.search(r"\[TECHNIQUE:(\w+)\]", raw):
        technique_used = m3.group(1)
    raw = re.sub(r"\[TECHNIQUE:\w+\]","",raw).strip()
    if shifted := _detect_interest_shift(user_message, refined): refined = shifted
    if next_stage is None:
        if funnel_stage=="warming" and stage_replies>=3: next_stage="tease"
        elif funnel_stage=="tease" and stage_replies>=2: next_stage="cta"
    return raw, refined, next_stage, technique_used
