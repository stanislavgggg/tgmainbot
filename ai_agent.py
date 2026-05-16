"""
ai_agent.py — OddsVault Bot v14 (cleaned)

Utils-модуль: HTTP retry, history sanitizer, web search, tone/profile helpers.
Все промпты живут в conversation.py и ftd_onboarding.py.

УДАЛЕНО (мёртвый код):
  - ask_valeria()           — заменена ask_valeria_conversational()
  - _system_prompt()        — промпт переехал в conversation.py
  - _build_subscribed_prompt()
  - generate_warm_opener()
  - generate_reengage_message()
  - generate_post_sub_hook()
  - respond_to_commitment() + get_commitment_question() + _COMMITMENT_QUESTIONS
  - _detect_interest_shift() — дублирует detect_interest_from_text()
"""
import asyncio, logging, re, json
from typing import Optional
from datetime import datetime, timezone
import httpx
from config import ANTHROPIC_KEY, AI_MAX_TOKENS

logger = logging.getLogger(__name__)

ANTHROPIC_URL   = "https://api.anthropic.com/v1/messages"
MODEL           = "claude-sonnet-4-20250514"
WEB_SEARCH_TOOL = {"type": "web_search_20250305", "name": "web_search", "max_uses": 1}

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
                    wait = 2 ** attempt
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

# ── Anti-hallucination web search ─────────────────────────────────────────────

def _is_valid_search_result(text: str) -> bool:
    if not text or len(text) < 80: return False
    lower = text.lower()
    if any(m in lower for m in ["no results", "not found", "couldn't find",
                                 "nothing found", "no_data_found"]): return False
    return bool(re.search(r'\d', text))

def _build_search_queries(interest: str, geo: str = "") -> list:
    today = datetime.now(timezone.utc).strftime("%B %Y")
    geo_league = {
        "ES": "La Liga", "HR": "HNL Croatia",
        "LT": "A lyga Lithuania", "LV": "Virsliga Latvia",
    }.get(geo.upper() if geo else "", "European football")
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
    headers = {
        "x-api-key": ANTHROPIC_KEY, "anthropic-version": "2023-06-01",
        "anthropic-beta": "web-search-2025-03-05", "content-type": "application/json",
    }
    payload = {
        "model": MODEL, "max_tokens": 400, "tools": [WEB_SEARCH_TOOL],
        "system": ("Extract ONLY concrete facts from search: team names, odds, bonus amounts, dates. "
                   "If nothing found reply: NO_DATA_FOUND. Never invent. Max 100 words."),
        "messages": [{"role": "user", "content": query}],
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
        role, content = msg.get("role"), msg.get("content", "")
        if role not in ("user", "assistant"): continue
        if role == last_role:
            if sanitized: sanitized[-1]["content"] += "\n" + content
        else:
            sanitized.append({"role": role, "content": content})
            last_role = role
    while sanitized and sanitized[0]["role"] == "assistant":
        sanitized.pop(0)
    return sanitized

# ── Profile / objection context builders ─────────────────────────────────────

def _build_profile_ctx(user_profile: dict) -> str:
    if not user_profile: return ""
    parts = [f"{k}={v}" for k, v in user_profile.items() if v]
    return ("Known: " + "; ".join(parts) + ".") if parts else ""

def _build_obj_summary(objections: dict) -> str:
    if not objections: return ""
    labels = {
        "scam": "scam", "no_money": "no money", "tried_before": "tried before",
        "not_interested": "not interested", "skeptical": "skeptical", "later": "said later",
        "no_trust": "no trust", "dont_understand": "doesn't understand",
        "not_urgent": "not urgent", "already_elsewhere": "already elsewhere",
    }
    parts = [f"{labels.get(k, k)}×{v}" for k, v in objections.items()]
    return "Objections: " + ", ".join(parts) + "."

# ── Tone detector ─────────────────────────────────────────────────────────────

_POS = {"yes", "sí", "si", "taip", "jā", "ok", "bueno", "bien", "super",
        "claro", "naravno", "👍", "🔥", "✅"}
_NEG = {"no", "nope", "ne", "scam", "estafa", "prevara", "😐", "😑", "🤔"}
_SKP = {"duda", "sumnja", "abejonė", "šaubas", "seguro", "siguran",
        "tikras", "prueba", "dokaz"}

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
    already = ", ".join(f"{k}={v}" for k, v in current_profile.items()) or "nothing yet"
    system = ("Extract ONLY: name (first name if introduced), league (team/sport mentioned), "
              "experience (beginner/intermediate/experienced), budget (stake size). "
              "Return valid JSON with NEW fields only. If nothing new: {}. Never invent.")
    try:
        data = await _post_with_retry(
            ANTHROPIC_URL,
            {"model": MODEL, "max_tokens": 60, "system": system,
             "messages": [{"role": "user", "content": f"Known: {already}\nMessage: {user_message}"}]},
            {"x-api-key": ANTHROPIC_KEY, "anthropic-version": "2023-06-01",
             "content-type": "application/json"},
            timeout=8, max_retries=1)
        text = next((b["text"].strip() for b in data.get("content", [])
                     if b.get("type") == "text"), "")
        if not text or text == "{}": return {}
        text = re.sub(r"```json|```", "", text).strip()
        updates = json.loads(text)
        return {k: v for k, v in updates.items()
                if k in {"name", "league", "experience", "budget"}
                and isinstance(v, str) and v}
    except Exception as e:
        logger.debug(f"Profile skip: {e}")
        return {}

# ── Fallback responses (safe, no invented data) ───────────────────────────────

def _fallback_response(lang: str, interest: str, funnel_stage: str) -> str:
    fb = {
        "en": {
            "warming":    "There are patterns in how lines move before big matches — most people don't know what to look for. You tracking anything specific or starting fresh?",
            "tease":      "The people positioned on the last one like this — they're already on the next. That's what the channel is for. 🔥",
            "cta":        "What you're looking for is already in there. The next move gets shared before the market catches up.",
            "subscribed": "Something interesting is developing right now. Want to talk through what you're seeing?",
        },
        "es": {
            "warming":    "Hay patrones en cómo se mueven las cuotas antes de los partidos — la mayoría no sabe qué buscar. ¿Sigues algo concreto o empiezas desde cero?",
            "tease":      "Los que estaban posicionados en el último así — ya están en el siguiente. Para eso es el canal. 🔥",
            "cta":        "Lo que buscas ya está ahí. El próximo movimiento se comparte antes de que el mercado reaccione.",
            "subscribed": "Ahora mismo hay algo interesante desarrollándose. ¿Quieres hablar de lo que estás viendo?",
        },
        "hr": {
            "warming":    "Postoje obrasci u kretanju kvota — većina ne zna što tražiti. Pratiš li nešto konkretno ili počinješ iz nule?",
            "tease":      "Oni koji su bili pozicionirani na zadnjem takvom — već su na sljedećem. Za to je kanal. 🔥",
            "cta":        "Ono što tražiš već je tamo. Sljedeći potez se dijeli prije nego tržište reagira.",
            "subscribed": "Nešto zanimljivo se razvija upravo sada. Želiš li razgovarati o tome?",
        },
        "lt": {
            "warming":    "Yra modeliai kaip koeficientai juda prieš svarbias rungtynes — dauguma nežino ko ieškoti. Seki ką nors konkretaus ar pradedi nuo nulio?",
            "tease":      "Tie kurie buvo pozicionuoti paskutiniame — jau yra sekančiame. Tam ir yra kanalas. 🔥",
            "cta":        "Tai ko ieškai jau yra ten. Kitas žingsnis pasidalijamas prieš rinkai reaguojant.",
            "subscribed": "Dabar kažkas įdomaus vystosi. Nori pakalbėti apie tai, ką matai?",
        },
        "lv": {
            "warming":    "Ir modeļi kā koeficienti kustas pirms svarīgām spēlēm — lielākā daļa nezina ko meklēt. Tu seko kaut kam konkrētam vai sāc no nulles?",
            "tease":      "Tie kas bija pozicionēti pēdējā tādā — jau ir nākamajā. Tādēļ kanāls pastāv. 🔥",
            "cta":        "Tas ko meklē jau ir tur. Nākamais gājiens tiek dalīts pirms tirgus reaģē.",
            "subscribed": "Tagad kaut kas interesants attīstās. Gribi runāt par to, ko redzi?",
        },
    }
    lang_fb = fb.get(lang, fb["en"])
    return lang_fb.get(funnel_stage, lang_fb["warming"])
