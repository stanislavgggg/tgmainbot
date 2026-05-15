"""
ftd_onboarding.py — OddsVault Bot v11

Полный онбординг после подписки на канал.
Цель: провести пользователя от "подписался" до первого депозита (FTD).

FLOW после нажатия "I'm already in":
  T+0s   → POST_SUB (уже есть в bot.py) — тёплое приветствие
  T+90s  → STEP_1: персональный breakdown бонуса/стратегии под интерес
  T+30m  → STEP_2: конкретный первый шаг ("вот что делают прямо сейчас")
  T+2h   → STEP_3: follow-up ("как результат?") — если молчат
  T+6h   → STEP_4: urgency push — последний толчок с дедлайном
  T+24h  → REENGAGE — если так и не написали (стандартный re-engage)

Каждый шаг:
  - Проверяет что юзер ещё не сделал FTD (не написал о депозите)
  - Если юзер сам написал между шагами → шаг отменяется (не спамим)
  - Персонализирован под lang + interest + profile
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from telegram.error import TelegramError
from telegram.constants import ParseMode

from storage import get_user, add_ai_message, mark_push_sent, get_profile, get_ai_history
from ai_agent import _post_with_retry, _fallback_response, _build_profile_ctx, ANTHROPIC_URL, MODEL, ANTHROPIC_KEY

logger = logging.getLogger(__name__)


# ════════════════════════════════════════════════════════════════════════════
#  Статичные тексты онбординга (fallback если API недоступен)
# ════════════════════════════════════════════════════════════════════════════

_STEP1_FALLBACK: dict[str, dict[str, str]] = {
    "en": {
        "betting": (
            "Here's how the sharp side actually works 🎯\n\n"
            "The channel posts before lines move. That gap — between when the signal appears "
            "and when the public catches up — is usually *15–45 minutes*.\n\n"
            "Most people wait for confirmation. The ones making money act in that window.\n\n"
            "What's your usual stake size? I want to make sure what I flag is relevant for you."
        ),
        "casino": (
            "Let me break down how the bonus actually works 💎\n\n"
            "The channel posts bonuses with *real wagering math* — not just the headline number. "
            "A ×8 wagering on €50 = €400 to play through. At 96% RTP that's about *€16 expected cost*.\n\n"
            "Most people don't know this and lose money on 'good' bonuses.\n\n"
            "What kind of games do you usually play — slots, live tables, or both?"
        ),
        "nodeposit": (
            "No-deposit is the easiest first step 🎁\n\n"
            "Here's the math: €25 free, ×10 wagering = €250 to play through. "
            "At 96% RTP slots that's *~€10 expected cost* — but the upside is real cash.\n\n"
            "The key is picking the right games. Low volatility slots clear wagering fastest.\n\n"
            "Have you done any no-deposit offers before, or would this be your first?"
        ),
        "exclusive": (
            "Here's what the channel actually gives you 🔥\n\n"
            "Two types of edges: *value bets* (line mispricing, usually 0.3–0.5 off true odds) "
            "and *bonus arbitrage* (free money from promotions with positive EV).\n\n"
            "Most people only use one. Combining both is where the consistent edge comes from.\n\n"
            "Which side are you more comfortable with — the betting lines or the bonus math?"
        ),
    },
    "es": {
        "betting": (
            "Así funciona el lado inteligente 🎯\n\n"
            "El canal publica antes de que las cuotas se muevan. Esa ventana — entre cuando "
            "aparece la señal y cuando el público reacciona — suele ser *15–45 minutos*.\n\n"
            "La mayoría espera confirmación. Los que ganan actúan en esa ventana.\n\n"
            "¿Cuál es tu apuesta habitual? Quiero asegurarme de que lo que te señalo sea relevante."
        ),
        "casino": (
            "Te explico cómo funciona el bono de verdad 💎\n\n"
            "El canal publica bonos con *la matemática real del wagering* — no solo el titular. "
            "Un ×8 sobre €50 = €400 a jugar. Con RTP del 96% son unos *€16 de coste esperado*.\n\n"
            "La mayoría no sabe esto y pierde con bonos 'buenos'.\n\n"
            "¿Qué tipo de juegos sueles usar — slots, mesas en vivo, o los dos?"
        ),
        "nodeposit": (
            "El sin depósito es el primer paso más fácil 🎁\n\n"
            "La matemática: €25 gratis, ×10 wagering = €250 a jugar. "
            "Con slots al 96% RTP eso son *~€10 de coste esperado* — pero el upside es dinero real.\n\n"
            "La clave es elegir los juegos correctos. Los slots de baja volatilidad liberan el wagering más rápido.\n\n"
            "¿Has usado algún bono sin depósito antes o sería el primero?"
        ),
        "exclusive": (
            "Esto es lo que te da el canal de verdad 🔥\n\n"
            "Dos tipos de ventaja: *value bets* (error en cuotas, suele ser 0.3–0.5 de diferencia) "
            "y *arbitraje de bonos* (dinero gratis de promociones con EV positivo).\n\n"
            "La mayoría solo usa uno. Combinar los dos es donde está el edge consistente.\n\n"
            "¿Con cuál te sientes más cómodo — las cuotas o la matemática de bonos?"
        ),
    },
    "hr": {
        "betting": (
            "Evo kako zapravo funkcionira pametna strana 🎯\n\n"
            "Kanal objavljuje prije nego se kvote pomaknu. Taj prozor — između kada se signal pojavi "
            "i kada javnost reagira — obično je *15–45 minuta*.\n\n"
            "Većina čeka potvrdu. Oni koji zarađuju djeluju u tom prozoru.\n\n"
            "Koliki ti je uobičajeni ulog? Želim osigurati da je ono što ti naglasim relevantno."
        ),
        "casino": (
            "Razložit ću ti kako bonus zapravo funkcionira 💎\n\n"
            "Kanal objavljuje bonuse s *pravom matematikom wagering-a* — ne samo naslovni broj. "
            "×8 na €50 = €400 za proigravanje. Pri RTP-u 96% to je *~€16 očekivanog troška*.\n\n"
            "Većina toga ne zna i gubi na 'dobrim' bonusima.\n\n"
            "Koje igre obično igraš — slotove, live stolove, ili oboje?"
        ),
        "nodeposit": (
            "Bez depozita je najlakši prvi korak 🎁\n\n"
            "Matematika: €25 besplatno, ×10 wagering = €250 za proigravanje. "
            "Na slotovima s RTP 96% to je *~€10 očekivanog troška* — ali potencijal je pravi novac.\n\n"
            "Ključ je odabir pravih igara. Slotovi niske volatilnosti najbrže čiste wagering.\n\n"
            "Jesi li ikad koristio ponudu bez depozita ili bi ovo bilo prvo?"
        ),
        "exclusive": (
            "Evo što ti kanal zapravo daje 🔥\n\n"
            "Dvije vrste prednosti: *value bets* (pogreška u kvotama, obično 0.3–0.5 razlike) "
            "i *bonus arbitraža* (besplatan novac iz promocija s pozitivnim EV-om).\n\n"
            "Većina koristi samo jedno. Kombiniranje obaju je gdje dolazi dosljedna prednost.\n\n"
            "Čime se osjećaš ugodnije — kvotama ili matematikom bonusa?"
        ),
    },
    "lt": {
        "betting": (
            "Štai kaip iš tikrųjų veikia protinga pusė 🎯\n\n"
            "Kanalas publikuoja prieš koeficientams judant. Tas langas — tarp signalo pasirodymo "
            "ir visuomenės reakcijos — paprastai yra *15–45 minutės*.\n\n"
            "Dauguma laukia patvirtinimo. Tie kurie uždirba veikia per tą langą.\n\n"
            "Koks tavo įprastas statymas? Noriu įsitikinti kad tai ką pažymiu bus aktualu."
        ),
        "casino": (
            "Leisk man paaiškinti kaip bonusas iš tikrųjų veikia 💎\n\n"
            "Kanalas publikuoja bonusus su *tikrąja wagering matematika* — ne tik antraštę. "
            "×8 nuo €50 = €400 sužaisti. Su 96% RTP tai yra *~€16 tikėtinų išlaidų*.\n\n"
            "Dauguma to nežino ir pralaimi su 'gerais' bonusais.\n\n"
            "Kokius žaidimus paprastai žaidi — slotus, live stalus, ar abu?"
        ),
        "nodeposit": (
            "Be depozito yra lengviausias pirmas žingsnis 🎁\n\n"
            "Matematika: €25 nemokamai, ×10 wagering = €250 sužaisti. "
            "Su 96% RTP slotais tai yra *~€10 tikėtinų išlaidų* — bet potencialas yra tikri pinigai.\n\n"
            "Raktas yra tinkamų žaidimų pasirinkimas. Mažo nepastovumo slotai greičiausiai išvalo wagering.\n\n"
            "Ar esi naudojęs be depozito pasiūlymą anksčiau ar tai būtų pirmas?"
        ),
        "exclusive": (
            "Štai ką kanalas iš tikrųjų suteikia 🔥\n\n"
            "Du pranašumų tipai: *value bets* (klaida koeficientuose, paprastai 0.3–0.5 skirtumas) "
            "ir *bonusų arbitražas* (nemokamas pinigai iš akcijų su teigiamu EV).\n\n"
            "Dauguma naudoja tik vieną. Abiejų derinimas yra nuoseklaus pranašumo šaltinis.\n\n"
            "Su kuo jautiesi patogiau — koeficientais ar bonusų matematika?"
        ),
    },
    "lv": {
        "betting": (
            "Lūk kā gudrā puse patiesībā darbojas 🎯\n\n"
            "Kanāls publicē pirms koeficienti kustas. Tas logs — starp signāla parādīšanos "
            "un sabiedrības reakciju — parasti ir *15–45 minūtes*.\n\n"
            "Vairākums gaida apstiprinājumu. Tie kas pelna rīkojas tajā logā.\n\n"
            "Kāds ir tavs parastais likums? Gribu pārliecināties ka tas ko atzīmēju būs relevants."
        ),
        "casino": (
            "Ļauj man izskaidrot kā bonuss patiesībā darbojas 💎\n\n"
            "Kanāls publicē bonusus ar *īstu wagering matemātiku* — ne tikai virsrakstu. "
            "×8 no €50 = €400 nospēlēt. Ar 96% RTP tas ir *~€16 paredzamo izmaksu*.\n\n"
            "Vairākums to nezina un zaudē uz 'labiem' bonusiem.\n\n"
            "Kādas spēles parasti spēlē — slotus, live galdiņus vai abus?"
        ),
        "nodeposit": (
            "Bez depozīta ir vieglākais pirmais solis 🎁\n\n"
            "Matemātika: €25 bez maksas, ×10 wagering = €250 nospēlēt. "
            "Ar 96% RTP slotiem tas ir *~€10 paredzamo izmaksu* — bet potenciāls ir īsta nauda.\n\n"
            "Atslēga ir pareizo spēļu izvēle. Zemas nepastāvības sloti ātrāk attīra wagering.\n\n"
            "Vai esi izmantojis bez depozīta piedāvājumu iepriekš vai tas būtu pirmais?"
        ),
        "exclusive": (
            "Lūk ko kanāls patiesībā dod 🔥\n\n"
            "Divi priekšrocību veidi: *value bets* (kļūda koeficientos, parasti 0.3–0.5 starpība) "
            "un *bonusu arbitrāža* (bezmaksas nauda no akcijām ar pozitīvu EV).\n\n"
            "Vairākums izmanto tikai vienu. Abu apvienošana ir pastāvīgu priekšrocību avots.\n\n"
            "Ar ko jūties ērtāk — koeficientiem vai bonusu matemātiku?"
        ),
    },
}

_STEP2_FALLBACK: dict[str, dict[str, str]] = {
    "en": {
        "betting":   "There's a line moving in the channel right now that fits exactly what we talked about. *The window is open.* What's stopping you from taking a position today?",
        "casino":    "The bonus I mentioned earlier — wagering is still at ×8. *That resets tomorrow.* Have you looked at the channel yet or still deciding?",
        "nodeposit": "That no-deposit window closes at midnight. *€25 free, no risk.* If not today — when? Serious question.",
        "exclusive": "Three value gaps posted in the channel in the last 6 hours. People already positioned. *What's your first move going to be?*",
    },
    "es": {
        "betting":   "Hay una cuota moviéndose en el canal ahora mismo que encaja con lo que hablamos. *La ventana está abierta.* ¿Qué te impide tomar una posición hoy?",
        "casino":    "El bono que mencioné antes — el wagering sigue en ×8. *Se resetea mañana.* ¿Ya has visto el canal o todavía lo estás decidiendo?",
        "nodeposit": "Esa ventana sin depósito cierra a medianoche. *€25 gratis, sin riesgo.* Si no hoy — ¿cuándo? Pregunta en serio.",
        "exclusive": "Tres gaps de valor publicados en el canal en las últimas 6 horas. La gente ya está posicionada. *¿Cuál va a ser tu primer movimiento?*",
    },
    "hr": {
        "betting":   "U kanalu se sada kreće kvota koja točno odgovara onome o čemu smo pričali. *Prozor je otvoren.* Što te sprečava da danas zauzmеš poziciju?",
        "casino":    "Bonus koji sam ranije spominjala — wagering je još na ×8. *Resetira se sutra.* Jesi li već pogledao kanal ili se još odlučuješ?",
        "nodeposit": "Taj prozor bez depozita zatvara se u ponoć. *€25 besplatno, bez rizika.* Ako ne danas — kada? Ozbiljno pitanje.",
        "exclusive": "Tri value gapa objavljena u kanalu u zadnjih 6 sati. Ljudi su već pozicionirani. *Koji će biti tvoj prvi potez?*",
    },
    "lt": {
        "betting":   "Kanale dabar juda koeficientas kuris tiksliai atitinka tai apie ką kalbėjome. *Langas yra atviras.* Kas trukdo šiandien užimti poziciją?",
        "casino":    "Bonusas kurį minėjau anksčiau — wagering vis dar ×8. *Rytoj atsigamins.* Ar jau peržiūrėjai kanalą ar dar sprendžiasi?",
        "nodeposit": "Tas be depozito langas užsidaro vidurnaktį. *€25 nemokamai, be rizikos.* Jei ne šiandien — kada? Rimtas klausimas.",
        "exclusive": "Per paskutines 6 valandas kanale paskelbti trys value tarpai. Žmonės jau pozicionuoti. *Koks bus tavo pirmas žingsnis?*",
    },
    "lv": {
        "betting":   "Kanālā tagad kustas koeficients kas precīzi atbilst tam par ko runājām. *Logs ir atvērts.* Kas kavē šodien ieņemt pozīciju?",
        "casino":    "Bonuss ko minēju agrāk — wagering joprojām ×8. *Atjaunojas rīt.* Vai jau apskatīji kanālu vai vēl izlemj?",
        "nodeposit": "Tas bez depozīta logs aizveras pusnaktī. *€25 bez maksas, bez riska.* Ja ne šodien — kad? Nopietns jautājums.",
        "exclusive": "Pēdējo 6 stundu laikā kanālā publicētas trīs value atstarpes. Cilvēki jau pozicionēti. *Kāds būs tavs pirmais gājiens?*",
    },
}

_STEP3_FALLBACK: dict[str, dict[str, str]] = {
    "en": {
        "betting":   "Hey — how did it go? Did you catch anything from the channel today? Even just watching the line movements tells you a lot. 🎯",
        "casino":    "Checking in — did you look at the bonus details? Sometimes the wagering math changes things. Happy to walk through it with you if you want. 💎",
        "nodeposit": "Still thinking about it? The no-deposit is the lowest possible risk — literally free to try. What's holding you back? 🎁",
        "exclusive": "Any questions after looking at the channel? The first move is always the hardest. I can help you pick the right entry point. 🔥",
    },
    "es": {
        "betting":   "Oye — ¿cómo fue? ¿Pillaste algo del canal hoy? Incluso solo ver los movimientos de cuotas te dice mucho. 🎯",
        "casino":    "Un check — ¿miraste los detalles del bono? A veces la matemática del wagering cambia las cosas. Puedo explicártelo si quieres. 💎",
        "nodeposit": "¿Todavía lo estás pensando? El sin depósito es el menor riesgo posible — literalmente gratis para probar. ¿Qué te frena? 🎁",
        "exclusive": "¿Alguna pregunta después de ver el canal? El primer movimiento siempre es el más difícil. Puedo ayudarte a elegir el punto de entrada correcto. 🔥",
    },
    "hr": {
        "betting":   "Hej — kako je prošlo? Jesi li uhvatio nešto iz kanala danas? Čak i samo gledanje kretanja kvota govori ti puno. 🎯",
        "casino":    "Provjera — jesi li pogledao detalje bonusa? Ponekad matematika wageringa mijenja stvari. Rado ću ti to objasniti ako želiš. 💎",
        "nodeposit": "Još razmišljaš? Bez depozita je najmanji mogući rizik — doslovno besplatno za isprobati. Što te koči? 🎁",
        "exclusive": "Imaš li pitanja nakon pregledavanja kanala? Prvi potez je uvijek najtežji. Mogu ti pomoći odabrati pravo ulazišno točku. 🔥",
    },
    "lt": {
        "betting":   "Ei — kaip sekėsi? Ar šiandien kanalas sugavo ką nors? Net ir tik stebėdamas koeficientų judėjimus daug sužinosi. 🎯",
        "casino":    "Patikrinimas — ar peržiūrėjai bonuso detales? Kartais wagering matematika keičia situaciją. Galiu paaiškinti jei nori. 💎",
        "nodeposit": "Dar galvoji? Be depozito yra mažiausia galima rizika — tiesiogiai nemokamai išbandyti. Kas stabdo? 🎁",
        "exclusive": "Ar yra klausimų po kanalo peržiūros? Pirmas žingsnis visada yra sunkiausias. Galiu padėti pasirinkti tinkamą įėjimo tašką. 🔥",
    },
    "lv": {
        "betting":   "Ei — kā gāja? Vai šodien kaut ko noķēri no kanāla? Pat tikai vērojot koeficientu kustību daudz uzzini. 🎯",
        "casino":    "Pārbaude — vai apskatīji bonusa detaļas? Dažreiz wagering matemātika maina lietas. Labprāt izskaidrošu ja gribi. 💎",
        "nodeposit": "Vēl domā? Bez depozīta ir mazākais iespējamais risks — burtiski bezmaksas izmēģināt. Kas kavē? 🎁",
        "exclusive": "Vai ir jautājumi pēc kanāla apskatīšanas? Pirmais gājiens vienmēr ir grūtākais. Varu palīdzēt izvēlēties pareizo ieejas punktu. 🔥",
    },
}

_STEP4_FALLBACK: dict[str, dict[str, str]] = {
    "en": {
        "betting":   "Last thing I'll say unprompted — there's a match tomorrow where the line is sitting *off* from where it should be. I'll post it tonight. After that I go quiet unless you write first. 🎯",
        "casino":    "I'll be direct: the bonus window closes tomorrow. After that the wagering goes back to standard terms. *This week's conditions are the best I've seen this month.* Up to you. 💎",
        "nodeposit": "Okay, last nudge. The free bonus expires. After tomorrow there's no way in without a deposit. *This was the zero-risk entry.* Let me know if you change your mind. 🎁",
        "exclusive": "I'm going quiet after this. But I want you to know — the gap we talked about is still open. The people who acted on it are already in profit. Your call. 🔥",
    },
    "es": {
        "betting":   "Lo último que te digo sin que lo pidas — hay un partido mañana donde la cuota está *mal calculada*. Lo publicaré esta noche. Después me callo a menos que me escribas tú. 🎯",
        "casino":    "Voy a ser directa: la ventana del bono cierra mañana. Después el wagering vuelve a condiciones estándar. *Las condiciones de esta semana son las mejores que he visto este mes.* Tú decides. 💎",
        "nodeposit": "Bien, último empujón. El bono gratuito vence. Después de mañana no hay forma de entrar sin depósito. *Esta era la entrada de cero riesgo.* Dime si cambias de opinión. 🎁",
        "exclusive": "Me voy a callar después de esto. Pero quiero que sepas — el gap del que hablamos sigue abierto. Los que actuaron ya están en beneficio. Tú decides. 🔥",
    },
    "hr": {
        "betting":   "Zadnja stvar što ću reći bez poticaja — sutra ima utakmica gdje kvota *nije tamo gdje bi trebala biti*. Objavit ću večeras. Nakon toga šutim osim ako mi ti pišeš. 🎯",
        "casino":    "Bit ću izravna: prozor bonusa zatvara se sutra. Nakon toga wagering se vraća na standardne uvjete. *Uvjeti ovog tjedna su najbolji koje sam vidjela ovog mjeseca.* Na tebi je. 💎",
        "nodeposit": "U redu, zadnji poticaj. Besplatni bonus istječe. Nakon sutra nema načina bez depozita. *Ovo je bio ulaz bez rizika.* Javi mi ako promijeniš mišljenje. 🎁",
        "exclusive": "Šutim nakon ovoga. Ali hoću da znaš — gap o kojem smo pričali je još uvijek otvoren. Oni koji su djelovali već su u plusu. Tvoj izbor. 🔥",
    },
    "lt": {
        "betting":   "Paskutinis dalykas kurį pasakysiu be prašymo — rytoj yra rungtynės kur koeficientas *nėra ten kur turėtų būti*. Paskelbsiu šį vakarą. Po to tyliu jei pats nerašai. 🎯",
        "casino":    "Būsiu tiesioginis: bonuso langas užsidaro rytoj. Po to wagering grįžta į standartines sąlygas. *Šios savaitės sąlygos yra geriausios kurias mačiau šį mėnesį.* Tau spręsti. 💎",
        "nodeposit": "Gerai, paskutinis postūmis. Nemokamas bonusas baigiasi. Po rytojaus nėra būdo be depozito. *Tai buvo be rizikos įėjimas.* Pranesk jei pakeisi nuomonę. 🎁",
        "exclusive": "Po šito tyliu. Bet noriu kad žinotum — tas tarpas apie kurį kalbėjome vis dar atviras. Tie kurie veikė jau yra pliuse. Tavo pasirinkimas. 🔥",
    },
    "lv": {
        "betting":   "Pēdējā lieta ko teikšu bez aicinājuma — rīt ir spēle kur koeficients *nav tur kur vajadzētu būt*. Publicēšu šovakar. Pēc tam klusēju ja vien tu pats neraksti. 🎯",
        "casino":    "Būšu tieša: bonusa logs aizveras rīt. Pēc tam wagering atgriežas standarta noteikumos. *Šīs nedēļas nosacījumi ir labākie ko esmu redzējusi šomēnes.* Tev izlemt. 💎",
        "nodeposit": "Labi, pēdējais grūdiens. Bezmaksas bonuss beidzas. Pēc rīt nav veida bez depozīta. *Tā bija bezriska ieeja.* Paziņo ja mainīsi domas. 🎁",
        "exclusive": "Pēc šī klusēju. Bet gribu lai zinātu — tas tarpas par ko runājām joprojām ir atvērts. Tie kas rīkojās jau ir plusā. Tavs lēmums. 🔥",
    },
}


# ════════════════════════════════════════════════════════════════════════════
#  AI-генерируемые шаги (если API доступен)
# ════════════════════════════════════════════════════════════════════════════

async def _generate_onboarding_step(
    step: int,
    lang: str,
    interest: str,
    user_profile: dict,
    history: list,
) -> Optional[str]:
    """Генерирует онбординг сообщение через AI. Fallback если API недоступен."""
    if not ANTHROPIC_KEY:
        return None

    lang_names = {
        "en": "English", "es": "Spanish (Spain, tú)",
        "hr": "Croatian", "lt": "Lithuanian", "lv": "Latvian",
    }
    language = lang_names.get(lang, "English")

    interest_ctx = {
        "betting":   "sports betting, value bets, sharp money, line movements",
        "casino":    "casino bonuses, wagering requirements, RTP, cashback",
        "nodeposit": "no-deposit bonuses, free spins, low wagering, first steps",
        "exclusive": "arbitrage, value bets, bonus EV, combined strategy",
    }.get(interest, "betting & bonuses")

    profile_ctx = _build_profile_ctx(user_profile)

    step_instructions = {
        1: (
            "This is the FIRST message after the user subscribed to the channel. "
            "Break down SPECIFICALLY how the channel benefits them given their interest. "
            "Use real math where possible (wagering calculations, expected value, timing windows). "
            "End with ONE personal question about their experience or preference that makes the next message natural. "
            "Tone: insider explaining to a friend, not a sales pitch. Warm, specific, direct."
        ),
        2: (
            "This is 30 minutes after subscription. User has had time to look at the channel. "
            "Create URGENCY around taking their first real action (first bet or first deposit). "
            "Reference something happening NOW — a line moving, a bonus expiring, people already acting. "
            "ONE direct question: what's stopping them, or what's their first move. "
            "No soft talk — this is the push moment. 2-3 sentences max."
        ),
        3: (
            "This is a follow-up 2 hours later. User hasn't responded. "
            "Casual check-in — not pushy. Like a friend asking how it went. "
            "Acknowledge they might be busy or still deciding. "
            "ONE easy question that invites them back into conversation. "
            "Very short — 2 sentences max."
        ),
        4: (
            "This is the FINAL push — 6 hours after subscription with no action. "
            "Be honest and direct: this is the last unprompted message. "
            "Create final urgency (something expiring, window closing). "
            "Make clear you'll go quiet after this unless they reach out. "
            "Respectful, not desperate. 2-3 sentences."
        ),
    }

    system = f"""You are Valeria — private AI companion for betting and bonuses.
This is onboarding step {step} after user subscribed to the channel.
Goal: move them to their first deposit (FTD) through natural conversation.

Language: {language} ONLY.
User interest: {interest_ctx}
{profile_ctx}

Step instructions: {step_instructions.get(step, '')}

RULES:
- NEVER sound like marketing copy or a bot
- NEVER invent specific match names, odds numbers, or exact bonus amounts
- NEVER say "I'm an AI" or reference being a bot
- Use *bold* for 1-2 key numbers or concepts only
- Max 3 sentences (step 1 can be 4-5). 1 emoji max at end.
- End with a question OR a clear statement — never both
- Tone: smart friend who has real insider knowledge"""

    try:
        # Keep only last 6 messages for context
        from ai_agent import _sanitize_history
        clean_history = _sanitize_history(history[-6:])

        data = await _post_with_retry(
            ANTHROPIC_URL,
            {
                "model":      MODEL,
                "max_tokens": 250,
                "system":     system,
                "messages":   clean_history + [
                    {"role": "user", "content": f"[ONBOARDING_STEP_{step}]"}
                ],
            },
            {
                "x-api-key":         ANTHROPIC_KEY,
                "anthropic-version": "2023-06-01",
                "content-type":      "application/json",
            },
            timeout=20,
        )
        text = next(
            (b["text"].strip() for b in data.get("content", []) if b.get("type") == "text"),
            "",
        )
        if text and len(text) > 20:
            # Clean markdown
            import re
            text = re.sub(r'\*\*(.+?)\*\*', r'*\1*', text)
            return text
    except Exception as e:
        logger.error(f"Onboarding step {step} AI error: {e}")

    return None


# ════════════════════════════════════════════════════════════════════════════
#  Проверка активности пользователя
# ════════════════════════════════════════════════════════════════════════════

def _user_active_since(user_id: int, since_ts: float) -> bool:
    """Писал ли пользователь сам после given timestamp."""
    user = get_user(user_id)
    last_active_str = user.get("last_active", "")
    if not last_active_str:
        return False
    try:
        la = datetime.fromisoformat(last_active_str)
        if la.tzinfo is None:
            la = la.replace(tzinfo=timezone.utc)
        return la.timestamp() > since_ts
    except Exception:
        return False

def _user_ftd_done(user_id: int) -> bool:
    """Пометили ли мы что юзер сделал FTD."""
    return bool(get_user(user_id).get("ftd_done"))


# ════════════════════════════════════════════════════════════════════════════
#  Job функции (вызываются из job_queue)
# ════════════════════════════════════════════════════════════════════════════

async def onboarding_step1_job(context) -> None:
    """T+90s: breakdown бонуса/стратегии под интерес."""
    d        = context.job.data
    user_id  = d["user_id"]
    chat_id  = d["chat_id"]
    lang     = d["lang"]
    interest = d["interest"]
    start_ts = d["start_ts"]

    if _user_ftd_done(user_id):
        return
    # Если юзер сам написал после подписки — пропускаем шаг
    if _user_active_since(user_id, start_ts):
        logger.info(f"Onboarding step1 skipped — user {user_id} already active")
        return

    profile = get_profile(user_id)
    history = get_ai_history(user_id)

    text = await _generate_onboarding_step(1, lang, interest, profile, history)
    if not text:
        text = _STEP1_FALLBACK.get(lang, _STEP1_FALLBACK["en"]).get(interest, "")
    if not text:
        return

    try:
        await context.bot.send_chat_action(chat_id=chat_id, action="typing")
        await asyncio.sleep(2.5)
        await context.bot.send_message(
            chat_id=chat_id, text=text, parse_mode=ParseMode.MARKDOWN)
        add_ai_message(user_id, "assistant", text)
        mark_push_sent(user_id)
        logger.info(f"Onboarding step1 → {user_id}")
    except TelegramError as e:
        logger.warning(f"Onboarding step1 failed [{user_id}]: {e}")


async def onboarding_step2_job(context) -> None:
    """T+30min: urgency — конкретный первый шаг."""
    d        = context.job.data
    user_id  = d["user_id"]
    chat_id  = d["chat_id"]
    lang     = d["lang"]
    interest = d["interest"]
    start_ts = d["start_ts"]

    if _user_ftd_done(user_id):
        return
    # Если юзер активен (написал что-то после step1) — не спамим
    if _user_active_since(user_id, start_ts + 90):
        logger.info(f"Onboarding step2 skipped — user {user_id} active")
        return

    profile = get_profile(user_id)
    history = get_ai_history(user_id)

    text = await _generate_onboarding_step(2, lang, interest, profile, history)
    if not text:
        text = _STEP2_FALLBACK.get(lang, _STEP2_FALLBACK["en"]).get(interest, "")
    if not text:
        return

    try:
        await context.bot.send_chat_action(chat_id=chat_id, action="typing")
        await asyncio.sleep(3.0)
        await context.bot.send_message(
            chat_id=chat_id, text=text, parse_mode=ParseMode.MARKDOWN)
        add_ai_message(user_id, "assistant", text)
        mark_push_sent(user_id)
        logger.info(f"Onboarding step2 → {user_id}")
    except TelegramError as e:
        logger.warning(f"Onboarding step2 failed [{user_id}]: {e}")


async def onboarding_step3_job(context) -> None:
    """T+2h: follow-up если молчат."""
    d        = context.job.data
    user_id  = d["user_id"]
    chat_id  = d["chat_id"]
    lang     = d["lang"]
    interest = d["interest"]
    start_ts = d["start_ts"]

    if _user_ftd_done(user_id):
        return
    if _user_active_since(user_id, start_ts + 1800):  # после step2
        logger.info(f"Onboarding step3 skipped — user {user_id} active")
        return

    profile = get_profile(user_id)
    history = get_ai_history(user_id)

    text = await _generate_onboarding_step(3, lang, interest, profile, history)
    if not text:
        text = _STEP3_FALLBACK.get(lang, _STEP3_FALLBACK["en"]).get(interest, "")
    if not text:
        return

    try:
        await context.bot.send_chat_action(chat_id=chat_id, action="typing")
        await asyncio.sleep(2.0)
        await context.bot.send_message(
            chat_id=chat_id, text=text, parse_mode=ParseMode.MARKDOWN)
        add_ai_message(user_id, "assistant", text)
        mark_push_sent(user_id)
        logger.info(f"Onboarding step3 → {user_id}")
    except TelegramError as e:
        logger.warning(f"Onboarding step3 failed [{user_id}]: {e}")


async def onboarding_step4_job(context) -> None:
    """T+6h: финальный urgency push."""
    d        = context.job.data
    user_id  = d["user_id"]
    chat_id  = d["chat_id"]
    lang     = d["lang"]
    interest = d["interest"]
    start_ts = d["start_ts"]

    if _user_ftd_done(user_id):
        return
    if _user_active_since(user_id, start_ts + 7200):  # после step3
        logger.info(f"Onboarding step4 skipped — user {user_id} active")
        return

    profile = get_profile(user_id)
    history = get_ai_history(user_id)

    text = await _generate_onboarding_step(4, lang, interest, profile, history)
    if not text:
        text = _STEP4_FALLBACK.get(lang, _STEP4_FALLBACK["en"]).get(interest, "")
    if not text:
        return

    try:
        await context.bot.send_chat_action(chat_id=chat_id, action="typing")
        await asyncio.sleep(2.0)
        await context.bot.send_message(
            chat_id=chat_id, text=text, parse_mode=ParseMode.MARKDOWN)
        add_ai_message(user_id, "assistant", text)
        mark_push_sent(user_id)
        logger.info(f"Onboarding step4 → {user_id}")
    except TelegramError as e:
        logger.warning(f"Onboarding step4 failed [{user_id}]: {e}")


# ════════════════════════════════════════════════════════════════════════════
#  PUBLIC: schedule_onboarding — вызывается из bot.py после user_joined
# ════════════════════════════════════════════════════════════════════════════

def schedule_onboarding(
    job_queue,
    user_id: int,
    chat_id: int,
    lang: str,
    interest: str,
) -> None:
    """
    Ставит в очередь 4 шага онбординга.
    Вызывать ПОСЛЕ того как подписка подтверждена.
    """
    start_ts = datetime.now(timezone.utc).timestamp()
    base_data = {
        "user_id":  user_id,
        "chat_id":  chat_id,
        "lang":     lang,
        "interest": interest,
        "start_ts": start_ts,
    }

    # T+90s  — breakdown бонуса/стратегии
    job_queue.run_once(
        onboarding_step1_job,
        when=90,
        data=base_data,
        name=f"ob1_{user_id}",
    )
    # T+30min — urgency первого шага
    job_queue.run_once(
        onboarding_step2_job,
        when=30 * 60,
        data=base_data,
        name=f"ob2_{user_id}",
    )
    # T+2h — follow-up
    job_queue.run_once(
        onboarding_step3_job,
        when=2 * 3600,
        data=base_data,
        name=f"ob3_{user_id}",
    )
    # T+6h — финальный push
    job_queue.run_once(
        onboarding_step4_job,
        when=6 * 3600,
        data=base_data,
        name=f"ob4_{user_id}",
    )

    logger.info(f"Onboarding scheduled for user {user_id} [{lang}/{interest}]")


# ════════════════════════════════════════════════════════════════════════════
#  FTD detector — определяет по тексту что юзер сделал депозит
# ════════════════════════════════════════════════════════════════════════════

_FTD_SIGNALS: list[str] = [
    # EN
    "deposited", "made a deposit", "put in", "funded", "added funds",
    "registered", "signed up", "joined", "i'm in", "did it", "done it",
    "placed a bet", "placed my first", "first bet", "first deposit",
    # ES
    "depositado", "hice un depósito", "me registré", "me apunté", "ya estoy",
    "puse dinero", "aposté", "primera apuesta", "primer depósito",
    # HR
    "uplatio", "napravio depozit", "registrirao", "pridružio", "kladio",
    "prvi ulog", "prva uplata",
    # LT
    "įnešiau", "užsiregistravau", "prisijungiau", "pastatiau",
    "pirmas statymas", "pirmas depozitas",
    # LV
    "iemaksāju", "reģistrējos", "pievienojos", "likumu",
    "pirmā likme", "pirmais depozīts",
]

def detect_ftd_signal(text: str) -> bool:
    """Определяет по тексту что пользователь сделал депозит/зарегистрировался."""
    lower = text.lower()
    return any(signal in lower for signal in _FTD_SIGNALS)
