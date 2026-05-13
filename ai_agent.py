"""
ai_agent.py — AI-персонаж Валерия через OpenRouter.
"""
import re
import httpx
import logging
from config import OPENROUTER_KEY, AI_MODEL, AI_BASE_URL, SYSTEM_PROMPT_TEMPLATE

logger = logging.getLogger(__name__)

HEADERS = {
    "Authorization": f"Bearer {OPENROUTER_KEY}",
    "Content-Type": "application/json",
    "HTTP-Referer": "https://t.me/valeria_bot",
    "X-Title": "Valeria Gambling Bot",
}

VALID_INTERESTS = {"betting", "casino", "nodeposit", "exclusive"}


async def ask_valeria(
    user_message: str,
    history: list[dict],
    lang: str = "ru",
    interest: str = "betting",
    funnel_stage: str = "warming",
) -> tuple[str, str]:
    """
    Отправляет запрос к AI и возвращает (ответ, refined_interest).
    history — список {"role": "user"/"assistant", "content": "..."}
    """
    system = SYSTEM_PROMPT_TEMPLATE.format(
        lang=lang,
        interest=interest,
        funnel_stage=funnel_stage,
    )

    messages = [{"role": "system", "content": system}]
    messages += history[-14:]  # последние 7 пар сообщений
    messages.append({"role": "user", "content": user_message})

    payload = {
        "model": AI_MODEL,
        "messages": messages,
        "max_tokens": 350,
        "temperature": 0.85,
        "stream": False,
    }

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(AI_BASE_URL, json=payload, headers=HEADERS)
            resp.raise_for_status()
            data = resp.json()
            raw = data["choices"][0]["message"]["content"].strip()
            return _parse_response(raw, interest)
    except httpx.HTTPStatusError as e:
        logger.error(f"OpenRouter HTTP error: {e.response.status_code} — {e.response.text}")
        return _fallback(lang), interest
    except Exception as e:
        logger.error(f"OpenRouter error: {e}")
        return _fallback(lang), interest


def _parse_response(raw: str, current_interest: str) -> tuple[str, str]:
    """
    Извлекает метку [INTEREST:xxx] из ответа модели.
    Возвращает (очищенный текст, refined_interest).
    """
    match = re.search(r"\[INTEREST:(\w+)\]", raw)
    if match:
        candidate = match.group(1)
        refined = candidate if candidate in VALID_INTERESTS else current_interest
        # Удаляем метку из текста (и возможный пустой хвост)
        text = re.sub(r"\s*\[INTEREST:\w+\]", "", raw).strip()
    else:
        refined = current_interest
        text = raw

    return text, refined


def detect_tone(user_message: str, history: list[dict]) -> str:
    """
    Простая эвристика тона последнего сообщения пользователя.
    Возвращает: 'excited' | 'skeptical' | 'neutral' | 'ready'
    """
    msg = user_message.lower()

    excited_kw  = ["wow", "класс", "круто", "отлично", "серьёзно", "да ладно", "интересно",
                   "genial", "increíble", "en serio", "wow", "super", "sjajno", "super",
                   "nuostabu", "fantastiška", "lieliski", "fantastiski"]
    skeptical_kw = ["не верю", "сомневаюсь", "докажи", "это развод", "мошенник",
                    "no creo", "mentira", "estafa", "ne vjerujem", "prijevara",
                    "netikiu", "sukčiai", "neticu", "krāpniecība"]
    ready_kw    = ["хочу", "давай", "как начать", "что делать", "подписался",
                   "quiero", "cómo empiezo", "ya estoy", "hoću", "kako početi",
                   "noriu", "kaip pradėti", "gribu", "kā sākt"]

    for kw in ready_kw:
        if kw in msg:
            return "ready"
    for kw in excited_kw:
        if kw in msg:
            return "excited"
    for kw in skeptical_kw:
        if kw in msg:
            return "skeptical"
    return "neutral"


def _fallback(lang: str) -> str:
    """Резервный ответ если AI недоступен."""
    msgs = {
        "es": "Un momento… estoy revisando mis notas 🎰 Escríbeme en un minuto.",
        "hr": "Trenutak… provjeravam svoje zapise 🎰 Piši mi za minutu.",
        "lt": "Minutėlę… tikrinu savo užrašus 🎰 Parašyk man po minutės.",
        "lv": "Brītiņu… pārbaudu savus pierakstus 🎰 Raksti man pēc minūtes.",
    }
    return msgs.get(lang, "Секунду… проверяю свои записи 🎰 Напиши чуть позже.")
