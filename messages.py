"""
messages.py — все тексты воронки на 4 языках.
Пиши от лица персонажа — живо, коротко, с характером.
"""

# ─── Шаг 1: Крючок (сразу после /start) ──────────────────────────────────────
#
# ЧТО ИЗМЕНЕНО И ПОЧЕМУ:
# Было: абстрактное "я читаю рынок уже 3 года" — звучит как резюме.
# Стало: конкретный момент-триггер. Человек чувствует что пропустил что-то
# реальное и ценное. Эмоция = FOMO + любопытство + лёгкое превосходство
# ("есть те, кто знает — и ты можешь быть среди них").
# Никакого слова "казино" / "ставки" в лоб — только ощущение инсайда.
#
HOOK = {
    "default": (
        "🔥 Last night something happened.\n\n"
        "A match no one was watching. The odds were *wrong* — and a few people "
        "who knew where to look walked away very happy.\n\n"
        "I'm Valeria. I find these moments before they disappear. 🎯\n\n"
        "_Pick your language:_"
    ),
    "en": (
        "🔥 Last night something happened.\n\n"
        "A match no one was watching. The odds were *wrong* — and a few people "
        "who knew where to look walked away very happy.\n\n"
        "I'm Valeria. I find these moments before they disappear. 🎯\n\n"
        "_Pick your language:_"
    ),
    "es": (
        "🔥 Anoche pasó algo.\n\n"
        "Un partido que nadie vigilaba. Las cuotas estaban *mal calculadas* — "
        "y los pocos que sabían dónde mirar salieron muy contentos.\n\n"
        "Soy Valeria. Encuentro estos momentos antes de que desaparezcan. 🎯\n\n"
        "_¿Qué idioma prefieres?_"
    ),
    "hr": (
        "🔥 Sinoć se nešto dogodilo.\n\n"
        "Utakmica koju nitko nije pratio. Kvote su bile *pogrešne* — "
        "i nekolicina koji su znali gdje gledati izašla je vrlo zadovoljna.\n\n"
        "Ja sam Valerija. Pronalazim te trenutke prije nego nestanu. 🎯\n\n"
        "_Koji jezik preferiraš?_"
    ),
    "lt": (
        "🔥 Vakar vakare kažkas nutiko.\n\n"
        "Rungtynės, kurių niekas nestebėjo. Koeficientai buvo *neteisingi* — "
        "ir keletas žmonių, žinojusių kur žiūrėti, išėjo labai laimingi.\n\n"
        "Aš esu Valerija. Randu šias akimirkas prieš joms išnykstant. 🎯\n\n"
        "_Kokią kalbą renkiesi?_"
    ),
    "lv": (
        "🔥 Pagājušajā naktī kaut kas notika.\n\n"
        "Spēle, ko neviens nesekoja. Koeficienti bija *nepareizi* — "
        "un daži cilvēki, kas zināja kur skatīties, aizgāja ļoti priecīgi.\n\n"
        "Es esmu Valerija. Atklāju šos mirkļus pirms tie pazūd. 🎯\n\n"
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
#
# ЧТО ИЗМЕНЕНО И ПОЧЕМУ:
# Было: нейтральное "что тебя больше интересует?"
# Стало: вопрос с интригой — "где ты чуешь запах денег?" — уже создаёт
# ощущение что это про реальные возможности, а не просто опрос.
#
QUIZ = {
    "es": "¿Dónde hueles el dinero? 👇",
    "hr": "Gdje osjećaš miris novca? 👇",
    "lt": "Kur užuodi pinigų kvapą? 👇",
    "lv": "Kur tu saož naudu? 👇",
    "default": "Где чуешь запах денег? 👇",
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
#
# ЧТО ИЗМЕНЕНО И ПОЧЕМУ:
# Было: спокойный рассказ про "анализ" и "статистику" — звучит как лекция.
# Стало: короткая история с конкретным исходом ("заработала") + эмоция
# от момента. Читатель должен почувствовать что Валерия живёт этим,
# это не теория — а реальный азарт и реальный результат.
#
WARM1 = {
    "betting": {
        "es": (
            "⚽ Ayer vi una cuota que me llamó la atención a las 11 de la noche.\n\n"
            "Nadie la estaba mirando. El mercado se equivocó — yo no.\n\n"
            "No siempre sale. Pero cuando sale… ese feeling no tiene precio. 🔥"
        ),
        "hr": (
            "⚽ Jučer sam u 23h vidjela kvotu koja me zaustavila.\n\n"
            "Nitko je nije gledao. Tržište se prevarilo — ja nisam.\n\n"
            "Ne uspijeva uvijek. Ali kad uspije… taj osjećaj nema cijenu. 🔥"
        ),
        "lt": (
            "⚽ Vakar vakare 23 val. pamačiau koeficientą, kuris sustabdė mane.\n\n"
            "Niekas jo nestebėjo. Rinka suklydo — aš ne.\n\n"
            "Ne visada pavyksta. Bet kai pavyksta… tas jausmas neįkainojamas. 🔥"
        ),
        "lv": (
            "⚽ Vakar pulksten 23 redzēju koeficientu, kas mani apturēja.\n\n"
            "Neviens to nesekoja. Tirgus kļūdījās — es ne.\n\n"
            "Ne vienmēr izdodas. Bet kad izdodas… tas sajūta nav ar naudu novērtējama. 🔥"
        ),
    },
    "casino": {
        "es": (
            "🎰 El casino siempre gana — si juegas como todo el mundo.\n\n"
            "Pero hay bonos donde la matemática está del lado del jugador. "
            "Por 20 minutos. Si sabes cuáles y cómo usarlos.\n\n"
            "Yo los busco cada semana. Y los encuentro. 🔍"
        ),
        "hr": (
            "🎰 Casino uvijek pobjeđuje — ako igraš kao svi.\n\n"
            "Ali postoje bonusi gdje matematika stoji na strani igrača. "
            "Na 20 minuta. Ako znaš koje i kako ih koristiti.\n\n"
            "Tražim ih svaki tjedan. I pronalazim ih. 🔍"
        ),
        "lt": (
            "🎰 Kazino visada laimi — jei žaidi kaip visi.\n\n"
            "Bet yra bonusų, kur matematika stovi žaidėjo pusėje. "
            "20 minučių. Jei žinai kuriuos ir kaip juos naudoti.\n\n"
            "Ieškau jų kiekvieną savaitę. Ir randu. 🔍"
        ),
        "lv": (
            "🎰 Kazino vienmēr uzvar — ja spēlē kā visi.\n\n"
            "Bet ir bonusi, kur matemātika stāv spēlētāja pusē. "
            "20 minūtes. Ja zini kurus un kā tos izmantot.\n\n"
            "Meklēju tos katru nedēļu. Un atklāju. 🔍"
        ),
    },
    "nodeposit": {
        "es": (
            "🎁 Esta mañana me registré en una plataforma nueva.\n\n"
            "Sin depositar nada — me dieron 15€ para jugar. "
            "La mayoría ni sabe que existen estas ofertas.\n\n"
            "Yo llevo una lista. La actualizo cuando encuentro algo real. ✅"
        ),
        "hr": (
            "🎁 Jutros sam se registrirala na novoj platformi.\n\n"
            "Bez uplate — dali su mi 15€ za igranje. "
            "Većina ni ne zna da postoje takve ponude.\n\n"
            "Vodim popis. Ažuriram ga kad nađem nešto stvarno. ✅"
        ),
        "lt": (
            "🎁 Šiandien rytą užsiregistravau naujoje platformoje.\n\n"
            "Nieko neįmokėjus — davė man 15€ žaidimui. "
            "Dauguma net nežino, kad tokių pasiūlymų egzistuoja.\n\n"
            "Turiu sąrašą. Atnaujinu jį kai randu ką tikrai verta. ✅"
        ),
        "lv": (
            "🎁 Šorīt reģistrējos jaunā platformā.\n\n"
            "Neko neiemaksājot — deva man 15€ spēlēšanai. "
            "Vairākums pat nezina, ka šādi piedāvājumi eksistē.\n\n"
            "Man ir saraksts. Atjauninu to kad atklāju ko patiešām vērtu. ✅"
        ),
    },
    "exclusive": {
        "es": (
            "🔥 Hay un tipo de situación en el mercado que casi nunca se habla.\n\n"
            "Cuando dos bookmakers calculan diferente el mismo evento — "
            "existe una ventana. Pequeña. Pero existe.\n\n"
            "Yo la busco. Y cuando aparece, la comparto antes que se cierre. ⚡"
        ),
        "hr": (
            "🔥 Postoji vrsta situacije na tržištu o kojoj se gotovo nikad ne govori.\n\n"
            "Kad dva kladioničara različito procijene isti događaj — "
            "postoji prozor. Mali. Ali postoji.\n\n"
            "Tražim ga. I kad se pojavi, dijelim ga prije nego se zatvori. ⚡"
        ),
        "lt": (
            "🔥 Yra vienas rinkos situacijos tipas, apie kurį beveik nekalbama.\n\n"
            "Kai du bukmeikeriai skirtingai įvertina tą patį įvykį — "
            "atsidaro langas. Mažas. Bet jis egzistuoja.\n\n"
            "Ieškau jo. Ir kai atsiranda — dalinuosi prieš jam užsiverdant. ⚡"
        ),
        "lv": (
            "🔥 Ir viens tirgus situācijas veids, par ko gandrīz nekad nerunā.\n\n"
            "Kad divi bukmekeri atšķirīgi novērtē vienu un to pašu notikumu — "
            "pastāv logs. Mazs. Bet pastāv.\n\n"
            "Meklēju to. Un kad parādās — dalūos pirms tas aizveras. ⚡"
        ),
    },
}

# ─── Шаг 4: Прогрев 2 — социальное доказательство ────────────────────────────
#
# ЧТО ИЗМЕНЕНО И ПОЧЕМУ:
# Было: мягкое "я не обещаю результатов, делюсь процессом" — звучит
# слишком осторожно и снижает энергию воронки.
# Стало: живой момент — реакция подписчиков в реальном времени,
# ощущение движухи в канале прямо сейчас. FOMO усиливается.
#
WARM2 = {
    "es": (
        "Hace una hora alguien en el canal escribió: *\"no me lo esperaba, pero funcionó\"*\n\n"
        "No sé si le hablo a escépticos o a convencidos. "
        "Solo sé que en el canal hay gente que lleva meses sin perderse nada.\n\n"
        "Ahora mismo están ahí. 👀"
    ),
    "hr": (
        "Sat vremena prije netko u kanalu je napisao: *\"nisam to očekivala, ali je uspjelo\"*\n\n"
        "Ne znam razgovaram li sa skepticima ili uvjerenima. "
        "Samo znam da u kanalu ima ljudi koji već mjesecima ne propuštaju ništa.\n\n"
        "Upravo su tamo. 👀"
    ),
    "lt": (
        "Prieš valandą kažkas kanale parašė: *\"nesitikėjau, bet suveikė\"*\n\n"
        "Nežinau — kalbu su skeptikais ar įsitikinusiais. "
        "Žinau tik, kad kanale yra žmonių, kurie jau mėnesius nieko nepraleido.\n\n"
        "Jie ten dabar pat. 👀"
    ),
    "lv": (
        "Pirms stundas kāds kanālā rakstīja: *\"negaidīju, bet strādāja\"*\n\n"
        "Nezinu — runāju ar skeptiķiem vai pārliecinātiem. "
        "Zinu tikai, ka kanālā ir cilvēki, kas mēnešiem nav palaiduši garām neko.\n\n"
        "Viņi tur ir tieši tagad. 👀"
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
