"""
referral.py — OddsVault Bot v12

Soft referral механика.
После 5 позитивных сообщений в AI_CHAT Валерия предлагает "позвать друга".
Не агрессивно — как личная рекомендация от Валерии.

ЛОГИКА:
  - Только если positive_message_count >= 5
  - Только 1 раз (после этого referral_offered = True)
  - Если юзер делится ссылкой — трекаем referral_count
  - Реферальная ссылка: t.me/BOTNAME?start=ref_USERID
"""

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

_BOT_USERNAME = os.getenv("BOT_USERNAME", "CasaValeriaBot")

# ── Тексты предложения ────────────────────────────────────────────────────────

_REFERRAL_OFFER: dict[str, str] = {
    "en": (
        "Quick sidebar — is there anyone in your circle who'd get value from this kind of insight? "
        "I can start the same conversation with them directly. "
        "Here's your link: {link} 🔗\n\n"
        "No pressure — just thought I'd mention it."
    ),
    "es": (
        "Un aparte rápido — ¿hay alguien en tu círculo que sacaría valor de este tipo de insights? "
        "Puedo empezar la misma conversación con ellos directamente. "
        "Aquí está tu enlace: {link} 🔗\n\n"
        "Sin presión — solo lo mencioné."
    ),
    "hr": (
        "Kratka digresija — ima li netko u tvom krugu tko bi imao korist od ovakvih insights? "
        "Mogu početi isti razgovor s njima direktno. "
        "Evo tvoj link: {link} 🔗\n\n"
        "Nema pritiska — samo sam htjela spomenuti."
    ),
    "lt": (
        "Greitas nukrypimas — ar yra kas nors tavo rate kas gautų naudos iš tokių įžvalgų? "
        "Galiu pradėti tą patį pokalbį su jais tiesiogiai. "
        "Čia tavo nuoroda: {link} 🔗\n\n"
        "Jokio spaudimo — tiesiog norėjau paminėti."
    ),
    "lv": (
        "Ātra novirze — vai ir kāds tavā lokā kas gūtu vērtību no šādiem ieskатiem? "
        "Varu uzsākt to pašu sarunu ar viņiem tieši. "
        "Šeit tava saite: {link} 🔗\n\n"
        "Nav spiediena — tikai gribēju pieminēt."
    ),
}

_REFERRAL_THANKS: dict[str, str] = {
    "en": "Thanks for sharing — I'll take good care of them. 🎯",
    "es": "Gracias por compartir — los atenderé bien. 🎯",
    "hr": "Hvala na dijeljenju — dobar ću se pobrinuti za njih. 🎯",
    "lt": "Ačiū už dalinimąsi — gerai pasirūpinsiu jais. 🎯",
    "lv": "Paldies par dalīšanos — labi parūpēšos par viņiem. 🎯",
}

# ── Детекторы позитивного тона ────────────────────────────────────────────────

_POSITIVE_SIGNALS = [
    "thanks", "thank you", "gracias", "hvala", "ačiū", "paldies",
    "great", "awesome", "amazing", "perfect", "exactly", "yes",
    "genial", "perfecto", "exacto", "odlično", "točno", "puiku", "perfekti",
    "useful", "helpful", "love it", "love this",
    "👍", "🔥", "💎", "✅", "❤️", "😊", "🎯",
    "makes sense", "got it", "understood", "i see",
]

def is_positive_message(text: str) -> bool:
    lower = text.lower()
    return any(sig in lower for sig in _POSITIVE_SIGNALS)

# ── PUBLIC API ────────────────────────────────────────────────────────────────

def get_referral_link(user_id: int) -> str:
    """Генерирует персональную реферальную ссылку."""
    return f"https://t.me/{_BOT_USERNAME}?start=ref_{user_id}"

def should_offer_referral(user_id: int, positive_count: int) -> bool:
    """Предлагать ли реферал сейчас."""
    from storage import get_user
    user = get_user(user_id)
    if user.get("referral_offered"):
        return False
    return positive_count >= 5

def get_referral_offer_text(lang: str, user_id: int) -> str:
    """Текст предложения с персональной ссылкой."""
    link = get_referral_link(user_id)
    tmpl = _REFERRAL_OFFER.get(lang, _REFERRAL_OFFER["en"])
    return tmpl.format(link=link)

def track_referral_offer(user_id: int) -> None:
    """Помечаем что предложение уже сделано."""
    from storage import update_user
    update_user(user_id, referral_offered=True)
    logger.info(f"Referral offered to {user_id}")

def track_referral_click(referrer_id: int) -> None:
    """Трекаем когда по реферальной ссылке кто-то пришёл."""
    from storage import get_user, update_user
    user = get_user(referrer_id)
    count = user.get("referral_count", 0) + 1
    update_user(referrer_id, referral_count=count)
    logger.info(f"Referral click for {referrer_id}, total: {count}")

def get_referrer_from_start(start_param: str) -> Optional[int]:
    """Извлекает referrer_id из параметра /start ref_12345."""
    if start_param and start_param.startswith("ref_"):
        try:
            return int(start_param[4:])
        except ValueError:
            pass
    return None

def get_thanks_text(lang: str) -> str:
    return _REFERRAL_THANKS.get(lang, _REFERRAL_THANKS["en"])
