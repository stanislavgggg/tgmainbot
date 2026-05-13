"""
storage.py — хранение состояния пользователей.
Использует JSON-файл для персистентности между перезапусками.
Для продакшна замени на Redis или PostgreSQL.
"""
import json
import os
import logging
from typing import Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

DB_FILE = os.getenv("DB_FILE", "users.json")

_cache: dict[int, dict] = {}


def _load() -> None:
    global _cache
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                raw = json.load(f)
            _cache = {int(k): v for k, v in raw.items()}
        except Exception as e:
            logger.warning(f"Could not load DB: {e}")
            _cache = {}


def _save() -> None:
    try:
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump({str(k): v for k, v in _cache.items()}, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.warning(f"Could not save DB: {e}")


def get_user(user_id: int) -> dict:
    if not _cache:
        _load()
    if user_id not in _cache:
        _cache[user_id] = {
            "id": user_id,
            "state": None,
            "lang": None,
            "interest": None,       # betting / casino / nodeposit / exclusive
            "funnel_stage": "new",  # new / warming / tease / cta / subscribed
            "ai_history": [],       # история для AI (последние N сообщений)
            "created_at": datetime.now().isoformat(),
            "last_active": datetime.now().isoformat(),
            "reengage_1_sent": False,
            "reengage_2_sent": False,
            "username": None,
            "first_name": None,
        }
    return _cache[user_id]


def update_user(user_id: int, **kwargs) -> None:
    user = get_user(user_id)
    user.update(kwargs)
    user["last_active"] = datetime.now().isoformat()
    _save()


def add_ai_message(user_id: int, role: str, content: str, max_history: int = 10) -> None:
    """Добавляет сообщение в историю AI-чата, обрезая до max_history."""
    user = get_user(user_id)
    history = user.get("ai_history", [])
    history.append({"role": role, "content": content})
    if len(history) > max_history * 2:
        history = history[-max_history * 2:]
    user["ai_history"] = history
    user["last_active"] = datetime.now().isoformat()
    _save()


def get_all_users() -> list[dict]:
    if not _cache:
        _load()
    return list(_cache.values())


# Загружаем при импорте
_load()
