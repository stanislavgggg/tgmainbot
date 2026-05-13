"""
messages.py — ДОПОЛНЕНИЕ к существующему файлу
Вставь эти два словаря ПЕРЕД функцией get() в конце messages.py.

WAKE_UP  — живое первое сообщение когда язык определён автоматически.
           Заменяет HOOK + выбор языка для поддерживаемых локалей.
QUIZ_ACK — короткое подтверждение после выбора интереса,
           пока бот "печатает" WARM1.
"""


# ══════════════════════════════════════════════════════════════════════════════
#  WAKE_UP — первое сообщение когда язык определён автоматически
#  Цель: создать персонажа за одно сообщение, не информировать.
# ══════════════════════════════════════════════════════════════════════════════
WAKE_UP: dict[str, str] = {
    "es": (
        "Hola.\n\n"
        "Te estaba esperando. 🎯\n\n"
        "Me llamo *Valeria*. Llevo años rastreando odds y bonos que no llegan "
        "a ningún comparador — solo a las personas que están en el lugar correcto.\n\n"
        "No vendo nada. Solo comparto lo que encuentro."
    ),
    "hr": (
        "Hej.\n\n"
        "Čekala sam te. 🎯\n\n"
        "Zovem se *Valerija*. Godinama pratim kvote i bonuse koji ne dolaze "
        "ni na jedan uspoređivač — samo do ljudi koji su na pravom mjestu.\n\n"
        "Ništa ne prodajem. Samo dijelim ono što pronađem."
    ),
    "lt": (
        "Sveiki.\n\n"
        "Laukiau tavęs. 🎯\n\n"
        "Mano vardas *Valerija*. Metų metus seku koeficientus ir bonusus, "
        "kurie nepatenka į jokius palyginimo puslapius — tik pas žmones, "
        "kurie yra tinkamoje vietoje.\n\n"
        "Nieko neparduodu. Tik dalinausi tuo, ką randu."
    ),
    "lv": (
        "Sveiki.\n\n"
        "Es tevi gaidīju. 🎯\n\n"
        "Mani sauc *Valerija*. Gadus seku koeficientiem un bonusiem, "
        "kas nenonāk nevienā salīdzinātājā — tikai pie cilvēkiem, "
        "kas ir pareizajā vietā.\n\n"
        "Es neko nepārdodu. Tikai dalūos ar to, ko atrodu."
    ),
}


# ══════════════════════════════════════════════════════════════════════════════
#  QUIZ_ACK — подтверждение после выбора интереса
#  Показывается пока бот "думает" и готовит WARM1.
#  Заменяет кнопки в edit_message_text чтобы не было пустого сообщения.
# ══════════════════════════════════════════════════════════════════════════════
QUIZ_ACK: dict[str, str] = {
    "es": "Entendido. Dame un momento... ⏳",
    "hr": "Razumijem. Daj mi trenutak... ⏳",
    "lt": "Suprantu. Duok man akimirką... ⏳",
    "lv": "Saprotu. Dod man brīdi... ⏳",
}
