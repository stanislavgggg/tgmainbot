"""
storage.py — OddsVault Bot
v2.0: трекинг возражений, психотипа, использованных техник.
"""

import json
import os
import threading
from datetime import datetime, timezone

from config import AI_MAX_HISTORY

_DB_FILE  = os.getenv("DB_FILE", "users.json")
_lock     = threading.Lock()
_users: dict[int, dict] = {}


# ── Классификатор возражений ─────────────────────────────────────────────────
OBJECTION_PATTERNS: dict[str, list[str]] = {
    "scam": [
        "scam", "estafa", "prevara", "krāpšana", "apgaulė",
        "развод", "мошенник", "обман", "лохотрон", "не верю", "fake",
    ],
    "no_money": [
        "no money", "sin dinero", "nema novca", "nėra pinigų", "nav naudas",
        "нет денег", "денег нет", "broke",
    ],
    "no_time": [
        "no time", "sin tiempo", "nema vremena", "neturiu laiko", "nav laika",
        "нет времени", "некогда", "busy", "ocupado",
    ],
    "tried_before": [
        "tried", "probé", "probao", "bandžiau", "mēģināju",
        "пробовал", "пробовала", "уже пробовал", "already tried", "lost before",
    ],
    "not_interested": [
        "not interested", "no me interesa", "ne zanima", "neįdomu", "neinteresē",
        "не интересно", "неинтересно", "не надо", "don't care",
    ],
    "skeptical": [
        "doubt", "duda", "sumnja", "abejonė", "šaubas",
        "сомневаюсь", "не верится", "sounds fake", "bullshit", "really?",
    ],
    "later": [
        "later", "después", "kasnije", "vėliau", "vēlāk",
        "потом", "позже", "не сейчас", "maybe later",
    ],
    "dont_understand": [
        "don't understand", "no entiendo", "ne razumijem", "nesuprantu", "nesaprotu",
        "не понимаю", "что это",
    ],
}


# ── init ──────────────────────────────────────────────────────────────────────
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


# ── базовый API ───────────────────────────────────────────────────────────────

def get_user(user_id: int) -> dict:
    with _lock:
        return dict(_users.get(user_id, {}))


def update_user(user_id: int, **kwargs) -> None:
    with _lock:
        user = _users.setdefault(user_id, {"id": user_id})
        user.update(kwargs)
        user["last_active"] = datetime.now(timezone.utc).isoformat()
        _save()


def mark_push_sent(user_id: int) -> None:
    """Записывает время последнего проактивного пуша.
    Намеренно НЕ трогает last_active — чтобы не сбивать логику
    «юзер сам написал vs мы написали ему».
    """
    with _lock:
        user = _users.setdefault(user_id, {"id": user_id})
        user["last_push_at"] = datetime.now(timezone.utc).isoformat()
        _save()


def get_all_users() -> list[dict]:
    with _lock:
        return [dict(u) for u in _users.values()]


def add_ai_message(user_id: int, role: str, content: str) -> None:
    with _lock:
        user = _users.setdefault(user_id, {"id": user_id})
        history: list = user.setdefault("ai_history", [])
        history.append({"role": role, "content": content})
        if len(history) > AI_MAX_HISTORY:
            user["ai_history"] = history[-AI_MAX_HISTORY:]
        _save()


def get_ai_history(user_id: int) -> list[dict]:
    with _lock:
        return list(_users.get(user_id, {}).get("ai_history", []))


def add_tone(user_id: int, tone: str) -> None:
    with _lock:
        user = _users.setdefault(user_id, {"id": user_id})
        tones: list = user.setdefault("tone_history", [])
        tones.append(tone)
        if len(tones) > 10:
            user["tone_history"] = tones[-10:]
        _save()


# ── возражения ────────────────────────────────────────────────────────────────

def classify_objection(text: str) -> str | None:
    """Возвращает тип возражения или None."""
    lower = text.lower()
    for obj_type, patterns in OBJECTION_PATTERNS.items():
        if any(p in lower for p in patterns):
            return obj_type
    return None


def log_objection(user_id: int, objection_type: str) -> None:
    with _lock:
        user = _users.setdefault(user_id, {"id": user_id})
        obj: dict = user.setdefault("objections_log", {})
        obj[objection_type] = obj.get(objection_type, 0) + 1
        _save()


def get_objections(user_id: int) -> dict[str, int]:
    with _lock:
        return dict(_users.get(user_id, {}).get("objections_log", {}))


# ── психотип ──────────────────────────────────────────────────────────────────

def compute_psychotype(user_id: int, latest_message: str = "") -> str:
    with _lock:
        user         = _users.get(user_id, {})
        objections   = user.get("objections_log", {})
        tone_history = user.get("tone_history", [])

    scam_hits    = objections.get("scam", 0)
    skeptic_hits = objections.get("skeptical", 0)
    tried_hits   = objections.get("tried_before", 0)
    passive_hits = (objections.get("later", 0)
                    + objections.get("no_time", 0)
                    + objections.get("no_money", 0))
    disinterest  = objections.get("not_interested", 0)

    neg_tones     = tone_history.count("skeptical")
    short_tones   = tone_history.count("short")
    curious_tones = tone_history.count("curious")

    if scam_hits >= 2 or (disinterest >= 2 and scam_hits >= 1):
        return "cynic"
    if scam_hits >= 1 or skeptic_hits >= 2 or (tried_hits >= 1 and neg_tones >= 2):
        return "skeptic"
    if passive_hits >= 2 or (short_tones >= 4 and curious_tones == 0):
        return "passive"
    if curious_tones >= 2 or ("?" in latest_message and scam_hits == 0):
        return "curious"
    return "neutral"


def update_psychotype(user_id: int, latest_message: str = "") -> str:
    psychotype = compute_psychotype(user_id, latest_message)
    with _lock:
        _users.setdefault(user_id, {"id": user_id})["psychotype"] = psychotype
        _save()
    return psychotype


def get_psychotype(user_id: int) -> str:
    with _lock:
        return _users.get(user_id, {}).get("psychotype", "neutral")


# ── использованные техники ────────────────────────────────────────────────────

def log_technique(user_id: int, technique: str) -> None:
    with _lock:
        user = _users.setdefault(user_id, {"id": user_id})
        techniques: list = user.setdefault("used_techniques", [])
        if technique not in techniques:
            techniques.append(technique)
        _save()


def get_used_techniques(user_id: int) -> list[str]:
    with _lock:
        return list(_users.get(user_id, {}).get("used_techniques", []))
