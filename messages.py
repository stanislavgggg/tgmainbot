"""
messages.py — все тексты воронки на 4 языках.
Пиши от лица персонажа — живо, коротко, с характером.
"""

# ─── Шаг 1: Крючок (сразу после /start) ──────────────────────────────────────
HOOK = {
    # Дефолт — английский (для всех неизвестных языков)
    "default": (
        "🎰 Hey.\n\n"
        "I'm Valeria. I've been reading the market for 3 years — and I found something "
        "most people miss.\n\n"
        "It's not magic. It's reading what others don't. 📊\n\n"
        "_Choose your language:_"
    ),
    "en": (
        "🎰 Hey.\n\n"
        "I'm Valeria. I've been reading the market for 3 years — and I found something "
        "most people miss.\n\n"
        "It's not magic. It's reading what others don't. 📊\n\n"
        "_Choose your language:_"
    ),
    "es": (
        "🎰 Oye.\n\n"
        "Soy Valeria. Llevo 3 años siguiendo el mercado — y encontré algo "
        "que la mayoría ignora.\n\n"
        "No es magia. Es leer lo que otros no leen. 📊\n\n"
        "_¿Qué idioma prefieres?_"
    ),
    "hr": (
        "🎰 Hej.\n\n"
        "Ja sam Valerija. Tri godine pratim tržište — i pronašla sam nešto "
        "što većina ignorira.\n\n"
        "Nije magija. To je čitanje onoga što drugi ne čitaju. 📊\n\n"
        "_Koji jezik preferiraš?_"
    ),
    "lt": (
        "🎰 Ei.\n\n"
        "Aš esu Valerija. Trejus metus seku rinką — ir radau tai, "
        "ką dauguma ignoruoja.\n\n"
        "Tai ne magija. Tai skaityti tai, ko kiti neskaito. 📊\n\n"
        "_Kokią kalbą renkiesi?_"
    ),
    "lv": (
        "🎰 Hei.\n\n"
        "Es esmu Valerija. Trīs gadus seku tirgum — un atradu ko tādu, "
        "ko vairākums ignorē.\n\n"
        "Tā nav maģija. Tas ir lasīt to, ko citi nelasa. 📊\n\n"
        "_Kādu valodu preferi?_"
    ),
}

# ─── Кнопки выбора языка ──────────────────────────────────────────────────────
LANG_BUTTONS = [
    ("🇪🇸 Español",  "lang_es"),
    ("🇭🇷 Hrvatski", "lang_hr"),
    ("🇱🇹 Lietuvių", "lang_lt"),
    ("🇱🇻 Latviešu", "lang_lv"),
]

# ─── Шаг 2: Квиз — что тебя цепляет? ─────────────────────────────────────────
QUIZ = {
    "es": "¿Qué te engancha más? 👇",
    "hr": "Što te više zanima? 👇",
    "lt": "Kas tave labiau domina? 👇",
    "lv": "Kas tevi vairāk interesē? 👇",
    "default": "Что тебя больше цепляет? 👇",
}

QUIZ_BUTTONS = {
    "es": [
        ("⚽ Apuestas deportivas",  "int_betting"),
        ("🎰 Bonos de casino",      "int_casino"),
        ("🎁 Sin depósito",         "int_nodeposit"),
        ("🔥 Lo más exclusivo",     "int_exclusive"),
    ],
    "hr": [
        ("⚽ Sportsko klađenje",    "int_betting"),
        ("🎰 Casino bonusi",        "int_casino"),
        ("🎁 Bez depozita",         "int_nodeposit"),
        ("🔥 Ekskluzivno",          "int_exclusive"),
    ],
    "lt": [
        ("⚽ Sporto lažybos",       "int_betting"),
        ("🎰 Kazino bonusai",       "int_casino"),
        ("🎁 Be depozito",          "int_nodeposit"),
        ("🔥 Išskirtiniai",         "int_exclusive"),
    ],
    "lv": [
        ("⚽ Sporta likmes",        "int_betting"),
        ("🎰 Kazino bonusi",        "int_casino"),
        ("🎁 Bez depozīta",         "int_nodeposit"),
        ("🔥 Ekskluzīvi",           "int_exclusive"),
    ],
}

# ─── Шаг 3: Прогрев 1 — личная история ───────────────────────────────────────
WARM1 = {
    "betting": {
        "es": (
            "⚽ Ayer analicé 6 partidos. Solo aposté en 2.\n\n"
            "La clave no es apostar mucho — es esperar el momento donde las cuotas "
            "no reflejan la realidad. Eso pasa más seguido de lo que crees.\n\n"
            "Yo llevo mis propias estadísticas desde hace 2 años. 📋"
        ),
        "hr": (
            "⚽ Jučer sam analizirala 6 utakmica. Kladila se samo na 2.\n\n"
            "Ključ nije klađenje puno — nego čekanje trenutka kad kvote "
            "ne odražavaju stvarnost. To se dogodi češće nego misliš.\n\n"
            "Vodim vlastitu statistiku već 2 godine. 📋"
        ),
        "lt": (
            "⚽ Vakar analizavau 6 rungtynes. Lažinausi tik iš 2.\n\n"
            "Raktas — ne daug lažintis, o laukti momento, kai koeficientai "
            "neatspindi realybės. Tai nutinka dažniau nei manai.\n\n"
            "Pati vedu statistiką jau 2 metus. 📋"
        ),
        "lv": (
            "⚽ Vakar analizēju 6 spēles. Derēju tikai uz 2.\n\n"
            "Atslēga nav daudz derēt — bet gaidīt mirkli, kad koeficienti "
            "neatbilst realitātei. Tas notiek biežāk nekā domā.\n\n"
            "Pati vedu statistiku jau 2 gadus. 📋"
        ),
    },
    "casino": {
        "es": (
            "🎰 La mayoría entra al casino sin entender los bonos.\n\n"
            "Hay plataformas donde el bono de bienvenida tiene wagering x20 "
            "— y otras donde es x5. Esa diferencia lo cambia todo.\n\n"
            "Yo reviso los T&C antes de registrarme en cualquier sitio. 🔍"
        ),
        "hr": (
            "🎰 Većina ulazi u casino bez razumijevanja bonusa.\n\n"
            "Ima platforma gdje bonus dobrodošlice ima wagering x20 "
            "— a drugdje x5. Ta razlika mijenja sve.\n\n"
            "Uvijek čitam uvjete prije registracije. 🔍"
        ),
        "lt": (
            "🎰 Dauguma žmonių eina į kazino nesuprasdami bonusų.\n\n"
            "Yra platformų, kur sveikinamasis bonusas turi wagering x20 "
            "— kitur x5. Tas skirtumas keičia viską.\n\n"
            "Visada skaitau sąlygas prieš registruodamasi. 🔍"
        ),
        "lv": (
            "🎰 Vairums cilvēku iet kazino nesaprotot bonusus.\n\n"
            "Ir platformas ar wagering x20 — un citas ar x5. "
            "Šī atšķirība maina visu.\n\n"
            "Vienmēr lasu noteikumus pirms reģistrācijas. 🔍"
        ),
    },
    "nodeposit": {
        "es": (
            "🎁 Hay bonos sin depósito que casi nadie conoce.\n\n"
            "No los anuncian en la página principal — los encuentras si sabes "
            "dónde buscar. Yo tengo una lista actualizada cada semana.\n\n"
            "Esta semana encontré 3 que tienen sentido real. ✅"
        ),
        "hr": (
            "🎁 Postoje bonusi bez depozita koje gotovo nitko ne zna.\n\n"
            "Ne oglašavaju ih na glavnoj stranici — pronađeš ih ako znaš "
            "gdje tražiti. Ja imam listu koja se ažurira svaki tjedan.\n\n"
            "Ovaj tjedan pronašla sam 3 koje imaju smisla. ✅"
        ),
        "lt": (
            "🎁 Yra bonusų be depozito, kuriuos beveik niekas nežino.\n\n"
            "Jie nereklamuojami pagrindiniame puslapyje — randi, jei žinai "
            "kur ieškoti. Turiu sąrašą, atnaujinamą kas savaitę.\n\n"
            "Šią savaitę radau 3, kurie tikrai prasmingi. ✅"
        ),
        "lv": (
            "🎁 Ir bonusi bez depozīta, kurus gandrīz neviens nezina.\n\n"
            "Tos nereklamē galvenajā lapā — atrod, ja zini kur meklēt. "
            "Man ir saraksts, kas atjaunināts katru nedēļu.\n\n"
            "Šonedēļ atradu 3, kas tiešām ir vērtīgi. ✅"
        ),
    },
    "exclusive": {
        "es": (
            "🔥 Esta semana vi algo interesante en el mercado.\n\n"
            "Las cuotas en un partido específico estaban claramente desajustadas "
            "respecto al histórico. Poca gente lo notó.\n\n"
            "Ese tipo de situaciones son las que yo busco. 🎯"
        ),
        "hr": (
            "🔥 Ovaj tjedan vidio sam nešto zanimljivo na tržištu.\n\n"
            "Kvote na jednoj utakmici bile su jasno neusklađene s poviješću. "
            "Malo tko je to primijetio.\n\n"
            "Takve situacije su ono što tražim. 🎯"
        ),
        "lt": (
            "🔥 Šią savaitę pamačiau kažką įdomaus rinkoje.\n\n"
            "Vieno mačo koeficientai buvo aiškiai neatitinkantys istorinių duomenų. "
            "Nedaug kas tai pastebėjo.\n\n"
            "Tokios situacijos — tai ko aš ieškau. 🎯"
        ),
        "lv": (
            "🔥 Šonedēļ redzēju ko interesantu tirgū.\n\n"
            "Koeficienti vienā spēlē bija skaidri nesakritīgi ar vēsturi. "
            "Maz kas to pamanīja.\n\n"
            "Tādas situācijas ir tas, ko es meklēju. 🎯"
        ),
    },
}

# ─── Шаг 4: Прогрев 2 — социальное доказательство ────────────────────────────
WARM2 = {
    "es": (
        "Por cierto — no soy la única.\n\n"
        "En el canal donde comparto mi análisis hay gente que lleva meses "
        "siguiendo mi lógica. Algunos empezaron escépticos. 😅\n\n"
        "No prometo resultados — comparto mi proceso. El resto es decisión tuya."
    ),
    "hr": (
        "Usput — nisam jedina.\n\n"
        "U kanalu gdje dijelim svoju analizu ima ljudi koji prate moju logiku "
        "već mjesecima. Neki su počeli skeptično. 😅\n\n"
        "Ne obećavam rezultate — dijelim svoj proces. Ostalo je tvoja odluka."
    ),
    "lt": (
        "Beje — aš ne viena.\n\n"
        "Kanale, kur dalinuosi savo analize, yra žmonių, kurie seka mano logiką "
        "jau kelis mėnesius. Kai kurie pradėjo skeptiškai. 😅\n\n"
        "Nežadu rezultatų — dalinuosi savo procesu. Likusi dalis — tavo sprendimas."
    ),
    "lv": (
        "Starp citu — es neesmu vienīgā.\n\n"
        "Kanālā, kur dalūos ar savu analīzi, ir cilvēki, kas seko manai loģikai "
        "jau mēnešus. Daži sākuši skeptiski. 😅\n\n"
        "Nesolu rezultātus — dalūos ar savu procesu. Pārējais ir tavs lēmums."
    ),
}

# ─── Шаг 5: Тизер перед CTA ──────────────────────────────────────────────────
TEASE = {
    "betting": {
        "es": "⚡ Hoy tengo preparado el análisis de los 3 partidos del fin de semana.\n\nEl más interesante no es el más obvio. Lo suelto en el canal esta noche. 👇",
        "hr": "⚡ Danas imam pripremljenu analizu 3 utakmice za vikend.\n\nNajzanimljivija nije najočitija. Objavljujem u kanalu večeras. 👇",
        "lt": "⚡ Šiandien turiu paruoštą 3 savaitgalio rungtynių analizę.\n\nĮdomiausia nėra akivaizdžiausia. Paskelbiu kanale šį vakarą. 👇",
        "lv": "⚡ Šodien man ir sagatavota 3 nedēļas nogales spēļu analīze.\n\nInteresantākā nav acīmredzamākā. Publicēju kanālā šovakar. 👇",
    },
    "casino": {
        "es": "⚡ Esta semana hay 2 bonos con condiciones que casi nadie conoce.\n\nLos detallo en el canal — con los T&C reales, no el resumen de marketing. 👇",
        "hr": "⚡ Ovaj tjedan ima 2 bonusa s uvjetima koje gotovo nitko ne poznaje.\n\nDetaljno ih opisujem u kanalu — s pravim uvjetima, ne marketinškim sažetkom. 👇",
        "lt": "⚡ Šią savaitę yra 2 bonusai su sąlygomis, kurių beveik niekas nežino.\n\nAptariu juos kanale — su tikromis sąlygomis, ne marketingo santrauka. 👇",
        "lv": "⚡ Šonedēļ ir 2 bonusi ar nosacījumiem, kurus gandrīz neviens nezina.\n\nIzskaidroju tos kanālā — ar īstiem noteikumiem, ne mārketinga kopsavilkumu. 👇",
    },
    "nodeposit": {
        "es": "⚡ Encontré un bono sin depósito nuevo — caduca en 48h.\n\nLink y condiciones completas las comparto solo en el canal. 👇",
        "hr": "⚡ Pronašla sam novi bonus bez depozita — ističe za 48h.\n\nLink i potpune uvjete dijelim samo u kanalu. 👇",
        "lt": "⚡ Radau naują bonusą be depozito — galioja 48 val.\n\nNuorodą ir pilnas sąlygas dalinuosi tik kanale. 👇",
        "lv": "⚡ Atradu jaunu bonusu bez depozīta — beidzas 48h laikā.\n\nSaiti un pilnus nosacījumus dalūos tikai kanālā. 👇",
    },
    "exclusive": {
        "es": "⚡ Esta noche voy a publicar el análisis más detallado del mes.\n\nSolo en el canal. Si no estás ahí, te lo pierdes. 👇",
        "hr": "⚡ Večeras ću objaviti najdetaljniju analizu ovog mjeseca.\n\nSamo u kanalu. Ako nisi tamo, propuštaš. 👇",
        "lt": "⚡ Šiąnakt paskelbsiu išsamiausią šio mėnesio analizę.\n\nTik kanale. Jei ten nesi — praleidi. 👇",
        "lv": "⚡ Šovakar publicēšu šī mēneša detalizētāko analīzi.\n\nTikai kanālā. Ja neesi tur — palaid garām. 👇",
    },
}

# ─── CTA — подписка ───────────────────────────────────────────────────────────
CTA = {
    "es": "📲 Únete al canal",
    "hr": "📲 Pridruži se kanalu",
    "lt": "📲 Prisijunk prie kanalo",
    "lv": "📲 Pievienojies kanālam",
}

CTA_BUTTON_JOINED = {
    "es": "✅ Ya me uní",
    "hr": "✅ Već sam se pridružio",
    "lt": "✅ Jau prisijungiau",
    "lv": "✅ Jau pievienojos",
}

# ─── После подписки ───────────────────────────────────────────────────────────
POST_SUB = {
    "es": (
        "✅ Perfecto.\n\n"
        "Ahora estás donde pasan las cosas. Yo publico ahí cada día.\n\n"
        "Y si quieres hablar directamente — escríbeme aquí. Respondo cuando puedo. 💬"
    ),
    "hr": (
        "✅ Savršeno.\n\n"
        "Sada si tamo gdje se stvari događaju. Objavljujem tamo svaki dan.\n\n"
        "A ako želiš razgovarati izravno — piši mi ovdje. Odgovaram kad mogu. 💬"
    ),
    "lt": (
        "✅ Puiku.\n\n"
        "Dabar esi ten, kur vyksta veiksmas. Skelbiu ten kasdien.\n\n"
        "O jei nori kalbėti tiesiogiai — rašyk man čia. Atsakau kai galiu. 💬"
    ),
    "lv": (
        "✅ Lieliski.\n\n"
        "Tagad esi tur, kur notiek darbība. Publicēju tur katru dienu.\n\n"
        "Un ja gribi runāt tieši — raksti man šeit. Atbildu kad varu. 💬"
    ),
}

# ─── Re-engage 1 (24 часа, не подписался) ────────────────────────────────────
REENGAGE_1 = {
    "es": (
        "🎰 Oye, ¿sigues por aquí?\n\n"
        "Ayer en el canal publiqué algo que generó bastante debate. "
        "No voy a hacer spoiler — está ahí esperándote.\n\n"
        "¿Te apuntas? 👇"
    ),
    "hr": (
        "🎰 Hej, jesi li još ovdje?\n\n"
        "Jučer sam u kanalu objavila nešto što je izazvalo dosta rasprave. "
        "Neću spoilati — tamo te čeka.\n\n"
        "Priključuješ se? 👇"
    ),
    "lt": (
        "🎰 Ei, ar vis dar čia?\n\n"
        "Vakar kanale paskelbiau kai ką, kas sukėlė nemažai diskusijų. "
        "Nespoilinsu — ten laukia tavęs.\n\n"
        "Prisijungi? 👇"
    ),
    "lv": (
        "🎰 Hei, vai joprojām esi šeit?\n\n"
        "Vakar kanālā publicēju ko tādu, kas izraisīja diezgan daudz diskusiju. "
        "Nespoilerošu — tas tur gaida tevi.\n\n"
        "Pievienojies? 👇"
    ),
}

# ─── Re-engage 2 (48 часов, не подписался) ───────────────────────────────────
REENGAGE_2 = {
    "es": (
        "📊 Última vez que te escribo sobre esto.\n\n"
        "Esta semana en el canal: 4 análisis, 2 bonos interesantes, "
        "y una situación de value que raramente se ve.\n\n"
        "Si en algún momento cambias de idea — el canal sigue ahí. 🎰"
    ),
    "hr": (
        "📊 Zadnji put da ti pišem o ovome.\n\n"
        "Ovaj tjedan u kanalu: 4 analize, 2 zanimljiva bonusa "
        "i value situacija koja se rijetko vidi.\n\n"
        "Ako ikad promijeniš mišljenje — kanal je i dalje tamo. 🎰"
    ),
    "lt": (
        "📊 Paskutinis kartas rašau tau apie tai.\n\n"
        "Šią savaitę kanale: 4 analizės, 2 įdomūs bonusai "
        "ir value situacija, kuri retai pasitaiko.\n\n"
        "Jei kada nors pakeisi nuomonę — kanalas vis dar ten. 🎰"
    ),
    "lv": (
        "📊 Pēdējoreiz rakstu tev par to.\n\n"
        "Šonedēļ kanālā: 4 analīzes, 2 interesanti bonusi "
        "un value situācija, kas reti sastopama.\n\n"
        "Ja kādreiz mainīsi domas — kanāls joprojām tur. 🎰"
    ),
}

# ─── Хелпер: достать текст с фолбэком ────────────────────────────────────────
def get(mapping: dict, lang: str, interest: str = None) -> str:
    """Достаёт текст из вложенного словаря с фолбэком на es."""
    if interest and isinstance(mapping.get(interest), dict):
        d = mapping[interest]
        return d.get(lang) or d.get("es", "")
    return mapping.get(lang) or mapping.get("es") or mapping.get("default", "")
