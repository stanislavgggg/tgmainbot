"""
conversation.py — OddsVault Bot v14

Диалоговый flow вместо кнопок-анкет.
Валерия ведёт живой разговор — определяет interest и GEO из слов пользователя.

ПРИНЦИП:
  Никаких кнопок до CTA. Всё через текст.
  Валерия задаёт один вопрос → слушает → реагирует → следующий вопрос.
  Interest и GEO определяются из разговора, не из нажатий.

FLOW ДО ПОДПИСКИ:
  /start → HOOK (фото + текст) → открытый вопрос
  Юзер отвечает → AI детектирует interest+GEO из ответа → warming
  warming (2-3 обмена) → tease → CTA

FLOW ПОСЛЕ ПОДПИСКИ (диалог, не рассылка):
  POST_SUB → Валерия задаёт первый вопрос об опыте
  Юзер отвечает → AI ведёт к FTD естественно
  Если молчат >4ч → один точечный пуш (не серия)
  Если отвечают → продолжаем разговор, не прерываем таймерами
"""

import asyncio
import logging
import re
from typing import Optional

from ai_agent import (
    _post_with_retry, _build_profile_ctx, _build_obj_summary,
    ANTHROPIC_URL, MODEL, ANTHROPIC_KEY,
    _sanitize_history, _fallback_response,
    _safe_web_search, _clean_for_telegram, _strip_thinking,
)

logger = logging.getLogger(__name__)

# ════════════════════════════════════════════════════════════════════════════
#  ОТКРЫВАЮЩИЙ ВОПРОС — первое что Валерия пишет после фото
#  Заменяет QUIZ кнопки. Открытый, провокационный, без анкеты.
# ════════════════════════════════════════════════════════════════════════════

OPENING_QUESTION: dict[str, str] = {
    "en": (
        "Quick question before I let you in — "
        "how did you end up here? Recommendation or you found it yourself? 🎯"
    ),
    "es": (
        "Pregunta rápida antes de dejarte pasar — "
        "¿cómo llegaste aquí? ¿Recomendación o lo encontraste tú mismo? 🎯"
    ),
    "hr": (
        "Brzo pitanje prije nego te pustim unutra — "
        "kako si završio ovdje? Preporuka ili si sam pronašao? 🎯"
    ),
    "lt": (
        "Greitas klausimas prieš praleisdama tave — "
        "kaip čia atsidūrei? Rekomendacija ar pats radai? 🎯"
    ),
    "lv": (
        "Ātrs jautājums pirms ielaižu tevi iekšā — "
        "kā tu šeit nokļuvi? Ieteikums vai pats atradai? 🎯"
    ),
}

# ════════════════════════════════════════════════════════════════════════════
#  ДЕТЕКТОР INTEREST ИЗ СВОБОДНОГО ТЕКСТА
# ════════════════════════════════════════════════════════════════════════════

_INTEREST_SIGNALS: dict[str, list[str]] = {
    "betting": [
        "bet", "odds", "match", "football", "soccer", "sport", "league",
        "stake", "tipster", "prediction", "apuesta", "cuota", "partido",
        "klađenje", "kvota", "utakmica", "lažybos", "koeficient", "likmes",
        "la liga", "premier", "champions", "bundesliga", "serie a",
        "ставки", "коэффициент", "матч",
    ],
    "casino": [
        "casino", "slot", "roulette", "blackjack", "spin", "bonus",
        "wagering", "cashback", "live", "table", "kazino", "bonusas",
        "spēle", "slotovi", "bonos", "ruleta",
    ],
    "nodeposit": [
        "free", "no deposit", "without deposit", "sin depósito",
        "bez depozita", "be depozito", "bez depozīta", "freebie",
        "gratis", "nemokamas", "bezmaksas", "besplatno",
    ],
    "exclusive": [
        "arbitrage", "arb", "value", "edge", "ev", "sharp", "both",
        "all", "everything", "combined", "mix", "arbitražas",
        "всё", "комбо",
    ],
}

def detect_interest_from_text(text: str) -> Optional[str]:
    """Определяет interest из свободного текста пользователя."""
    lower = text.lower()
    scores: dict[str, int] = {i: 0 for i in _INTEREST_SIGNALS}
    for interest, signals in _INTEREST_SIGNALS.items():
        for s in signals:
            if s in lower:
                scores[interest] += 1
    best = max(scores, key=lambda k: scores[k])
    return best if scores[best] > 0 else None


# ════════════════════════════════════════════════════════════════════════════
#  ДЕТЕКТОР GEO ИЗ СВОБОДНОГО ТЕКСТА
# ════════════════════════════════════════════════════════════════════════════

_GEO_SIGNALS: dict[str, list[str]] = {
    "ES": [
        "spain", "españa", "espana", "spanish", "español", "madrid",
        "barcelona", "sevilla", "valencia", "bilbao", "la liga",
        "primera division", "atletico",
    ],
    "HR": [
        "croatia", "hrvatska", "croatian", "zagreb", "split",
        "dubrovnik", "rijeka", "hnl", "dinamo", "hajduk",
    ],
    "RS": [
        "serbia", "srbija", "serbian", "belgrade", "beograd",
        "novi sad", "bosnia", "balkan", "makedoni", "crna gora",
        "slovenija", "slovenia",
    ],
    "LT": [
        "lithuania", "lietuva", "lithuanian", "vilnius", "kaunas",
        "klaipeda", "a lyga",
    ],
    "LV": [
        "latvia", "latvija", "latvian", "riga", "daugavpils",
        "virsliga",
    ],
}

def detect_geo_from_text(text: str) -> Optional[str]:
    """Определяет GEO из свободного текста."""
    lower = text.lower()
    for geo, signals in _GEO_SIGNALS.items():
        if any(s in lower for s in signals):
            return geo
    return None


# ════════════════════════════════════════════════════════════════════════════
#  ГЛАВНАЯ ФУНКЦИЯ ДИАЛОГА — ask_valeria_conversational
#  Один AI вызов. Знает весь контекст. Ведёт естественный разговор.
# ════════════════════════════════════════════════════════════════════════════

async def ask_valeria_conversational(
    user_message: str,
    history: list,
    lang: str,
    interest: Optional[str],
    geo: Optional[str],
    funnel_stage: str,        # "discovery" | "warming" | "subscribed"
    psychotype: str = "neutral",
    user_profile: Optional[dict] = None,
    objections: Optional[dict] = None,
    ftd_done: bool = False,
    ftd_count: int = 0,
    search_context: Optional[str] = None,
) -> dict:
    """
    Главная функция диалога. Возвращает dict:
    {
      "text": str,                    — ответ Валерии
      "detected_interest": str|None, — если определила interest из ответа
      "detected_geo": str|None,      — если определила GEO из ответа
      "next_stage": str|None,        — "tease" | "cta" | None
      "move_to_tease": bool,
      "move_to_cta": bool,
    }
    """
    user_profile = user_profile or {}
    objections   = objections or {}

    if not ANTHROPIC_KEY:
        return {
            "text":              _fallback_response(lang, interest or "betting", funnel_stage),
            "detected_interest": None,
            "detected_geo":      None,
            "next_stage":        None,
            "move_to_tease":     False,
            "move_to_cta":       False,
        }

    # Детектируем interest и GEO из текста пользователя прямо здесь
    detected_interest = detect_interest_from_text(user_message) if not interest else None
    detected_geo      = detect_geo_from_text(user_message) if not geo or geo == "OTHER" else None

    effective_interest = interest or detected_interest or "betting"
    effective_geo      = (detected_geo or geo or "OTHER")

    lang_names = {
        "en": "English — casual, direct",
        "es": "Spanish (Spain, casual tú)",
        "hr": "Croatian — warm, direct",
        "lt": "Lithuanian — warm, direct",
        "lv": "Latvian — warm, direct",
    }
    language = lang_names.get(lang, "English — casual, direct")

    interest_ctx = {
        "betting":   "sports betting, value bets, odds movements, line analysis",
        "casino":    "casino bonuses, wagering math, RTP, cashback",
        "nodeposit": "no-deposit bonuses, free spins, zero-risk entry",
        "exclusive": "arbitrage, value bets, bonus EV, combined strategy",
    }.get(effective_interest, "betting & bonuses")

    psychotype_instr = {
        "cynic":   "CYNIC: One verifiable fact only. No pitch.",
        "skeptic": "SKEPTIC: Specific numbers, social proof.",
        "passive": "PASSIVE: One tiny step. Dead simple.",
        "curious": "CURIOUS: Real depth. Pull toward action.",
        "neutral": "NEUTRAL: Hook → gap → next step.",
    }.get(psychotype, "NEUTRAL: Hook → gap → next step.")

    # Контекст поиска
    search_section = ""
    if search_context:
        search_section = (
            f"\nReal market data (use naturally, never cite source):\n{search_context}"
        )
    else:
        search_section = (
            f"\nNo real-time data available. Use general patterns about {interest_ctx} "
            "WITHOUT inventing specific team names, odds, or bonus amounts."
        )

    # Инструкции по стадии
    if funnel_stage == "discovery":
        stage_instr = """DISCOVERY — user just started talking. You don't know their interest yet.
Goals:
1. Respond naturally to what they said
2. Ask ONE question that uncovers their interest (betting vs casino vs nodeposit)
3. If they mention a country/league — note it, use it
4. Keep it conversational — this is a chat, not a form
5. DO NOT ask about language or country explicitly — pick it up from context
6. Add [READY:warming] on its own line when you've identified their interest (after 1-2 exchanges)"""

    elif funnel_stage == "warming":
        stage_instr = f"""WARMING — you know their interest: {effective_interest}
Goals:
1. Build genuine curiosity about what's in the channel
2. Use real data (from search context) or compelling patterns
3. Ask questions that reveal MORE about their situation (experience, typical stake, goals)
4. Each reply should feel like you're learning about THEM, not selling
5. After 2-3 good exchanges → add [READY:tease] on its own line"""

    else:  # subscribed
        if ftd_done:
            stage_instr = f"""SUBSCRIBED — user has made {ftd_count} deposit(s). FTD done.
Goals: Keep them active, push toward repeat deposit, optimize their strategy.
Treat them as an active participant. Give real practical advice.
Ask about their actual results. Help them make the next move."""
        else:
            stage_instr = f"""SUBSCRIBED — user hasn't deposited yet.
Goal: FIRST DEPOSIT. Every reply moves toward this.
Be specific about what they're missing. Don't be soft.
Make inaction feel expensive, action feel obvious.
Address their specific words — don't repeat yourself."""

    system = f"""You are Valeria — private AI companion for betting and bonuses.
You are having a REAL CONVERSATION. Not running a script. Not a chatbot.

LANGUAGE: {language} — write ONLY in this language. Detect from context, never ask.
INTEREST: {interest_ctx}
GEO context: {effective_geo}
PSYCHOTYPE: {psychotype_instr}
{_build_obj_summary(objections)}
{_build_profile_ctx(user_profile)}
{search_section}

STAGE: {stage_instr}

━━━ CONVERSATION RULES ━━━
- Read what they actually wrote. Respond to IT specifically.
- Mirror their tone: short reply → short answer. Long → match depth.
- ONE question per reply. Never two.
- If they're skeptical: don't argue. Validate → pivot.
- If they say "no money": immediately offer no-deposit path.
- If they're vague: ask one clarifying question, don't assume.
- NEVER repeat your previous message.
- NEVER close conversation. NEVER say goodbye.
- Max 3 sentences (4 if genuinely needed). *bold* 1 key thing. 1 emoji max.

━━━ FORBIDDEN ━━━
- Never say "I'm an AI" or reference being a bot
- Never promise profits or guaranteed results
- Never invent specific match names, exact odds, or exact bonus amounts without real data
- Never sound like marketing copy
- Never start with "Great!", "Absolutely!", "Of course!"

━━━ HIDDEN TAGS (invisible to user, on own line at END) ━━━
[READY:warming]  — you've learned their interest, ready to warm
[READY:tease]    — warming complete, ready to tease
[INTEREST:xxx]   — detected interest (betting/casino/nodeposit/exclusive)
[GEO:xx]         — detected geo (ES/HR/RS/LT/LV)"""

    try:
        clean_history = _sanitize_history(history[-14:])
        messages = clean_history + [{"role": "user", "content": user_message}]

        data = await _post_with_retry(
            ANTHROPIC_URL,
            {
                "model":      MODEL,
                "max_tokens": 350,
                "system":     system,
                "messages":   messages,
            },
            {
                "x-api-key":         ANTHROPIC_KEY,
                "anthropic-version": "2023-06-01",
                "content-type":      "application/json",
            },
            timeout=25,
        )
        raw = next(
            (b["text"].strip() for b in data.get("content", []) if b.get("type") == "text"),
            "",
        )
    except Exception as e:
        logger.error(f"ask_valeria_conversational error: {e}")
        raw = ""

    if not raw:
        raw = _fallback_response(lang, effective_interest, funnel_stage)

    # Парсим скрытые теги
    next_stage        = None
    tag_interest      = None
    tag_geo           = None

    if m := re.search(r"\[READY:(\w+)\]", raw):
        next_stage = m.group(1)  # "warming" или "tease"
    raw = re.sub(r"\[READY:\w+\]", "", raw).strip()

    if m := re.search(r"\[INTEREST:(\w+)\]", raw):
        tag_interest = m.group(1)
        if tag_interest not in ("betting", "casino", "nodeposit", "exclusive"):
            tag_interest = None
    raw = re.sub(r"\[INTEREST:\w+\]", "", raw).strip()

    if m := re.search(r"\[GEO:(\w+)\]", raw):
        tag_geo = m.group(1)
        if tag_geo not in ("ES", "HR", "RS", "LT", "LV"):
            tag_geo = None
    raw = re.sub(r"\[GEO:\w+\]", "", raw).strip()

    raw = _clean_for_telegram(_strip_thinking(raw))

    return {
        "text":              raw,
        "detected_interest": tag_interest or detected_interest,
        "detected_geo":      tag_geo or detected_geo,
        "next_stage":        next_stage,
        "move_to_tease":     next_stage == "tease",
        "move_to_cta":       False,  # tease → CTA через _send_tease в bot.py
    }


# ════════════════════════════════════════════════════════════════════════════
#  POST-SUBSCRIPTION OPENER — первое что Валерия пишет подписавшемуся
#  Не "Well done" — живой вопрос который начинает диалог
# ════════════════════════════════════════════════════════════════════════════

_POST_SUB_OPENERS: dict[str, dict[str, str]] = {
    "en": {
        "betting":   "Good. Now — *have you actually placed bets before*, or are you starting fresh? Makes a difference in where I'd point you first.",
        "casino":    "Good. Quick one — *what's your usual approach with bonuses?* Do you pick them based on size, wagering, or just what's available?",
        "nodeposit": "Good. *Have you cleared a no-deposit before?* Knowing your experience helps me point you to the right one first.",
        "exclusive": "Good. *Which side do you know better — the betting signals or the bonus math?* I'll start where it's most useful.",
    },
    "es": {
        "betting":   "Bien. Ahora — *¿has hecho apuestas antes*, o empiezas desde cero? Cambia mucho a dónde te apunto primero.",
        "casino":    "Bien. Rápido — *¿cuál es tu enfoque habitual con los bonos?* ¿Los eliges por tamaño, wagering, o lo que esté disponible?",
        "nodeposit": "Bien. *¿Has liberado un sin depósito antes?* Saber tu experiencia me ayuda a apuntarte al correcto primero.",
        "exclusive": "Bien. *¿Qué lado conoces mejor — las señales de apuestas o la matemática de bonos?* Empiezo por donde sea más útil.",
    },
    "hr": {
        "betting":   "Dobro. Sad — *jesi li ikad kladi prije*, ili počinješ ispočetka? Dosta mijenja gdje bih te prvo uputio.",
        "casino":    "Dobro. Kratko — *kakav je tvoj uobičajeni pristup bonusima?* Biraš ih po veličini, wageringu, ili što je dostupno?",
        "nodeposit": "Dobro. *Jesi li ikad oslobodio bez depozita?* Poznavanje tvog iskustva pomaže mi da te uputim na pravi prvi.",
        "exclusive": "Dobro. *Koju stranu bolje poznaješ — signale klađenja ili matematiku bonusa?* Počinjem tamo gdje je najkorisnije.",
    },
    "lt": {
        "betting":   "Gerai. Dabar — *ar esi statęs anksčiau*, ar pradedi nuo nulio? Labai keičia kur pirmiausia nukreipčiau.",
        "casino":    "Gerai. Greitai — *koks tavo įprastas požiūris į bonusus?* Renkiesi pagal dydį, wagering, ar kas yra prieinama?",
        "nodeposit": "Gerai. *Ar esi išvalius be depozito anksčiau?* Žinodama tavo patirtį galiu nukreipti į tinkamą pirmą.",
        "exclusive": "Gerai. *Kurią pusę geriau žinai — lažybų signalus ar bonusų matematiką?* Pradėsiu ten kur naudingiausia.",
    },
    "lv": {
        "betting":   "Labi. Tagad — *vai esi likis likmes iepriekš*, vai sāc no nulles? Mainās kur tevi vispirms norādītu.",
        "casino":    "Labi. Ātri — *kāda ir tava parastā pieeja bonusiem?* Izvēlies pēc lieluma, wagering, vai kas ir pieejams?",
        "nodeposit": "Labi. *Vai esi notīrījis bez depozīta iepriekš?* Zinot tavu pieredzi palīdz norādīt uz pareizo pirmo.",
        "exclusive": "Labi. *Kuru pusi zini labāk — likmju signālus vai bonusu matemātiku?* Sākšu tur kur noderīgāk.",
    },
}

def get_post_sub_opener(lang: str, interest: str) -> str:
    """Первый вопрос Валерии после подписки — начинает диалог, не рассылку."""
    lang_openers = _POST_SUB_OPENERS.get(lang, _POST_SUB_OPENERS["en"])
    return lang_openers.get(interest, lang_openers.get("betting", ""))


# ════════════════════════════════════════════════════════════════════════════
#  SILENCE DETECTOR — один точечный пуш если молчат
#  Не серия таймеров. Один умный пуш через N часов молчания.
# ════════════════════════════════════════════════════════════════════════════

from datetime import datetime, timezone

def hours_since_last_message(user_id: int) -> float:
    """Сколько часов прошло с последнего сообщения пользователя."""
    from storage import get_user
    user = get_user(user_id)
    last_str = user.get("last_user_message_at", user.get("last_active", ""))
    if not last_str:
        return 999
    try:
        la = datetime.fromisoformat(last_str)
        if la.tzinfo is None:
            la = la.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - la).total_seconds() / 3600
    except Exception:
        return 999

def should_send_silence_push(user_id: int, silence_hours: float = 4.0) -> bool:
    """
    Отправлять ли тихий пуш?
    Да если: молчат > N часов И ещё не отправляли пуш за это молчание.
    """
    from storage import get_user
    hours = hours_since_last_message(user_id)
    if hours < silence_hours:
        return False

    user = get_user(user_id)
    last_push_str = user.get("last_push_at", "")
    if not last_push_str:
        return True
    try:
        lp = datetime.fromisoformat(last_push_str)
        if lp.tzinfo is None:
            lp = lp.replace(tzinfo=timezone.utc)
        # Не спамим — минимум silence_hours между пушами
        hours_since_push = (datetime.now(timezone.utc) - lp).total_seconds() / 3600
        return hours_since_push >= silence_hours
    except Exception:
        return True


# ════════════════════════════════════════════════════════════════════════════
#  SILENCE PUSH GENERATOR — один вопрос, не монолог
# ════════════════════════════════════════════════════════════════════════════

_SILENCE_PUSH: dict[str, dict[str, str]] = {
    "pre_ftd": {
        "en": [
            "Still thinking things over? What's the one question you still have?",
            "Something came up in the channel today that fits what you mentioned. Still around?",
            "No rush — but the window I mentioned is still open. What's holding you back?",
        ],
        "es": [
            "¿Todavía pensándolo? ¿Cuál es la única pregunta que todavía tienes?",
            "Algo salió en el canal hoy que encaja con lo que mencionaste. ¿Sigues por aquí?",
            "Sin prisa — pero la ventana que mencioné sigue abierta. ¿Qué te frena?",
        ],
        "hr": [
            "Još razmišljaš? Koje je jedino pitanje koje još imaš?",
            "Nešto se pojavilo u kanalu danas što odgovara onome što si spominjao. Jesi li još tu?",
            "Nema žurbe — ali prozor koji sam spominjala je još otvoren. Što te drži?",
        ],
        "lt": [
            "Vis dar galvoji? Koks yra vienintelis klausimas kurio vis dar turi?",
            "Šiandien kanale pasirodė kažkas kas atitinka tai ką minėjai. Vis dar čia?",
            "Neskubėk — bet langas kurį minėjau vis dar atviras. Kas tave laiko?",
        ],
        "lv": [
            "Vēl domā? Kāds ir viens jautājums kuru joprojām esi?",
            "Šodien kanālā parādījās kaut kas kas atbilst tam ko pieminēji. Vēl esi šeit?",
            "Nav steiga — bet logs kuru minēju joprojām ir atvērts. Kas tevi kavē?",
        ],
    },
    "post_ftd": {
        "en": [
            "How's it going with the first session? Anything I can help optimize?",
            "Results from yesterday — good, bad, or mixed?",
            "Ready for the next move or still processing the first one?",
        ],
        "es": [
            "¿Cómo va con la primera sesión? ¿Algo que pueda ayudar a optimizar?",
            "Resultados de ayer — ¿buenos, malos o mixtos?",
            "¿Listo para el siguiente movimiento o todavía procesando el primero?",
        ],
        "hr": [
            "Kako ide s prvom sesijom? Ima li nešto što mogu pomoći optimizirati?",
            "Rezultati od jučer — dobri, loši ili mješoviti?",
            "Spreman za sljedeći potez ili još obrađuješ prvi?",
        ],
        "lt": [
            "Kaip sekasi su pirmąja sesija? Ar yra kažkas ką galiu padėti optimizuoti?",
            "Vakarykščiai rezultatai — geri, blogi ar mišrūs?",
            "Pasiruošęs kitam žingsniui ar vis dar apdoroji pirmąjį?",
        ],
        "lv": [
            "Kā iet ar pirmo sesiju? Vai ir kaut kas ko varu palīdzēt optimizēt?",
            "Vakardienas rezultāti — labi, slikti vai jaukti?",
            "Gatavs nākamajam gājienam vai vēl apstrādā pirmo?",
        ],
    },
}

import random

def get_silence_push(lang: str, ftd_done: bool) -> str:
    """Возвращает случайный точечный пуш для молчащего пользователя."""
    key   = "post_ftd" if ftd_done else "pre_ftd"
    texts = _SILENCE_PUSH.get(key, _SILENCE_PUSH["pre_ftd"])
    options = texts.get(lang, texts.get("en", ["Still there?"]))
    return random.choice(options)
