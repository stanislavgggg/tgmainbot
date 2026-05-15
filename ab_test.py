"""
ab_test.py — OddsVault Bot v12

A/B тест первого сообщения (HOOK).
3 варианта с разными психологическими подходами.
Метрики: показы → дошли до CTA → подписались → FTD.

ВАРИАНТЫ:
  A — Рациональный (текущий): факты, Валерия как эксперт
  B — Эмоциональный: история одного момента, FOMO, без представления
  C — Провокационный: вопрос без представления, интрига

Ротация: случайная равномерная (33/33/33).
Данные: хранятся в storage как ab_test_variant + метрики.
"""

import random
import logging
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

# ── Варианты HOOK ─────────────────────────────────────────────────────────────

HOOK_VARIANTS: dict[str, dict[str, str]] = {
    "A": {
        # Рациональный — факты + Валерия как эксперт
        "en": (
            "Hey.\n\n"
            "Not sure if you got here by chance or by instinct — but your timing is good. 🎯\n\n"
            "I'm *Valeria* — I spent 4 years tracking odds, bonuses and signals across European markets. "
            "Built this bot so I can share what I find with more people at once.\n\n"
            "I'm not selling anything. No subscriptions, no fees. "
            "I just drop what I find into a channel — and people are already making the most of it.\n\n"
            "Quick question — how did you end up here? Recommendation or you found it yourself?"
        ),
        "es": (
            "Oye.\n\n"
            "No sé si llegaste aquí por suerte o por instinto — pero llegas en buen momento. 🎯\n\n"
            "Soy *Valeria* — llevo 4 años rastreando odds, bonos y señales en mercados europeos. "
            "Creé esto para compartir lo que encuentro con más gente a la vez.\n\n"
            "No vendo nada. Sin suscripciones, sin tarifas. "
            "Solo comparto lo que encuentro — y la gente ya está sacando partido.\n\n"
            "Pregunta rápida — ¿cómo llegaste aquí? ¿Recomendación o lo encontraste tú mismo?"
        ),
        "hr": (
            "Hej.\n\n"
            "Ne znam jesi li ovdje slučajno ili instinktom — ali dolaziš u pravo vrijeme. 🎯\n\n"
            "Ja sam *Valerija* — 4 godine pratim kvote, bonuse i signale na europskim tržištima. "
            "Napravila sam ovo da mogu dijeliti što pronađem s više ljudi odjednom.\n\n"
            "Ništa ne prodajem. Bez pretplata, bez naknada. "
            "Samo dijelim što pronađem — i ima ljudi koji već izvlače korist.\n\n"
            "Brzo pitanje — kako si završio ovdje? Preporuka ili si sam pronašao?"
        ),
        "lt": (
            "Sveiki.\n\n"
            "Nežinau ar atkeliavote čia atsitiktinai ar instinktu — bet atvykstate geru laiku. 🎯\n\n"
            "Aš esu *Valerija* — 4 metus seku koeficientus, bonusus ir signalus Europos rinkose. "
            "Sukūriau tai kad galėčiau dalintis tuo, ką randu, su daugiau žmonių.\n\n"
            "Nieko neparduodu. Jokių prenumeratų, jokių mokesčių. "
            "Tiesiog dalinausi tuo, ką randu — ir žmonės jau iš to gauna naudos.\n\n"
            "Greitas klausimas — kaip čia atsidūrei? Rekomendacija ar pats radai?"
        ),
        "lv": (
            "Sveiki.\n\n"
            "Nezinu vai esat šeit nejauši vai instinktīvi — bet ierodaties īstajā laikā. 🎯\n\n"
            "Es esmu *Valerija* — 4 gadus seku koeficientiem, bonusiem un signāliem Eiropas tirgos. "
            "Izveidoju šo lai varētu dalīties ar to, ko atrodu, ar vairāk cilvēkiem.\n\n"
            "Es neko nepārdodu. Nav abonementu, nav maksas. "
            "Vienkārši dalūos ar to, ko atrodu — un cilvēki jau no tā gūst labumu.\n\n"
            "Ātrs jautājums — kā tu šeit nokļuvi? Ieteikums vai pats atradai?"
        ),
    },
    "B": {
        # Эмоциональный — история момента, без вопроса о языке
        "en": (
            "Last Tuesday, three people I know caught a line that was sitting *completely wrong*.\n\n"
            "Not because they're geniuses. Because they were in the right place when I posted it. "
            "The window was about 40 minutes. Then the market corrected.\n\n"
            "I'm *Valeria*. I find these moments — odds gaps, bonus windows, sharp money moves — "
            "before they close. And I share them.\n\n"
            "How did you end up here — recommendation or you found it yourself? 🎯"
        ),
        "es": (
            "El martes pasado, tres personas que conozco pillaron una cuota que estaba *completamente mal calculada*.\n\n"
            "No porque sean genios. Porque estaban en el lugar correcto cuando lo publiqué. "
            "La ventana fue de unos 40 minutos. Luego el mercado corrigió.\n\n"
            "Soy *Valeria*. Encuentro estos momentos — gaps en cuotas, ventanas de bonos, movimientos de dinero inteligente — "
            "antes de que se cierren. Y los comparto.\n\n"
            "¿Cómo llegaste aquí — recomendación o lo encontraste tú mismo? 🎯"
        ),
        "hr": (
            "Prošlog utorka, troje ljudi koje poznajem uhvatilo je kvotu koja je bila *potpuno pogrešna*.\n\n"
            "Ne zato što su genijalci. Nego zato što su bili na pravom mjestu kad sam to objavio. "
            "Prozor je bio oko 40 minuta. Onda je tržište ispravilo.\n\n"
            "Ja sam *Valerija*. Pronalazim te trenutke — jazzovi u kvotama, bonus prozori, pokreti pametnog novca — "
            "prije nego se zatvore. I dijelim ih.\n\n"
            "Kako si završio ovdje — preporuka ili si sam pronašao? 🎯"
        ),
        "lt": (
            "Praeitą antradienį trys žmonės kuriuos pažįstu sugavo koeficientą kuris buvo *visiškai klaidingas*.\n\n"
            "Ne todėl kad jie genialūs. O todėl kad buvo tinkamoje vietoje kai tai paskelbiau. "
            "Langas buvo apie 40 minučių. Tada rinka pasitaisė.\n\n"
            "Aš esu *Valerija*. Randu šiuos momentus — koeficientų spragas, bonusų langus, protingų pinigų judėjimą — "
            "prieš jiems užsiverdant. Ir dalinuosi jais.\n\n"
            "Kaip čia atsidūrei — rekomendacija ar pats radai? 🎯"
        ),
        "lv": (
            "Pagājušajā otrdienā trīs cilvēki ko pazīstu noķēra koeficientu kas bija *pilnīgi nepareizs*.\n\n"
            "Ne tāpēc ka viņi ir ģēniji. Bet tāpēc ka bija īstajā vietā kad to publicēju. "
            "Logs bija apmēram 40 minūtes. Tad tirgus koriģēja.\n\n"
            "Es esmu *Valerija*. Es atrodu šos mirkļus — koeficientu atstarpes, bonusu logus, gudras naudas kustības — "
            "pirms tie aizveras. Un daloties ar tiem.\n\n"
            "Kā tu šeit nokļuvi — ieteikums vai pats atradai? 🎯"
        ),
    },
    "C": {
        # Провокационный — сразу вопрос, минимум текста
        "en":  "Quick question before I let you in 🔐\n\n*How did you end up here — recommendation or you found it yourself?*",
        "es":  "Pregunta rápida antes de dejarte pasar 🔐\n\n*¿Cómo llegaste aquí — recomendación o lo encontraste tú mismo?*",
        "hr":  "Brzo pitanje prije nego te pustim unutra 🔐\n\n*Kako si završio ovdje — preporuka ili si sam pronašao?*",
        "lt":  "Greitas klausimas prieš praleisdama tave 🔐\n\n*Kaip čia atsidūrei — rekomendacija ar pats radai?*",
        "lv":  "Ātrs jautājums pirms ielaižu tevi iekšā 🔐\n\n*Kā tu šeit nokļuvi — ieteikums vai pats atradai?*",
    },
}

# Вариант C идёт в диалог сразу — без отдельного HOOK
VARIANT_C_SKIPS_HOOK = False  # теперь не нужен — вопрос встроен в caption

# ── Метрики ───────────────────────────────────────────────────────────────────

def assign_variant() -> str:
    """Равномерно распределяет варианты A/B/C."""
    return random.choice(["A", "B", "C"])

def get_hook_text(variant: str, lang: str) -> str:
    """Возвращает текст HOOK для варианта и языка."""
    variant_texts = HOOK_VARIANTS.get(variant, HOOK_VARIANTS["A"])
    return variant_texts.get(lang, variant_texts.get("en", ""))

def track_event(user_id: int, event: str) -> None:
    """
    Записывает событие для A/B метрик.
    Events: 'hook_shown', 'quiz_answered', 'geo_answered',
            'warm_replied', 'cta_clicked', 'subscribed', 'ftd_done'
    """
    from storage import get_user, update_user
    user = get_user(user_id)
    variant = user.get("ab_variant", "A")

    # Загружаем текущие метрики
    metrics = user.get("ab_metrics", {})
    if event not in metrics:
        metrics[event] = 0
    metrics[event] += 1

    update_user(user_id, ab_metrics=metrics)
    logger.debug(f"A/B [{variant}] {event} for user {user_id}")

def get_ab_stats() -> dict:
    """
    Возвращает агрегированную статистику по всем вариантам.
    Для команды /admin_ab_stats.
    """
    from storage import get_all_users
    users = get_all_users()

    stats: dict[str, dict] = {"A": {}, "B": {}, "C": {}}
    counts: dict[str, int] = {"A": 0, "B": 0, "C": 0}

    events = ["hook_shown", "quiz_answered", "geo_answered",
              "warm_replied", "cta_clicked", "subscribed", "ftd_done"]

    for v in stats:
        for e in events:
            stats[v][e] = 0

    for user in users:
        variant = user.get("ab_variant", "A")
        if variant not in stats:
            continue
        counts[variant] += 1
        metrics = user.get("ab_metrics", {})
        for e in events:
            stats[variant][e] += metrics.get(e, 0)

    # Вычисляем conversion rates
    result = {}
    for v in ["A", "B", "C"]:
        shown = stats[v].get("hook_shown", 0) or 1
        result[v] = {
            "users":       counts[v],
            "hook_shown":  stats[v].get("hook_shown", 0),
            "quiz_rate":   round(stats[v].get("quiz_answered", 0) / shown * 100, 1),
            "cta_rate":    round(stats[v].get("cta_clicked", 0) / shown * 100, 1),
            "sub_rate":    round(stats[v].get("subscribed", 0) / shown * 100, 1),
            "ftd_rate":    round(stats[v].get("ftd_done", 0) / shown * 100, 1),
        }

    return result

def format_ab_stats_message(stats: dict) -> str:
    """Форматирует статистику для отправки в Telegram."""
    lines = ["📊 *A/B Test Results*\n"]
    variant_names = {
        "A": "A — Rational (facts + expertise)",
        "B": "B — Emotional (story + FOMO)",
        "C": "C — Provocative (question only)",
    }
    for v in ["A", "B", "C"]:
        s = stats.get(v, {})
        lines.append(f"*{variant_names[v]}*")
        lines.append(f"  Users: {s.get('users', 0)}")
        lines.append(f"  Quiz rate: {s.get('quiz_rate', 0)}%")
        lines.append(f"  CTA rate: {s.get('cta_rate', 0)}%")
        lines.append(f"  Sub rate: {s.get('sub_rate', 0)}%")
        lines.append(f"  FTD rate: {s.get('ftd_rate', 0)}%\n")

    # Определяем победителя по FTD rate
    best = max(["A","B","C"], key=lambda v: stats.get(v,{}).get("ftd_rate", 0))
    best_rate = stats.get(best, {}).get("ftd_rate", 0)
    if best_rate > 0:
        lines.append(f"🏆 Best FTD: Variant *{best}* ({best_rate}%)")

    total = sum(s.get("users", 0) for s in stats.values())
    lines.append(f"\n_Total users: {total}_")
    if total < 300:
        lines.append(f"_⚠️ Need {300-total} more users for statistical significance_")

    return "\n".join(lines)
