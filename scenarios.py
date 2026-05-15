"""
scenarios.py — OddsVault Bot v14
Полная обработка всех сценариев пользователей.
Импортируется в bot.py и conversation.py.
"""

VIP_FTD_THRESHOLD = 2  # пользователь считается VIP после N депозитов

# ══════════════════════════════════════════════════════════════════════════════
# СЦЕНАРИИ ДО ПОДПИСКИ
# ══════════════════════════════════════════════════════════════════════════════

PRE_SUB_SCENARIOS = {

    # S1: Активный диалог → tease → CTA
    # Обрабатывается: conversation.py ask_valeria_conversational
    # Триггер: [READY:tease] от AI когда разговор созрел
    "s1_active_dialogue": {
        "description": "Normal flow — active conversation leads naturally to tease",
        "handled_by": "ask_valeria_conversational + _handle_warming",
        "tease_trigger": "AI sets [READY:tease] based on conversation quality",
    },

    # S2: Замолчал в warming → возврат
    # Обрабатывается: reengage_job
    # 4h silence → один вопрос продолжающий разговор (без CTA)
    # 24h silence → последний шанс + CTA если был в tease/cta
    "s2_went_silent_pre_sub": {
        "description": "User stopped responding during warming",
        "silence_4h": "One contextual question — continue the conversation",
        "silence_24h": "Last chance message + CTA button if in tease/cta",
        "no_more_pushes": "After 2 attempts, go quiet",
    },

    # S3: Скептик
    # Обрабатывается: ask_valeria_conversational с психотипом cynic/skeptic
    # Длинный диалог нормален — AI не торопит
    "s3_skeptic": {
        "description": "Skeptical user, many objections",
        "approach": "Facts only, no pressure, let them draw conclusions",
        "tease_timing": "Only when skepticism addressed, could be 10+ exchanges",
    },

    # S4: Нет денег
    # Обрабатывается: detect_interest_from_text → nodeposit
    # Переключение на no-deposit путь
    "s4_no_money": {
        "description": "User says they have no money",
        "auto_switch": "interest → nodeposit",
        "approach": "Zero-risk no-deposit path, math explanation",
    },

    # S5: Уже зарегистрирован где-то
    # Обрабатывается: classify_objection → already_elsewhere
    # Переиспользуем как преимущество (больше каналов = больше возможностей)
    "s5_already_registered": {
        "description": "User has account elsewhere",
        "approach": "Reframe as advantage — stack accounts, more opportunities",
    },

    # S6: Другой язык
    # Обрабатывается: _detect_lang_switch + detect_geo_from_text
    "s6_language_switch": {
        "description": "User writes in different language",
        "auto_detect": "Language + GEO detected from text, switch immediately",
    },

    # S7: Повторный /start
    # Обрабатывается: start() — проверяем существующего пользователя
    "s7_returning_user": {
        "description": "User sends /start again after silence",
        "approach": "Warm return, reference past conversation, don't start from scratch",
    },

    # S8: Пользователь ругается / троллит
    # Обрабатывается: AI промпт — не вовлекаться, мягко вернуть к теме
    "s8_troll": {
        "description": "User sends inappropriate or trolling messages",
        "approach": "Don't engage, brief redirect to the topic",
    },
}

# ══════════════════════════════════════════════════════════════════════════════
# СЦЕНАРИИ ПОСЛЕ ПОДПИСКИ (онбординг → FTD)
# ══════════════════════════════════════════════════════════════════════════════

POST_SUB_SCENARIOS = {

    # S9: Активно отвечает на онбординг
    # Обрабатывается: _handle_ai_chat → ask_valeria_conversational
    # Таймеры онбординга НЕ отправляются если пользователь активен
    "s9_active_onboarding": {
        "description": "User responds actively after subscription",
        "skip_timers": "Onboarding steps skipped if user_active_since()",
        "approach": "Pure dialogue — AI leads to FTD naturally",
    },

    # S10: Молчит после подписки
    # Обрабатывается: ftd_onboarding scheduled jobs
    # Шаги 1-6 по барьеру, адаптивные задержки
    "s10_silent_post_sub": {
        "description": "User doesn't respond after subscription",
        "sequence": "step1(90s) → classify_barrier(15m) → step2-6 adaptive",
    },

    # S11: Нет денег (после подписки)
    # barrier = no_money → no-deposit path
    "s11_no_money_post_sub": {
        "description": "User mentions no money after subscribing",
        "barrier": "no_money",
        "step2": "Zero-risk no-deposit path, specific offer",
        "step3": "Someone who started same way — result",
    },

    # S12: Недоверие
    # barrier = no_trust → факты без CTA
    "s12_trust_issues": {
        "description": "User doesn't trust — says it's a scam etc",
        "barrier": "no_trust",
        "step2": "One verifiable fact. Check it yourself. No CTA.",
        "step3": "Public track record. Let them verify.",
    },

    # S13: Уже в другом сервисе
    # barrier = already_elsewhere → стакинг как преимущество
    "s13_other_service": {
        "description": "User already uses another platform",
        "barrier": "already_elsewhere",
        "step2": "Multiple accounts = more access. What platform?",
    },

    # S14: Не понимает как работает
    # barrier = dont_understand → одно простое объяснение
    "s14_confused": {
        "description": "User doesn't understand the mechanic",
        "barrier": "dont_understand",
        "step2": "One sentence. Which part is unclear?",
    },

    # S15: Думает (passive/thinking)
    # barrier = thinking → мягкий nudge
    "s15_thinking": {
        "description": "User engaged but still considering",
        "barrier": "thinking",
        "step2": "What's the one thing you're not sure about?",
    },

    # S16: Выиграл первую ставку/бонус
    # FTD detected + message about win → celebrate + maximize
    "s16_won": {
        "description": "User won on first session",
        "detect": "Keywords: won, profit, +, winning",
        "response": "Celebrate briefly → how to compound this win → next step",
    },

    # S17: Проиграл первую ставку/бонус
    # FTD detected + message about loss → reframe, don't abandon
    "s17_lost": {
        "description": "User lost on first session",
        "detect": "Keywords: lost, minus, didn't work, -",
        "response": "Normalize → edge is over many bets → what to do next",
    },
}

# ══════════════════════════════════════════════════════════════════════════════
# СЦЕНАРИИ REPEAT FTD
# ══════════════════════════════════════════════════════════════════════════════

REPEAT_SCENARIOS = {

    # S18: Второй депозит
    "s18_second_ftd": {
        "description": "User makes second deposit",
        "approach": "Confirm they're doing it right. Optimize strategy.",
        "prompt_shift": "From selling to coaching",
    },

    # S19: VIP (2+ депозитов)
    "s19_vip": {
        "description": "User has 2+ FTDs — loyal active user",
        "tone_shift": "Peer to peer, not sales. Real analysis.",
        "content": "Deeper strategy, P&L optimization, stacking techniques",
    },

    # S20: Реферал сработал
    "s20_referral_converted": {
        "description": "Someone they referred subscribed/deposited",
        "notify": "Brief thanks + acknowledge their contribution",
    },

    # S21: Долгое молчание VIP (7+ дней)
    "s21_vip_gone_silent": {
        "description": "Active user went quiet for a week",
        "approach": "Personal check-in. Not a push. What happened?",
    },
}

# ══════════════════════════════════════════════════════════════════════════════
# ДЕТЕКТОРЫ СЦЕНАРИЕВ
# ══════════════════════════════════════════════════════════════════════════════

_WIN_SIGNALS = [
    "won","profit","win","winning","+","made money","worked","it worked",
    "ganó","gané","beneficio","funcionó","ganancia",
    "zaradio","zarada","profitirao","funkcioniralo",
    "laimėjau","pelnas","veikė",
    "nopelnīju","peļņa","darbojās",
]

_LOSS_SIGNALS = [
    "lost","loss","losing","didn't work","minus","went wrong","failed",
    "perdí","perdida","no funcionó","fallido",
    "izgubio","gubitak","nije radilo",
    "pralaimėjau","nuostolis","neveikė",
    "zaudēju","zaudējums","nedarbojās",
]

_RETURN_SIGNALS = [
    "i'm back","back again","returning","missed","volvió","vratio se",
    "grįžau","atgriezos",
]

def detect_win_signal(text: str) -> bool:
    lower = text.lower()
    return any(s in lower for s in _WIN_SIGNALS)

def detect_loss_signal(text: str) -> bool:
    lower = text.lower()
    return any(s in lower for s in _LOSS_SIGNALS)

def detect_return_signal(text: str) -> bool:
    lower = text.lower()
    return any(s in lower for s in _RETURN_SIGNALS)

def classify_post_ftd_message(text: str) -> str:
    """Classify what kind of message a post-FTD user sent."""
    from ftd_onboarding import detect_ftd_signal
    if detect_ftd_signal(text):    return "new_ftd"
    if detect_win_signal(text):    return "won"
    if detect_loss_signal(text):   return "lost"
    if detect_return_signal(text): return "returning"
    return "normal"

# ══════════════════════════════════════════════════════════════════════════════
# WIN/LOSS RESPONSE TEMPLATES
# ══════════════════════════════════════════════════════════════════════════════

_WIN_RESPONSES = {
    "en": {
        "betting":   "That's how it starts. 🎯 *Don't scale up too fast* — the edge compounds over many bets, not one. What did you stake and what did the signal say?",
        "casino":    "Good start. 💎 *Check your wagering progress now* — that's the number that matters. How much is left to clear?",
        "nodeposit": "That's real money from zero risk. 🎁 *How much did you clear?* The next step depends on the number.",
        "exclusive": "Both sides working. 🔥 *Log this one* — after 20 bets the pattern becomes obvious. What was the edge on this signal?",
    },
    "es": {
        "betting":   "Así empieza. 🎯 *No escales demasiado rápido* — el edge se compone en muchas apuestas, no en una. ¿Cuánto apostaste y qué decía la señal?",
        "casino":    "Buen comienzo. 💎 *Revisa tu progreso de wagering ahora* — ese es el número que importa. ¿Cuánto queda por liberar?",
        "nodeposit": "Eso es dinero real con riesgo cero. 🎁 *¿Cuánto liberaste?* El siguiente paso depende del número.",
        "exclusive": "Ambos lados funcionando. 🔥 *Registra este* — después de 20 apuestas el patrón se vuelve obvio. ¿Cuál era el edge en esta señal?",
    },
    "hr": {
        "betting":   "Tako počinje. 🎯 *Ne skaliraj prebrzo* — edge se komponira u mnogim okladama, ne u jednoj. Koliko si uložio i što je signal govorio?",
        "casino":    "Dobar početak. 💎 *Provjeri napredak wageringa sada* — to je broj koji je važan. Koliko je ostalo za osloboditi?",
        "nodeposit": "To je pravi novac bez rizika. 🎁 *Koliko si oslobodio?* Sljedeći korak ovisi o broju.",
        "exclusive": "Obje strane rade. 🔥 *Zabilježi ovu* — nakon 20 oklada obrazac postaje očit. Koji je bio edge na ovom signalu?",
    },
    "lt": {
        "betting":   "Taip prasideda. 🎯 *Neskubėk didinti* — pranašumas kaupiasi daugelyje statymų, ne viename. Kiek statei ir ką signalas sakė?",
        "casino":    "Geras pradžia. 💎 *Patikrink wagering pažangą dabar* — tai yra svarbus skaičius. Kiek liko išvalyti?",
        "nodeposit": "Tai realūs pinigai be rizikos. 🎁 *Kiek išvalei?* Kitas žingsnis priklauso nuo skaičiaus.",
        "exclusive": "Abi pusės veikia. 🔥 *Užrašyk šį* — po 20 statymų modelis tampa akivaizdus. Koks buvo pranašumas šiame signale?",
    },
    "lv": {
        "betting":   "Tā tas sākas. 🎯 *Nepalielinies pārāk ātri* — priekšrocība uzkrājas daudzās likmēs, nevis vienā. Cik liki un ko signāls teica?",
        "casino":    "Labs sākums. 💎 *Pārbaudi wagering progresu tagad* — tas ir svarīgais skaitlis. Cik palicis notīrīt?",
        "nodeposit": "Tā ir īsta nauda bez riska. 🎁 *Cik notīrīji?* Nākamais solis ir atkarīgs no skaitļa.",
        "exclusive": "Abas puses darbojas. 🔥 *Pieraksti šo* — pēc 20 likmēm modelis kļūst acīmredzams. Kāds bija pranašums šajā signālā?",
    },
}

_LOSS_RESPONSES = {
    "en": {
        "betting":   "That happens. One result doesn't define the edge — *the pattern over 20+ bets does*. What was the signal, and was the line where it was supposed to be before kick-off?",
        "casino":    "Variance. *The wagering math still works over enough spins* — one session doesn't tell you much. How far through the wagering are you?",
        "nodeposit": "Still at zero risk — you didn't put any of your own money in. *That's the point of the no-deposit entry.* What game were you playing?",
        "exclusive": "Expected variance. *Even a 3% edge loses 47% of bets* — that's normal. What matters is the next 20 signals. What was the size on this one?",
    },
    "es": {
        "betting":   "Pasa. Un resultado no define el edge — *el patrón en 20+ apuestas sí*. ¿Cuál era la señal, y estaba la cuota donde debía antes del partido?",
        "casino":    "Varianza. *La matemática del wagering sigue funcionando en suficientes spins* — una sesión no te dice mucho. ¿Qué tan avanzado estás en el wagering?",
        "nodeposit": "Sigues sin arriesgar nada propio — no pusiste tu propio dinero. *Ese es el punto de la entrada sin depósito.* ¿Qué juego estabas jugando?",
        "exclusive": "Varianza esperada. *Incluso un edge del 3% pierde el 47% de las apuestas* — es normal. Lo que importa son las próximas 20 señales. ¿Qué tamaño tenía esta?",
    },
    "hr": {
        "betting":   "Dogodi se. Jedan rezultat ne definira edge — *obrazac u 20+ oklada da*. Koji je bio signal, i je li kvota bila tamo gdje je trebala biti pred utakmicu?",
        "casino":    "Varijanca. *Matematika wageringa i dalje funkcionira u dovoljno spinova* — jedna sesija ne govori puno. Koliko daleko si u wageringu?",
        "nodeposit": "Još uvijek si bez rizika — nisi uložio vlastiti novac. *To je smisao ulaza bez depozita.* Koju igru si igrao?",
        "exclusive": "Očekivana varijanca. *Čak i 3% edge gubi 47% oklada* — to je normalno. Što je važno su sljedećih 20 signala. Koliko je bio ulog na ovom?",
    },
    "lt": {
        "betting":   "Taip atsitinka. Vienas rezultatas neapibrėžia pranašumo — *modelis per 20+ statymų apibrėžia*. Koks buvo signalas, ir ar koeficientas buvo ten kur turėjo būti prieš rungtynes?",
        "casino":    "Variacija. *Wagering matematika vis dar veikia per pakankamai sukimų* — viena sesija nepasako daug. Kiek išvalei wagering?",
        "nodeposit": "Vis dar be rizikos — neįdėjai savo pinigų. *Tai ir yra be depozito įėjimo prasmė.* Kokį žaidimą žaidei?",
        "exclusive": "Tikėtina variacija. *Net 3% pranašumas pralaimi 47% statymų* — tai normalu. Svarbiausia yra kiti 20 signalų. Koks buvo šio dydis?",
    },
    "lv": {
        "betting":   "Tā notiek. Viens rezultāts nenosaka priekšrocību — *modelis 20+ likmēs nosaka*. Kāds bija signāls, un vai koeficients bija tur kur vajadzēja pirms spēles?",
        "casino":    "Variācija. *Wagering matemātika joprojām darbojas pietiekami daudz griezienu* — viena sesija daudz nepasaka. Cik tālu esi wagering izpildē?",
        "nodeposit": "Joprojām bez riska — neieguldīji savu naudu. *Tas ir bez depozīta ieejas mērķis.* Kādu spēli spēlēji?",
        "exclusive": "Paredzamā variācija. *Pat 3% priekšrocība zaudē 47% likmju* — tas ir normāli. Svarīgi ir nākamie 20 signāli. Kāds bija šīs likmes lielums?",
    },
}

_VIP_TONE_SHIFT = {
    "en": "You've got real data now — *{ftd_count} sessions in*. Want to do a quick P&L review and see where the actual edge is sitting?",
    "es": "Ya tienes datos reales — *{ftd_count} sesiones*. ¿Quieres hacer una revisión rápida de P&L y ver dónde está el edge real?",
    "hr": "Imaš prave podatke sada — *{ftd_count} sesija*. Želiš li brzi P&L pregled i vidjeti gdje je pravi edge?",
    "lt": "Dabar turi realius duomenis — *{ftd_count} sesijų*. Nori greito P&L peržiūros ir pamatyti kur yra tikrasis pranašumas?",
    "lv": "Tagad tev ir reāli dati — *{ftd_count} sesijas*. Gribi ātru P&L pārskatu un redzēt kur atrodas īstā priekšrocība?",
}

_RETURNING_USER_OPENERS = {
    "en": "You're back. *Where did we leave off* — did anything change on your end?",
    "es": "Has vuelto. *¿Dónde lo dejamos* — ¿ha cambiado algo de tu lado?",
    "hr": "Vratio si se. *Gdje smo stali* — je li se nešto promijenilo s tvoje strane?",
    "lt": "Grįžai. *Kur sustojome* — ar kažkas pasikeitė tavo pusėje?",
    "lv": "Tu atgriezies. *Kur mēs apstājāmies* — vai kaut kas mainījās tavā pusē?",
}

def get_win_response(lang: str, interest: str) -> str:
    return _WIN_RESPONSES.get(lang, _WIN_RESPONSES["en"]).get(interest, "")

def get_loss_response(lang: str, interest: str) -> str:
    return _LOSS_RESPONSES.get(lang, _LOSS_RESPONSES["en"]).get(interest, "")

def get_vip_message(lang: str, ftd_count: int) -> str:
    tmpl = _VIP_TONE_SHIFT.get(lang, _VIP_TONE_SHIFT["en"])
    return tmpl.format(ftd_count=ftd_count)

def get_returning_opener(lang: str) -> str:
    return _RETURNING_USER_OPENERS.get(lang, _RETURNING_USER_OPENERS["en"])
