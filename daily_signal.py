"""
daily_signal.py — OddsVault Bot v12

Ежедневный персональный сигнал для подписчиков.
Отправляется в 18:00 по таймзоне пользователя (перед вечерними матчами).

ЛОГИКА:
  - Только подписчикам (funnel_stage == "subscribed")
  - Только если не писали в последние 3 часа (не спамим активным)
  - AI генерирует уникальный сигнал под interest + geo + профиль
  - Если поиск нашёл реальный факт — используем его
  - Если нет — безопасный шаблон без выдуманных цифр
  - После 3 дней без ответа — пауза (не надоедаем)

ЧАСОВЫЕ ПОЯСА по GEO:
  ES → Europe/Madrid (UTC+1/+2)
  HR → Europe/Zagreb (UTC+1/+2)
  RS → Europe/Belgrade (UTC+1/+2)
  LT → Europe/Vilnius (UTC+2/+3)
  LV → Europe/Riga (UTC+2/+3)
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from telegram.error import TelegramError
from telegram.constants import ParseMode

from storage import get_all_users, get_user, add_ai_message, mark_push_sent, get_profile, get_ai_history, get_objections, get_psychotype
from ai_agent import _post_with_retry, _build_profile_ctx, ANTHROPIC_URL, MODEL, ANTHROPIC_KEY, _safe_web_search, _fallback_response

logger = logging.getLogger(__name__)

# ── Таймзоны по GEO ──────────────────────────────────────────────────────────

_GEO_UTC_OFFSET: dict[str, int] = {
    "ES":    1,   # CET (зимой UTC+1, летом UTC+2 — берём среднее)
    "HR":    1,
    "RS":    1,
    "BALKAN":1,
    "LT":    2,
    "LV":    2,
    "OTHER": 1,
}

def _user_local_hour(geo: str) -> int:
    """Возвращает текущий час в таймзоне пользователя."""
    offset = _GEO_UTC_OFFSET.get(geo.upper() if geo else "OTHER", 1)
    utc_now = datetime.now(timezone.utc)
    local_time = utc_now + timedelta(hours=offset)
    return local_time.hour

def _is_signal_time(geo: str) -> bool:
    """True если сейчас 17:00–19:00 в таймзоне пользователя."""
    hour = _user_local_hour(geo)
    return 17 <= hour <= 19

# ── Проверки активности ───────────────────────────────────────────────────────

def _user_active_recently(user_id: int, hours: int = 3) -> bool:
    """Писал ли пользователь сам в последние N часов."""
    user = get_user(user_id)
    last_active_str = user.get("last_active", "")
    if not last_active_str:
        return False
    try:
        la = datetime.fromisoformat(last_active_str)
        if la.tzinfo is None:
            la = la.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - la).total_seconds() < hours * 3600
    except Exception:
        return False

def _signal_sent_today(user_id: int) -> bool:
    """Уже отправляли дейли сигнал сегодня."""
    user = get_user(user_id)
    last_signal_str = user.get("last_daily_signal", "")
    if not last_signal_str:
        return False
    try:
        ls = datetime.fromisoformat(last_signal_str)
        if ls.tzinfo is None:
            ls = ls.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - ls).total_seconds() < 20 * 3600
    except Exception:
        return False

def _days_without_response(user_id: int) -> int:
    """Сколько дней пользователь не отвечал."""
    user = get_user(user_id)
    last_msg_str = user.get("last_user_message_at", user.get("last_active", ""))
    if not last_msg_str:
        return 99
    try:
        lm = datetime.fromisoformat(last_msg_str)
        if lm.tzinfo is None:
            lm = lm.replace(tzinfo=timezone.utc)
        return int((datetime.now(timezone.utc) - lm).total_seconds() / 86400)
    except Exception:
        return 99

# ── Fallback тексты ───────────────────────────────────────────────────────────

_SIGNAL_FALLBACK: dict[str, dict[str, str]] = {
    "en": {
        "betting":   "Evening check-in 🎯\n\nLines are starting to move ahead of tonight's matches. The early movers are usually the ones who already know something. Are you watching anything specific tonight?",
        "casino":    "Evening edge 💎\n\nSome of the better wagering conditions of the week tend to appear on weekday evenings — operators run quiet promos when traffic is lower. Anything you've been eyeing in the channel?",
        "nodeposit": "Evening window 🎁\n\nA few no-deposit offers tend to reset or expire around midnight. If you've been sitting on one — tonight might be the right moment. Have you looked at what's active right now?",
        "exclusive": "Evening signal 🔥\n\nThe best edges of the day usually appear in the 2-hour window before kick-off. Sharp money moves fast. Anything from the channel you want to talk through?",
    },
    "es": {
        "betting":   "Check-in de tarde 🎯\n\nLas cuotas empiezan a moverse antes de los partidos de esta noche. Los que mueven primero suelen ser los que ya saben algo. ¿Estás siguiendo algo concreto esta noche?",
        "casino":    "Ventaja de tarde 💎\n\nAlgunas de las mejores condiciones de wagering de la semana aparecen en las tardes entre semana — los operadores hacen promos silenciosas cuando el tráfico es menor. ¿Hay algo que hayas visto en el canal?",
        "nodeposit": "Ventana de tarde 🎁\n\nAlgunos bonos sin depósito se resetean o vencen alrededor de medianoche. Si llevas tiempo pensándolo — esta noche podría ser el momento. ¿Has visto qué está activo ahora mismo?",
        "exclusive": "Señal de tarde 🔥\n\nLos mejores edges del día suelen aparecer en las 2 horas antes del partido. El dinero inteligente se mueve rápido. ¿Hay algo del canal que quieras analizar?",
    },
    "hr": {
        "betting":   "Večernji check-in 🎯\n\nKvote počinju da se kreću pred večerašnje utakmice. Oni koji se kreću prvi obično već nešto znaju. Pratiš li nešto konkretno večeras?",
        "casino":    "Večernja prednost 💎\n\nNeki od boljih uvjeta wageringa u tjednu pojavljuju se radnim večerima — operateri rade tihe promocije kada je promet manji. Ima li nešto u kanalu što si primijetio?",
        "nodeposit": "Večernji prozor 🎁\n\nNeki bonusi bez depozita se resetiraju ili istječu oko ponoći. Ako si već neko vrijeme razmišljao — večeras bi mogao biti pravi trenutak. Jesi li pogledao što je sad aktivno?",
        "exclusive": "Večernji signal 🔥\n\nNajbolji edgevi dana obično se pojavljuju u 2 sata prije utakmice. Pametni novac se brzo kreće. Ima li nešto iz kanala o čemu želiš razgovarati?",
    },
    "lt": {
        "betting":   "Vakarinis patikrinimas 🎯\n\nKoeficientai pradeda judėti prieš šiandienos vakaro rungtynes. Tie kurie juda pirmieji paprastai jau kažką žino. Seki ką nors konkretaus šį vakarą?",
        "casino":    "Vakarinis pranašumas 💎\n\nNekurios geriausios wagering sąlygos savaitėje atsiranda darbo vakarais — operatoriai vykdo tylias akcijas kai srautas mažesnis. Ar yra kažkas kanale ką pastebėjai?",
        "nodeposit": "Vakarinis langas 🎁\n\nKeli bonusai be depozito atsigamina arba baigiasi apie vidurnaktį. Jei jau kurį laiką svarstai — šis vakaras gali būti tinkamas momentas. Ar peržiūrėjai kas dabar aktyvus?",
        "exclusive": "Vakarinis signalas 🔥\n\nGeriausi dienos tarpai paprastai atsiranda 2 valandų lange prieš pradžią. Protingi pinigai juda greitai. Ar yra kažkas iš kanalo apie ką nori pakalbėti?",
    },
    "lv": {
        "betting":   "Vakara pārbaude 🎯\n\nKoeficienti sāk kustēties pirms šovakar spēlēm. Tie kas kustas pirmie parasti jau kaut ko zina. Vai tu seko kaut kam konkrētam šovakar?",
        "casino":    "Vakara priekšrocība 💎\n\nDaži no labākajiem wagering nosacījumiem nedēļā parādās darbdienu vakaros — operatori rīko klusas akcijas kad satiksme ir mazāka. Vai ir kaut kas kanālā ko pamanīji?",
        "nodeposit": "Vakara logs 🎁\n\nDaži bonusi bez depozīta atjaunojas vai beidzas ap pusnakti. Ja jau kādu laiku domā — šovakar varētu būt īstais brīdis. Vai esi apskatījis kas tagad ir aktīvs?",
        "exclusive": "Vakara signāls 🔥\n\nLabākie dienas tarpi parasti parādās 2 stundu logā pirms sākuma. Gudrā nauda kustas ātri. Vai ir kaut kas no kanāla par ko gribi parunāt?",
    },
}

# ── AI генерация дейли сигнала ────────────────────────────────────────────────

async def _generate_daily_signal(
    lang: str,
    interest: str,
    geo: str,
    user_profile: dict,
    history: list,
    psychotype: str,
    search_context: Optional[str] = None,
) -> Optional[str]:
    if not ANTHROPIC_KEY:
        return None

    lang_names = {
        "en": "English", "es": "Spanish (Spain, tú)",
        "hr": "Croatian", "lt": "Lithuanian", "lv": "Latvian",
    }
    language = lang_names.get(lang, "English")

    interest_ctx = {
        "betting":   "sports betting, value bets, line movements, evening matches",
        "casino":    "casino bonuses, wagering conditions, evening promos",
        "nodeposit": "no-deposit bonuses expiring, free offers active right now",
        "exclusive": "arbitrage, sharp money signals, value gaps before kick-off",
    }.get(interest, "betting & bonuses")

    profile_ctx = _build_profile_ctx(user_profile)

    psychotype_instr = {
        "cynic":   "Skeptical user. One concrete verifiable fact. No hype.",
        "skeptic": "Cautious user. Specific and factual. Let them draw conclusions.",
        "passive": "Disengaged user. Very short. One dead-simple question.",
        "curious": "Engaged user. Give real insight. Pull toward action.",
        "neutral": "Standard. Real hook → gap → what they should do.",
    }.get(psychotype, "Standard. Real hook → gap → what they should do.")

    search_section = ""
    if search_context:
        search_section = (
            f"\nReal data found (use naturally as your own insight, never cite source):\n"
            f"{search_context}\n"
            f"Use this as the hook for your signal."
        )
    else:
        search_section = (
            f"\nNo real data found. Write a general but compelling evening hook about "
            f"{interest_ctx} WITHOUT inventing specific team names, odds numbers, or bonus amounts."
        )

    system = f"""You are Valeria — private AI companion for betting and bonuses.
It's evening — time for the daily signal. Write ONE short, compelling message.

Language: {language} ONLY.
User interest: {interest_ctx}
User psychotype: {psychotype_instr}
{profile_ctx}
{search_section}

Rules:
- This is a DAILY SIGNAL — it should feel like a timely insider tip, not a broadcast
- Start with what's happening RIGHT NOW (tonight, this evening, before kick-off)
- End with ONE question that invites a reply — make it about THEIR plans or experience
- Max 3-4 sentences. *bold* one key insight if from real data. 1-2 emoji max.
- NEVER sound like a newsletter. NEVER say "here's your daily signal".
- NEVER close with "feel free to reach out" or similar.
- NEVER invent specific team names, exact odds, or bonus amounts without real data."""

    try:
        clean_history = history[-4:] if history else []
        # Keep only assistant messages for context (don't send user messages in proactive push)
        context_msgs = [m for m in clean_history if m.get("role") == "assistant"][-2:]

        data = await _post_with_retry(
            ANTHROPIC_URL,
            {
                "model":      MODEL,
                "max_tokens": 220,
                "system":     system,
                "messages":   context_msgs + [
                    {"role": "user", "content": "[DAILY_SIGNAL_REQUEST]"}
                ],
            },
            {
                "x-api-key":         ANTHROPIC_KEY,
                "anthropic-version": "2023-06-01",
                "content-type":      "application/json",
            },
            timeout=20,
        )
        text = next(
            (b["text"].strip() for b in data.get("content", []) if b.get("type") == "text"),
            "",
        )
        if text and len(text) > 20:
            import re
            text = re.sub(r'\*\*(.+?)\*\*', r'*\1*', text)
            return text
    except Exception as e:
        logger.error(f"Daily signal AI error: {e}")

    return None


# ── PUBLIC: daily_signal_job ──────────────────────────────────────────────────

async def daily_signal_job(context) -> None:
    """
    Запускается каждый час. Отправляет сигнал пользователям у которых сейчас 17–19 по локальному времени.
    """
    from storage import update_user as _update_user

    users = get_all_users()
    sent_count = 0

    for user in users:
        user_id = user.get("id")
        if not user_id:
            continue

        # Только подписчики
        if user.get("funnel_stage") != "subscribed":
            continue

        geo      = user.get("geo", "OTHER")
        lang     = user.get("lang", "en")
        interest = user.get("interest", "betting")

        # Проверяем что сейчас вечер в таймзоне пользователя
        if not _is_signal_time(geo):
            continue

        # Уже отправляли сегодня
        if _signal_sent_today(user_id):
            continue

        # Пользователь сам активен — не прерываем разговор
        if _user_active_recently(user_id, hours=3):
            continue

        # Пауза если 3+ дня без ответа (не спамим)
        days_silent = _days_without_response(user_id)
        if days_silent >= 3:
            logger.info(f"Daily signal skipped — {user_id} silent {days_silent} days")
            continue

        profile    = get_profile(user_id)
        history    = get_ai_history(user_id)
        psychotype = get_psychotype(user_id)

        # Поиск реального факта
        search_context = await _safe_web_search(interest, geo)

        # Генерируем сигнал
        text = await _generate_daily_signal(
            lang=lang, interest=interest, geo=geo,
            user_profile=profile, history=history,
            psychotype=psychotype, search_context=search_context,
        )

        if not text:
            # Fallback
            text = _SIGNAL_FALLBACK.get(lang, _SIGNAL_FALLBACK["en"]).get(interest, "")

        if not text:
            continue

        try:
            await context.bot.send_chat_action(chat_id=user_id, action="typing")
            await asyncio.sleep(2.0)
            await context.bot.send_message(
                chat_id=user_id, text=text, parse_mode=ParseMode.MARKDOWN)
            add_ai_message(user_id, "assistant", text)
            _update_user(user_id, last_daily_signal=datetime.now(timezone.utc).isoformat())
            mark_push_sent(user_id)
            sent_count += 1
            logger.info(f"Daily signal → {user_id} [{lang}/{interest}]")

            # Небольшая пауза между отправками чтобы не флудить API Telegram
            await asyncio.sleep(0.3)

        except TelegramError as e:
            logger.warning(f"Daily signal failed [{user_id}]: {e}")
        except Exception as e:
            logger.error(f"Daily signal error [{user_id}]: {e}")

    if sent_count > 0:
        logger.info(f"Daily signal batch complete: {sent_count} sent")
