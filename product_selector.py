"""
product_selector.py — OddsVault Bot v14

Выбирает правильный продукт под юзера (GEO + interest + funnel stage)
и строит контекст для conversation.py.

Логика:
  1. По GEO + interest определяем нужный канал
  2. Из канала берём подходящий продукт (приоритет: pinned → nodeposit → welcome)
  3. Возвращаем строку контекста для промпта Валерии

ВАЖНО: бот НИКОГДА не придумывает продукты сам.
Все данные только из channel_products.json.
Если продукт не найден — возвращаем только канал без деталей продукта.
"""

import json
import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)

_PRODUCTS_FILE = os.path.join(os.path.dirname(__file__), "channel_products.json")
_data: dict = {}


def _load() -> dict:
    global _data
    if _data:
        return _data
    try:
        with open(_PRODUCTS_FILE, "r", encoding="utf-8") as f:
            _data = json.load(f)
        logger.info(f"Products loaded: {len(_data.get('channels', {}))} channels")
    except Exception as e:
        logger.error(f"Failed to load channel_products.json: {e}")
        _data = {}
    return _data


def get_channel_for_user(geo: str, interest: str) -> Optional[str]:
    """Возвращает название канала для GEO + interest."""
    data = _load()
    routing = data.get("geo_routing", {})
    geo_upper = (geo or "OTHER").upper()
    geo_routes = routing.get(geo_upper, routing.get("OTHER", {}))
    return geo_routes.get(interest or "betting")


def get_product_for_user(
    geo: str,
    interest: str,
    funnel_stage: str = "subscribed",
    ftd_done: bool = False,
) -> Optional[dict]:
    """
    Выбирает лучший продукт для юзера.

    Приоритет:
    1. nodeposit interest → продукт с nodeposit_spins (free entry)
    2. pinned продукт канала
    3. первый активный продукт
    """
    data = _load()
    channel_name = get_channel_for_user(geo, interest)
    if not channel_name:
        return None

    channel = data.get("channels", {}).get(channel_name)
    if not channel:
        return None

    products = [p for p in channel.get("products", []) if p.get("status") == "active"]
    if not products:
        return None

    # Для nodeposit interest — ищем продукт с бесплатным входом
    if interest == "nodeposit":
        nodeposit_products = [p for p in products if p.get("nodeposit_spins")]
        if nodeposit_products:
            return nodeposit_products[0]

    # После FTD — не повторяем тот же продукт, можно показать другой
    # Пока возвращаем pinned или первый активный

    # Pinned продукт — основная рекомендация канала
    pinned = [p for p in products if p.get("pinned")]
    if pinned:
        return pinned[0]

    return products[0]


def build_product_context(
    geo: str,
    interest: str,
    funnel_stage: str = "subscribed",
    ftd_done: bool = False,
) -> str:
    """
    Строит строку контекста продукта для промпта Валерии.

    Возвращает текст который вставляется в system prompt.
    Если продукт не найден — возвращает только базовый контекст канала.
    """
    data = _load()
    channel_name = get_channel_for_user(geo, interest)

    if not channel_name:
        return ""

    channel = data.get("channels", {}).get(channel_name)
    if not channel:
        return ""

    product = get_product_for_user(geo, interest, funnel_stage, ftd_done)

    channel_ctx = (
        f"CHANNEL: {channel.get('telegram', channel_name)}\n"
        f"Channel value: {channel.get('channel_value_prop', '')}"
    )

    if not product:
        return channel_ctx

    # Строим контекст продукта
    lines = [
        channel_ctx,
        "",
        f"PRODUCT TO RECOMMEND: {product['name']}",
        f"Type: {product['type']}",
        f"Offer: {product.get('welcome_offer', '')}",
    ]

    if product.get("nodeposit_spins"):
        lines.append(f"No-deposit entry: {product['nodeposit_spins']} free spins — zero risk")

    if product.get("bonus_amount"):
        lines.append(f"Bonus amount: up to €{product['bonus_amount']}")

    if product.get("free_spins"):
        lines.append(f"Free spins: {product['free_spins']}")

    if product.get("key_features"):
        lines.append(f"Key features: {', '.join(product['key_features'][:3])}")

    lines.append(f"Link: {product.get('url', '')}")
    lines.append(f"How to sell it: {product.get('sell_angle', '')}")

    if product.get("urgency"):
        lines.append(f"Urgency: {product['urgency']}")

    lines += [
        "",
        "RULES FOR USING PRODUCT INFO:",
        "- Mention the product name naturally in conversation, never as a pitch",
        "- Use ONLY the features listed above — never invent extras",
        "- Never give exact URLs directly — say 'link is in the channel' or 'register through the channel link'",
        "- Goal: get user to join the channel first, product details are context for your conversation",
        "- If user asks for a link — tell them it's pinned in the channel",
    ]

    return "\n".join(lines)


def get_channel_display(geo: str, interest: str) -> dict:
    """
    Возвращает display данные канала для CTA кнопки.
    Используется в bot.py вместо прямого обращения к membership.py.
    """
    data = _load()
    channel_name = get_channel_for_user(geo, interest)
    if not channel_name:
        return {"username": "@ApuestasGuruES", "title": "📲 OddsVault"}

    channel = data.get("channels", {}).get(channel_name, {})
    telegram = channel.get("telegram", f"@{channel_name}")

    return {
        "username": telegram,
        "title": f"📲 {channel_name}",
        "url": f"https://t.me/{telegram.lstrip('@')}",
    }


def list_all_products(channel_name: Optional[str] = None) -> list:
    """Список всех продуктов. Для /admin команды."""
    data = _load()
    result = []
    channels = data.get("channels", {})

    if channel_name:
        channels = {channel_name: channels.get(channel_name, {})}

    for ch_name, ch_data in channels.items():
        for product in ch_data.get("products", []):
            result.append({
                "channel": ch_name,
                "product": product.get("name"),
                "type": product.get("type"),
                "status": product.get("status"),
                "offer": product.get("welcome_offer", ""),
                "pinned": product.get("pinned", False),
            })
    return result


def reload_products() -> bool:
    """Перезагружает JSON без рестарта бота. Для /admin_reload команды."""
    global _data
    _data = {}
    try:
        _load()
        return True
    except Exception as e:
        logger.error(f"Reload failed: {e}")
        return False


# ── Форматтер для /admin_products команды ────────────────────────────────────

def format_products_message() -> str:
    products = list_all_products()
    if not products:
        return "❌ No products loaded"

    lines = ["📦 *Channel Products*\n"]
    current_channel = None

    for p in products:
        if p["channel"] != current_channel:
            current_channel = p["channel"]
            lines.append(f"\n*{current_channel}*")

        pin = "📌 " if p["pinned"] else "  "
        status = "✅" if p["status"] == "active" else "❌"
        lines.append(f"{pin}{status} {p['product']} ({p['type']})")
        if p["offer"]:
            lines.append(f"     _{p['offer'][:60]}_")

    return "\n".join(lines)
