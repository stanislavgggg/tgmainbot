"""
messages.py — OddsVault Bot v14 (cleaned)

Только то что реально используется в bot.py:
  - HOOK (через ab_test.py get_hook_text)
  - TEASE[lang][interest]
  - CTA_TEXT, CTA, CTA_BUTTON_JOINED
  - POST_SUB[lang][interest]

УДАЛЕНО (мёртвый код):
  - WARM1, WARM2 — заменены AI-диалогом (ask_valeria_conversational)
  - INTEREST_SHIFT — нет handler-а
  - WAKE_UP — дубль HOOK
  - QUIZ, QUIZ_BUTTONS, QUIZ_ACK, LANG_BUTTONS — квиз через кнопки заменён
    диалоговым detect_interest_from_text
  - FTD_PUSH — заменён ftd_onboarding schedule
  - REENGAGE_1, REENGAGE_2 — заменены _REENGAGE_ANGLES в bot.py
"""

from typing import Optional


# ══════════════════════════════════════════════════════════════════════════════
#  TEASE — срочность + дедлайн
# ══════════════════════════════════════════════════════════════════════════════
TEASE: dict[str, dict[str, str]] = {
    "en": {
        "betting": (
            "Okay. Listen to this.\n\n"
            "Tomorrow there's a match — I'm not telling you which one yet — "
            "where the market is clearly miscalibrated. "
            "The real line should be ~2.10. It's sitting at 2.85.\n\n"
            "That gap doesn't last. Once the bookmakers correct it, there's nothing left to do.\n\n"
            "*I'll post it in the channel before the match.* The people who are there will see it.\n\n"
            "The rest... well, you know."
        ),
        "casino": (
            "I've got something in the works.\n\n"
            "A platform is running a promo this week — "
            "×8 wagering, low minimum deposit, cashback included.\n\n"
            "It's not on their main site. It's on a specific landing page that expires Friday.\n\n"
            "*I posted it in the channel 3 days ago. Already 200+ people are inside.*\n\n"
            "Do you want to be the one who arrives late, or the one who's already there?"
        ),
        "nodeposit": (
            "Today there are 3 active no-deposit bonuses that aren't on any comparison site.\n\n"
            "Two of them have ×10 wagering or less. One has no wagering at all.\n\n"
            "Comparison sites update every 48–72 hours. We have them in real time.\n\n"
            "*The window is closing — some already expired while you're reading this.*\n\n"
            "Want to know which ones are still active?"
        ),
        "exclusive": (
            "This week in the vault:\n\n"
            "• A value signal published 18h in advance ✅\n"
            "• A casino bonus with ×9 wagering that lasted 11 hours ✅\n"
            "• An arbitrage between two European bookmakers with estimated ROI +6% ✅\n\n"
            "All of this happened. Last week.\n\n"
            "*Next week it'll happen again — with or without you.*"
        ),
    },
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
            "• Una señal de valor publicada con 18h de antelación ✅\n"
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
            "• Signal vrijednosti objavljen 18h unaprijed ✅\n"
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
            "• Vertės signalas paskelbtas likus 18val ✅\n"
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
            "Šī plaisa neturpinās. Kad буkmekери to labos, vairs nebūs ko darīt.\n\n"
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
            "• Vērtības signāls publicēts 18h iepriekš ✅\n"
            "• Kazino bonuss ar wagering ×9 kas ilga 11 stundas ✅\n"
            "• Arbitrāža starp diviem Eiropas буkmekерiem ar aprēķināto ROI +6% ✅\n\n"
            "Tas viss notika. Pagājušajā nedēļā.\n\n"
            "*Nākamnedēļ arī notiks — ar tevi vai bez tevis.*"
        ),
    },
}


# ══════════════════════════════════════════════════════════════════════════════
#  CTA
# ══════════════════════════════════════════════════════════════════════════════
CTA_TEXT: dict[str, str] = {
    "en": "🔐 *The vault is right there.*\n\nI've told you everything I can here.",
    "es": "🔐 *El vault está ahí.*\n\nNo te cuento más por aquí.",
    "hr": "🔐 *Vault je tamo.*\n\nNe pričam više ovdje.",
    "lt": "🔐 *Vault yra ten.*\n\nDaugiau čia nepasakosiu.",
    "lv": "🔐 *Vault ir tur.*\n\nVairs šeit nestāstīšu.",
}

CTA: dict[str, str] = {
    "en": "📲 Join OddsVault",
    "es": "📲 Entrar al OddsVault",
    "hr": "📲 Ući u OddsVault",
    "lt": "📲 Įeiti į OddsVault",
    "lv": "📲 Ienākt OddsVault",
}

CTA_BUTTON_JOINED: dict[str, str] = {
    "en": "✅ I'm already in",
    "es": "✅ Ya estoy dentro",
    "hr": "✅ Već sam unutra",
    "lt": "✅ Jau esu viduje",
    "lv": "✅ Jau esmu iekšā",
}


# ══════════════════════════════════════════════════════════════════════════════
#  POST_SUB — после «Я уже вступил» (fallback если get_post_sub_opener вернул "")
# ══════════════════════════════════════════════════════════════════════════════
POST_SUB: dict[str, dict[str, str]] = {
    "en": {
        "betting":   "Perfect. You're exactly where you need to be.\n\nIf you ever want to talk through an analysis, a specific line, or a strategy, just write me here.\n\nI respond. Not like a bot — like someone who actually knows this stuff. 🎯",
        "casino":    "Well done. You'll notice the difference.\n\nAnd if you have questions about any bonus — conditions, how to calculate it, whether it's worth it — I'm right here.\n\nReal conversation. 💎",
        "nodeposit": "Welcome to the side where bonuses actually make sense.\n\nIf you ever have doubts about wagering, eligible games, or withdrawals — ask me here.\n\nI'm here. 🎁",
        "exclusive": "You're part of the vault now.\n\nThis chat stays active — if you want to analyse something, ask about a line or a bonus, we do it here.\n\nNo limits. No filters. 🔥",
    },
    "es": {
        "betting":   "Perfecto. Ya estás donde tiene que estar.\n\nSi alguna vez quieres hablar de un análisis, una cuota concreta o una estrategia, escríbeme aquí.\n\nRespondo. No como un bot — como alguien que sabe de esto. 🎯",
        "casino":    "Bien hecho. Vas a ver la diferencia.\n\nY si tienes preguntas sobre algún bono — condiciones, cómo calcularlo, si compensa — aquí estoy.\n\nHablo contigo de verdad. 💎",
        "nodeposit": "Bienvenido al lado donde los bonos sí se entienden.\n\nSi alguna vez tienes dudas sobre wagering, juego válido o retiro — pregúntame aquí.\n\nEstoy. 🎁",
        "exclusive": "Ya eres parte del vault.\n\nEste chat sigue activo — si quieres analizar algo, preguntarme sobre una cuota o un bono, lo hacemos aquí.\n\nSin límite. Sin filtros. 🔥",
    },
    "hr": {
        "betting":   "Savršeno. Već si gdje treba biti.\n\nAko ikad želiš razgovarati o analizi, konkretnoj kvoti ili strategiji, piši mi ovdje.\n\nOdgovaram. Ne kao bot — kao netko tko se razumije u ovo. 🎯",
        "casino":    "Bravo. Vidjet ćeš razliku.\n\nI ako imaš pitanja o nekom bonusu — uvjeti, kako ga izračunati, isplati li se — tu sam.\n\nPravi razgovor. 💎",
        "nodeposit": "Dobrodošao na stranu gdje se bonusi zaista razumiju.\n\nAko ikad imaš nedoumica oko wagering-a, prihvatljive igre ili isplate — pitaj me ovdje.\n\nTu sam. 🎁",
        "exclusive": "Već si dio vaulta.\n\nOvaj chat ostaje aktivan — ako želiš analizirati nešto, pitati me o kvoti ili bonusu, radimo to ovdje.\n\nBez ograničenja. Bez filtera. 🔥",
    },
    "lt": {
        "betting":   "Puiku. Jau esi ten kur reikia.\n\nJei kada nori pakalbėti apie analizę, konkretų koeficientą ar strategiją, rašyk man čia.\n\nAtsakau. Ne kaip botas — kaip kažkas kas išmano šį dalyką. 🎯",
        "casino":    "Gerai padaryta. Pamatysi skirtumą.\n\nIr jei turi klausimų apie kokį bonusą — sąlygos, kaip apskaičiuoti, ar verta — čia esu.\n\nTikras pokalbis. 💎",
        "nodeposit": "Sveiki atvykę į pusę kur bonusai tikrai suprantami.\n\nJei kada turėsi abejonių dėl wageringo, tinkamo žaidimo ar išmokėjimo — klausk manęs čia.\n\nEsu čia. 🎁",
        "exclusive": "Jau esi vaulto dalis.\n\nŠis pokalbis lieka aktyvus — jei nori ką nors analizuoti, klausti apie koeficientą ar bonusą, darome čia.\n\nBe apribojimų. Be filtrų. 🔥",
    },
    "lv": {
        "betting":   "Lieliski. Jau esi tur kur vajag.\n\nJa kādreiz gribi runāt par analīzi, konkrētu koeficientu vai stratēģiju, raksti man šeit.\n\nAtbildu. Ne kā bots — kā kāds, kas to pārzina. 🎯",
        "casino":    "Labi izdarīts. Redzēsi atšķirību.\n\nUn ja ir jautājumi par kādu bonusu — noteikumi, kā aprēķināt, vai tas atmaksājas — esmu šeit.\n\nĪsts dialogs. 💎",
        "nodeposit": "Laipni lūdzam pusē kur bonusi tiešām tiek saprasti.\n\nJa kādreiz būs šaubas par wagering, pieļaujamo spēli vai izmaksu — jautā man šeit.\n\nEsmu šeit. 🎁",
        "exclusive": "Jau esi vault daļa.\n\nŠis čats paliek aktīvs — ja gribi kaut ko analizēt, jautāt par koeficientu vai bonusu, darām to šeit.\n\nBez ierobežojumiem. Bez filtriem. 🔥",
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
    default_lang: str = "en",
    default_interest: str = "betting",
) -> str:
    lang_data = mapping.get(lang) or mapping.get(default_lang, {})
    if isinstance(lang_data, str):
        return lang_data
    if interest:
        result = lang_data.get(interest) or lang_data.get(default_interest)
        if isinstance(result, str):
            return result
    for v in lang_data.values():
        if isinstance(v, str):
            return v
    return ""
