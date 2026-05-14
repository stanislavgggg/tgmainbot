"""
membership.py — OddsVault Bot v8
Верификация подписки на Telegram-каналы.

КАК РАБОТАЕТ:
  1. Бот должен быть АДМИНИСТРАТОРОМ в каждом канале (иначе getChatMember не вернёт info).
  2. check_membership() вызывает getChatMember для нужного channel_id.
  3. Статусы "member", "administrator", "creator" = подписан.
  4. Статусы "left", "kicked", "restricted" = не подписан.
  5. Если бот не admin в канале → возвращаем UNKNOWN (не блокируем пользователя).

ВАЖНО ДЛЯ ДЕПЛОЯ:
  - В каждом канале: Settings → Administrators → добавить бота
  - Боту нужны права: только "Add members" НЕ нужны; достаточно базового admin статуса
  - CHANNEL_IDS заполняются через @userinfobot или get_chat() — username не всегда работает
    напрямую, надёжнее числовой ID вида -1001234567890
"""

import logging
from enum import Enum
from typing import Optional

from telegram import Bot
from telegram.error import TelegramError

logger = logging.getLogger(__name__)


class MemberStatus(str, Enum):
    SUBSCRIBED = "subscribed"   # точно подписан
    NOT_MEMBER = "not_member"   # точно НЕ подписан
    UNKNOWN    = "unknown"       # не удалось проверить (бот не admin, или API error)


# ════════════════════════════════════════════════════════════════════════════
#  CHANNEL ROUTING MATRIX
#
#  Структура: CHANNEL_MATRIX[geo][interest] = {
#      "username":    "@handle",        — для ссылки в кнопке
#      "channel_id":  -100XXXXXXXXXX,   — числовой ID для getChatMember
#      "title":       "Display name",   — отображается в кнопке
#      "lang":        "es",             — язык контента канала
#  }
#
#  geo: "ES", "HR", "RS", "LT", "LV", "BALKAN", "OTHER"
#  interest: "betting", "casino", "nodeposit", "exclusive"
#
#  ВАЖНО: channel_id нужно получить один раз и прописать здесь.
#  Способ получить ID: переслать любое сообщение из канала боту @userinfobot
#  Или вызвать: bot.get_chat("@username") и взять .id из ответа
# ════════════════════════════════════════════════════════════════════════════

_CH = {
    # @ApuestasGuruES — ставки, Испания, язык испанский
    # Chat ID из скриншота IMG_1975: -1001040179885
    "apuestas": {
        "username":   "@ApuestasGuruES",
        "channel_id": -1001040179885,
        "title":      "ApuestasGuru ⚽",
        "lang":       "es",
        "topic":      "betting",
    },
    # @bet_croatia — ставки, Хорватия, язык английский
    # Chat ID из скриншота IMG_1972: -1002655084586
    "bet_croatia": {
        "username":   "@bet_croatia",
        "channel_id": -1002655084586,
        "title":      "BetCroatia ⚽",
        "lang":       "en",
        "topic":      "betting",
    },
    # @luckycasinoguru — казино, Литва, язык литовский
    # Chat ID из скриншота IMG_1971 / IMG_1970: -1003237183860
    "luckycasinoguru": {
        "username":   "@luckycasinoguru",
        "channel_id": -1003237183860,
        "title":      "LuckyCasino 🎰",
        "lang":       "lt",
        "topic":      "casino",
    },
    # @luckylatviaan — казино, Латвия, язык латышский
    # Chat ID из скриншота IMG_1974: -1003910322335
    "luckylatviaan": {
        "username":   "@luckylatviaan",
        "channel_id": -1003910322335,
        "title":      "LuckyLatvia 🎰",
        "lang":       "lv",
        "topic":      "casino",
    },
    # @balkanjackpot — казино, Сербия+Хорватия+Балканы, язык английский
    # Chat ID из скриншота IMG_1969: -1003522266492
    "balkanjackpot": {
        "username":   "@balkanjackpot",
        "channel_id": -1003522266492,
        "title":      "BalkanJackpot 🎰",
        "lang":       "en",
        "topic":      "casino",
    },
}

# GEO × INTEREST → ключ канала из _CH
# None = нет подходящего канала для этой комбинации
CHANNEL_MATRIX: dict[str, dict[str, Optional[str]]] = {
    "ES": {
        "betting":   "apuestas",
        "casino":    None,          # нет казино-канала для Испании
        "nodeposit": None,          # нет no-deposit канала для Испании
        "exclusive": "apuestas",    # используем ставочный канал
    },
    "HR": {
        "betting":   "bet_croatia",
        "casino":    "balkanjackpot",
        "nodeposit": "balkanjackpot",
        "exclusive": "bet_croatia",
    },
    "RS": {                         # Сербия → балкан-казино
        "betting":   None,
        "casino":    "balkanjackpot",
        "nodeposit": "balkanjackpot",
        "exclusive": "balkanjackpot",
    },
    "BALKAN": {                     # Общий балкан (Босния, Слования и др.)
        "betting":   None,
        "casino":    "balkanjackpot",
        "nodeposit": "balkanjackpot",
        "exclusive": "balkanjackpot",
    },
    "LT": {
        "betting":   None,
        "casino":    "luckycasinoguru",
        "nodeposit": "luckycasinoguru",
        "exclusive": "luckycasinoguru",
    },
    "LV": {
        "betting":   None,
        "casino":    "luckylatviaan",
        "nodeposit": "luckylatviaan",
        "exclusive": "luckylatviaan",
    },
    "OTHER": {                      # неизвестное/прочее гео → наиболее широкий канал
        "betting":   "apuestas",
        "casino":    "balkanjackpot",
        "nodeposit": "balkanjackpot",
        "exclusive": "apuestas",
    },
}


# ════════════════════════════════════════════════════════════════════════════
#  ЯЗЫК РАЗГОВОРА с пользователем по ГЕО
#  Бот разговаривает на языке ПОЛЬЗОВАТЕЛЯ, а не канала.
# ════════════════════════════════════════════════════════════════════════════

GEO_TO_LANG: dict[str, str] = {
    "ES":     "es",
    "HR":     "hr",
    "RS":     "hr",     # сербы — Croatian/Serbian взаимопонятны, общий hr
    "BALKAN": "hr",     # балканы — используем хорватский как lingua franca
    "LT":     "lt",
    "LV":     "lv",
    "OTHER":  "en",
}

# Язык Telegram интерфейса пользователя → ГЕО (приоритет ниже чем выбор в квизе)
TGLANG_TO_GEO: dict[str, str] = {
    "es": "ES",
    "hr": "HR",
    "sr": "RS",
    "bs": "BALKAN",  # Боснийский
    "sl": "BALKAN",  # Словенский
    "lt": "LT",
    "lv": "LV",
}


# ════════════════════════════════════════════════════════════════════════════
#  Resolve channel for user
# ════════════════════════════════════════════════════════════════════════════

def resolve_channel(geo: str, interest: str) -> Optional[dict]:
    """
    Возвращает dict с данными канала для данного GEO + interest, или None.
    Fallback: если нет канала для interest → пробуем "exclusive", потом "casino", потом "betting".
    """
    geo_upper = geo.upper() if geo else "OTHER"
    geo_matrix = CHANNEL_MATRIX.get(geo_upper, CHANNEL_MATRIX["OTHER"])

    # Пробуем точное совпадение
    ch_key = geo_matrix.get(interest)

    # Fallback по приоритету интересов
    if ch_key is None:
        for fallback_interest in ("exclusive", "casino", "betting", "nodeposit"):
            if fallback_interest != interest:
                ch_key = geo_matrix.get(fallback_interest)
                if ch_key:
                    logger.info(f"Channel fallback: [{geo_upper}][{interest}] → [{fallback_interest}] → {ch_key}")
                    break

    if ch_key is None:
        # Последний fallback — глобальный OTHER
        for fi in ("exclusive", "casino", "betting", "nodeposit"):
            ch_key = CHANNEL_MATRIX["OTHER"].get(fi)
            if ch_key:
                break

    if ch_key is None:
        return None

    return _CH.get(ch_key)


def resolve_lang(geo: str, tg_lang_code: Optional[str] = None) -> str:
    """
    Определяет язык разговора с пользователем.
    Приоритет: выбор ГЕО в квизе > язык Telegram.
    """
    geo_upper = geo.upper() if geo else ""

    # Если ГЕО известно из квиза — берём язык по ГЕО
    if geo_upper in GEO_TO_LANG:
        return GEO_TO_LANG[geo_upper]

    # Иначе — из кода языка Telegram
    if tg_lang_code:
        base = tg_lang_code.split("-")[0].lower()
        geo_from_tg = TGLANG_TO_GEO.get(base)
        if geo_from_tg:
            return GEO_TO_LANG.get(geo_from_tg, "en")

    return "en"


def infer_geo_from_tg_lang(tg_lang_code: Optional[str]) -> Optional[str]:
    """Угадывает ГЕО из кода языка Telegram. Используется как начальный hint."""
    if not tg_lang_code:
        return None
    base = tg_lang_code.split("-")[0].lower()
    return TGLANG_TO_GEO.get(base)


# ════════════════════════════════════════════════════════════════════════════
#  Membership verification
# ════════════════════════════════════════════════════════════════════════════

_SUBSCRIBED_STATUSES = {"member", "administrator", "creator"}

async def check_membership(
    bot: Bot,
    user_id: int,
    geo: str,
    interest: str,
) -> MemberStatus:
    """
    Проверяет подписку пользователя на нужный канал через Telegram API.

    Требования:
      - Бот должен быть АДМИНИСТРАТОРОМ в канале
      - channel_id в _CH должен быть заполнен (не None)

    Returns:
      MemberStatus.SUBSCRIBED   — пользователь точно подписан
      MemberStatus.NOT_MEMBER   — пользователь точно НЕ подписан
      MemberStatus.UNKNOWN      — не удалось проверить (считаем OK, не блокируем)
    """
    channel = resolve_channel(geo, interest)
    if not channel:
        logger.info(f"No channel configured for GEO={geo} interest={interest}")
        return MemberStatus.UNKNOWN

    channel_id = channel.get("channel_id")
    if not channel_id:
        # channel_id не заполнен → нельзя проверить, не блокируем
        logger.warning(
            f"channel_id not set for {channel.get('username')} — "
            f"skipping membership check. Fill in CHANNEL_IDS in membership.py."
        )
        return MemberStatus.UNKNOWN

    try:
        member = await bot.get_chat_member(chat_id=channel_id, user_id=user_id)
        status = member.status
        if status in _SUBSCRIBED_STATUSES:
            logger.info(f"User {user_id} IS member of {channel.get('username')} (status={status})")
            return MemberStatus.SUBSCRIBED
        else:
            logger.info(f"User {user_id} NOT member of {channel.get('username')} (status={status})")
            return MemberStatus.NOT_MEMBER
    except TelegramError as e:
        # Типичная ошибка: "Bad Request: user not found" (если юзер никогда не взаимодействовал)
        # или "Forbidden" (бот не admin в канале)
        err_str = str(e).lower()
        if "user not found" in err_str or "participant_id_invalid" in err_str:
            logger.info(f"User {user_id} not found in {channel.get('username')} — treating as NOT_MEMBER")
            return MemberStatus.NOT_MEMBER
        if "forbidden" in err_str or "chat not found" in err_str or "not a member" in err_str:
            logger.warning(
                f"Bot is not admin in {channel.get('username')} or channel_id is wrong. "
                f"Error: {e}. Returning UNKNOWN to avoid blocking users."
            )
            return MemberStatus.UNKNOWN
        logger.error(f"Unexpected error checking membership [{user_id}] in {channel.get('username')}: {e}")
        return MemberStatus.UNKNOWN
    except Exception as e:
        logger.error(f"check_membership error [{user_id}]: {e}")
        return MemberStatus.UNKNOWN


async def get_channel_link(geo: str, interest: str) -> Optional[str]:
    """Возвращает t.me ссылку на канал для кнопки."""
    channel = resolve_channel(geo, interest)
    if not channel:
        return None
    username = channel.get("username", "")
    return f"https://t.me/{username.lstrip('@')}"


def get_channel_title(geo: str, interest: str) -> str:
    """Возвращает название канала для кнопки."""
    channel = resolve_channel(geo, interest)
    if not channel:
        return "📲 OddsVault"
    return channel.get("title", "📲 OddsVault")


def get_channel_username(geo: str, interest: str) -> Optional[str]:
    """Возвращает @username канала."""
    channel = resolve_channel(geo, interest)
    if not channel:
        return None
    return channel.get("username")


# ════════════════════════════════════════════════════════════════════════════
#  GEO Quiz buttons
#  Показываются после выбора интереса в квизе.
#  Пользователь выбирает свой регион → бот знает какой канал показать
#  и на каком языке разговаривать.
# ════════════════════════════════════════════════════════════════════════════

GEO_QUIZ: dict[str, dict] = {
    "en": {
        "text": "And where are you based? I'll find what's most relevant for your market.",
        "buttons": [
            ("🇪🇸 Spain",            "geo_ES"),
            ("🇭🇷 Croatia",          "geo_HR"),
            ("🇷🇸 Serbia / Balkan",  "geo_RS"),
            ("🇱🇹 Lithuania",        "geo_LT"),
            ("🇱🇻 Latvia",           "geo_LV"),
            ("🌍 Other / EU",        "geo_OTHER"),
        ],
    },
    "es": {
        "text": "¿Y dónde estás? Así encuentro lo más relevante para tu mercado.",
        "buttons": [
            ("🇪🇸 España",          "geo_ES"),
            ("🇭🇷 Croacia",         "geo_HR"),
            ("🇷🇸 Serbia / Balcanes","geo_RS"),
            ("🇱🇹 Lituania",        "geo_LT"),
            ("🇱🇻 Letonia",         "geo_LV"),
            ("🌍 Otro / UE",        "geo_OTHER"),
        ],
    },
    "hr": {
        "text": "I gdje si? Pronaći ću što je najrelevantnije za tvoje tržište.",
        "buttons": [
            ("🇪🇸 Španjolska",      "geo_ES"),
            ("🇭🇷 Hrvatska",        "geo_HR"),
            ("🇷🇸 Srbija / Balkan", "geo_RS"),
            ("🇱🇹 Litva",           "geo_LT"),
            ("🇱🇻 Latvija",         "geo_LV"),
            ("🌍 Ostalo / EU",      "geo_OTHER"),
        ],
    },
    "lt": {
        "text": "O kur esi? Rasiu kas labiausiai tinka tavo rinkai.",
        "buttons": [
            ("🇪🇸 Ispanija",        "geo_ES"),
            ("🇭🇷 Kroatija",        "geo_HR"),
            ("🇷🇸 Serbija / Balkan","geo_RS"),
            ("🇱🇹 Lietuva",         "geo_LT"),
            ("🇱🇻 Latvija",         "geo_LV"),
            ("🌍 Kita / ES",        "geo_OTHER"),
        ],
    },
    "lv": {
        "text": "Un kur tu esi? Atradīšu kas vispiemērotākais tavam tirgum.",
        "buttons": [
            ("🇪🇸 Spānija",         "geo_ES"),
            ("🇭🇷 Horvātija",       "geo_HR"),
            ("🇷🇸 Serbija / Balkāni","geo_RS"),
            ("🇱🇹 Lietuva",         "geo_LT"),
            ("🇱🇻 Latvija",         "geo_LV"),
            ("🌍 Citi / ES",        "geo_OTHER"),
        ],
    },
}


# ════════════════════════════════════════════════════════════════════════════
#  Helper: get_channel_id_from_username
#  Утилита для одноразового получения числового ID канала.
#  Вызывать вручную один раз, потом прописать ID в _CH выше.
# ════════════════════════════════════════════════════════════════════════════

async def fetch_channel_ids(bot: Bot) -> dict[str, int]:
    """
    Вспомогательная функция для получения числовых ID всех каналов.
    Запусти один раз командой /admin_fetch_ids и скопируй ID в _CH.
    """
    results = {}
    for key, data in _CH.items():
        username = data.get("username")
        if not username:
            continue
        try:
            chat = await bot.get_chat(username)
            results[key] = chat.id
            logger.info(f"Channel {username} → id={chat.id}")
        except TelegramError as e:
            logger.error(f"Cannot get chat for {username}: {e}")
    return results
