"""
storage.py — хранилище пользователей.
Данные живут в памяти + сохраняются в users.json на диск.
На Railway данные сбрасываются при рестарте — для продакшена
подключи PostgreSQL или Redis через переменную DATABASE_URL.
"""

import json
import os
import threading
from datetime import datetime, timezone
from typing import Any

from config import AI_MAX_HISTORY

_DB_FILE  = os.getenv("DB_FILE", "users.json")
_lock     = threading.Lock()
_users: dict[int, dict] = {}


# ── init: загружаем JSON если есть ──────────────────────────────────────────
def _load() -> None:
    global _users
    if os.path.exists(_DB_FILE):
        try:
            with open(_DB_FILE, "r", encoding="utf-8") as f:
                raw = json.load(f)
            _users = {int(k): v for k, v in raw.items()}
        except Exception:
            _users = {}


def _save() -> None:
    try:
        with open(_DB_FILE, "w", encoding="utf-8") as f:
            json.dump({str(k): v for k, v in _users.items()},
                      f, ensure_ascii=False, indent=2)
    except Exception:
        pass


_load()


# ── публичный API ────────────────────────────────────────────────────────────

def get_user(user_id: int) -> dict:
    with _lock:
        return dict(_users.get(user_id, {}))


def update_user(user_id: int, **kwargs) -> None:
    with _lock:
        user = _users.setdefault(user_id, {"id": user_id})
        user.update(kwargs)
        user["last_active"] = datetime.now(timezone.utc).isoformat()
        _save()


def get_all_users() -> list[dict]:
    with _lock:
        return [dict(u) for u in _users.values()]


def add_ai_message(user_id: int, role: str, content: str) -> None:
    """Добавляет сообщение в историю чата, обрезая старые."""
    with _lock:
        user = _users.setdefault(user_id, {"id": user_id})
        history: list = user.setdefault("ai_history", [])
        history.append({"role": role, "content": content})
        # Держим только последние AI_MAX_HISTORY сообщений
        if len(history) > AI_MAX_HISTORY:
            user["ai_history"] = history[-AI_MAX_HISTORY:]
        _save()


def get_ai_history(user_id: int) -> list[dict]:
    with _lock:
        user = _users.get(user_id, {})
        return list(user.get("ai_history", []))


def add_tone(user_id: int, tone: str) -> None:
    with _lock:
        user = _users.setdefault(user_id, {"id": user_id})
        tones: list = user.setdefault("tone_history", [])
        tones.append(tone)
        if len(tones) > 10:
            user["tone_history"] = tones[-10:]
        _save()
