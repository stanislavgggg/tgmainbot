"""
messages.py — ДОПОЛНЕНИЕ v2 (English как дефолт)

КАК ПРИМЕНИТЬ:
1. LANG_BUTTONS — замени весь список целиком (добавлен English).
2. QUIZ / QUIZ_BUTTONS — добавь "en" ключи.
3. WAKE_UP, QUIZ_ACK — новые словари, вставь перед get().
4. В каждый существующий словарь добавь "en" ключ из этого файла.
5. config.py — добавь "en" в CHANNELS.
"""

# ══════════════════════════════════════════════════════════════════════════════
#  LANG_BUTTONS — ЗАМЕНИ ЦЕЛИКОМ в messages.py
# ══════════════════════════════════════════════════════════════════════════════
LANG_BUTTONS: list[tuple[str, str]] = [
    ("🇬🇧 English",  "lang_en"),
    ("🇪🇸 Español",  "lang_es"),
    ("🇭🇷 Hrvatski", "lang_hr"),
    ("🇱🇹 Lietuvių", "lang_lt"),
    ("🇱🇻 Latviešu", "lang_lv"),
]

# ══════════════════════════════════════════════════════════════════════════════
#  QUIZ — ДОБАВЬ "en" в существующий словарь
# ══════════════════════════════════════════════════════════════════════════════
# "en": (
#     "Quick question before I let you in 🔐\n\n"
#     "*What interests you most right now?*"
# ),

# ══════════════════════════════════════════════════════════════════════════════
#  QUIZ_BUTTONS — ДОБАВЬ "en" в существующий словарь
# ══════════════════════════════════════════════════════════════════════════════
# "en": [
#     ("⚽ Sports betting",    "int_betting"),
#     ("🎰 Casino & bonuses", "int_casino"),
#     ("🎁 No deposit",       "int_nodeposit"),
#     ("🔥 All of it",        "int_exclusive"),
# ],

# ══════════════════════════════════════════════════════════════════════════════
#  WAKE_UP — НОВЫЙ СЛОВАРЬ. Вставь перед get() в конце messages.py
# ══════════════════════════════════════════════════════════════════════════════
WAKE_UP: dict[str, str] = {
    "en": (
        "Hey.\n\n"
        "I've been waiting for you. 🎯\n\n"
        "My name is *Valeria*. I track odds and bonuses that never make it "
        "to any comparison site — only to the people who are in the right place.\n\n"
        "I'm not selling anything. I just share what I find."
    ),
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
#  QUIZ_ACK — НОВЫЙ СЛОВАРЬ. Вставь перед get() в конце messages.py
# ══════════════════════════════════════════════════════════════════════════════
QUIZ_ACK: dict[str, str] = {
    "en": "Got it. Give me a moment... ⏳",
    "es": "Entendido. Dame un momento... ⏳",
    "hr": "Razumijem. Daj mi trenutak... ⏳",
    "lt": "Suprantu. Duok man akimirką... ⏳",
    "lv": "Saprotu. Dod man brīdi... ⏳",
}

# ══════════════════════════════════════════════════════════════════════════════
#  WARM1 — ДОБАВЬ "en" в существующий словарь WARM1 (перед "es")
# ══════════════════════════════════════════════════════════════════════════════
# "en": {
#     "betting": (
#         "A few months back, someone messaged me at 2am.\n\n"
#         "«Valeria, I just saw the line you posted yesterday. I missed it. 3.40 on the Over. "
#         "Why didn't I get here sooner?»\n\n"
#         "That hit me — because I know that feeling exactly.\n\n"
#         "*The right information always arrives late when you're not in the right place.* ⏱️\n\n"
#         "Has that ever happened to you — seeing something too late?"
#     ),
#     "casino": (
#         "Let me tell you something you rarely see out there.\n\n"
#         "Last week there was a welcome bonus with ×12 wagering. "
#         "Not ×35, not ×40 — *twelve*. It lasted 6 hours before they adjusted it.\n\n"
#         "We posted it in the channel. 340 people grabbed it that day.\n\n"
#         "*Good bonuses don't wait.* And the people who arrive late always see an empty screen.\n\n"
#         "Do you actively hunt for the best bonuses, or do they just find you?"
#     ),
#     "nodeposit": (
#         "People think all no-deposit bonuses are the same.\n\n"
#         "Spoiler: they're not. There's a brutal difference between ×60 wagering "
#         "and ×8 — the first is basically an illusion, the second is real money.\n\n"
#         "We've been filtering the garbage for 2 years to keep only what's worth it.\n\n"
#         "*The problem isn't that good bonuses don't exist — it's knowing which ones they are.*\n\n"
#         "Have you ever burned through a bonus without understanding the conditions?"
#     ),
#     "exclusive": (
#         "I'll be straight with you.\n\n"
#         "There are two types of people in this world:\n"
#         "the ones who react when it's already too late, and the ones who are there when it happens.\n\n"
#         "It's not luck. It's being in the right place with the right information.\n\n"
#         "*What we post in the vault — odds, bonuses, signals — "
#         "never reaches Twitter or public groups. It lands there first.*\n\n"
#         "What's been missing for you until now — speed or quality?"
#     ),
# },

# ══════════════════════════════════════════════════════════════════════════════
#  WARM2 — ДОБАВЬ "en" в существующий словарь WARM2 (перед "es")
# ══════════════════════════════════════════════════════════════════════════════
# "en": (
#     "And it's not just me saying this.\n\n"
#     "Last month the channel grew by +2,800 people. Not through ads — "
#     "through word of mouth.\n\n"
#     "Miguel (Seville): *«Been following the signals for 3 weeks. I haven't changed anything, "
#     "just added context to the analysis I was already doing. I notice the difference.»*\n\n"
#     "Andris (Riga): *«The no-wagering bonus you found saved my January.»*\n\n"
#     "No promises. Just real people who found something useful.\n\n"
#     "What are you looking for right now — signals, bonuses, analysis?"
# ),

# ══════════════════════════════════════════════════════════════════════════════
#  TEASE — ДОБАВЬ "en" в существующий словарь TEASE (перед "es")
# ══════════════════════════════════════════════════════════════════════════════
# "en": {
#     "betting": (
#         "Okay. Listen to this.\n\n"
#         "Tomorrow there's a match — I'm not telling you which one yet — "
#         "where the market is clearly miscalibrated. "
#         "The real line should be ~2.10. It's sitting at 2.85.\n\n"
#         "That gap doesn't last. Once the bookmakers correct it, there's nothing left to do.\n\n"
#         "*I'll post it in the channel before the match.* The people who are there will see it.\n\n"
#         "The rest... well, you know."
#     ),
#     "casino": (
#         "I've got something in the works.\n\n"
#         "A platform is running a promo this week — "
#         "×8 wagering, low minimum deposit, cashback included.\n\n"
#         "It's not on their main site. It's on a specific landing page that expires Friday.\n\n"
#         "*I posted it in the channel 3 days ago. Already 200+ people are inside.*\n\n"
#         "Do you want to be the one who arrives late, or the one who's already there?"
#     ),
#     "nodeposit": (
#         "Today there are 3 active no-deposit bonuses that aren't on any comparison site.\n\n"
#         "Two of them have ×10 wagering or less. One has no wagering at all.\n\n"
#         "Comparison sites update every 48–72 hours. We have them in real time.\n\n"
#         "*The window is closing — some already expired while you're reading this.*\n\n"
#         "Want to know which ones are still active?"
#     ),
#     "exclusive": (
#         "This week in the vault:\n\n"
#         "• A value signal in La Liga published 18h in advance ✅\n"
#         "• A casino bonus with ×9 wagering that lasted 11 hours ✅\n"
#         "• An arbitrage between two European bookmakers with estimated ROI +6% ✅\n\n"
#         "All of this happened. Last week.\n\n"
#         "*Next week it'll happen again — with or without you.*"
#     ),
# },

# ══════════════════════════════════════════════════════════════════════════════
#  CTA_TEXT — ДОБАВЬ "en" в существующий словарь
# ══════════════════════════════════════════════════════════════════════════════
# "en": "🔐 *The vault is right there.*\n\nI've told you everything I can here.",

# ══════════════════════════════════════════════════════════════════════════════
#  CTA — ДОБАВЬ "en" в существующий словарь
# ══════════════════════════════════════════════════════════════════════════════
# "en": "📲 Join OddsVault",

# ══════════════════════════════════════════════════════════════════════════════
#  CTA_BUTTON_JOINED — ДОБАВЬ "en" в существующий словарь
# ══════════════════════════════════════════════════════════════════════════════
# "en": "✅ I'm already in",

# ══════════════════════════════════════════════════════════════════════════════
#  POST_SUB — ДОБАВЬ "en" в существующий словарь (перед "es")
# ══════════════════════════════════════════════════════════════════════════════
# "en": {
#     "betting": (
#         "Perfect. You're exactly where you need to be.\n\n"
#         "One more thing — if you ever want to talk through an analysis, "
#         "a specific line, or a strategy, just write me here.\n\n"
#         "I respond. Not like a bot — like someone who actually knows this stuff. 🎯"
#     ),
#     "casino": (
#         "Well done. You'll notice the difference.\n\n"
#         "And if you have questions about any bonus — conditions, "
#         "how to calculate it, whether it's worth it — I'm right here.\n\n"
#         "Real conversation. 💎"
#     ),
#     "nodeposit": (
#         "Welcome to the side where bonuses actually make sense.\n\n"
#         "If you ever have doubts about wagering, "
#         "eligible games, or withdrawals — ask me here.\n\n"
#         "I'm here. 🎁"
#     ),
#     "exclusive": (
#         "You're part of the vault now.\n\n"
#         "This chat stays active — if you want to analyse something, "
#         "ask about a line or a bonus, we do it here.\n\n"
#         "No limits. No filters. 🔥"
#     ),
# },

# ══════════════════════════════════════════════════════════════════════════════
#  REENGAGE_1 — ДОБАВЬ "en" в существующий словарь
# ══════════════════════════════════════════════════════════════════════════════
# "en": (
#     "Hey — still there? 👀\n\n"
#     "Yesterday I posted something in the vault you won't find anywhere else.\n\n"
#     "If you want to see it, you know where to go."
# ),

# ══════════════════════════════════════════════════════════════════════════════
#  REENGAGE_2 — ДОБАВЬ "en" в существующий словарь
# ══════════════════════════════════════════════════════════════════════════════
# "en": (
#     "Last time I'll write about this.\n\n"
#     "There are 3 big events this week. The analysis is already ready.\n\n"
#     "After the first whistle... it's too late. ⏳"
# ),

# ══════════════════════════════════════════════════════════════════════════════
#  FTD_PUSH — ДОБАВЬ "en" в существующий словарь (перед "es")
# ══════════════════════════════════════════════════════════════════════════════
# "en": {
#     "betting":   ("By the way — there's a value window in the top flight this week. Details in the channel. 📊"),
#     "casino":    ("New bonus this week with very low wagering. In the channel with all details. 💎"),
#     "nodeposit": ("Two new no-deposit bonuses just went live. In the channel — grab them before they expire. 🎁"),
#     "exclusive": ("The vault has fresh material this week. Signals, bonuses, and analysis you won't find elsewhere. 🔥"),
# },

# ══════════════════════════════════════════════════════════════════════════════
#  config.py — ДОБАВЬ "en" В CHANNELS
# ══════════════════════════════════════════════════════════════════════════════
# В CHANNELS добавь блок "en" (используй тот же канал что и "es" или свой):
#
# "en": {
#     "betting":   {"url": "https://t.me/ApuestasGuruES",  "extra_url": ""},
#     "casino":    {"url": "https://t.me/ApuestasGuruES",  "extra_url": ""},
#     "nodeposit": {"url": "https://t.me/ApuestasGuruES",  "extra_url": ""},
#     "exclusive": {"url": "https://t.me/ApuestasGuruES",  "extra_url": ""},
# },
