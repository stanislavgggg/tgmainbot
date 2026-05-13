"""
ai_agent.py — AI-персонаж Валерия через OpenRouter.
"""
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


async def ask_valeria(
    user_message: str,
    history: list[dict],
    lang: str = "ru",
    interest: str = "betting",
    funnel_stage: str = "warming",
) -> str:
    """
    Отправляет запрос к AI и возвращает ответ персонажа.
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
        "max_tokens": 300,
        "temperature": 0.85,
        "stream": False,
    }

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(AI_BASE_URL, json=payload, headers=HEADERS)
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"].strip()
    except httpx.HTTPStatusError as e:
        logger.error(f"OpenRouter HTTP error: {e.response.status_code} — {e.response.text}")
        return _fallback(lang)
    except Exception as e:
        logger.error(f"OpenRouter error: {e}")
        return _fallback(lang)


def _fallback(lang: str) -> str:
    """Резервный ответ если AI недоступен."""
    msgs = {
        "es": "Un momento… estoy revisando mis notas 🎰 Escríbeme en un minuto.",
        "hr": "Trenutak… provjeravam svoje zapise 🎰 Piši mi za minutu.",
        "lt": "Minutėlę… tikrinu savo užrašus 🎰 Parašyk man po minutės.",
        "lv": "Brītiņu… pārbaudu savus pierakstus 🎰 Raksti man pēc minūtes.",
    }
    return msgs.get(lang, "Секунду… проверяю свои записи 🎰 Напиши чуть позже.")
