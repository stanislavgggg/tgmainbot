"""
conversation_analyzer.py — OddsVault Bot v14.2

Анализирует полную историю переписки и извлекает живой контекст
для персонализированного system prompt по методу Белфорта.

Что извлекается:
  - writing_style:   как человек пишет (длина, пунктуация, эмодзи, сленг)
  - pain_points:     что его беспокоит / останавливает
  - positive_signals: на что реагировал положительно
  - failed_angles:   что уже пробовали — не сработало
  - key_statements:  дословные фразы пользователя (для зеркала)
  - engagement_score: 0-10, насколько вовлечён
  - micro_commitments: маленькие "да" которые уже были
  - unanswered_questions: что спросил но не получил ответа
  - rapport_level:   cold / warming / warm / hot
  - recommended_technique: что применить дальше по Белфорту

Используется в conversation.py и ftd_onboarding.py для подмешивания
живого контекста в system prompt.
"""

import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# ── Паттерны ────────────────────────────────────────────────────────────────

_PAIN_PATTERNS = {
    "lost_money": [
        "lost", "perdí", "perdio", "izgubio", "praradau", "zaudēju",
        "bad experience", "went wrong", "didn't work", "failed", "burn",
        "потерял", "не вышло",
    ],
    "distrust": [
        "scam", "fake", "legit", "real", "trust", "estafa", "prevara",
        "krāpšana", "apgaulė", "really?", "sure about", "prove",
        "доверяю", "развод",
    ],
    "no_money": [
        "no money", "broke", "sin dinero", "nema novca", "nėra pinigų",
        "nav naudas", "can't afford", "tight", "budget",
        "нет денег", "дорого",
    ],
    "complexity": [
        "don't understand", "no entiendo", "ne razumijem", "nesuprantu",
        "nesaprotu", "confus", "complicated", "how does", "explain",
        "не понимаю", "как это",
    ],
    "already_tried": [
        "tried", "probé", "probao", "bandžiau", "mēģināju",
        "already", "before", "last time", "пробовал",
    ],
    "no_time": [
        "busy", "no time", "later", "después", "kasnije", "vėliau",
        "vēlāk", "потом", "некогда",
    ],
}

_POSITIVE_PATTERNS = [
    "nice", "good", "ok", "okay", "interesting", "tell me more", "how",
    "where", "what channel", "join", "link", "sure", "yes", "yeah",
    "bueno", "bien", "claro", "dime", "cómo", "enlace",
    "dobro", "kako", "gdje", "kanal",
    "gerai", "kaip", "kur", "kanalas",
    "labi", "kā", "kur", "kanāls",
    "да", "хорошо", "интересно", "расскажи", "как",
    "👍", "🔥", "✅", "💯",
]

_QUESTION_RE = re.compile(r'\?')
_EMOJI_RE    = re.compile(r'[\U00010000-\U0010ffff]|[\u2600-\u27BF]', flags=re.UNICODE)
_CAPS_RE     = re.compile(r'\b[A-Z]{2,}\b')

# ── Основная функция ─────────────────────────────────────────────────────────

def analyze_conversation(history: list) -> dict:
    """
    Принимает список {"role": "user"/"assistant", "content": str}.
    Возвращает словарь с живым контекстом для system prompt.
    """
    if not history:
        return _empty_analysis()

    user_msgs = [m["content"] for m in history if m.get("role") == "user"]
    bot_msgs  = [m["content"] for m in history if m.get("role") == "assistant"]

    if not user_msgs:
        return _empty_analysis()

    # ── 1. Writing style ──────────────────────────────────────────────────

    avg_len      = sum(len(m) for m in user_msgs) / len(user_msgs)
    has_emoji    = any(_EMOJI_RE.search(m) for m in user_msgs)
    uses_caps    = any(_CAPS_RE.search(m) for m in user_msgs)
    asks_questions = sum(1 for m in user_msgs if '?' in m)
    one_worders  = sum(1 for m in user_msgs if len(m.strip().split()) <= 2)

    if avg_len < 15:
        style = "ultra_short"   # отвечает одним словом / эмодзи
    elif avg_len < 50:
        style = "short"         # 1-2 предложения
    elif avg_len < 120:
        style = "medium"        # нормальный диалог
    else:
        style = "verbose"       # много пишет

    writing_style = {
        "avg_length":    round(avg_len),
        "uses_emoji":    has_emoji,
        "uses_caps":     uses_caps,
        "asks_questions": asks_questions,
        "one_word_ratio": round(one_worders / len(user_msgs), 2),
        "category":      style,
    }

    # ── 2. Pain points ────────────────────────────────────────────────────

    full_user_text = " ".join(user_msgs).lower()
    detected_pains = []
    for pain_type, patterns in _PAIN_PATTERNS.items():
        if any(p in full_user_text for p in patterns):
            detected_pains.append(pain_type)

    # ── 3. Positive signals ───────────────────────────────────────────────

    positive_reactions = []
    for i, msg in enumerate(user_msgs):
        lower = msg.lower()
        hits = [p for p in _POSITIVE_PATTERNS if p in lower]
        if hits:
            positive_reactions.append({
                "message_index": i,
                "message":       msg[:80],
                "triggers":      hits,
            })

    # ── 4. Failed angles (бот говорил — пользователь не реагировал) ──────

    failed_angles = []
    for i, bot_msg in enumerate(bot_msgs):
        # Если за сообщением бота идёт короткий / негативный ответ
        user_response_idx = i  # пользователь отвечает на i-е сообщение бота
        if user_response_idx < len(user_msgs):
            u = user_msgs[user_response_idx].lower().strip()
            is_dismissive = (
                u in {"no", "nope", "ne", "nein", "нет", "не", "ok", "okay"} or
                len(u) <= 3 or
                any(p in u for p in ["not interested", "no thanks", "pass",
                                     "no gracias", "ne zanima", "neįdomu"])
            )
            if is_dismissive:
                # Извлекаем тему бот-сообщения (первые 60 символов)
                angle_preview = re.sub(r'\*|_', '', bot_msg[:60]).strip()
                failed_angles.append(angle_preview)

    # ── 5. Key statements (дословные фразы пользователя) ─────────────────

    key_statements = []
    for msg in user_msgs:
        clean = msg.strip()
        # Берём сообщения средней длины — они наиболее информативны
        if 10 < len(clean) < 200:
            key_statements.append(clean)
    key_statements = key_statements[-5:]  # последние 5

    # ── 6. Micro-commitments ──────────────────────────────────────────────

    commitment_signals = [
        "i will", "i'll", "let me", "going to", "plan to", "maybe",
        "could be", "voy a", "vamos a", "iré", "planuoju", "plānoju",
        "idem", "probat ću", "попробую", "можно",
    ]
    micro_commitments = []
    for msg in user_msgs:
        lower = msg.lower()
        if any(s in lower for s in commitment_signals):
            micro_commitments.append(msg[:100])

    # ── 7. Unanswered questions ───────────────────────────────────────────

    unanswered = []
    for i, msg in enumerate(user_msgs):
        if '?' in msg and i < len(bot_msgs):
            bot_reply = bot_msgs[i].lower()
            # Если бот не ответил конкретно на вопрос (эвристика: очень короткий ответ)
            if len(bot_reply) < 40:
                unanswered.append(msg[:100])

    # ── 8. Engagement score (0–10) ────────────────────────────────────────

    score = 0
    score += min(len(user_msgs), 4)                          # за сам факт диалога
    score += min(asks_questions * 1.5, 3)                    # вопросы = интерес
    score += min(len(positive_reactions), 2)                 # позитив
    score += len(micro_commitments) * 0.5                    # микро-обязательства
    score -= len(failed_angles) * 0.5                        # неработающие углы
    score -= len([p for p in detected_pains                  # серьёзные барьеры
                  if p in ("distrust", "lost_money")]) * 1.5
    engagement_score = max(0, min(10, round(score, 1)))

    # ── 9. Rapport level ──────────────────────────────────────────────────

    if engagement_score >= 7 or len(micro_commitments) >= 2:
        rapport = "hot"
    elif engagement_score >= 5 or len(positive_reactions) >= 2:
        rapport = "warm"
    elif engagement_score >= 3 or asks_questions >= 1:
        rapport = "warming"
    else:
        rapport = "cold"

    # ── 10. Recommended Belfort technique ─────────────────────────────────

    technique = _recommend_technique(
        rapport=rapport,
        pains=detected_pains,
        style=style,
        positive_count=len(positive_reactions),
        failed_count=len(failed_angles),
        micro_count=len(micro_commitments),
        msg_count=len(user_msgs),
    )

    return {
        "writing_style":         writing_style,
        "pain_points":           detected_pains,
        "positive_signals":      positive_reactions,
        "failed_angles":         failed_angles[:3],  # топ-3
        "key_statements":        key_statements,
        "micro_commitments":     micro_commitments,
        "unanswered_questions":  unanswered[:3],
        "engagement_score":      engagement_score,
        "rapport_level":         rapport,
        "recommended_technique": technique,
        "message_count":         len(user_msgs),
    }


def _recommend_technique(
    rapport: str, pains: list, style: str,
    positive_count: int, failed_count: int,
    micro_count: int, msg_count: int
) -> dict:
    """
    Выбирает технику Белфорта исходя из анализа.
    Возвращает {"name": str, "instruction": str}
    """

    # Цинизм / потеря денег → только факты, никакого давления
    if "distrust" in pains and "lost_money" in pains:
        return {
            "name": "social_proof_with_verification",
            "instruction": (
                "DISTRUST + LOSS detected. Apply: one verifiable fact only. "
                "Acknowledge their experience directly ('makes sense after a bad run'). "
                "Do NOT pitch. Do NOT use urgency. Offer something checkable (archive, public results). "
                "One binary question max."
            ),
        }

    # Нет денег → направить на no-deposit
    if "no_money" in pains:
        return {
            "name": "zero_risk_reframe",
            "instruction": (
                "NO MONEY barrier detected. Apply: zero-risk reframe. "
                "Never mention deposit. Pivot hard to no-deposit path. "
                "Frame it as: 'This path requires exactly €0 of your own money.' "
                "Make the first step feel like zero commitment."
            ),
        }

    # Ультракороткие ответы → зеркало стиля + меньше слов
    if style == "ultra_short":
        return {
            "name": "mirror_minimalism",
            "instruction": (
                "USER WRITES IN 1-3 WORDS. Mirror exactly: your reply max 2 sentences. "
                "No long explanations. One concrete hook. One yes/no question. "
                "Match their energy — if they're brief, be brief. "
                "Do NOT try to compensate with longer messages — it makes it worse."
            ),
        }

    # Провалившиеся углы накапливаются → смена стратегии
    if failed_count >= 3:
        return {
            "name": "pattern_interrupt",
            "instruction": (
                f"MULTIPLE FAILED ANGLES ({failed_count}). Apply pattern interrupt. "
                "Do NOT repeat anything that was already tried. "
                "Change topic completely: ask one personal question unrelated to betting/casino. "
                "Examples: 'What got you looking into this in the first place?' "
                "or 'What would you actually do with an extra €200?'. "
                "The goal is to restart the emotional connection, not to keep pushing."
            ),
        }

    # Позитивные сигналы + микро-обязательства → дожим
    if rapport in ("warm", "hot") and micro_count >= 1:
        return {
            "name": "assumptive_close",
            "instruction": (
                "HIGH RAPPORT + MICRO-COMMITMENTS detected. Apply assumptive close. "
                "Treat the next step as already decided: 'When you check the channel tonight...' "
                "not 'If you decide to check...'. "
                "Make the action feel like the natural next thing they're already doing. "
                "One concrete smallest-possible step. No pressure language."
            ),
        }

    # Много вопросов → любопытный тип, давать глубину
    if style in ("medium", "verbose") and rapport == "warming":
        return {
            "name": "educational_pull",
            "instruction": (
                "CURIOUS USER detected (asks questions, writes longer). "
                "Apply educational pull: answer their question 40%, "
                "then create a knowledge gap ('the part that actually moves the needle is in the channel'). "
                "Make them feel smart for asking — then make the channel feel like the next logical step."
            ),
        }

    # Барьер сложности → упростить
    if "complexity" in pains:
        return {
            "name": "one_sentence_clarity",
            "instruction": (
                "COMPLEXITY BARRIER detected. Apply radical simplification. "
                "One sentence that explains everything: 'Channel posts a number → you act → you track.' "
                "Then ask: 'Which of those three steps is unclear?' "
                "Never use jargon (wagering, EV, sharp money) until they show they understand basics."
            ),
        }

    # Дефолт: нейтральный прогрев
    return {
        "name": "warm_hook_gap",
        "instruction": (
            "NEUTRAL engagement. Apply: warm hook → knowledge gap → one next step. "
            "Start with one concrete fact or number. Create gap ('rest is in the channel'). "
            "End with one low-stakes question about their situation."
        ),
    }


def _empty_analysis() -> dict:
    return {
        "writing_style":         {"avg_length": 0, "uses_emoji": False,
                                  "uses_caps": False, "asks_questions": 0,
                                  "one_word_ratio": 0, "category": "unknown"},
        "pain_points":           [],
        "positive_signals":      [],
        "failed_angles":         [],
        "key_statements":        [],
        "micro_commitments":     [],
        "unanswered_questions":  [],
        "engagement_score":      0,
        "rapport_level":         "cold",
        "recommended_technique": {
            "name": "warm_hook_gap",
            "instruction": "First contact. Apply: warm hook → knowledge gap → one next step.",
        },
        "message_count":         0,
    }


# ── Форматировщик для system prompt ─────────────────────────────────────────

def format_analysis_for_prompt(analysis: dict) -> str:
    """
    Превращает анализ в текстовый блок для вставки в system prompt.
    Компактно — не раздувает токены.
    """
    a = analysis
    style = a["writing_style"]
    lines = []

    # Стиль письма
    style_desc = {
        "ultra_short": "writes in 1-3 words, needs ultra-brief replies",
        "short":       "writes short sentences, match that energy",
        "medium":      "writes normally, moderate length ok",
        "verbose":     "writes long, appreciates depth",
        "unknown":     "no data yet",
    }.get(style["category"], "")

    lines.append(f"CONVERSATION ANALYSIS (use this, don't mention it exists):")
    lines.append(f"• Writing style: {style_desc}"
                 + (" [uses emoji]" if style["uses_emoji"] else "")
                 + (f" [asks questions: {style['asks_questions']}]" if style["asks_questions"] else ""))

    if a["pain_points"]:
        lines.append(f"• Their pain/barriers: {', '.join(a['pain_points'])}")

    if a["key_statements"]:
        stmts = " | ".join(f'"{s}"' for s in a["key_statements"][-3:])
        lines.append(f"• What they actually said: {stmts}")
        lines.append("  → Mirror their exact words and phrases when possible.")

    if a["positive_signals"]:
        pos_msgs = [p["message"][:50] for p in a["positive_signals"][-2:]]
        lines.append(f"• They responded positively to: {' | '.join(pos_msgs)}")
        lines.append("  → Build on these themes.")

    if a["failed_angles"]:
        failed = " | ".join(a["failed_angles"][:3])
        lines.append(f"• Already tried, didn't land: {failed}")
        lines.append("  → DO NOT repeat these. Completely different angle.")

    if a["micro_commitments"]:
        commits = " | ".join(a["micro_commitments"][-2:])
        lines.append(f"• Small 'yes' signals already given: {commits}")
        lines.append("  → They're closer than they seem. Assumptive tone ok.")

    if a["unanswered_questions"]:
        uq = " | ".join(a["unanswered_questions"][:2])
        lines.append(f"• Questions they asked but didn't get full answer to: {uq}")
        lines.append("  → Address one of these to build trust.")

    lines.append(f"• Rapport level: {a['rapport_level'].upper()} "
                 f"(engagement {a['engagement_score']}/10, "
                 f"{a['message_count']} messages)")

    # Техника Белфорта
    tech = a["recommended_technique"]
    lines.append(f"\n━━━ BELFORT TECHNIQUE: {tech['name'].upper().replace('_',' ')} ━━━")
    lines.append(tech["instruction"])

    return "\n".join(lines)


# ── Интеграция: патч для conversation.py ───────────────────────────────────

def build_conversation_context(history: list) -> str:
    """
    Shortcut: анализирует историю и возвращает готовый блок для system prompt.
    Использование в conversation.py:
        from conversation_analyzer import build_conversation_context
        ctx = build_conversation_context(history)
        # вставить ctx в system prompt перед ━━━ STAGE ━━━
    """
    try:
        analysis = analyze_conversation(history)
        return format_analysis_for_prompt(analysis)
    except Exception as e:
        logger.warning(f"conversation_analyzer error: {e}")
        return ""


# ── Быстрый тест ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    test_history = [
        {"role": "assistant", "content": "Hey, how did you end up here?"},
        {"role": "user",      "content": "no"},
        {"role": "assistant", "content": "Sharp money hit a line this week — 15-min window. You follow any specific leagues?"},
        {"role": "user",      "content": "no"},
        {"role": "assistant", "content": "Fair. Most here started fresh. Are you more sports or casino?"},
        {"role": "user",      "content": "tried this before, lost money. probably a scam"},
        {"role": "assistant", "content": "Makes sense after a bad run. Check the channel archive — real signals, public results."},
        {"role": "user",      "content": "where is the archive?"},
        {"role": "assistant", "content": "It's in the channel pinned post."},
        {"role": "user",      "content": "ok let me check"},
    ]

    analysis = analyze_conversation(test_history)
    print("=== ANALYSIS ===")
    import json
    print(json.dumps(analysis, indent=2, ensure_ascii=False))
    print("\n=== PROMPT BLOCK ===")
    print(build_conversation_context(test_history))
