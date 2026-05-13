"""
messages.py — все тексты воронки на 4 языках.
Визуальный ритм, эмодзи, энергия. Стиль Белфорта — продаём через эмоцию и картину.
"""

# ─── Шаг 1: Крючок (сразу после /start) ──────────────────────────────────────
HOOK = {
    "default": (
        "🔥 *Прошлой ночью несколько человек сделали очень правильный ход.*\n\n"
        "Матч, который никто не смотрел. Коэффициент был *неправильным* — "
        "и те, кто знал куда смотреть, вышли с хорошим результатом.\n\n"
        "Я Валерия. Я нахожу такие моменты раньше всех. 🎯\n\n"
        "_Выбери язык:_"
    ),
    "en": (
        "🔥 *Last night a few people made a very smart move.*\n\n"
        "A match nobody was watching. The odds were *miscalculated* — "
        "and the ones who knew where to look walked away happy.\n\n"
        "I'm Valeria. I find these moments before they're gone. 🎯\n\n"
        "_Pick your language:_"
    ),
    "es": (
        "🔥 *Anoche unas pocas personas hicieron un movimiento muy inteligente.*\n\n"
        "Un partido que nadie miraba. Las cuotas estaban *mal calculadas* — "
        "y los que sabían dónde mirar salieron con algo muy bueno.\n\n"
        "Soy Valeria. Encuentro estos momentos antes de que desaparezcan. 🎯\n\n"
        "_Elige tu idioma:_"
    ),
    "hr": (
        "🔥 *Sinoć su neki pametni ljudi napravili pravi potez.*\n\n"
        "Utakmica koju nitko nije pratio. Kvote su bile *pogrešne* — "
        "i oni koji su znali gdje gledati izašli su s dobrim rezultatom.\n\n"
        "Ja sam Valerija. Pronalazim te trenutke prije nego nestanu. 🎯\n\n"
        "_Odaberi jezik:_"
    ),
    "lt": (
        "🔥 *Vakar vakare keli protingi žmonės padarė tinkamą žingsnį.*\n\n"
        "Rungtynės, kurių niekas nestebėjo. Koeficientai buvo *klaidingi* — "
        "ir tie, kurie žinojo kur žiūrėti, išėjo su puikiu rezultatu.\n\n"
        "Aš esu Valerija. Randu šias akimirkas prieš joms išnykstant. 🎯\n\n"
        "_Pasirink kalbą:_"
    ),
    "lv": (
        "🔥 *Pagājušajā naktī daži gudri cilvēki izdarīja pareizo gājienu.*\n\n"
        "Spēle, ko neviens nesekoja. Koeficienti bija *nepareizi* — "
        "un tie, kas zināja kur skatīties, aizgāja ar labu rezultātu.\n\n"
        "Es esmu Valerija. Atklāju šos mirkļus pirms tie pazūd. 🎯\n\n"
        "_Izvēlies valodu:_"
    ),
}

# ─── Кнопки выбора языка ──────────────────────────────────────────────────────
LANG_BUTTONS = [
    ("🇪🇸 Español",  "lang_es"),
    ("🇭🇷 Hrvatski", "lang_hr"),
    ("🇱🇹 Lietuvių", "lang_lt"),
    ("🇱🇻 Latviešu", "lang_lv"),
]

# ─── Шаг 2: Квиз ──────────────────────────────────────────────────────────────
QUIZ = {
    "es": "💰 ¿Dónde hueles el dinero?\n\n_Elige lo que más te llama:_",
    "hr": "💰 Gdje osjećaš miris novca?\n\n_Odaberi što te više privlači:_",
    "lt": "💰 Kur užuodi pinigų kvapą?\n\n_Pasirink kas tave labiau traukia:_",
    "lv": "💰 Kur tu saož naudu?\n\n_Izvēlies kas tevi vairāk vilina:_",
    "default": "💰 Где чуешь запах денег?\n\n_Выбери что тебя цепляет больше:_",
}

QUIZ_BUTTONS = {
    "es": [
        ("⚽ Apuestas deportivas",  "int_betting"),
        ("🎰 Casino y bonos",       "int_casino"),
        ("🎁 Sin depósito",         "int_nodeposit"),
        ("👑 Lo más exclusivo",     "int_exclusive"),
    ],
    "hr": [
        ("⚽ Sportsko klađenje",    "int_betting"),
        ("🎰 Casino i bonusi",      "int_casino"),
        ("🎁 Bez depozita",         "int_nodeposit"),
        ("👑 Ekskluzivno",          "int_exclusive"),
    ],
    "lt": [
        ("⚽ Sporto lažybos",       "int_betting"),
        ("🎰 Kazino ir bonusai",    "int_casino"),
        ("🎁 Be depozito",          "int_nodeposit"),
        ("👑 Išskirtiniai",         "int_exclusive"),
    ],
    "lv": [
        ("⚽ Sporta likmes",        "int_betting"),
        ("🎰 Kazino un bonusi",     "int_casino"),
        ("🎁 Bez depozīta",         "int_nodeposit"),
        ("👑 Ekskluzīvi",           "int_exclusive"),
    ],
}

# ─── Шаг 3: Прогрев 1 — личная история с картиной результата ─────────────────
WARM1 = {
    "betting": {
        "es": (
            "⚽ *Ayer a las 11 de la noche vi una cuota que nadie más vio.*\n\n"
            "El mercado se equivocó. Yo no. Y esa diferencia es exactamente "
            "de lo que vivo — no de suerte, sino de sistema.\n\n"
            "Hay gente que lleva meses siguiendo mi lógica. *Los resultados hablan.* 📈"
        ),
        "hr": (
            "⚽ *Jučer u 23h vidio sam kvotu koju nitko drugi nije vidio.*\n\n"
            "Tržište se prevarilo. Ja nisam. I ta razlika je upravo od čega živim — "
            "ne od sreće, nego od sustava.\n\n"
            "Ima ljudi koji prate moju logiku već mjesecima. *Rezultati govore.* 📈"
        ),
        "lt": (
            "⚽ *Vakar 23:00 pamačiau koeficientą, kurio niekas kitas nematė.*\n\n"
            "Rinka suklydo. Aš ne. Ir būtent ta skirtumas yra tai, nuo ko gyvenu — "
            "ne iš sėkmės, o iš sistemos.\n\n"
            "Yra žmonių, kurie seka mano logiką jau mėnesius. *Rezultatai kalba.* 📈"
        ),
        "lv": (
            "⚽ *Vakar pulksten 23 redzēju koeficientu, ko neviens cits neredzēja.*\n\n"
            "Tirgus kļūdījās. Es ne. Un tā atšķirība ir tieši tas, no kā dzīvoju — "
            "ne no veiksmes, bet no sistēmas.\n\n"
            "Ir cilvēki, kas seko manai loģikai jau mēnešiem. *Rezultāti runā.* 📈"
        ),
    },
    "casino": {
        "es": (
            "🎰 *El casino siempre gana — si juegas como todo el mundo.*\n\n"
            "Pero hay bonos donde la matemática está del lado del jugador. "
            "Ventana pequeña. Si sabes cuáles son y cuándo entrar — la cosa cambia.\n\n"
            "Yo llevo meses buscando esos momentos. *Y los encuentro cada semana.* 🔍"
        ),
        "hr": (
            "🎰 *Casino uvijek pobjeđuje — ako igraš kao svi.*\n\n"
            "Ali postoje bonusi gdje matematika stoji na strani igrača. "
            "Mali prozor. Ako znaš koje su i kada ući — stvar se mijenja.\n\n"
            "Tražim te trenutke već mjesecima. *I pronalazim ih svaki tjedan.* 🔍"
        ),
        "lt": (
            "🎰 *Kazino visada laimi — jei žaidi kaip visi.*\n\n"
            "Bet yra bonusų, kur matematika stovi žaidėjo pusėje. "
            "Mažas langas. Jei žinai kurie ir kada įeiti — viskas keičiasi.\n\n"
            "Ieškau tų momentų jau mėnesius. *Ir randu juos kiekvieną savaitę.* 🔍"
        ),
        "lv": (
            "🎰 *Kazino vienmēr uzvar — ja spēlē kā visi.*\n\n"
            "Bet ir bonusi, kur matemātika stāv spēlētāja pusē. "
            "Mazs logs. Ja zini kuri un kad ienākt — lieta mainās.\n\n"
            "Meklēju tos mirkļus jau mēnešiem. *Un atklāju tos katru nedēļu.* 🔍"
        ),
    },
    "nodeposit": {
        "es": (
            "🎁 *Esta mañana entré a una plataforma nueva sin poner ni un euro.*\n\n"
            "Me dieron 15€ de bienvenida. La mayoría ni sabe que estas ofertas existen — "
            "caducan rápido y no las anuncian en ningún lado.\n\n"
            "Yo llevo una lista actualizada. *Solo la comparto con los que están cerca.* ✅"
        ),
        "hr": (
            "🎁 *Jutros sam ušla na novu platformu bez ulaganja ni centa.*\n\n"
            "Dali su mi 15€ dobrodošlice. Većina ne zna da ove ponude uopće postoje — "
            "brzo ističu i nigdje ih ne oglašavaju.\n\n"
            "Vodim ažuriranu listu. *Dijelim je samo s onima koji su blizu.* ✅"
        ),
        "lt": (
            "🎁 *Šiandien rytą prisijungiau prie naujos platformos be nė cento.*\n\n"
            "Davė man 15€ sveikinamojo bonus. Dauguma nežino, kad tokios pasiūlos egzistuoja — "
            "greitai baigiasi ir niekur nereklamuojamos.\n\n"
            "Prižiūriu atnaujintą sąrašą. *Dalinuosi tik su tais, kurie šalia.* ✅"
        ),
        "lv": (
            "🎁 *Šorīt pievienojos jaunai platformai bez neviena centa ieguldījuma.*\n\n"
            "Deva man 15€ sagaidīšanas bonusu. Vairums pat nezina, ka šādi piedāvājumi eksistē — "
            "ātri beidzas un nekur netiek reklamēti.\n\n"
            "Uzturos atjauninātu sarakstu. *Dalūos tikai ar tiem, kas ir tuvu.* ✅"
        ),
    },
    "exclusive": {
        "es": (
            "👑 *Hay un tipo de situación en el mercado del que casi nadie habla.*\n\n"
            "Cuando dos plataformas valoran el mismo evento de forma diferente — "
            "se abre una ventana. Pequeña. Pero existe.\n\n"
            "La busco. Y cuando aparece, actúo antes de que se cierre. *Eso es lo exclusivo.* ⚡"
        ),
        "hr": (
            "👑 *Postoji vrsta tržišne situacije o kojoj gotovo nitko ne govori.*\n\n"
            "Kada dvije platforme različito vrednuju isti događaj — "
            "otvori se prozor. Mali. Ali postoji.\n\n"
            "Tražim ga. I kad se pojavi, djelujem prije nego se zatvori. *To je ekskluzivno.* ⚡"
        ),
        "lt": (
            "👑 *Yra vienas rinkos situacijos tipas, apie kurį beveik niekas nekalba.*\n\n"
            "Kai dvi platformos skirtingai įvertina tą patį įvykį — "
            "atsidaro langas. Mažas. Bet egzistuoja.\n\n"
            "Ieškau jo. Ir kai atsiranda, veikiu prieš jam užsiverdant. *Tai yra išskirtina.* ⚡"
        ),
        "lv": (
            "👑 *Ir viens tirgus situācijas veids, par ko gandrīz neviens nerunā.*\n\n"
            "Kad divas platformas atšķirīgi novērtē vienu un to pašu notikumu — "
            "pastāv logs. Mazs. Bet pastāv.\n\n"
            "Meklēju to. Un kad parādās, rīkojos pirms tas aizveras. *Tas ir ekskluzīvi.* ⚡"
        ),
    },
}

# ─── Шаг 4: Прогрев 2 — социальное доказательство + FOMO ─────────────────────
WARM2 = {
    "es": (
        "👀 *Hace una hora alguien en el canal escribió: \"no me lo esperaba, pero funcionó\"*\n\n"
        "No sé si te llegas convencido o escéptico. No importa.\n"
        "Lo que sé es que hay gente ahí dentro que lleva meses *sin perderse nada* — "
        "y que cada semana hay alguien nuevo que dice exactamente lo mismo.\n\n"
        "Ellos están ahí *ahora mismo.* 🔥"
    ),
    "hr": (
        "👀 *Sat vremena prije netko u kanalu je napisao: \"nisam očekivala, ali je uspjelo\"*\n\n"
        "Ne znam dolaziš li uvjeren ili skeptičan. Nije važno.\n"
        "Ono što znam je da ima ljudi unutra koji već mjesecima *ne propuštaju ništa* — "
        "i da svaki tjedan netko novi kaže točno isto.\n\n"
        "Oni su tamo *upravo sada.* 🔥"
    ),
    "lt": (
        "👀 *Prieš valandą kažkas kanale parašė: \"nesitikėjau, bet suveikė\"*\n\n"
        "Nežinau ar ateini įsitikinęs ar skeptiškas. Nesvarbu.\n"
        "Žinau tik, kad yra žmonių viduje, kurie jau mėnesius *nieko nepraleido* — "
        "ir kad kiekvieną savaitę kažkas naujas sako lygiai tą patį.\n\n"
        "Jie ten *dabar pat.* 🔥"
    ),
    "lv": (
        "👀 *Pirms stundas kāds kanālā rakstīja: \"negaidīju, bet strādāja\"*\n\n"
        "Nezinu vai nāc pārliecināts vai skeptiski. Nav svarīgi.\n"
        "Zinu tikai, ka ir cilvēki iekšā, kas jau mēnešiem *neko nav palaiduši garām* — "
        "un ka katru nedēļu kāds jauns saka tieši to pašu.\n\n"
        "Viņi tur ir *tieši tagad.* 🔥"
    ),
}

# ─── Шаг 5: Тизер перед CTA — создаём конкретный повод ───────────────────────
TEASE = {
    "betting": {
        "es": (
            "⚡ *Tengo preparado el análisis de 3 partidos para este fin de semana.*\n\n"
            "El más interesante no es el más obvio — y la mayoría no lo va a ver.\n"
            "Lo publico esta noche en el canal.\n\n"
            "Si no estás ahí cuando salga… ya no cambia nada. 👇"
        ),
        "hr": (
            "⚡ *Imam pripremljenu analizu 3 utakmice za ovaj vikend.*\n\n"
            "Najzanimljivija nije najočitija — i većina je neće vidjeti.\n"
            "Objavljujem večeras u kanalu.\n\n"
            "Ako nisi tamo kad izađe… više ne mijenja ništa. 👇"
        ),
        "lt": (
            "⚡ *Turiu paruoštą 3 savaitgalio rungtynių analizę.*\n\n"
            "Įdomiausia nėra akivaizdžiausia — ir dauguma jos nematys.\n"
            "Skelbiu šį vakarą kanale.\n\n"
            "Jei ten nebūsi kai išeis… niekas jau nesikeis. 👇"
        ),
        "lv": (
            "⚡ *Man ir sagatavota 3 nedēļas nogales spēļu analīze.*\n\n"
            "Interesantākā nav acīmredzamākā — un vairums to neredzēs.\n"
            "Publicēju šovakar kanālā.\n\n"
            "Ja nebūsi tur, kad iznāks… vairs nekas nemainās. 👇"
        ),
    },
    "casino": {
        "es": (
            "⚡ *Esta semana encontré 2 bonos con condiciones que casi nadie conoce.*\n\n"
            "No es el resumen de marketing — son los T&C reales, con los huecos que importan.\n"
            "Uno de ellos caduca en 72 horas.\n\n"
            "Lo detallo en el canal. Solo ahí. 👇"
        ),
        "hr": (
            "⚡ *Ovaj tjedan pronašla sam 2 bonusa s uvjetima koje gotovo nitko ne zna.*\n\n"
            "Nije marketinški sažetak — to su pravi uvjeti, s rupama koje su važne.\n"
            "Jedan od njih ističe za 72 sata.\n\n"
            "Detaljno opisujem u kanalu. Samo tamo. 👇"
        ),
        "lt": (
            "⚡ *Šią savaitę radau 2 bonusus su sąlygomis, kurių beveik niekas nežino.*\n\n"
            "Tai ne marketingo santrauka — tai tikros sąlygos su spragomis, kurios svarbios.\n"
            "Vienas jų galioja dar 72 valandas.\n\n"
            "Aptariu kanale. Tik ten. 👇"
        ),
        "lv": (
            "⚡ *Šonedēļ atradu 2 bonusus ar nosacījumiem, kurus gandrīz neviens nezina.*\n\n"
            "Tā nav mārketinga kopsavilkums — tie ir īsti noteikumi ar caurumiem, kas svarīgi.\n"
            "Viens no tiem beidzas 72 stundu laikā.\n\n"
            "Izskaidroju kanālā. Tikai tur. 👇"
        ),
    },
    "nodeposit": {
        "es": (
            "⚡ *Encontré un bono sin depósito nuevo — caduca en 48 horas.*\n\n"
            "No está anunciado en ningún agregador. Lo vi directamente.\n"
            "Link y condiciones completas solo en el canal.\n\n"
            "Después de 48h no sirve de nada. 👇"
        ),
        "hr": (
            "⚡ *Pronašla sam novi bonus bez depozita — ističe za 48 sati.*\n\n"
            "Nije najavljen ni na jednom agregatu. Vidjela sam ga direktno.\n"
            "Link i potpuni uvjeti samo u kanalu.\n\n"
            "Nakon 48 sati nema smisla. 👇"
        ),
        "lt": (
            "⚡ *Radau naują bonusą be depozito — galioja 48 valandas.*\n\n"
            "Nereklamuojamas jokiame agregatoriuje. Mačiau tiesiogiai.\n"
            "Nuoroda ir pilnos sąlygos tik kanale.\n\n"
            "Po 48 valandų nebereikšminga. 👇"
        ),
        "lv": (
            "⚡ *Atradu jaunu bonusu bez depozīta — beidzas 48 stundu laikā.*\n\n"
            "Nav paziņots nevienā agregatorā. Redzēju tieši.\n"
            "Saite un pilni nosacījumi tikai kanālā.\n\n"
            "Pēc 48 stundām nav jēgas. 👇"
        ),
    },
    "exclusive": {
        "es": (
            "⚡ *Esta noche publico el análisis más detallado del mes.*\n\n"
            "No es para todo el mundo — hay contexto que necesitas entender para usarlo.\n"
            "Por eso solo va al canal.\n\n"
            "Si no estás ahí, simplemente no lo verás. 👇"
        ),
        "hr": (
            "⚡ *Večeras objavljujem najdetaljniju analizu ovog mjeseca.*\n\n"
            "Nije za svakoga — ima konteksta koji trebaš razumjeti da bi ga koristio.\n"
            "Zato ide samo u kanal.\n\n"
            "Ako nisi tamo, jednostavno ga nećeš vidjeti. 👇"
        ),
        "lt": (
            "⚡ *Šiąnakt skelbiu išsamiausią šio mėnesio analizę.*\n\n"
            "Ne visiems — yra konteksto, kurį reikia suprasti, kad būtų galima naudotis.\n"
            "Todėl eina tik į kanalą.\n\n"
            "Jei ten nebūsi, paprasčiausiai nematysi. 👇"
        ),
        "lv": (
            "⚡ *Šovakar publicēju šī mēneša detalizētāko analīzi.*\n\n"
            "Nav paredzēts visiem — ir konteksts, kas jāsaprot, lai to izmantotu.\n"
            "Tāpēc iet tikai uz kanālu.\n\n"
            "Ja nebūsi tur, vienkārši neredzēsi. 👇"
        ),
    },
}

# ─── CTA — подписка ───────────────────────────────────────────────────────────
CTA = {
    "es": "🚀 Entrar al canal ahora",
    "hr": "🚀 Ući u kanal sada",
    "lt": "🚀 Įeiti į kanalą dabar",
    "lv": "🚀 Ienākt kanālā tagad",
}

CTA_BUTTON_JOINED = {
    "es": "✅ Ya entré al canal",
    "hr": "✅ Već sam u kanalu",
    "lt": "✅ Jau esu kanale",
    "lv": "✅ Jau esmu kanālā",
}

# ─── CTA сообщение (текст над кнопками) ──────────────────────────────────────
CTA_MESSAGE = {
    "betting": {
        "es": "📲 *El análisis del fin de semana sale esta noche.*\nLos que están en el canal lo ven primero.",
        "hr": "📲 *Analiza za vikend izlazi večeras.*\nOni u kanalu vide je prvi.",
        "lt": "📲 *Savaitgalio analizė išeina šį vakarą.*\nKanale esantys mato pirmieji.",
        "lv": "📲 *Nedēļas nogales analīze iznāk šovakar.*\nKanālā esošie redz to pirmie.",
    },
    "casino": {
        "es": "📲 *El bono del que hablé caduca en 72h.*\nCondiciones completas solo en el canal.",
        "hr": "📲 *Bonus o kojem sam govorila ističe za 72h.*\nPotpuni uvjeti samo u kanalu.",
        "lt": "📲 *Bonusas, apie kurį kalbėjau, galioja 72 val.*\nPilnos sąlygos tik kanale.",
        "lv": "📲 *Bonuss, par ko runāju, beidzas 72h laikā.*\nPilni nosacījumi tikai kanālā.",
    },
    "nodeposit": {
        "es": "📲 *El bono sin depósito caduca en 48h.*\nEl link está solo en el canal.",
        "hr": "📲 *Bonus bez depozita ističe za 48h.*\nLink je samo u kanalu.",
        "lt": "📲 *Bonusas be depozito galioja 48 val.*\nNuoroda tik kanale.",
        "lv": "📲 *Bonuss bez depozīta beidzas 48h laikā.*\nSaite ir tikai kanālā.",
    },
    "exclusive": {
        "es": "📲 *El análisis completo sale esta noche.*\nSolo para los que están en el canal.",
        "hr": "📲 *Potpuna analiza izlazi večeras.*\nSamo za one koji su u kanalu.",
        "lt": "📲 *Pilna analizė išeina šį vakarą.*\nTik tiems, kurie yra kanale.",
        "lv": "📲 *Pilnā analīze iznāk šovakar.*\nTikai tiem, kas ir kanālā.",
    },
}

# ─── После подписки — переход к FTD ──────────────────────────────────────────
POST_SUB = {
    "betting": {
        "es": (
            "🔥 *Ahora sí. Bienvenido/a.*\n\n"
            "Ya estás donde pasan las cosas. Publico ahí cada día — análisis, situaciones, momentos.\n\n"
            "Una cosa más: la mayoría de las plataformas que menciono tienen bono de bienvenida "
            "para el primer depósito. Pequeño. Pero es un punto de partida real.\n"
            "Si quieres, te cuento cómo lo uso. 💬"
        ),
        "hr": (
            "🔥 *Sad je to to. Dobrodošao/la.*\n\n"
            "Sada si tamo gdje se stvari događaju. Objavljujem tamo svaki dan — analize, situacije, trenutke.\n\n"
            "Još jedna stvar: većina platformi koje spominjem ima bonus dobrodošlice "
            "za prvi depozit. Mali. Ali pravi polazni bod.\n"
            "Ako želiš, kažem ti kako ga koristim. 💬"
        ),
        "lt": (
            "🔥 *Dabar taip. Sveiki.*\n\n"
            "Dabar esi ten, kur vyksta veiksmas. Skelbiu ten kasdien — analizes, situacijas, momentus.\n\n"
            "Dar vienas dalykas: dauguma platformų, kurias minėjau, turi sveikinamąjį bonusą "
            "už pirmąjį depozitą. Mažas. Bet tikras pradžios taškas.\n"
            "Jei nori — papasakoju kaip naudoju. 💬"
        ),
        "lv": (
            "🔥 *Tagad tā. Laipni lūgts/-a.*\n\n"
            "Tagad esi tur, kur notiek darbība. Publicēju tur katru dienu — analīzes, situācijas, mirkļus.\n\n"
            "Vēl viena lieta: lielākā daļa platformu, ko minēju, ir sveiciena bonuss "
            "pirmajam depozītam. Mazs. Bet īsts sākuma punkts.\n"
            "Ja gribi — pastāstu kā to izmantoju. 💬"
        ),
    },
    "casino": {
        "es": (
            "🎰 *Perfecto. Ya estás dentro.*\n\n"
            "En el canal actualizo bonos cada semana — con condiciones reales, sin letra pequeña escondida.\n\n"
            "El primer depósito siempre es el más rentable si sabes elegir la oferta correcta. "
            "Tengo una que ahora mismo tiene los mejores números.\n"
            "¿Te la cuento? 💬"
        ),
        "hr": (
            "🎰 *Savršeno. Sad si unutra.*\n\n"
            "U kanalu ažuriram bonuse svaki tjedan — s pravim uvjetima, bez skrivenog sitnog tiska.\n\n"
            "Prvi depozit je uvijek najisplativiji ako znaš izabrati pravu ponudu. "
            "Imam jednu koja trenutno ima najbolje brojke.\n"
            "Povjeruješ li mi? 💬"
        ),
        "lt": (
            "🎰 *Puiku. Dabar esi viduje.*\n\n"
            "Kanale atnaujinu bonusus kiekvieną savaitę — su tikromis sąlygomis, be paslėptų smulkmenų.\n\n"
            "Pirmasis depozitas visada yra pelningiausias, jei žinai kaip pasirinkti tinkamą pasiūlą. "
            "Turiu vieną, kuri šiuo metu turi geriausius skaičius.\n"
            "Ar papasakoju? 💬"
        ),
        "lv": (
            "🎰 *Lieliski. Tagad esi iekšā.*\n\n"
            "Kanālā atjauninu bonusus katru nedēļu — ar īstiem noteikumiem, bez slēptā sīkā drukājuma.\n\n"
            "Pirmais depozīts vienmēr ir izdevīgākais, ja zini kā izvēlēties pareizo piedāvājumu. "
            "Man ir viens, kuram pašlaik ir labākie skaitļi.\n"
            "Vai pastāstu? 💬"
        ),
    },
    "nodeposit": {
        "es": (
            "🎁 *Listo. Ya estás donde están los que saben.*\n\n"
            "En el canal hay bonos sin depósito actualizados — los que siguen activos hoy mismo.\n\n"
            "Cuando te sientas cómodo/a y quieras dar el siguiente paso, "
            "hay ofertas de primer depósito que multiplican lo que entras.\n"
            "Sin prisa — pero la info está cuando la quieras. 💬"
        ),
        "hr": (
            "🎁 *Gotovo. Sada si tamo gdje su oni koji znaju.*\n\n"
            "U kanalu su ažurirani bonusi bez depozita — oni koji su i danas aktivni.\n\n"
            "Kad se budeš osjećao/la ugodno i htio/htjela napraviti sljedeći korak, "
            "ima ponuda prvog depozita koje multipliciraju ono s čim ulaziš.\n"
            "Nema žurbe — ali info je tu kad je budeš trebao/la. 💬"
        ),
        "lt": (
            "🎁 *Atlikta. Dabar esi ten, kur yra tie, kurie žino.*\n\n"
            "Kanale yra atnaujinti bonusai be depozito — tie, kurie šiandien vis dar aktyvūs.\n\n"
            "Kai pasijusi patogiai ir norėsi žengti kitą žingsnį, "
            "yra pirmojo depozito pasiūlų, kurie padaugina tai, su kuo ateini.\n"
            "Neskubėk — bet informacija yra kai jos norėsi. 💬"
        ),
        "lv": (
            "🎁 *Gatavs/-a. Tagad esi tur, kur ir tie, kas zina.*\n\n"
            "Kanālā ir atjaunināti bonusi bez depozīta — tie, kas šodien joprojām ir aktīvi.\n\n"
            "Kad jutīsies komfortabli un gribēsi spert nākamo soli, "
            "ir pirmā depozīta piedāvājumi, kas reizina to, ar ko ienāc.\n"
            "Nesteidzies — bet info ir, kad vēlēsies. 💬"
        ),
    },
    "exclusive": {
        "es": (
            "👑 *Ahora sí estás en el grupo que ve lo que otros no ven.*\n\n"
            "Publico análisis exclusivos — situaciones que requieren entender el contexto completo.\n\n"
            "Para aprovecharlos de verdad necesitas estar activo/a en plataforma. "
            "¿Ya tienes cuenta en alguna, o empezamos desde cero? 💬"
        ),
        "hr": (
            "👑 *Sada si u grupi koja vidi ono što drugi ne vide.*\n\n"
            "Objavljujem ekskluzivne analize — situacije koje zahtijevaju razumijevanje cijelog konteksta.\n\n"
            "Da ih zaista iskoristiš trebaš biti aktivan/na na platformi. "
            "Imaš li već račun negdje, ili počinjemo od nule? 💬"
        ),
        "lt": (
            "👑 *Dabar esi grupėje, kuri mato tai, ko kiti nemato.*\n\n"
            "Skelbiu išskirtines analizes — situacijas, kurioms reikia suprasti visą kontekstą.\n\n"
            "Kad tikrai jomis pasinaudotum, turi būti aktyvus/-i platformoje. "
            "Ar jau turi paskyrą kur nors, ar pradedame nuo nulio? 💬"
        ),
        "lv": (
            "👑 *Tagad esi grupā, kas redz to, ko citi neredz.*\n\n"
            "Publicēju ekskluzīvas analīzes — situācijas, kurām nepieciešams izprast visu kontekstu.\n\n"
            "Lai tās patiešām izmantotu, tev jābūt aktīvam/-ai platformā. "
            "Vai tev jau ir konts kaut kur, vai sākam no nulles? 💬"
        ),
    },
}

# ─── Re-engage 1 (24 часа) — острее, с конкретикой ───────────────────────────
REENGAGE_1 = {
    "es": (
        "🎰 *Oye — ¿sigues por aquí?*\n\n"
        "Ayer en el canal hubo bastante movimiento. "
        "Algo que no esperábamos pero que se veía venir si sabías dónde mirar.\n\n"
        "Sin spoilers. Pero está ahí, esperándote. ¿Te apuntas ahora? 👇"
    ),
    "hr": (
        "🎰 *Hej — jesi li još ovdje?*\n\n"
        "Jučer je u kanalu bilo dosta pomicanja. "
        "Nešto što nismo očekivali ali se vidjelo ako si znao gdje gledati.\n\n"
        "Bez spoilera. Ali je tamo, čeka te. Pridružuješ se sada? 👇"
    ),
    "lt": (
        "🎰 *Ei — ar vis dar čia?*\n\n"
        "Vakar kanale buvo nemažai judėjimo. "
        "Kažkas, ko nesitikėjome, bet buvo matyti jei žinojai kur žiūrėti.\n\n"
        "Be spoilerių. Bet yra ten, laukia tavęs. Prisijungi dabar? 👇"
    ),
    "lv": (
        "🎰 *Hei — vai joprojām esi šeit?*\n\n"
        "Vakar kanālā bija diezgan daudz kustības. "
        "Kaut kas, ko negaidījām, bet bija redzams, ja zināji kur skatīties.\n\n"
        "Bez spoileriem. Bet ir tur, gaida tevi. Pievienojies tagad? 👇"
    ),
}

# ─── Re-engage 2 (48 часов) — последний шанс, финальное закрытие ─────────────
REENGAGE_2 = {
    "es": (
        "📊 *Es la última vez que te escribo sobre esto.*\n\n"
        "Esta semana en el canal: 4 análisis, 2 bonos con números reales, "
        "y una situación de value que aparece quizás 2 veces al mes.\n\n"
        "Si en algún momento cambias de idea — el canal sigue ahí. "
        "Pero las oportunidades no esperan. 🎰"
    ),
    "hr": (
        "📊 *Ovo je zadnji put da ti pišem o ovome.*\n\n"
        "Ovaj tjedan u kanalu: 4 analize, 2 bonusa s pravim brojevima, "
        "i value situacija koja se pojavljuje možda 2 puta mjesečno.\n\n"
        "Ako ikad promijeniš mišljenje — kanal je i dalje tamo. "
        "Ali prilike ne čekaju. 🎰"
    ),
    "lt": (
        "📊 *Tai paskutinis kartas, kai rašau tau apie tai.*\n\n"
        "Šią savaitę kanale: 4 analizės, 2 bonusai su tikrais skaičiais, "
        "ir value situacija, kuri pasitaiko gal 2 kartus per mėnesį.\n\n"
        "Jei kada nors pakeisi nuomonę — kanalas vis dar ten. "
        "Bet galimybės nelaukia. 🎰"
    ),
    "lv": (
        "📊 *Šī ir pēdējā reize, kad rakstu tev par to.*\n\n"
        "Šonedēļ kanālā: 4 analīzes, 2 bonusi ar īstiem skaitļiem, "
        "un value situācija, kas parādās varbūt 2 reizes mēnesī.\n\n"
        "Ja kādreiz mainīsi domas — kanāls joprojām tur. "
        "Bet iespējas negaida. 🎰"
    ),
}

# ─── Хелпер: достать текст с фолбэком ────────────────────────────────────────
def get(mapping: dict, lang: str, interest: str = None) -> str:
    """Достаёт текст из вложенного словаря с фолбэком на es."""
    if interest and isinstance(mapping.get(interest), dict):
        d = mapping[interest]
        return d.get(lang) or d.get("es", "")
    return mapping.get(lang) or mapping.get("es") or mapping.get("default", "")
