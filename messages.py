"""
messages.py — OddsVault Bot
Все тексты воронки на 4 языках.
Концепция: OddsVault — закрытый клуб инсайдеров.
Персонаж: Valeria — аналитик, говорит как умный друг, не как бот.
Стиль: Белфорт — крючок, тепло, доказательство, срочность, CTA.
"""

from typing import Optional


# ══════════════════════════════════════════════════════════════════════════════
#  HOOK — первое сообщение /start
# ══════════════════════════════════════════════════════════════════════════════
HOOK: dict[str, str] = {
    "es": (
        "Oye.\n\n"
        "No sé si llegaste aquí por suerte o por instinto — pero llegas en buen momento. 🎯\n\n"
        "Me llamo *Valeria*. Llevo 4 años rastreando odds, bonos y señales en los mercados de España y Balcanes.\n\n"
        "No vendo nada. No pido dinero. Solo comparto lo que encuentro — "
        "y hay gente que ya está sacando partido de ello.\n\n"
        "¿En qué idioma seguimos?"
    ),
    "hr": (
        "Hej.\n\n"
        "Ne znam jesi li ovdje slučajno ili instinktom — ali dolaziš u pravo vrijeme. 🎯\n\n"
        "Zovem se *Valerija*. 4 godine pratim kvote, bonuse i signale na tržištima Hrvatske i Baltika.\n\n"
        "Ništa ne prodajem. Ne tražim novac. Samo dijelim ono što pronađem — "
        "i ima ljudi koji već izvlače korist iz toga.\n\n"
        "Na kojem jeziku nastavljamo?"
    ),
    "lt": (
        "Sveiki.\n\n"
        "Nežinau ar atkeliavote čia atsitiktinai ar instinktu — bet atvykstate geru laiku. 🎯\n\n"
        "Mano vardas *Valerija*. 4 metus seku koeficientus, bonusus ir signalus Ispanijos ir Baltijos rinkose.\n\n"
        "Nieko neparduodu. Nereikalauju pinigų. Tik dalinausi tuo, ką randu — "
        "ir jau yra žmonių, kurie iš to gauna naudos.\n\n"
        "Kuria kalba tęsiame?"
    ),
    "lv": (
        "Sveiki.\n\n"
        "Nezinu, vai esat šeit nejauši vai instinktīvi — bet ierodaties īstajā laikā. 🎯\n\n"
        "Mani sauc *Valerija*. 4 gadus seku koeficientiem, bonusiem un signāliem Spānijas un Baltijas tirgos.\n\n"
        "Es neko nepārdodu. Neprasu naudu. Tikai dalūos ar to, ko atrodu — "
        "un jau ir cilvēki, kas no tā gūst labumu.\n\n"
        "Kurā valodā turpinām?"
    ),
}

LANG_BUTTONS: list[tuple[str, str]] = [
    ("🇪🇸 Español",  "lang_es"),
    ("🇭🇷 Hrvatski", "lang_hr"),
    ("🇱🇹 Lietuvių", "lang_lt"),
    ("🇱🇻 Latviešu", "lang_lv"),
]


# ══════════════════════════════════════════════════════════════════════════════
#  QUIZ — «что тебя интересует?»
# ══════════════════════════════════════════════════════════════════════════════
QUIZ: dict[str, str] = {
    "default": "Bien. Una pregunta rápida antes de entrar al vault 🔐",
    "es": (
        "Bien. Una pregunta antes de que te abra la puerta 🔐\n\n"
        "*¿Qué es lo que más te interesa ahora mismo?*"
    ),
    "hr": (
        "Dobro. Jedno pitanje prije nego što ti otvorim vrata 🔐\n\n"
        "*Što te trenutno najviše zanima?*"
    ),
    "lt": (
        "Gerai. Vienas klausimas prieš atidarant duris 🔐\n\n"
        "*Kas jus labiausiai domina šiuo metu?*"
    ),
    "lv": (
        "Labi. Viens jautājums pirms atveru durvis 🔐\n\n"
        "*Kas jūs visvairāk interesē šobrīd?*"
    ),
}

QUIZ_BUTTONS: dict[str, list[tuple[str, str]]] = {
    "es": [
        ("⚽ Apuestas deportivas",   "int_betting"),
        ("🎰 Casinos y bonos",       "int_casino"),
        ("🎁 Sin depósito",          "int_nodeposit"),
        ("🔥 Todo — quiero lo mejor","int_exclusive"),
    ],
    "hr": [
        ("⚽ Sportsko klađenje",     "int_betting"),
        ("🎰 Casinos i bonusi",      "int_casino"),
        ("🎁 Bez depozita",          "int_nodeposit"),
        ("🔥 Sve — hoću najbolje",   "int_exclusive"),
    ],
    "lt": [
        ("⚽ Sporto lažybos",        "int_betting"),
        ("🎰 Kazino ir bonusai",     "int_casino"),
        ("🎁 Be depozito",           "int_nodeposit"),
        ("🔥 Viską — noriu geriausio","int_exclusive"),
    ],
    "lv": [
        ("⚽ Sporta likmes",         "int_betting"),
        ("🎰 Kazino un bonusi",      "int_casino"),
        ("🎁 Bez depozīta",          "int_nodeposit"),
        ("🔥 Visu — gribu labāko",   "int_exclusive"),
    ],
}


# ══════════════════════════════════════════════════════════════════════════════
#  WARM1 — история, момент, вовлечение (ждём реакции)
# ══════════════════════════════════════════════════════════════════════════════
WARM1: dict[str, dict[str, str]] = {
    "es": {
        "betting": (
            "Mira, hace unos meses un seguidor me mandó un mensaje a las 2am.\n\n"
            "«Valeria, acabo de ver la cuota que publicaste ayer. La perdí. 3.40 en el Over. "
            "¿Por qué no llegué antes?»\n\n"
            "Y eso me rompió un poco el corazón — porque sé exactamente ese feeling.\n\n"
            "*La información correcta llega tarde cuando no estás en el lugar correcto.* ⏱️\n\n"
            "¿Te ha pasado alguna vez — ver algo demasiado tarde?"
        ),
        "casino": (
            "Te cuento algo que no suele verse por ahí.\n\n"
            "La semana pasada había un bono de bienvenida con requisitos de apuesta ×12. "
            "No ×35, no ×40 — *doce*. Duró 6 horas antes de que lo ajustaran.\n\n"
            "Lo publicamos en el canal. 340 personas lo aprovecharon ese día.\n\n"
            "*Los bonos buenos no esperan.* Y los que llegan tarde siempre ven la pantalla vacía.\n\n"
            "¿Sueles buscar activamente los mejores bonos, o aparecen solos?"
        ),
        "nodeposit": (
            "La gente cree que los bonos sin depósito son todos iguales.\n\n"
            "Spoiler: no lo son. Hay una diferencia brutal entre un bono con wagering ×60 "
            "y uno con ×8 — el primero es casi ilusorio, el segundo es dinero real.\n\n"
            "Llevamos 2 años filtrando basura para quedarnos solo con lo que vale.\n\n"
            "*El problema no es que no existan bonos buenos — es saber cuáles son.*\n\n"
            "¿Has quemado alguna vez un bono sin entender las condiciones?"
        ),
        "exclusive": (
            "Voy a ser directa contigo.\n\n"
            "Hay dos tipos de personas en este mundo del betting:\n"
            "las que reaccionan cuando ya es tarde, y las que están ahí cuando pasa.\n\n"
            "No es suerte. Es estar en el lugar correcto con la información correcta.\n\n"
            "*Lo que publicamos en el vault — cuotas, bonos, señales — "
            "no llega a Twitter ni a los grupos públicos. Llega ahí primero.*\n\n"
            "¿Qué es lo que más te ha faltado hasta ahora — velocidad o calidad?"
        ),
    },
    "hr": {
        "betting": (
            "Prije par mjeseci jedan pratitelj mi je napisao poruku u 2 ujutro.\n\n"
            "«Valerija, upravo sam vidio kvotu koju si objavila jučer. Propustio sam je. 3.40 na Over. "
            "Zašto nisam bio tu ranije?»\n\n"
            "I to me malo slomilo — jer točno znam taj osjećaj.\n\n"
            "*Prava informacija kasni kad nisi na pravom mjestu.* ⏱️\n\n"
            "Je li ti se ikad dogodilo — da vidiš nešto prekasno?"
        ),
        "casino": (
            "Reći ću ti nešto što se rijetko vidi vani.\n\n"
            "Prošli tjedan bio je dobrodošlički bonus s uvjetom klađenja ×12. "
            "Ne ×35, ne ×40 — *dvanaest*. Trajalo je 6 sati prije nego su ga prilagodili.\n\n"
            "Objavili smo ga u kanalu. 340 ljudi ga je iskoristilo tog dana.\n\n"
            "*Dobri bonusi ne čekaju.* A oni koji kasne uvijek vide prazan zaslon.\n\n"
            "Tražiš li aktivno najbolje bonuse, ili se pojavljuju sami?"
        ),
        "nodeposit": (
            "Ljudi misle da su svi bonusi bez depozita isti.\n\n"
            "Spojler: nisu. Postoji brutalna razlika između bonusa s ulogom ×60 "
            "i onog s ×8 — prvi je gotovo iluzoran, drugi je pravi novac.\n\n"
            "2 godine filtriramo smeće da bismo zadržali samo ono što vrijedi.\n\n"
            "*Problem nije što ne postoje dobri bonusi — već znati koji su to.*\n\n"
            "Jesi li ikad izgubio bonus ne razumijevajući uvjete?"
        ),
        "exclusive": (
            "Bit ću s tobom direktna.\n\n"
            "Na ovom svijetu bettinga postoje dvije vrste ljudi:\n"
            "oni koji reagiraju kad je već kasno, i oni koji su tu kad se dogodi.\n\n"
            "Nije sreća. Radi se o tome da budeš na pravom mjestu s pravom informacijom.\n\n"
            "*Ono što objavljujemo u vaultu — kvote, bonuse, signale — "
            "ne dolazi na Twitter ni u javne grupe. Dolazi tamo prvo.*\n\n"
            "Što ti je do sada najviše nedostajalo — brzina ili kvaliteta?"
        ),
    },
    "lt": {
        "betting": (
            "Prieš kelis mėnesius sekėjas man parašė žinutę 2 valandą nakties.\n\n"
            "«Valerija, ką tik pamačiau vakar paskelbtą koeficientą. Praleidau. 3.40 ant Over. "
            "Kodėl neatėjau anksčiau?»\n\n"
            "Ir tai man šiek tiek suskaudino širdį — nes tiksliai žinau tą jausmą.\n\n"
            "*Teisinga informacija ateina per vėlai kai nesi tinkamoje vietoje.* ⏱️\n\n"
            "Ar tau kada nors nutiko — pamatyti ką nors per vėlai?"
        ),
        "casino": (
            "Papasakosiu tau kai ką, ko paprastai nematyti.\n\n"
            "Praeitą savaitę buvo sveikinamasis bonusas su statymo reikalavimu ×12. "
            "Ne ×35, ne ×40 — *dvylika*. Truko 6 valandas prieš jį pakoreguojant.\n\n"
            "Paskelbėme jį kanale. 340 žmonių tą dieną pasinaudojo.\n\n"
            "*Geri bonusai nelaukia.* O tie, kurie vėluoja, visada mato tuščią ekraną.\n\n"
            "Ar aktyviai ieškote geriausių bonusų, ar jie atsiranda savaime?"
        ),
        "nodeposit": (
            "Žmonės mano, kad visi bonusai be depozito yra vienodi.\n\n"
            "Spoileris: taip nėra. Yra brutali skirtumas tarp bonuso su wageringu ×60 "
            "ir to su ×8 — pirmasis yra beveik iliuzinis, antrasis yra tikri pinigai.\n\n"
            "2 metus filtruojame šiukšles, kad liktų tik tai, kas verta.\n\n"
            "*Problema ne ta, kad nėra gerų bonusų — o žinoti, kurie jie yra.*\n\n"
            "Ar kada nors praradote bonusą nesuprasdamas sąlygų?"
        ),
        "exclusive": (
            "Būsiu su jumis tiesi.\n\n"
            "Šiame lažybų pasaulyje yra dviejų tipų žmonės:\n"
            "tie, kurie reaguoja kai jau per vėlu, ir tie, kurie yra ten kai tai vyksta.\n\n"
            "Tai ne laimė. Tai apie tai, kad esi tinkamoje vietoje su teisinga informacija.\n\n"
            "*Tai, ką skelbiame vaulte — koeficientai, bonusai, signalai — "
            "nepatenka nei į Twitter nei į viešas grupes. Patenka ten pirmiausia.*\n\n"
            "Ko jums labiausiai trūko iki šiol — greičio ar kokybės?"
        ),
    },
    "lv": {
        "betting": (
            "Pirms dažiem mēnešiem sekotājs man uzrakstīja ziņu pulksten 2 naktī.\n\n"
            "«Valerija, tikko ieraudzīju vakar publicēto koeficientu. Palaidu garām. 3.40 uz Over. "
            "Kāpēc nenācu agrāk?»\n\n"
            "Un tas mani nedaudz salauza — jo es precīzi zinu to sajūtu.\n\n"
            "*Pareizā informācija nāk par vēlu, kad neesi pareizajā vietā.* ⏱️\n\n"
            "Vai tev kad ir gadījies — redzēt kaut ko par vēlu?"
        ),
        "casino": (
            "Pastāstīšu tev kaut ko, ko parasti nevar redzēt.\n\n"
            "Pagājušajā nedēļā bija sveiciena bonuss ar derību prasību ×12. "
            "Ne ×35, ne ×40 — *divpadsmit*. Tas ilga 6 stundas pirms to pielāgoja.\n\n"
            "Publicējām to kanālā. 340 cilvēki to izmantoja tajā dienā.\n\n"
            "*Labi bonusi negaida.* Un tie, kas kavējas, vienmēr redz tukšu ekrānu.\n\n"
            "Vai aktīvi meklējat labākos bonusus, vai tie parādās paši?"
        ),
        "nodeposit": (
            "Cilvēki domā, ka visi bonusi bez depozīta ir vienādi.\n\n"
            "Spoilers: tā nav. Ir brutāla atšķirība starp bonusu ar wagering ×60 "
            "un to ar ×8 — pirmais ir gandrīz iluzorisk, otrais ir īsta nauda.\n\n"
            "2 gadus filtrējam atkritumu, lai paliktu tikai tas, kas ir vērts.\n\n"
            "*Problēma nav tā, ka nav labu bonusu — bet zināt, kuri tie ir.*\n\n"
            "Vai kādreiz esat pazaudējis bonusu nesaprotot noteikumus?"
        ),
        "exclusive": (
            "Būšu ar tevi tieša.\n\n"
            "Šajā likmju pasaulē ir divu veidu cilvēki:\n"
            "tie, kas reaģē kad jau par vēlu, un tie, kas ir tur kad tas notiek.\n\n"
            "Tā nav veiksme. Runa ir par to, ka esi pareizajā vietā ar pareizo informāciju.\n\n"
            "*Tas, ko publicējam vaultā — koeficienti, bonusi, signāli — "
            "nenonāk ne Twitter ne publiskajās grupās. Nonāk tur pirmais.*\n\n"
            "Kas tev visvairāk trūcis līdz šim — ātrums vai kvalitāte?"
        ),
    },
}


# ══════════════════════════════════════════════════════════════════════════════
#  WARM2 — социальное доказательство (ждём реакции)
# ══════════════════════════════════════════════════════════════════════════════
WARM2: dict[str, str] = {
    "es": (
        "Mira, no soy la única que lo dice.\n\n"
        "En el último mes, el canal ha crecido +2.800 personas. No por anuncios — "
        "por recomendaciones.\n\n"
        "Miguel (Sevilla): *«Llevo 3 semanas siguiendo las señales. No cambio nada, "
        "solo añado contexto al análisis que ya hacía. Noto la diferencia.»*\n\n"
        "Andris (Riga): *«El bono sin wagering que encontrasteis me salvó el mes de enero.»*\n\n"
        "Keine promesas. Solo personas reales que encontraron algo útil.\n\n"
        "¿Qué estás buscando tú ahora mismo — señales, bonos, análisis?"
    ),
    "hr": (
        "Evo, nije samo ja koja to kaže.\n\n"
        "Prošlog mjeseca kanal je narastao za +2.800 osoba. Ne zbog reklama — "
        "zbog preporuka.\n\n"
        "Miguel (Sevilla): *«3 tjedna pratim signale. Ništa ne mijenjam, "
        "samo dodajem kontekst analizama koje već radim. Osjećam razliku.»*\n\n"
        "Andris (Riga): *«Bonus bez wagering-a koji ste pronašli spasio mi je siječanj.»*\n\n"
        "Nema obećanja. Samo pravi ljudi koji su pronašli nešto korisno.\n\n"
        "Što ti sad tražiš — signale, bonuse, analize?"
    ),
    "lt": (
        "Žiūrėk, tai ne tik aš taip sakau.\n\n"
        "Per praeitą mėnesį kanalas išaugo +2.800 žmonių. Ne dėl reklamos — "
        "dėl rekomendacijų.\n\n"
        "Miguelis (Sevilija): *«3 savaites seku signalus. Nieko nekeičiu, "
        "tik pridedu konteksto jau atliekamai analizei. Jaučiu skirtumą.»*\n\n"
        "Andris (Ryga): *«Bonusas be wageringo, kurį radote, išgelbėjo mano sausį.»*\n\n"
        "Jokių pažadų. Tik tikri žmonės, kurie rado kažką naudingo.\n\n"
        "Ko tu dabar ieškai — signalų, bonusų, analizės?"
    ),
    "lv": (
        "Skaties, to nesaku tikai es.\n\n"
        "Pagājušajā mēnesī kanāls pieauga par +2.800 cilvēkiem. Ne reklāmas dēļ — "
        "ieteikumu dēļ.\n\n"
        "Migels (Sevilja): *«3 nedēļas seku signāliem. Neko nemainīju, "
        "tikai pievieno kontekstu analīzei, ko jau daru. Jūtu atšķirību.»*\n\n"
        "Andris (Rīga): *«Bonuss bez wageringa, ko atradāt, izglāba manu janvāri.»*\n\n"
        "Nav solījumu. Tikai īsti cilvēki, kas atraduši kaut ko noderīgu.\n\n"
        "Ko tu tagad meklē — signālus, bonusus, analīzi?"
    ),
}


# ══════════════════════════════════════════════════════════════════════════════
#  TEASE — срочность + дедлайн (ждём реакции)
# ══════════════════════════════════════════════════════════════════════════════
TEASE: dict[str, dict[str, str]] = {
    "es": {
        "betting": (
            "Okay. Escucha esto.\n\n"
            "Mañana hay un partido — no te digo cuál todavía — "
            "donde el mercado está claramente mal calibrado. "
            "La cuota real debería ser ~2.10. Está en 2.85.\n\n"
            "Ese gap no dura. Cuando las casas lo corrijan, ya no habrá nada que hacer.\n\n"
            "*Lo publico en el canal antes del partido.* Los que estén ahí lo verán.\n\n"
            "El resto... pues ya sabes."
        ),
        "casino": (
            "Tengo algo entre manos.\n\n"
            "Una plataforma está corriendo una promo esta semana — "
            "wagering ×8, depósito mínimo bajo, cashback incluido.\n\n"
            "No está en su web principal. Está en una página de landing específica "
            "que expira el viernes.\n\n"
            "*En el canal lo publiqué hace 3 días. Ya hay 200+ personas dentro.*\n\n"
            "¿Quieres ser el que llega tarde, o el que ya está?"
        ),
        "nodeposit": (
            "Hoy hay 3 bonos sin depósito activos que no están en ningún comparador.\n\n"
            "Dos de ellos tienen wagering ×10 o menos. Uno no tiene wagering.\n\n"
            "Los comparadores los actualizan cada 48-72h. Nosotros los tenemos en tiempo real.\n\n"
            "*La ventana se cierra — algunos ya expiraron mientras lees esto.*\n\n"
            "¿Quieres saber cuáles siguen activos?"
        ),
        "exclusive": (
            "Esta semana en el vault:\n\n"
            "• Una señal de valor en La Liga que se publicó con 18h de antelación ✅\n"
            "• Un bono casino con wagering ×9 que duró 11 horas ✅\n"
            "• Un arbitraje entre dos casas europeas con ROI estimado +6% ✅\n\n"
            "Todo esto pasó. La semana pasada.\n\n"
            "*La próxima semana va a pasar también — con o sin ti.*"
        ),
    },
    "hr": {
        "betting": (
            "Okay. Slušaj ovo.\n\n"
            "Sutra je utakmica — ne govorim još koja — "
            "gdje je tržište jasno loše kalibrirano. "
            "Prava kvota trebala bi biti ~2.10. Stoji na 2.85.\n\n"
            "Taj jaz ne traje. Kad ga kladionice isprave, neće biti ništa za učiniti.\n\n"
            "*Objavljujem na kanalu prije utakmice.* Oni koji budu tamo to će vidjeti.\n\n"
            "Ostali... pa znaš."
        ),
        "casino": (
            "Imam nešto u rukama.\n\n"
            "Platforma ove sedmice vodi promo — "
            "ulog ×8, nizak minimalni depozit, cashback uključen.\n\n"
            "Nije na njihovoj glavnoj stranici. Nalazi se na specifičnoj odredišnoj stranici "
            "koja ističe u petak.\n\n"
            "*U kanalu sam to objavio prije 3 dana. Već je 200+ osoba unutra.*\n\n"
            "Hoćeš biti onaj koji kasni, ili onaj koji je već tu?"
        ),
        "nodeposit": (
            "Danas postoje 3 aktivna bonusa bez depozita koji nisu ni u jednom usporedniku.\n\n"
            "Dva od njih imaju ulog ×10 ili manje. Jedan nema ulog.\n\n"
            "Usporedioci se ažuriraju svakih 48-72h. Mi ih imamo u realnom vremenu.\n\n"
            "*Prozor se zatvara — neki su već istekli dok ovo čitaš.*\n\n"
            "Hoćeš znati koji su još aktivni?"
        ),
        "exclusive": (
            "Ovog tjedna u vaultu:\n\n"
            "• Signal vrijednosti u La Ligi objavljen 18h unaprijed ✅\n"
            "• Casino bonus s ulogom ×9 koji je trajao 11 sati ✅\n"
            "• Arbitraža između dvije europske kladionice s procijenjenim ROI +6% ✅\n\n"
            "Sve se ovo dogodilo. Prošli tjedan.\n\n"
            "*Sljedeći tjedan će se opet dogoditi — sa ili bez tebe.*"
        ),
    },
    "lt": {
        "betting": (
            "Gerai. Klausykis.\n\n"
            "Rytoj yra rungtynės — dar nesakau kurių — "
            "kur rinka yra aiškiai blogai sukalibruota. "
            "Tikrasis koeficientas turėtų būti ~2.10. Yra 2.85.\n\n"
            "Ta spraga netrunka. Kai bukmeikeriai ją ištaisys, nieko nebus galima padaryti.\n\n"
            "*Skelbu kanale prieš rungtynes.* Kas bus ten — pamatys.\n\n"
            "Kiti... na žinai."
        ),
        "casino": (
            "Turiu kažką rankose.\n\n"
            "Platforma šią savaitę vykdo promo — "
            "wageringas ×8, žemas minimumas, cashback įskaičiuotas.\n\n"
            "Nėra jų pagrindinėje svetainėje. Yra konkrečiame nukreipimo puslapyje "
            "kuris baigsis penktadienį.\n\n"
            "*Kanale paskelbiau tai prieš 3 dienas. Jau 200+ žmonių viduje.*\n\n"
            "Nori būti tas, kuris vėluoja, ar tas, kuris jau čia?"
        ),
        "nodeposit": (
            "Šiandien yra 3 aktyvūs bonusai be depozito, kurių nėra jokiame palyginimo portale.\n\n"
            "Du iš jų turi wageringą ×10 ar mažiau. Vienas neturi wageringo.\n\n"
            "Palyginimo portalai atnaujinami kas 48-72 val. Mes juos turime realiuoju laiku.\n\n"
            "*Langas užsidaro — kai kurie jau pasibaigė kol skaitai šitai.*\n\n"
            "Nori žinoti, kurie dar aktyvūs?"
        ),
        "exclusive": (
            "Šią savaitę vaulte:\n\n"
            "• Vertės signalas La Lygoje paskelbtas likus 18val ✅\n"
            "• Kazino bonusas su wageringu ×9 kuris truko 11 valandų ✅\n"
            "• Arbitražas tarp dviejų Europos bukmeikerių su apskaičiuotu ROI +6% ✅\n\n"
            "Visa tai įvyko. Praeitą savaitę.\n\n"
            "*Kitą savaitę irgi įvyks — su tavimi ar be tavęs.*"
        ),
    },
    "lv": {
        "betting": (
            "Labi. Klausies.\n\n"
            "Rīt ir spēle — vēl nepasaku kura — "
            "kur tirgus ir skaidri slikti kalibrēts. "
            "Patiesajam koeficientam vajadzētu būt ~2.10. Ir 2.85.\n\n"
            "Šī plaisa neturpinās. Kad букmekers to labos, vairs nebūs ko darīt.\n\n"
            "*Publicēšu kanālā pirms spēles.* Kas tur būs — redzēs.\n\n"
            "Pārējie... nu zini."
        ),
        "casino": (
            "Man ir kaut kas rokās.\n\n"
            "Platforma šonedēļ vada promo — "
            "wagering ×8, zems minimums, cashback iekļauts.\n\n"
            "Nav viņu galvenajā vietnē. Ir konkrētā novirzīšanas lapā "
            "kas beigsies piektdien.\n\n"
            "*Kanālā to publicēju pirms 3 dienām. Jau 200+ cilvēki iekšā.*\n\n"
            "Gribi būt tas, kas kavējas, vai tas, kas jau ir šeit?"
        ),
        "nodeposit": (
            "Šodien ir 3 aktīvi bonusi bez depozīta, kuru nav nevienā salīdzinātājā.\n\n"
            "Divi no tiem ir ar wagering ×10 vai mazāk. Vienam nav wageringa.\n\n"
            "Salīdzinātāji atjauninās ik pēc 48-72 stundām. Mums tie ir reāllaikā.\n\n"
            "*Logs aizveras — daži jau beidzās kamēr to lasi.*\n\n"
            "Gribi zināt, kuri vēl aktīvi?"
        ),
        "exclusive": (
            "Šonedēļ vaultā:\n\n"
            "• Vērtības signāls La Ligā publicēts 18h iepriekš ✅\n"
            "• Kazino bonuss ar wagering ×9 kas ilga 11 stundas ✅\n"
            "• Arbitrāža starp diviem Eiropas буkmekерiem ar aprēķināto ROI +6% ✅\n\n"
            "Tas viss notika. Pagājušajā nedēļā.\n\n"
            "*Nākamnedēļ arī notiks — ar tevi vai bez tevis.*"
        ),
    },
}


# ══════════════════════════════════════════════════════════════════════════════
#  CTA — кнопки
# ══════════════════════════════════════════════════════════════════════════════
CTA_TEXT: dict[str, str] = {
    "es": "🔐 *El vault está ahí.*\n\nNo te cuento más por aquí.",
    "hr": "🔐 *Vault je tamo.*\n\nNe pričam više ovdje.",
    "lt": "🔐 *Vault yra ten.*\n\nDaugiau čia nepasakosiu.",
    "lv": "🔐 *Vault ir tur.*\n\nVairs šeit nestāstīšu.",
}

CTA: dict[str, str] = {
    "es": "📲 Entrar al OddsVault",
    "hr": "📲 Ući u OddsVault",
    "lt": "📲 Įeiti į OddsVault",
    "lv": "📲 Ienākt OddsVault",
}

CTA_BUTTON_JOINED: dict[str, str] = {
    "es": "✅ Ya estoy dentro",
    "hr": "✅ Već sam unutra",
    "lt": "✅ Jau esu viduje",
    "lv": "✅ Jau esmu iekšā",
}


# ══════════════════════════════════════════════════════════════════════════════
#  POST_SUB — после «Я уже вступил»
# ══════════════════════════════════════════════════════════════════════════════
POST_SUB: dict[str, dict[str, str]] = {
    "es": {
        "betting": (
            "Perfecto. Ya estás donde tiene que estar.\n\n"
            "Una cosa más — si alguna vez quieres hablar de un análisis, "
            "una cuota concreta o una estrategia, escríbeme aquí.\n\n"
            "Respondo. No como un bot — como alguien que sabe de esto. 🎯"
        ),
        "casino": (
            "Bien hecho. Vas a ver la diferencia.\n\n"
            "Y si tienes preguntas sobre algún bono — condiciones, "
            "cómo calcularlo, si compensa — aquí estoy.\n\n"
            "Hablo contigo de verdad. 💎"
        ),
        "nodeposit": (
            "Bienvenido al lado donde los bonos sí se entienden.\n\n"
            "Si alguna vez tienes dudas sobre wagering, "
            "juego válido o retiro — pregúntame aquí.\n\n"
            "Estoy. 🎁"
        ),
        "exclusive": (
            "Ya eres parte del vault.\n\n"
            "Este chat sigue activo — si quieres analizar algo, "
            "preguntarme sobre una cuota o un bono, lo hacemos aquí.\n\n"
            "Sin límite. Sin filtros. 🔥"
        ),
    },
    "hr": {
        "betting": (
            "Savršeno. Već si gdje treba biti.\n\n"
            "Još jedna stvar — ako ikad želiš razgovarati o analizi, "
            "konkretnoj kvoti ili strategiji, piši mi ovdje.\n\n"
            "Odgovaram. Ne kao bot — kao netko tko se razumije u ovo. 🎯"
        ),
        "casino": (
            "Bravo. Vidjet ćeš razliku.\n\n"
            "I ako imaš pitanja o nekom bonusu — uvjeti, "
            "kako ga izračunati, isplati li se — tu sam.\n\n"
            "Pravi razgovor. 💎"
        ),
        "nodeposit": (
            "Dobrodošao na stranu gdje se bonusi zaista razumiju.\n\n"
            "Ako ikad imaš nedoumica oko wagering-a, "
            "prihvatljive igre ili isplate — pitaj me ovdje.\n\n"
            "Tu sam. 🎁"
        ),
        "exclusive": (
            "Već si dio vaulta.\n\n"
            "Ovaj chat ostaje aktivan — ako želiš analizirati nešto, "
            "pitati me o kvoti ili bonusu, radimo to ovdje.\n\n"
            "Bez ograničenja. Bez filtera. 🔥"
        ),
    },
    "lt": {
        "betting": (
            "Puiku. Jau esi ten kur reikia.\n\n"
            "Dar vienas dalykas — jei kada nori pakalbėti apie analizę, "
            "konkretų koeficientą ar strategiją, rašyk man čia.\n\n"
            "Atsakau. Ne kaip botas — kaip kažkas kas išmano šį dalyką. 🎯"
        ),
        "casino": (
            "Gerai padaryta. Pamatysi skirtumą.\n\n"
            "Ir jei turi klausimų apie kokį bonusą — sąlygos, "
            "kaip apskaičiuoti, ar verta — čia esu.\n\n"
            "Tikras pokalbis. 💎"
        ),
        "nodeposit": (
            "Sveiki atvykę į pusę kur bonusai tikrai suprantami.\n\n"
            "Jei kada turėsi abejonių dėl wageringo, "
            "tinkamo žaidimo ar išmokėjimo — klausk manęs čia.\n\n"
            "Esu čia. 🎁"
        ),
        "exclusive": (
            "Jau esi vaulto dalis.\n\n"
            "Šis pokalbis lieka aktyvus — jei nori ką nors analizuoti, "
            "klausti apie koeficientą ar bonusą, darome čia.\n\n"
            "Be apribojimų. Be filtrų. 🔥"
        ),
    },
    "lv": {
        "betting": (
            "Lieliski. Jau esi tur kur vajag.\n\n"
            "Vēl viena lieta — ja kādreiz gribi runāt par analīzi, "
            "konkrētu koeficientu vai stratēģiju, raksti man šeit.\n\n"
            "Atbildu. Ne kā bots — kā kāds, kas to pārzina. 🎯"
        ),
        "casino": (
            "Labi izdarīts. Redzēsi atšķirību.\n\n"
            "Un ja ir jautājumi par kādu bonusu — noteikumi, "
            "kā aprēķināt, vai tas atmaksājas — esmu šeit.\n\n"
            "Īsts dialogs. 💎"
        ),
        "nodeposit": (
            "Laipni lūdzam pusē kur bonusi tiešām tiek saprasti.\n\n"
            "Ja kādreiz būs šaubas par wagering, "
            "pieļaujamo spēli vai izmaksu — jautā man šeit.\n\n"
            "Esmu šeit. 🎁"
        ),
        "exclusive": (
            "Jau esi vault daļa.\n\n"
            "Šis čats paliek aktīvs — ja gribi kaut ko analizēt, "
            "jautāt par koeficientu vai bonusu, darām to šeit.\n\n"
            "Bez ierobežojumiem. Bez filtriem. 🔥"
        ),
    },
}


# ══════════════════════════════════════════════════════════════════════════════
#  REENGAGE — пуш через 24/48ч
# ══════════════════════════════════════════════════════════════════════════════
REENGAGE_1: dict[str, str] = {
    "es": (
        "Oye — sigues ahí? 👀\n\n"
        "Ayer publiqué algo en el vault que no suele verse en ningún otro sitio.\n\n"
        "Si quieres verlo, ya sabes dónde está."
    ),
    "hr": (
        "Hej — još si tu? 👀\n\n"
        "Jučer sam objavio nešto u vaultu što se rijetko vidi negdje drugdje.\n\n"
        "Ako to želiš vidjeti, znaš gdje je."
    ),
    "lt": (
        "Ei — dar čia? 👀\n\n"
        "Vakar paskelbiau kažką vaulte ko paprastai nematyti niekur kitur.\n\n"
        "Jei nori pamatyti, žinai kur yra."
    ),
    "lv": (
        "Hei — vēl esi šeit? 👀\n\n"
        "Vakar publicēju kaut ko vaultā, kas parasti nav redzams nekur citur.\n\n"
        "Ja gribi to redzēt, zini kur tas ir."
    ),
}

REENGAGE_2: dict[str, str] = {
    "es": (
        "Última vez que te escribo sobre esto.\n\n"
        "La semana tiene 3 eventos grandes. Ya tenemos los análisis preparados.\n\n"
        "Después del primer pitido... ya no sirve de nada. ⏳"
    ),
    "hr": (
        "Zadnji put ti pišem o ovome.\n\n"
        "Tjedan ima 3 velika događaja. Analize su već pripremljene.\n\n"
        "Nakon prvog zvižduka... nema više smisla. ⏳"
    ),
    "lt": (
        "Paskutinį kartą rašau tau apie tai.\n\n"
        "Savaitė turi 3 didelius renginius. Analizės jau paruoštos.\n\n"
        "Po pirmojo švilpuko... jau nebe prasminga. ⏳"
    ),
    "lv": (
        "Pēdējo reizi rakstu tev par šo.\n\n"
        "Nedēļā ir 3 lieli notikumi. Analīzes jau ir sagatavotas.\n\n"
        "Pēc pirmā svilpiena... vairs nav jēgas. ⏳"
    ),
}


# ══════════════════════════════════════════════════════════════════════════════
#  INTEREST_SHIFT — когда AI меняет интерес пользователя
# ══════════════════════════════════════════════════════════════════════════════
INTEREST_SHIFT: dict[str, dict[str, str]] = {
    "betting_to_casino": {
        "es": "Entendido — te mando al canal de casino donde está lo más relevante para ti. 🎰",
        "hr": "Razumijem — šaljem te na casino kanal gdje je najrelevantnije za tebe. 🎰",
        "lt": "Supratau — siunčiu tave į kazino kanalą kur tau labiausiai aktualu. 🎰",
        "lv": "Sapratu — sūtu tevi uz kazino kanālu kur tev visaktuālākais. 🎰",
    },
    "casino_to_betting": {
        "es": "Veo que el deporte te tira más — aquí las señales de valor. ⚽",
        "hr": "Vidim da te sport više privlači — ovdje su signali vrijednosti. ⚽",
        "lt": "Matau, kad sportas jus labiau traukia — čia vertės signalai. ⚽",
        "lv": "Redzu, ka sports tevi vairāk piesaista — šeit vērtības signāli. ⚽",
    },
}


# ══════════════════════════════════════════════════════════════════════════════
#  FTD_PUSH — пуш каждые 5 сообщений у подписанных (first-time deposit nudge)
# ══════════════════════════════════════════════════════════════════════════════
FTD_PUSH: dict[str, dict[str, str]] = {
    "es": {
        "betting": (
            "Por cierto — esta semana hay una ventana de valor en Primera División. "
            "Los detalles están en el canal. 📊"
        ),
        "casino": (
            "Hay un bono nuevo esta semana con wagering muy bajo. "
            "Está en el canal con todos los detalles. 💎"
        ),
        "nodeposit": (
            "Acaban de activar 2 bonos sin depósito nuevos. "
            "Están en el canal — corre antes de que expiren. 🎁"
        ),
        "exclusive": (
            "Esta semana el vault tiene material nuevo. "
            "Señales, bonos y un análisis que no vas a ver en ningún sitio. 🔥"
        ),
    },
    "hr": {
        "betting": (
            "Usput — ovaj tjedan postoji prozor vrijednosti u Prvoj ligi. "
            "Detalji su u kanalu. 📊"
        ),
        "casino": (
            "Postoji novi bonus ovog tjedna s vrlo niskim ulogom. "
            "Na kanalu je sa svim detaljima. 💎"
        ),
        "nodeposit": (
            "Upravo su aktivirana 2 nova bonusa bez depozita. "
            "Na kanalu su — požuri prije nego isteknu. 🎁"
        ),
        "exclusive": (
            "Ovog tjedna vault ima novi materijal. "
            "Signali, bonusi i analiza koja se ne vidi nigdje drugdje. 🔥"
        ),
    },
    "lt": {
        "betting": (
            "Beje — šią savaitę yra vertės langas Pirmojoje lygoje. "
            "Detalės kanale. 📊"
        ),
        "casino": (
            "Šią savaitę yra naujas bonusas su labai mažu wageringu. "
            "Kanale su visomis detalėmis. 💎"
        ),
        "nodeposit": (
            "Ką tik aktyvuoti 2 nauji bonusai be depozito. "
            "Kanale — skubėk prieš pasibaigiant. 🎁"
        ),
        "exclusive": (
            "Šią savaitę vaulte yra naujos medžiagos. "
            "Signalai, bonusai ir analizė kurios niekur kitur nematysi. 🔥"
        ),
    },
    "lv": {
        "betting": (
            "Starp citu — šonedēļ ir vērtības logs Pirmajā līgā. "
            "Sīkāka informācija kanālā. 📊"
        ),
        "casino": (
            "Šonedēļ ir jauns bonuss ar ļoti zemu wagering. "
            "Kanālā ar visiem sīkumiem. 💎"
        ),
        "nodeposit": (
            "Tikko aktivizēti 2 jauni bonusi bez depozīta. "
            "Kanālā — steidzies pirms tie beidzas. 🎁"
        ),
        "exclusive": (
            "Šonedēļ vaultā ir jauns materiāls. "
            "Signāli, bonusi un analīze ko nekur citur neredzēsi. 🔥"
        ),
    },
}


# ══════════════════════════════════════════════════════════════════════════════
#  Helper: получить текст из словаря [lang][interest] с fallback
# ══════════════════════════════════════════════════════════════════════════════
def get(
    mapping: dict,
    lang: str,
    interest: Optional[str] = None,
    *,
    default_lang: str = "es",
    default_interest: str = "betting",
) -> str:
    """
    Универсальный геттер с двойным fallback.
    mapping может быть:
      - dict[lang, str]
      - dict[lang, dict[interest, str]]
    """
    lang_data = mapping.get(lang) or mapping.get(default_lang, {})

    if isinstance(lang_data, str):
        return lang_data

    if interest:
        result = lang_data.get(interest) or lang_data.get(default_interest)
        if isinstance(result, str):
            return result

    # last resort
    for v in lang_data.values():
        if isinstance(v, str):
            return v
    return ""
