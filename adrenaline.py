"""
adrenaline.py — OddsVault Bot v12

Adrenaline Mode — live режим.
Валерия пишет первой когда линии двигаются.

ИНТЕГРАЦИЯ С ODDS API:
  Используем The Odds API (https://the-odds-api.com)
  Free tier: 500 запросов/месяц
  Данные: live odds, line movements для топ лиг

ЛОГИКА:
  - Проверяем движение линий каждые 15 минут
  - Если линия сдвинулась на 0.15+ за 30 мин → это сигнал
  - Отправляем только подписчикам с interest=betting или exclusive
  - Максимум 2 live пуша в день на пользователя
  - Не отправляем если пользователь сам писал последние 30 мин

НАСТРОЙКА:
  Добавить в Railway Variables:
  ODDS_API_KEY = your_key_from_the-odds-api.com

  Бесплатно зарегистрироваться: https://the-odds-api.com/
  Free plan: 500 запросов/месяц = ~16/день = достаточно для проверки каждые 1.5 часа

SPORT_KEYS для API:
  soccer_spain_la_liga     — La Liga
  soccer_epl               — Premier League
  soccer_germany_bundesliga— Bundesliga
  soccer_italy_serie_a     — Serie A
  soccer_croatia_hnl       — HNL Croatia
  soccer_uefa_champs_league— Champions League
"""

import asyncio
import logging
import os
from datetime import datetime, timezone, timedelta
from typing import Optional

import httpx

from storage import (get_all_users, get_user, update_user,
                     add_ai_message, mark_push_sent, get_profile, get_ai_history)
from ai_agent import (_post_with_retry, _build_profile_ctx,
                      ANTHROPIC_URL, MODEL, ANTHROPIC_KEY)

logger = logging.getLogger(__name__)

ODDS_API_KEY = os.getenv("ODDS_API_KEY", "6c287c70db387ce8374809f18925bc74")
ODDS_API_URL = "https://api.the-odds-api.com/v4"

# ── Лиги по GEO ──────────────────────────────────────────────────────────────

_GEO_SPORTS: dict[str, list[str]] = {
    "ES":    ["soccer_spain_la_liga", "soccer_uefa_champs_league"],
    "HR":    ["soccer_croatia_hnl", "soccer_uefa_champs_league"],
    "RS":    ["soccer_serbia_superliga", "soccer_uefa_champs_league"],
    "LT":    ["soccer_lithuania_a_lyga", "soccer_uefa_champs_league"],
    "LV":    ["soccer_latvia_virsliga", "soccer_uefa_champs_league"],
    "OTHER": ["soccer_epl", "soccer_uefa_champs_league"],
    "BALKAN":["soccer_croatia_hnl", "soccer_uefa_champs_league"],
}

# Порог движения линии для сигнала
LINE_MOVE_THRESHOLD = 0.12   # изменение коэффициента на 0.12+ = значимое
MIN_ODDS_VALUE      = 1.4    # не трекаем очень короткие фавориты
MAX_ODDS_VALUE      = 5.0    # не трекаем аутсайдеров с очень длинными линиями

# ── Кэш последних линий ──────────────────────────────────────────────────────

_odds_cache: dict[str, dict] = {}  # sport_key → {match_id: odds_data}
_last_fetch: dict[str, datetime] = {}

# ── Получение данных ──────────────────────────────────────────────────────────

async def _fetch_odds(sport_key: str) -> Optional[list]:
    """Получает текущие коэффициенты из The Odds API."""
    if not ODDS_API_KEY:
        return None
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{ODDS_API_URL}/sports/{sport_key}/odds",
                params={
                    "apiKey":  ODDS_API_KEY,
                    "regions": "eu",
                    "markets": "h2h",
                    "oddsFormat": "decimal",
                }
            )
            if resp.status_code == 200:
                remaining = resp.headers.get("x-requests-remaining", "?")
                logger.info(f"Odds API: {sport_key}, requests remaining: {remaining}")
                return resp.json()
            elif resp.status_code == 401:
                logger.error("Odds API: invalid API key")
            elif resp.status_code == 422:
                logger.warning(f"Odds API: sport {sport_key} not available")
            else:
                logger.error(f"Odds API error {resp.status_code}: {resp.text[:100]}")
    except Exception as e:
        logger.error(f"Odds API fetch error: {e}")
    return None

def _detect_line_moves(sport_key: str, new_data: list) -> list[dict]:
    """
    Сравнивает новые коэффициенты с кэшем.
    Возвращает список значимых движений.
    """
    moves = []
    cached = _odds_cache.get(sport_key, {})

    for game in new_data:
        game_id   = game.get("id", "")
        home_team = game.get("home_team", "")
        away_team = game.get("away_team", "")
        commence  = game.get("commence_time", "")

        # Смотрим только на игры которые начнутся в ближайшие 3 часа
        if commence:
            try:
                start = datetime.fromisoformat(commence.replace("Z", "+00:00"))
                hours_until = (start - datetime.now(timezone.utc)).total_seconds() / 3600
                if not (0.5 <= hours_until <= 3):
                    continue
            except Exception:
                continue

        # Берём лучшие доступные коэффициенты
        best_home = best_away = best_draw = None
        for bookmaker in game.get("bookmakers", [])[:5]:
            for market in bookmaker.get("markets", []):
                if market.get("key") != "h2h":
                    continue
                for outcome in market.get("outcomes", []):
                    price = outcome.get("price", 0)
                    name  = outcome.get("name", "")
                    if name == home_team:
                        if not best_home or price > best_home: best_home = price
                    elif name == away_team:
                        if not best_away or price > best_away: best_away = price
                    elif name == "Draw":
                        if not best_draw or price > best_draw: best_draw = price

        if not best_home or not best_away:
            continue

        # Фильтр по диапазону коэффициентов
        if not (MIN_ODDS_VALUE <= best_home <= MAX_ODDS_VALUE):
            if not (MIN_ODDS_VALUE <= best_away <= MAX_ODDS_VALUE):
                continue

        # Проверяем движение vs кэш
        prev = cached.get(game_id, {})
        prev_home = prev.get("home_odds", 0)
        prev_away = prev.get("away_odds", 0)

        home_move = abs(best_home - prev_home) if prev_home else 0
        away_move = abs(best_away - prev_away) if prev_away else 0

        if home_move >= LINE_MOVE_THRESHOLD or away_move >= LINE_MOVE_THRESHOLD:
            # Определяем направление движения
            if home_move >= away_move:
                moved_team = home_team
                old_price  = prev_home
                new_price  = best_home
                direction  = "shortened" if best_home < prev_home else "drifted"
            else:
                moved_team = away_team
                old_price  = prev_away
                new_price  = best_away
                direction  = "shortened" if best_away < prev_away else "drifted"

            moves.append({
                "game_id":    game_id,
                "home_team":  home_team,
                "away_team":  away_team,
                "moved_team": moved_team,
                "old_price":  round(old_price, 2),
                "new_price":  round(new_price, 2),
                "move":       round(abs(new_price - old_price), 2),
                "direction":  direction,  # "shortened" = фаворит растёт, "drifted" = коэффициент растёт
                "sport":      sport_key,
                "hours_until": hours_until,
            })

        # Обновляем кэш
        cached[game_id] = {"home_odds": best_home, "away_odds": best_away}

    _odds_cache[sport_key] = cached
    return moves

# ── Генерация сигнала ─────────────────────────────────────────────────────────

_MOVE_TEMPLATES: dict[str, dict] = {
    "en": {
        "shortened": (
            "⚡ Line alert\n\n"
            "*{team}* just shortened from {old} → *{new}* in the last 30 minutes. "
            "That's *{move:.2f} points* of sharp money movement before {hours:.0f}h to kick-off.\n\n"
            "When lines move like this before a match, it's usually not public money. "
            "Anything on your radar for tonight?"
        ),
        "drifted": (
            "⚡ Drift alert\n\n"
            "*{team}* drifted from {old} → *{new}* in the last 30 minutes — "
            "{move:.2f} points against the expected direction. "
            "{hours:.0f}h to kick-off.\n\n"
            "Sharp books are backing away. This kind of movement often means something. "
            "What's your read on this one?"
        ),
    },
    "es": {
        "shortened": (
            "⚡ Alerta de movimiento\n\n"
            "*{team}* acaba de acortarse de {old} → *{new}* en los últimos 30 minutos. "
            "Eso es *{move:.2f} puntos* de movimiento de dinero inteligente a {hours:.0f}h del pitido.\n\n"
            "Cuando las cuotas se mueven así antes de un partido, normalmente no es dinero público. "
            "¿Tienes algo en el radar para esta noche?"
        ),
        "drifted": (
            "⚡ Alerta de deriva\n\n"
            "*{team}* derivó de {old} → *{new}* en los últimos 30 minutos — "
            "{move:.2f} puntos contra la dirección esperada. "
            "A {hours:.0f}h del pitido.\n\n"
            "Las casas sharp están retrocediendo. Este tipo de movimiento a menudo significa algo. "
            "¿Cuál es tu lectura de este partido?"
        ),
    },
    "hr": {
        "shortened": (
            "⚡ Upozorenje o kretanju\n\n"
            "*{team}* se upravo skratio s {old} → *{new}* u zadnjih 30 minuta. "
            "To je *{move:.2f} boda* kretanja pametnog novca {hours:.0f}h pred utakmicu.\n\n"
            "Kad se kvote tako kreću prije utakmice, obično nije u pitanju javni novac. "
            "Imaš li nešto na radaru za večeras?"
        ),
        "drifted": (
            "⚡ Upozorenje o driftu\n\n"
            "*{team}* je odletio s {old} → *{new}* u zadnjih 30 minuta — "
            "{move:.2f} boda protiv očekivanog smjera. "
            "{hours:.0f}h do utakmice.\n\n"
            "Sharp kladionice se povlače. Ovakvo kretanje često znači nešto. "
            "Kakav je tvoj read na ovu utakmicu?"
        ),
    },
    "lt": {
        "shortened": (
            "⚡ Linijos judėjimo įspėjimas\n\n"
            "*{team}* ką tik sutrumpėjo nuo {old} → *{new}* per paskutines 30 minučių. "
            "Tai *{move:.2f} taškų* protingų pinigų judėjimas {hours:.0f}h iki starto.\n\n"
            "Kai koeficientai taip juda prieš rungtynes, paprastai tai ne viešieji pinigai. "
            "Turi ką nors ant radaro šiam vakarui?"
        ),
        "drifted": (
            "⚡ Dreifo įspėjimas\n\n"
            "*{team}* nukrypo nuo {old} → *{new}* per paskutines 30 minučių — "
            "{move:.2f} taškų prieš laukiamą kryptį. "
            "{hours:.0f}h iki starto.\n\n"
            "Sharp bukmecheriai traukiasi. Toks judėjimas dažnai reiškia kažką. "
            "Koks tavo skaitymas šioms rungtynėms?"
        ),
    },
    "lv": {
        "shortened": (
            "⚡ Līnijas kustības brīdinājums\n\n"
            "*{team}* tikko saīsinājās no {old} → *{new}* pēdējo 30 minūšu laikā. "
            "Tā ir *{move:.2f} punktu* gudras naudas kustība {hours:.0f}h pirms sākuma.\n\n"
            "Kad koeficienti tā kustas pirms spēles, parasti tā nav publiskā nauda. "
            "Vai tev ir kaut kas uz radara šovakar?"
        ),
        "drifted": (
            "⚡ Dreifēšanas brīdinājums\n\n"
            "*{team}* nodriftēja no {old} → *{new}* pēdējo 30 minūšu laikā — "
            "{move:.2f} punkti pret gaidīto virzienu. "
            "{hours:.0f}h līdz sākumam.\n\n"
            "Sharp grāmatas atkāpjas. Šāda kustība bieži vien ko nozīmē. "
            "Kāds ir tavs lasījums par šo spēli?"
        ),
    },
}

def _format_adrenaline_signal(lang: str, move: dict) -> str:
    """Форматирует live сигнал для отправки."""
    lang_templates = _MOVE_TEMPLATES.get(lang, _MOVE_TEMPLATES["en"])
    tmpl = lang_templates.get(move["direction"], lang_templates["shortened"])
    return tmpl.format(
        team=move["moved_team"],
        old=move["old_price"],
        new=move["new_price"],
        move=move["move"],
        hours=move.get("hours_until", 2),
    )

# ── Fallback если нет Odds API ────────────────────────────────────────────────

_ADRENALINE_FALLBACK: dict[str, str] = {
    "en": "⚡ Lines are moving ahead of tonight's matches — the action is starting. Anything from the channel you want to talk through before kick-off?",
    "es": "⚡ Las cuotas se están moviendo antes de los partidos de esta noche — la acción está empezando. ¿Hay algo del canal que quieras analizar antes del pitido?",
    "hr": "⚡ Kvote se kreću pred večerašnje utakmice — akcija počinje. Ima li nešto iz kanala o čemu želiš razgovarati prije utakmice?",
    "lt": "⚡ Prieš šiandienos vakaro rungtynes juda koeficientai — veiksmas prasideda. Ar yra kažkas iš kanalo apie ką nori pakalbėti prieš startą?",
    "lv": "⚡ Koeficienti kustas pirms šovakar spēlēm — akcija sākas. Vai ir kaut kas no kanāla par ko gribi parunāt pirms sākuma?",
}

# ── PUBLIC: adrenaline_check_job ──────────────────────────────────────────────

async def adrenaline_check_job(context) -> None:
    """
    Запускается каждые 15 минут.
    Проверяет движение линий и отправляет сигналы подписчикам.
    """
    if not ODDS_API_KEY:
        logger.info("Adrenaline: ODDS_API_KEY not set, skipping")
        return

    users = get_all_users()

    # Собираем уникальные GEO для которых нужно загрузить odds
    geos_needed = set()
    for user in users:
        if (user.get("funnel_stage") == "subscribed" and
                user.get("interest") in ("betting", "exclusive")):
            geos_needed.add(user.get("geo", "OTHER"))

    if not geos_needed:
        return

    # Загружаем odds для каждого GEO
    all_moves: dict[str, list] = {}  # geo → [moves]
    for geo in geos_needed:
        sports = _GEO_SPORTS.get(geo, _GEO_SPORTS["OTHER"])
        geo_moves = []
        for sport in sports[:2]:  # max 2 спорта на GEO чтобы не тратить API кредиты
            data = await _fetch_odds(sport)
            if data:
                moves = _detect_line_moves(sport, data)
                geo_moves.extend(moves)
            await asyncio.sleep(0.5)  # rate limit
        all_moves[geo] = geo_moves

    if not any(all_moves.values()):
        logger.info("Adrenaline: no significant line moves detected")
        return

    # Отправляем сигналы пользователям
    now = datetime.now(timezone.utc)
    sent_count = 0

    for user in users:
        user_id = user.get("id")
        if not user_id:
            continue

        if user.get("funnel_stage") != "subscribed":
            continue

        interest = user.get("interest", "betting")
        if interest not in ("betting", "exclusive"):
            continue

        geo  = user.get("geo", "OTHER")
        lang = user.get("lang", "en")

        # Не спамим — max 2 adrenaline пуша в день
        adrenaline_today = user.get("adrenaline_sent_today", 0)
        last_adrenaline  = user.get("last_adrenaline_at", "")
        if last_adrenaline:
            try:
                la = datetime.fromisoformat(last_adrenaline)
                if la.tzinfo is None: la = la.replace(tzinfo=timezone.utc)
                if (now - la).total_seconds() < 3600:  # раз в час минимум
                    continue
                if (now - la).total_seconds() < 86400 and adrenaline_today >= 2:
                    continue
            except Exception:
                pass

        # Пользователь сам активен — не прерываем
        last_active_str = user.get("last_active", "")
        if last_active_str:
            try:
                la = datetime.fromisoformat(last_active_str)
                if la.tzinfo is None: la = la.replace(tzinfo=timezone.utc)
                if (now - la).total_seconds() < 1800:  # активен последние 30 мин
                    continue
            except Exception:
                pass

        # Берём самый значимый сигнал для этого GEO
        moves = all_moves.get(geo, [])
        if not moves:
            continue

        best_move = max(moves, key=lambda m: m["move"])
        text = _format_adrenaline_signal(lang, best_move)

        try:
            await context.bot.send_chat_action(chat_id=user_id, action="typing")
            await asyncio.sleep(1.5)
            await context.bot.send_message(
                chat_id=user_id,
                text=text,
                parse_mode="Markdown")
            add_ai_message(user_id, "assistant", text)
            update_user(user_id,
                last_adrenaline_at=now.isoformat(),
                adrenaline_sent_today=adrenaline_today + 1)
            mark_push_sent(user_id)
            sent_count += 1
            logger.info(f"Adrenaline signal → {user_id}: {best_move['moved_team']} {best_move['move']:.2f}")
            await asyncio.sleep(0.3)

        except Exception as e:
            logger.warning(f"Adrenaline send failed [{user_id}]: {e}")

    if sent_count > 0:
        logger.info(f"Adrenaline batch: {sent_count} signals sent")

# ── Информация об API ─────────────────────────────────────────────────────────

def get_odds_api_status() -> str:
    """Статус для /debug команды."""
    if not ODDS_API_KEY:
        return "❌ ODDS_API_KEY not set (get free key at the-odds-api.com)"
    return f"✅ Odds API configured ({len(ODDS_API_KEY)} chars)"
