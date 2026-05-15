"""
bonus_calculator.py — OddsVault Bot v12

Интерактивный калькулятор бонуса прямо в чате.
Работает через InlineKeyboard без ввода текста.

FLOW для casino/nodeposit:
  Кнопка "Посчитай мой бонус 🧮"
  → Выбор размера депозита (кнопки)
  → Расчёт реальной EV с учётом вейджера
  → Персонализированный вывод + CTA

МАТЕМАТИКА:
  Wagering requirement (WR): сколько нужно прокрутить
  Expected Value = bonus_amount × (RTP - 1) × wagering_multiplier
  где RTP ≈ 0.96 для слотов, 0.995 для blackjack

  Пример: €50 бонус, ×20 вейджер, слоты (96% RTP)
    Нужно прокрутить: €50 × 20 = €1000
    Ожидаемые потери: €1000 × (1 - 0.96) = €40
    Ожидаемый выход: €50 - €40 = *€10 чистой прибыли*
    (плюс удовольствие от игры бесплатно)
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# ── Параметры бонусов по интересу ────────────────────────────────────────────

_BONUS_PARAMS: dict[str, dict] = {
    "casino": {
        "typical_wagering": 30,      # × (типичный)
        "good_wagering":    8,        # × (хороший, что мы продвигаем)
        "rtp_slots":        0.96,
        "rtp_blackjack":    0.995,
        "typical_bonus":    100,      # €
    },
    "nodeposit": {
        "typical_wagering": 40,
        "good_wagering":    10,       # что мы продвигаем
        "rtp_slots":        0.96,
        "rtp_blackjack":    0.995,
        "typical_bonus":    25,       # € no-deposit
    },
    "exclusive": {
        "typical_wagering": 20,
        "good_wagering":    8,
        "rtp_slots":        0.96,
        "rtp_blackjack":    0.995,
        "typical_bonus":    100,
    },
    "betting": {
        # Для betting — калькулятор value bet, не бонус
        "typical_margin":   0.05,     # типичная маржа букмекера 5%
        "sharp_margin":     0.02,     # у шарпов 2%
    },
}

# ── Тексты калькулятора ───────────────────────────────────────────────────────

_CALC_INTRO: dict[str, dict[str, str]] = {
    "en": {
        "casino":    "Let me run the actual numbers for you 🧮\n\nHow much are you planning to deposit?",
        "nodeposit": "Here's the math on no-deposit offers 🧮\n\nFirst — what's your usual game type?",
        "exclusive": "Let me calculate your expected edge 🧮\n\nWhat's your typical stake per bet?",
        "betting":   "Let me show you the real edge calculation 🧮\n\nWhat's your typical stake per bet?",
    },
    "es": {
        "casino":    "Déjame hacer los cálculos reales 🧮\n\n¿Cuánto planeas depositar?",
        "nodeposit": "Aquí está la matemática de los bonos sin depósito 🧮\n\nPrimero — ¿qué tipo de juego prefieres?",
        "exclusive": "Déjame calcular tu edge esperado 🧮\n\n¿Cuál es tu apuesta habitual por bet?",
        "betting":   "Déjame mostrarte el cálculo de edge real 🧮\n\n¿Cuál es tu apuesta habitual por bet?",
    },
    "hr": {
        "casino":    "Pusti me da izračunam stvarne brojke 🧮\n\nKoliko planiraš uplatiti?",
        "nodeposit": "Evo matematike za bonuse bez depozita 🧮\n\nPrvo — koji tip igre preferiraš?",
        "exclusive": "Pusti me da izračunam tvoj očekivani edge 🧮\n\nKoliki ti je tipičan ulog po betu?",
        "betting":   "Pusti me da pokažem pravi izračun edgea 🧮\n\nKoliki ti je tipičan ulog po betu?",
    },
    "lt": {
        "casino":    "Leisk man paskaičiuoti tikruosius skaičius 🧮\n\nKiek planuoji įnešti?",
        "nodeposit": "Čia yra be depozito pasiūlymų matematika 🧮\n\nPirmiausia — kokio tipo žaidimus mėgsti?",
        "exclusive": "Leisk man apskaičiuoti tavo tikėtiną pranašumą 🧮\n\nKoks tavo tipinis statymas vienam betui?",
        "betting":   "Leisk man parodyti tikrąjį pranašumo skaičiavimą 🧮\n\nKoks tavo tipinis statymas vienam betui?",
    },
    "lv": {
        "casino":    "Ļauj man aprēķināt īstos skaitļus 🧮\n\nCik plāno iemaksāt?",
        "nodeposit": "Šeit ir bez depozīta piedāvājumu matemātika 🧮\n\nVispirms — kāda veida spēles tev patīk?",
        "exclusive": "Ļauj man aprēķināt tavu paredzamo priekšrocību 🧮\n\nKāds ir tavs tipiskais likums vienai likmei?",
        "betting":   "Ļauj man parādīt reālo priekšrocības aprēķinu 🧮\n\nKāds ir tavs tipiskais likums vienai likmei?",
    },
}

# Кнопки выбора депозита
_DEPOSIT_BUTTONS: dict[str, list] = {
    "en": [
        ("€20–50",   "calc_dep_35"),
        ("€50–100",  "calc_dep_75"),
        ("€100–200", "calc_dep_150"),
        ("€200+",    "calc_dep_300"),
    ],
    "es": [
        ("€20–50",   "calc_dep_35"),
        ("€50–100",  "calc_dep_75"),
        ("€100–200", "calc_dep_150"),
        ("€200+",    "calc_dep_300"),
    ],
    "hr": [
        ("€20–50",   "calc_dep_35"),
        ("€50–100",  "calc_dep_75"),
        ("€100–200", "calc_dep_150"),
        ("€200+",    "calc_dep_300"),
    ],
    "lt": [
        ("€20–50",   "calc_dep_35"),
        ("€50–100",  "calc_dep_75"),
        ("€100–200", "calc_dep_150"),
        ("€200+",    "calc_dep_300"),
    ],
    "lv": [
        ("€20–50",   "calc_dep_35"),
        ("€50–100",  "calc_dep_75"),
        ("€100–200", "calc_dep_150"),
        ("€200+",    "calc_dep_300"),
    ],
}

_STAKE_BUTTONS: dict[str, list] = {
    "en": [
        ("€5–10/bet",  "calc_stake_7"),
        ("€10–25/bet", "calc_stake_17"),
        ("€25–50/bet", "calc_stake_37"),
        ("€50+/bet",   "calc_stake_75"),
    ],
    "es": [
        ("€5–10/apuesta",  "calc_stake_7"),
        ("€10–25/apuesta", "calc_stake_17"),
        ("€25–50/apuesta", "calc_stake_37"),
        ("€50+/apuesta",   "calc_stake_75"),
    ],
    "hr": [
        ("€5–10/ulog",  "calc_stake_7"),
        ("€10–25/ulog", "calc_stake_17"),
        ("€25–50/ulog", "calc_stake_37"),
        ("€50+/ulog",   "calc_stake_75"),
    ],
    "lt": [
        ("€5–10/statymas",  "calc_stake_7"),
        ("€10–25/statymas", "calc_stake_17"),
        ("€25–50/statymas", "calc_stake_37"),
        ("€50+/statymas",   "calc_stake_75"),
    ],
    "lv": [
        ("€5–10/likme",  "calc_stake_7"),
        ("€10–25/likme", "calc_stake_17"),
        ("€25–50/likme", "calc_stake_37"),
        ("€50+/likme",   "calc_stake_75"),
    ],
}

# ── Математика ────────────────────────────────────────────────────────────────

def calculate_bonus_ev(
    deposit: float,
    bonus_pct: float = 1.0,    # 100% match по умолчанию
    wagering: float = 30,      # ×30 типичный
    rtp: float = 0.96,         # слоты
) -> dict:
    """
    Рассчитывает ожидаемую ценность (EV) бонуса.
    Returns dict с ключевыми метриками.
    """
    bonus_amount   = deposit * bonus_pct
    total_to_wager = bonus_amount * wagering
    expected_loss  = total_to_wager * (1 - rtp)
    expected_ev    = bonus_amount - expected_loss

    # Реальный сценарий: считаем и с депозитом в обороте
    total_with_deposit = (deposit + bonus_amount) * wagering / 2  # обычно вейджер только на бонус
    ev_realistic = bonus_amount - (bonus_amount * wagering * (1 - rtp))

    return {
        "deposit":        deposit,
        "bonus_amount":   bonus_amount,
        "wagering_mult":  wagering,
        "to_wager":       total_to_wager,
        "expected_loss":  expected_loss,
        "expected_ev":    ev_realistic,
        "is_positive_ev": ev_realistic > 0,
        "rtp":            rtp,
    }

def calculate_nodeposit_ev(
    bonus: float = 25,
    wagering: float = 10,
    rtp: float = 0.96,
) -> dict:
    """EV для no-deposit бонуса."""
    to_wager      = bonus * wagering
    expected_loss = to_wager * (1 - rtp)
    ev            = bonus - expected_loss

    return {
        "bonus_amount":   bonus,
        "wagering_mult":  wagering,
        "to_wager":       to_wager,
        "expected_loss":  expected_loss,
        "expected_ev":    ev,
        "is_positive_ev": ev > 0,
        "rtp":            rtp,
    }

def calculate_betting_ev(
    stake: float,
    odds: float = 2.0,          # коэффициент
    true_prob: float = 0.52,    # наша оценка реальной вероятности
) -> dict:
    """EV для ставки с value."""
    ev_per_bet = stake * (odds * true_prob - 1)
    roi_pct    = (odds * true_prob - 1) * 100

    return {
        "stake":        stake,
        "odds":         odds,
        "true_prob":    true_prob,
        "ev_per_bet":   ev_per_bet,
        "roi_pct":      roi_pct,
        "is_value_bet": ev_per_bet > 0,
    }

# ── Форматирование результата ─────────────────────────────────────────────────

_RESULT_TEMPLATES: dict[str, dict] = {
    "en": {
        "casino_positive": (
            "Here's your *real* number 🧮\n\n"
            "Deposit: *€{deposit:.0f}*\n"
            "Bonus (100% match): *€{bonus:.0f}*\n"
            "Wagering ×{wagering:.0f}: need to play through *€{to_wager:.0f}*\n"
            "Expected cost at 96% RTP: *€{loss:.0f}*\n\n"
            "→ *Expected profit: €{ev:.0f}* on top of your gameplay\n\n"
            "That's real money sitting on the table. "
            "The channel has this week's best wagering conditions — "
            "most people are clearing it in 2–3 sessions."
        ),
        "casino_negative": (
            "Here's the *honest* math 🧮\n\n"
            "Deposit: *€{deposit:.0f}* | Bonus: *€{bonus:.0f}*\n"
            "Wagering ×{wagering:.0f}: play through *€{to_wager:.0f}*\n"
            "Expected loss at typical RTP: *€{loss:.0f}*\n\n"
            "That's a tough bonus. But here's the thing — the channel "
            "filters for bonuses with ×8–15 wagering. *Those* flip the math positive.\n\n"
            "Want to see what's available right now?"
        ),
        "nodeposit_result": (
            "No-deposit math 🧮\n\n"
            "Free bonus: *€{bonus:.0f}* (zero deposit needed)\n"
            "Wagering ×{wagering:.0f}: play through *€{to_wager:.0f}*\n"
            "Expected cost at 96% RTP: *€{loss:.0f}*\n\n"
            "→ *Expected net: €{ev:.0f}* — for zero investment\n\n"
            "Even if you come out slightly negative, you played for free "
            "and learned the platform. The channel tracks which ones have the best terms."
        ),
        "betting_result": (
            "Value bet math 🧮\n\n"
            "Stake: *€{stake:.0f}* | Odds: *{odds:.2f}*\n"
            "Our edge: *{roi:.1f}% ROI per bet*\n"
            "Expected profit: *€{ev:.2f}* per bet\n\n"
            "Over 100 bets at this edge: *€{total:.0f}* expected profit\n\n"
            "That's what consistent value betting looks like. "
            "The channel posts 3–5 of these per week. The compounding is real."
        ),
    },
    "es": {
        "casino_positive": (
            "Aquí están tus *números reales* 🧮\n\n"
            "Depósito: *€{deposit:.0f}*\n"
            "Bono (100% match): *€{bonus:.0f}*\n"
            "Wagering ×{wagering:.0f}: necesitas jugar *€{to_wager:.0f}*\n"
            "Pérdida esperada al 96% RTP: *€{loss:.0f}*\n\n"
            "→ *Ganancia esperada: €{ev:.0f}* además del juego\n\n"
            "Eso es dinero real sobre la mesa. "
            "El canal tiene las mejores condiciones de wagering de esta semana — "
            "la mayoría lo libera en 2–3 sesiones."
        ),
        "casino_negative": (
            "Aquí está la matemática *honesta* 🧮\n\n"
            "Depósito: *€{deposit:.0f}* | Bono: *€{bonus:.0f}*\n"
            "Wagering ×{wagering:.0f}: juega *€{to_wager:.0f}*\n"
            "Pérdida esperada: *€{loss:.0f}*\n\n"
            "Es un bono difícil. Pero aquí está la clave — el canal "
            "filtra bonos con wagering ×8–15. *Esos* hacen positiva la matemática.\n\n"
            "¿Quieres ver qué hay disponible ahora mismo?"
        ),
        "nodeposit_result": (
            "Matemática sin depósito 🧮\n\n"
            "Bono gratis: *€{bonus:.0f}* (sin depósito)\n"
            "Wagering ×{wagering:.0f}: juega *€{to_wager:.0f}*\n"
            "Pérdida esperada al 96% RTP: *€{loss:.0f}*\n\n"
            "→ *Neto esperado: €{ev:.0f}* — sin inversión\n\n"
            "Aunque salgas ligeramente negativo, jugaste gratis "
            "y conociste la plataforma. El canal rastrea cuáles tienen mejores términos."
        ),
        "betting_result": (
            "Matemática de value bet 🧮\n\n"
            "Apuesta: *€{stake:.0f}* | Cuota: *{odds:.2f}*\n"
            "Nuestro edge: *{roi:.1f}% ROI por apuesta*\n"
            "Ganancia esperada: *€{ev:.2f}* por apuesta\n\n"
            "En 100 apuestas con este edge: *€{total:.0f}* de ganancia esperada\n\n"
            "Así es como funciona el value betting consistente. "
            "El canal publica 3–5 de estos por semana. El interés compuesto es real."
        ),
    },
    "hr": {
        "casino_positive": (
            "Evo tvojih *stvarnih* brojki 🧮\n\n"
            "Uplata: *€{deposit:.0f}*\n"
            "Bonus (100% match): *€{bonus:.0f}*\n"
            "Wagering ×{wagering:.0f}: trebaš proigrati *€{to_wager:.0f}*\n"
            "Očekivani gubitak pri 96% RTP: *€{loss:.0f}*\n\n"
            "→ *Očekivana dobit: €{ev:.0f}* povrh igranja\n\n"
            "To je pravi novac na stolu. "
            "Kanal ima najbolje uvjete wageringa ovog tjedna — "
            "većina to odigra u 2–3 sesije."
        ),
        "casino_negative": (
            "Evo *poštene* matematike 🧮\n\n"
            "Uplata: *€{deposit:.0f}* | Bonus: *€{bonus:.0f}*\n"
            "Wagering ×{wagering:.0f}: odigraj *€{to_wager:.0f}*\n"
            "Očekivani gubitak: *€{loss:.0f}*\n\n"
            "Težak je bonus. Ali evo ključa — kanal "
            "filtrira bonuse s wageringom ×8–15. *Ti* čine matematiku pozitivnom.\n\n"
            "Želiš vidjeti što je dostupno sada?"
        ),
        "nodeposit_result": (
            "Matematika bez depozita 🧮\n\n"
            "Besplatni bonus: *€{bonus:.0f}* (bez depozita)\n"
            "Wagering ×{wagering:.0f}: odigraj *€{to_wager:.0f}*\n"
            "Očekivani gubitak pri 96% RTP: *€{loss:.0f}*\n\n"
            "→ *Očekivani neto: €{ev:.0f}* — bez investicije\n\n"
            "Čak i ako izađeš malo negativno, igrao si besplatno "
            "i upoznao platformu. Kanal prati koji imaju bolje uvjete."
        ),
        "betting_result": (
            "Matematika value beta 🧮\n\n"
            "Ulog: *€{stake:.0f}* | Kvota: *{odds:.2f}*\n"
            "Naš edge: *{roi:.1f}% ROI po betu*\n"
            "Očekivana dobit: *€{ev:.2f}* po betu\n\n"
            "Na 100 oklade s ovim edgeom: *€{total:.0f}* očekivane dobiti\n\n"
            "Ovako izgleda dosljedni value betting. "
            "Kanal objavljuje 3–5 ovakvih tjedno. Složeni prinos je stvaran."
        ),
    },
    "lt": {
        "casino_positive": (
            "Čia tavo *tikrasis* skaičius 🧮\n\n"
            "Depozitas: *€{deposit:.0f}*\n"
            "Bonusas (100% match): *€{bonus:.0f}*\n"
            "Wagering ×{wagering:.0f}: reikia sužaisti *€{to_wager:.0f}*\n"
            "Tikėtini nuostoliai esant 96% RTP: *€{loss:.0f}*\n\n"
            "→ *Tikėtinas pelnas: €{ev:.0f}* virš žaidimo\n\n"
            "Tai realūs pinigai ant stalo. "
            "Kanale yra geriausios šios savaitės wagering sąlygos — "
            "dauguma tai atžaidžia per 2–3 sesijas."
        ),
        "casino_negative": (
            "Čia *sąžininga* matematika 🧮\n\n"
            "Depozitas: *€{deposit:.0f}* | Bonusas: *€{bonus:.0f}*\n"
            "Wagering ×{wagering:.0f}: sužaisk *€{to_wager:.0f}*\n"
            "Tikėtini nuostoliai: *€{loss:.0f}*\n\n"
            "Sunkus bonusas. Bet čia esmė — kanalas "
            "filtruoja bonusus su wagering ×8–15. *Tie* daro matematiką teigiamą.\n\n"
            "Nori pamatyti kas šiuo metu prieinama?"
        ),
        "nodeposit_result": (
            "Be depozito matematika 🧮\n\n"
            "Nemokamas bonusas: *€{bonus:.0f}* (be depozito)\n"
            "Wagering ×{wagering:.0f}: sužaisk *€{to_wager:.0f}*\n"
            "Tikėtini nuostoliai esant 96% RTP: *€{loss:.0f}*\n\n"
            "→ *Tikėtinas grynasis: €{ev:.0f}* — be investicijų\n\n"
            "Net jei šiek tiek prarasite, žaidėte nemokamai "
            "ir pažinote platformą. Kanalas stebi kurie turi geresnes sąlygas."
        ),
        "betting_result": (
            "Value beto matematika 🧮\n\n"
            "Statymas: *€{stake:.0f}* | Koeficientas: *{odds:.2f}*\n"
            "Mūsų pranašumas: *{roi:.1f}% ROI vienam betui*\n"
            "Tikėtinas pelnas: *€{ev:.2f}* vienam betui\n\n"
            "Per 100 statymų su šiuo pranašumu: *€{total:.0f}* tikėtino pelno\n\n"
            "Taip atrodo nuoseklus value betting. "
            "Kanalas skelbia 3–5 tokių per savaitę. Sudėtinės palūkanos yra realios."
        ),
    },
    "lv": {
        "casino_positive": (
            "Šeit ir tavs *īstais* skaitlis 🧮\n\n"
            "Depozīts: *€{deposit:.0f}*\n"
            "Bonuss (100% match): *€{bonus:.0f}*\n"
            "Wagering ×{wagering:.0f}: jānospēlē *€{to_wager:.0f}*\n"
            "Paredzamie zaudējumi pie 96% RTP: *€{loss:.0f}*\n\n"
            "→ *Paredzamā peļņa: €{ev:.0f}* virs spēles\n\n"
            "Tā ir īsta nauda uz galda. "
            "Kanālā ir labākie šīs nedēļas wagering nosacījumi — "
            "vairākums to nospēlē 2–3 sesijās."
        ),
        "casino_negative": (
            "Šeit ir *godīgā* matemātika 🧮\n\n"
            "Depozīts: *€{deposit:.0f}* | Bonuss: *€{bonus:.0f}*\n"
            "Wagering ×{wagering:.0f}: nospēlē *€{to_wager:.0f}*\n"
            "Paredzamie zaudējumi: *€{loss:.0f}*\n\n"
            "Grūts bonuss. Bet šeit ir būtība — kanāls "
            "filtrē bonusus ar wagering ×8–15. *Tie* padara matemātiku pozitīvu.\n\n"
            "Gribi redzēt kas ir pieejams tagad?"
        ),
        "nodeposit_result": (
            "Bez depozīta matemātika 🧮\n\n"
            "Bezmaksas bonuss: *€{bonus:.0f}* (bez depozīta)\n"
            "Wagering ×{wagering:.0f}: nospēlē *€{to_wager:.0f}*\n"
            "Paredzamie zaudējumi pie 96% RTP: *€{loss:.0f}*\n\n"
            "→ *Paredzamais tīrais: €{ev:.0f}* — bez ieguldījuma\n\n"
            "Pat ja nedaudz zaudē, spēlēji bez maksas "
            "un iepazini platformu. Kanāls seko kuriem ir labāki nosacījumi."
        ),
        "betting_result": (
            "Value bets matemātika 🧮\n\n"
            "Likme: *€{stake:.0f}* | Koeficients: *{odds:.2f}*\n"
            "Mūsu priekšrocība: *{roi:.1f}% ROI vienai likmei*\n"
            "Paredzamā peļņa: *€{ev:.2f}* vienai likmei\n\n"
            "100 likmēs ar šo priekšrocību: *€{total:.0f}* paredzamās peļņas\n\n"
            "Tā izskatās konsekvents value betting. "
            "Kanāls publicē 3–5 tādus nedēļā. Saliktie procenti ir reāli."
        ),
    },
}

# ── PUBLIC API ────────────────────────────────────────────────────────────────

def should_show_calculator(interest: str, funnel_stage: str, msg_count: int) -> bool:
    """Показываем калькулятор casino/nodeposit пользователям в AI_CHAT после 3 сообщений."""
    return (
        interest in ("casino", "nodeposit", "exclusive")
        and funnel_stage == "subscribed"
        and msg_count in (3, 8, 15)  # показываем несколько раз
    )

def get_calculator_trigger_text(lang: str, interest: str) -> str:
    """Текст для кнопки запуска калькулятора."""
    triggers = {
        "en": "Want me to calculate your actual expected value? 🧮",
        "es": "¿Quieres que calcule tu valor esperado real? 🧮",
        "hr": "Želiš da izračunam tvoju stvarnu očekivanu vrijednost? 🧮",
        "lt": "Nori kad apskaičiuočiau tavo tikrąją tikėtiną vertę? 🧮",
        "lv": "Gribi lai aprēķinu tavu reālo paredzamo vērtību? 🧮",
    }
    return triggers.get(lang, triggers["en"])

def get_calc_intro(lang: str, interest: str) -> str:
    return _CALC_INTRO.get(lang, _CALC_INTRO["en"]).get(interest, "")

def get_deposit_buttons(lang: str) -> list:
    return _DEPOSIT_BUTTONS.get(lang, _DEPOSIT_BUTTONS["en"])

def get_stake_buttons(lang: str) -> list:
    return _STAKE_BUTTONS.get(lang, _STAKE_BUTTONS["en"])

def format_casino_result(lang: str, deposit: float, interest: str = "casino") -> str:
    """Форматирует результат калькулятора для casino/nodeposit."""
    params = _BONUS_PARAMS.get(interest, _BONUS_PARAMS["casino"])
    wagering = params["good_wagering"]  # Используем хорошие условия (что мы продвигаем)
    rtp      = params["rtp_slots"]

    if interest == "nodeposit":
        bonus  = params["typical_bonus"]  # €25 no-deposit
        result = calculate_nodeposit_ev(bonus=bonus, wagering=wagering, rtp=rtp)
        tmpl   = _RESULT_TEMPLATES.get(lang, _RESULT_TEMPLATES["en"])["nodeposit_result"]
        return tmpl.format(
            bonus=result["bonus_amount"],
            wagering=result["wagering_mult"],
            to_wager=result["to_wager"],
            loss=result["expected_loss"],
            ev=result["expected_ev"],
        )
    else:
        result = calculate_bonus_ev(deposit=deposit, wagering=wagering, rtp=rtp)
        tmpl_key = "casino_positive" if result["is_positive_ev"] else "casino_negative"
        tmpl = _RESULT_TEMPLATES.get(lang, _RESULT_TEMPLATES["en"])[tmpl_key]
        return tmpl.format(
            deposit=result["deposit"],
            bonus=result["bonus_amount"],
            wagering=result["wagering_mult"],
            to_wager=result["to_wager"],
            loss=result["expected_loss"],
            ev=abs(result["expected_ev"]),
        )

def format_betting_result(lang: str, stake: float) -> str:
    """Форматирует результат калькулятора для betting."""
    # Используем типичный value bet из канала: коэффициент 2.1, реальная вероятность 52%
    result = calculate_betting_ev(stake=stake, odds=2.1, true_prob=0.52)
    tmpl   = _RESULT_TEMPLATES.get(lang, _RESULT_TEMPLATES["en"])["betting_result"]
    return tmpl.format(
        stake=result["stake"],
        odds=result["odds"],
        roi=result["roi_pct"],
        ev=result["ev_per_bet"],
        total=result["ev_per_bet"] * 100,
    )

def parse_deposit_callback(callback_data: str) -> Optional[float]:
    """Парсит значение депозита из callback_data. Например 'calc_dep_75' → 75.0"""
    try:
        if callback_data.startswith("calc_dep_"):
            return float(callback_data.split("_")[-1])
        if callback_data.startswith("calc_stake_"):
            return float(callback_data.split("_")[-1])
    except ValueError:
        pass
    return None
