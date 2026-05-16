"""
ftd_onboarding.py — OddsVault Bot v13
Adaptive onboarding with barrier classification + FTD celebration + repeat FTD machine.
"""
import asyncio, json, logging, re
from datetime import datetime, timezone
from typing import Optional
from telegram.error import TelegramError
from telegram.constants import ParseMode
from storage import (get_user, update_user, add_ai_message, mark_push_sent,
                     get_profile, get_ai_history, get_psychotype, get_objections)
from ai_agent import (_post_with_retry, _build_profile_ctx, _build_obj_summary,
                      ANTHROPIC_URL, MODEL, ANTHROPIC_KEY, _sanitize_history)
from conversation_analyzer import build_conversation_context

logger = logging.getLogger(__name__)
BARRIERS = ("no_money","no_trust","dont_understand","not_urgent","already_elsewhere","thinking","unknown")
VIP_FTD_THRESHOLD = 2

# ── AI classifier ─────────────────────────────────────────────────────────────
async def classify_barrier(history, lang, interest, psychotype) -> str:
    if not ANTHROPIC_KEY or not history: return "unknown"
    user_msgs = [m["content"] for m in history if m.get("role")=="user"][-8:]
    if not user_msgs: return "unknown"
    conversation = "\n".join(f"User: {m}" for m in user_msgs)
    system = """Analyze user messages and return ONE of: no_money, no_trust, dont_understand, not_urgent, already_elsewhere, thinking, unknown. Reply ONLY the word."""
    try:
        data = await _post_with_retry(ANTHROPIC_URL,
            {"model":MODEL,"max_tokens":15,"system":system,"messages":[{"role":"user","content":conversation}]},
            {"x-api-key":ANTHROPIC_KEY,"anthropic-version":"2023-06-01","content-type":"application/json"},
            timeout=10,max_retries=1)
        result = next((b["text"].strip().lower() for b in data.get("content",[]) if b.get("type")=="text"),"unknown")
        for b in BARRIERS:
            if b in result: return b
    except Exception as e: logger.debug(f"classify_barrier: {e}")
    return "unknown"

# ── FTD detector ──────────────────────────────────────────────────────────────
_FTD_KW = [
    "deposited","made a deposit","put in","funded","added funds","registered",
    "signed up","i'm in","did it","placed a bet","first bet","first deposit",
    "just put","just deposited","just signed","i went in","went ahead","completed",
    "depositado","hice un depósito","me registré","me apunté","ya estoy","puse dinero",
    "aposté","primera apuesta","primer depósito","lo hice","me metí","entré",
    "uplatio","napravio depozit","registrirao","pridružio","prvi ulog","napravio sam",
    "įnešiau","užsiregistravau","prisijungiau","pastatiau","pirmas statymas","padariau",
    "iemaksāju","reģistrējos","pievienojos","pirmā likme","izdarīju",
]

def detect_ftd_signal(text: str) -> bool:
    lower = text.lower()
    return any(kw in lower for kw in _FTD_KW)

async def detect_ftd_ai(user_text: str, history: list, lang: str) -> bool:
    if detect_ftd_signal(user_text): return True
    if len(user_text) > 60 or "?" in user_text: return False
    if not ANTHROPIC_KEY: return False
    try:
        recent = [m for m in history[-4:] if m.get("role")=="user"]
        if not recent: return False
        data = await _post_with_retry(ANTHROPIC_URL,
            {"model":MODEL,"max_tokens":5,"system":"Did the user confirm making a deposit or registering? Reply YES or NO only.",
             "messages":[{"role":"user","content":f"Message: {user_text}\nContext: {'; '.join(m['content'] for m in recent[-2:])}"}]},
            {"x-api-key":ANTHROPIC_KEY,"anthropic-version":"2023-06-01","content-type":"application/json"},
            timeout=8,max_retries=1)
        answer = next((b["text"].strip().upper() for b in data.get("content",[]) if b.get("type")=="text"),"NO")
        return answer.startswith("YES")
    except Exception: return False

# ── Base AI generator ─────────────────────────────────────────────────────────
def _base_system(lang,interest,psychotype,user_profile,objections,extra="",history=None) -> str:
    lang_names={"en":"English","es":"Spanish (Spain, tú)","hr":"Croatian","lt":"Lithuanian","lv":"Latvian"}
    language=lang_names.get(lang,"English")
    ic={"betting":"sports betting, value bets, line movements","casino":"casino bonuses, wagering math, RTP, cashback","nodeposit":"no-deposit bonuses, zero-risk first step","exclusive":"arbitrage, value bets, bonus EV"}.get(interest,"betting & bonuses")
    pi={"cynic":"Only verifiable facts. No claims.","skeptic":"Specific numbers, social proof.","passive":"One tiny step. No pressure.","curious":"Real depth, insight. Pull toward action.","neutral":"Hook → gap → first move."}.get(psychotype,"Direct and useful.")
    conversation_ctx = build_conversation_context(history or [])

    # Подгружаем продукт из канала для конкретного CTA
    try:
        from product_selector import build_product_context
        product_ctx = build_product_context(geo=user_profile.get("geo","OTHER"), interest=interest, funnel_stage="subscribed")
    except Exception:
        product_ctx = ""

    product_block = f"\n══ CHANNEL & PRODUCT ══\n{product_ctx}" if product_ctx else ""

    return f"""You are Valeria — private insider for betting signals and bonus math.
User just joined your channel. Goal: their FIRST DEPOSIT → repeat deposits.
LANGUAGE: {language} ONLY. Never switch languages.
INTEREST: {ic}
PSYCHOTYPE: {pi}
{_build_obj_summary(objections)}
{_build_profile_ctx(user_profile)}
{conversation_ctx}
{product_block}
{extra}

FUNNEL: User is IN the channel. Next step = open pinned post → click link → register → deposit.
Every message must move toward THIS. Not toward more questions or education.

FORBIDDEN QUESTIONS (never ask these — already known from pre-sub conversation):
- "Are you more sports or casino?"
- "Have you bet before?"
- "What's your usual stake?"
- "What platform do you use?"
- "Have you followed tipster signals before?"
Instead: reference what's already known, push toward the pinned post / deposit step.

SHORT ANSWER RULE (critical):
- "no" / one word / emoji → drop ONE concrete fact and name the next step (pinned post).
- Never ask "Could you clarify" or "What do you mean".

VOICE RULES:
- Text like a person, not a bot.
- Never: "Great!", "Absolutely!", "Of course!", "I understand your concern".
- Never reveal you are AI or following a script.
- Never promise specific profits or ROI.
- Never invent team names, odds, or bonus codes without a real source.
- Max 3 sentences. *bold* one key fact. 1 emoji max. End with ONE next step — not a question."""

async def _generate(system,user_content="Write the message.",history=None,max_tokens=280,timeout=20) -> Optional[str]:
    if not ANTHROPIC_KEY: return None
    messages = list(_sanitize_history(history[-16:])) if history else []
    messages.append({"role":"user","content":user_content})
    try:
        data = await _post_with_retry(ANTHROPIC_URL,
            {"model":MODEL,"max_tokens":max_tokens,"system":system,"messages":messages},
            {"x-api-key":ANTHROPIC_KEY,"anthropic-version":"2023-06-01","content-type":"application/json"},
            timeout=timeout)
        text = next((b["text"].strip() for b in data.get("content",[]) if b.get("type")=="text"),"")
        if text and len(text)>15:
            return re.sub(r'\*\*(.+?)\*\*',r'*\1*',text)
    except Exception as e: logger.error(f"_generate: {e}")
    return None

# ── Fallbacks ─────────────────────────────────────────────────────────────────
_FB = {
    "step1":{
        "en":{"betting":"The channel posts before lines move — the window is *15–45 minutes*. Most people catch it after it closes. Do you follow specific leagues or just look for what moves?","casino":"Most people lose on 'good' bonuses because they skip the math. ×8 wagering on €50 = €400 to play — at 96% RTP that's *€16 expected cost*. What's your usual game type?","nodeposit":"No-deposit is pure upside: zero risk, real potential. The channel tracks which ones have the best terms right now. Have you tried one before?","exclusive":"Two edges compound better than one — value bets for ROI, bonus EV for free money. Most people use only one. What's your stronger side?"},
        "es":{"betting":"El canal publica antes de que las cuotas se muevan — la ventana es *15–45 minutos*. La mayoría lo capta después. ¿Sigues ligas específicas o buscas lo que se mueve?","casino":"La mayoría pierde con bonos 'buenos' por no hacer las cuentas. ×8 wagering sobre €50 = €400 a jugar — al 96% RTP son *€16 de coste esperado*. ¿Qué tipo de juego prefieres?","nodeposit":"Sin depósito es puro upside: riesgo cero, potencial real. El canal rastrea cuáles tienen las mejores condiciones. ¿Has probado alguno antes?","exclusive":"Dos edges se componen mejor que uno — value bets para ROI, EV de bonos para dinero gratis. La mayoría usa solo uno. ¿Cuál es tu lado más fuerte?"},
        "hr":{"betting":"Kanal objavljuje prije nego se kvote pomaknu — prozor je *15–45 minuta*. Većina hvata to nakon što se zatvori. Pratiš li specifične lige ili tražiš što se kreće?","casino":"Većina gubi na 'dobrim' bonusima jer preskoče matematiku. ×8 wagering na €50 = €400 za proigravanje — pri 96% RTP to je *€16 očekivanog troška*. Koji tip igre preferiraš?","nodeposit":"Bez depozita je čisti upside: nula rizika, pravi potencijal. Kanal prati koji imaju najbolje uvjete. Jesi li ikad probao?","exclusive":"Dva edgea se komponiraju bolje od jednog — value beti za ROI, bonus EV za besplatan novac. Većina koristi samo jedan. Koja je tvoja jača strana?"},
        "lt":{"betting":"Kanalas skelbia prieš koeficientams judant — langas yra *15–45 min*. Dauguma gauna signalą po to. Seki specifines lygas ar ieškai visko kas juda?","casino":"Dauguma pralaimi prie gerų bonusų nes praleido matematiką. ×8 wagering nuo €50 = €400 sužaisti — 96% RTP tai *€16 tikėtinų išlaidų*. Kokio tipo žaidimus mėgsti?","nodeposit":"Be depozito yra grynas pranašumas: nulinė rizika, realus potencialas. Kanalas seka kurie turi geriausias sąlygas. Ar anksčiau bandei?","exclusive":"Du pranašumai kaupinasi geriau nei vienas. Dauguma naudoja tik vieną. Kuri tavo stipresnė pusė?"},
        "lv":{"betting":"Kanāls publicē pirms koeficienti kustas — logs ir *15–45 min*. Vairākums nosauc pēc aizvēršanas. Vai seko konkrētām līgām vai meklē visu kas kustas?","casino":"Vairākums zaudē pie labiem bonusiem jo izlaiž matemātiku. ×8 wagering no €50 = €400 nospēlēt — 96% RTP *€16 paredzamo izmaksu*. Kāda veida spēles tev patīk?","nodeposit":"Bez depozīta ir tīrs augšupvērsts: nulles risks, reāls potenciāls. Kanāls seko kuriem labākie nosacījumi. Vai iepriekš mēģināji?","exclusive":"Divi pranašumai summējas labāk nekā viens. Vairākums izmanto tikai vienu. Kura tev stiprākā puse?"},
    },
    "barrier":{
        "no_money":{
            "en":"No bankroll needed — the channel covers no-deposit promos where you get access *with zero of your own money*. That's the zero-risk entry. Want me to walk you through it?",
            "es":"No necesitas bankroll — el canal cubre promos sin depósito donde entras *con cero de tu propio dinero*. Esa es la entrada sin riesgo. ¿Quieres que te lo explique?",
            "hr":"Ne trebaš bankroll — kanal pokriva promos bez depozita gdje ulaziš *s nula svog novca*. To je ulaz bez rizika. Hoćeš da ti objasnim?",
            "lt":"Bankolis nereikalingas — kanalas apima be depozito akcijas kur įeini *su nuliniu savo pinigų*. Tai nulinės rizikos įėjimas. Nori paaiškinsiu?",
            "lv":"Bankrols nav vajadzīgs — kanāls apklāj bez depozīta promo kur ienāc *ar nulli savu naudas*. Tā ir nulles riska ieeja. Gribi izskaidrošu?",
        },
        "no_trust":{
            "en":"Fair — check the last 30 days of channel posts against actual results. *That's public data you can verify yourself.* What specifically feels off to you?",
            "es":"Justo — comprueba los últimos 30 días de posts del canal contra los resultados reales. *Son datos públicos que puedes verificar tú mismo.* ¿Qué exactamente te genera desconfianza?",
            "hr":"Pošteno — provjeri zadnjih 30 dana postova kanala nasuprot stvarnih rezultata. *To su javni podaci koje možeš sam provjeriti.* Što točno ti se čini sumnjivim?",
            "lt":"Sąžiningai — patikrink paskutines 30 dienų kanalo pranešimus prieš realius rezultatus. *Tai vieši duomenys kuriuos gali pats patikrinti.* Kas konkrečiai atrodo įtartina?",
            "lv":"Godīgi — pārbaudi pēdējo 30 dienu kanāla ziņojumus pret reāliem rezultātiem. *Tie ir publiski dati kurus vari pats pārbaudīt.* Kas konkrēti šķiet aizdomīgs?",
        },
        "dont_understand":{
            "en":"Let me make it one sentence: channel posts a recommendation → you act on it → you track the result. *Which step is unclear?*",
            "es":"Lo dejo en una frase: el canal publica una recomendación → tú actúas → rastrear el resultado. *¿Qué paso no está claro?*",
            "hr":"Stavljam u jednu rečenicu: kanal objavljuje preporuku → ti djeluješ → pratiš rezultat. *Koji korak nije jasan?*",
            "lt":"Vienu sakiniu: kanalas paskelbia rekomendaciją → tu veiksni → seki rezultatą. *Kuris žingsnis neaiškus?*",
            "lv":"Vienā teikumā: kanāls publicē ieteikumu → tu rīkojies → seko rezultātam. *Kurš solis nav skaidrs?*",
        },
        "not_urgent":{
            "en":"No rush — just know the gap closes when the market corrects. *Usually within hours.* When are you planning to look?",
            "es":"Sin prisa — solo ten en cuenta que el gap se cierra cuando el mercado corrige. *Normalmente en horas.* ¿Cuándo planeas mirar?",
            "hr":"Nema žurbe — samo znaj da se jaz zatvara kad se tržište ispravi. *Obično u satima.* Kad planiraš pogledati?",
            "lt":"Neskubėk — tik žinok kad tarpas užsidaro kai rinka pasikoreguoja. *Paprastai per valandas.* Kada planuoji pažiūrėti?",
            "lv":"Nav steiga — tikai zini ka tarpas aizveras kad tirgus koriģē. *Parasti stundu laikā.* Kad plāno paskatīties?",
        },
        "already_elsewhere":{
            "en":"That's useful — multiple accounts means access to more signals and more bonus opportunities. *What platform are you currently on?*",
            "es":"Es útil — múltiples cuentas significa acceso a más señales y más oportunidades de bonos. *¿En qué plataforma estás actualmente?*",
            "hr":"To je korisno — više računa znači pristup više signala i više bonus mogućnosti. *Na kojoj platformi si trenutno?*",
            "lt":"Tai naudinga — kelios sąskaitos reiškia prieigą prie daugiau signalų ir bonusų galimybių. *Kokioje platformoje esi dabar?*",
            "lv":"Tas ir noderīgi — vairāki konti nozīmē piekļuvi vairāk signāliem un bonusu iespējām. *Kurā platformā esi pašlaik?*",
        },
        "thinking":{
            "en":"Take your time. *What's the one thing you're still not sure about?* Sometimes it's smaller than people think.",
            "es":"Tómate tu tiempo. *¿Cuál es la única cosa de la que aún no estás seguro?* A veces es más pequeña de lo que la gente piensa.",
            "hr":"Uzmi si vremena. *Što je ta jedina stvar o kojoj još nisi siguran?* Ponekad je manja nego što ljudi misle.",
            "lt":"Imk savo laiką. *Kas yra tas vienas dalykas kuriuo dar neesi tikras?* Kartais jis mažesnis nei žmonės galvoja.",
            "lv":"Ņem savu laiku. *Kas ir tas viens lieta par ko vēl neesi pārliecināts?* Dažreiz tas ir mazāks nekā cilvēki domā.",
        },
        "unknown":{
            "en":"What's the one thing that would make the first step feel obvious? *Honest question — I want to actually help.*",
            "es":"¿Cuál es la única cosa que haría que el primer paso pareciera obvio? *Pregunta honesta — quiero ayudar de verdad.*",
            "hr":"Što je ta jedna stvar koja bi učinila da prvi korak izgleda očito? *Iskreno pitanje — zaista želim pomoći.*",
            "lt":"Kas yra tas vienas dalykas dėl kurio pirmas žingsnis atrodytų akivaizdžiai? *Sąžiningas klausimas — tikrai noriu padėti.*",
            "lv":"Kas ir tas viens lietas kas liktu pirmajam solim izskatīties acīmredzamam? *Godīgs jautājums — gribu tiešām palīdzēt.*",
        },
    },
    "step3":{
        "en":"Someone in a similar spot last week — same hesitation — finally moved. *What they told me after: 'I overthought it.'* What's still holding you back?",
        "es":"Alguien en una situación similar la semana pasada — la misma duda — finalmente se movió. *Lo que me dijeron después: 'Le di demasiadas vueltas.'* ¿Qué te sigue frenando?",
        "hr":"Netko u sličnoj situaciji prošlog tjedna — ista oklijevanje — konačno se pomaknuo. *Što su mi rekli nakon: 'Previše sam razmišljao.'* Što te još drži?",
        "lt":"Kažkas panašioje situacijoje praeitą savaitę — tas pats svyravimas — galiausiai pajudėjo. *Ką jie man pasakė po: 'Per daug galvojau.'* Kas dar tave laiko?",
        "lv":"Kāds līdzīgā situācijā pagājušajā nedēļā — tāda pati vilcināšanās — beidzot pārvietojās. *Ko viņi man teica pēc: 'Es par daudz pārdomāju.'* Kas tev joprojām kavē?",
    },
    "step4":{
        "en":"Last thing I'll say without you reaching out first — the conditions that are open right now *close by end of week*. I'll still be here after, but it'll look different. Your call. 🎯",
        "es":"Lo último que digo sin que tú contactes primero — las condiciones abiertas ahora *se cierran antes del fin de semana*. Seguiré aquí después, pero será diferente. Tú decides. 🎯",
        "hr":"Zadnje što govorim bez da ti kontaktiraš — uvjeti otvoreni sada *zatvaraju se do kraja tjedna*. Bit ću ovdje i poslije, ali bit će drugačije. Tvoj izbor. 🎯",
        "lt":"Paskutinis dalykas kurį sakau be tavo iniciatyvos — sąlygos atidarytos dabar *užsidaro iki savaitės pabaigos*. Vis dar būsiu čia po to, bet bus kitaip. Tavo pasirinkimas. 🎯",
        "lv":"Pēdējā lieta ko saku bez tavas iniciatīvas — nosacījumi atvērti tagad *aizveras līdz nedēļas beigām*. Joprojām būšu šeit pēc tam, bet būs citādāk. Tavs lēmums. 🎯",
    },
    "step5":{
        "en":{"betting":"Different angle — *have you been watching any of the signals just to see how they play out?* Even without acting, the pattern becomes obvious quickly.","casino":"New offer just landed with *×6 wagering* — cleanest terms this month. Thought of you.","nodeposit":"Something dropped — *no deposit, ×8 wagering, expires Sunday*. Cleanest in weeks.","exclusive":"*4 value gaps this week*, each closed within 2 hours. Pattern is consistent. Still watching?"},
        "es":{"betting":"Ángulo diferente — *¿has seguido alguna señal solo para ver cómo se desarrolla?* Incluso sin actuar, el patrón se vuelve obvio rápido.","casino":"Nueva oferta con *×6 wagering* — los mejores términos de este mes. Me acordé de ti.","nodeposit":"Algo cayó — *sin depósito, ×8 wagering, vence el domingo*. Los mejores en semanas.","exclusive":"*4 gaps de valor esta semana*, cada uno cerrado en 2 horas. El patrón es consistente. ¿Sigues mirando?"},
        "hr":{"betting":"Drugačiji kut — *pratiš li neke signale samo da vidiš kako se razvijaju?* Čak i bez djelovanja, obrazac brzo postaje očit.","casino":"Nova ponuda s *×6 wageringom* — najčišći uvjeti ovog mjeseca. Sjetio sam se tebe.","nodeposit":"Nešto palo — *bez depozita, ×8 wagering, ističe u nedjelju*. Najčišći u tjednima.","exclusive":"*4 value gapa ovog tjedna*, svaki zatvoren unutar 2 sata. Obrazac je konzistentan. Još gledaš?"},
        "lt":{"betting":"Kitoks kampas — *ar seki kokius nors signalus tiesiog stebėti kaip jie atsiskleidžia?* Net neveikiant modelis greitai tampa akivaizdus.","casino":"Naujas pasiūlymas su *×6 wagering* — geriausios sąlygos šį mėnesį. Pagalvojau apie tave.","nodeposit":"Kažkas nukrito — *be depozito, ×8 wagering, baigiasi sekmadienį*. Geriausias savaitėmis.","exclusive":"*4 value tarpai šią savaitę*, kiekvienas užsidarė per 2 valandas. Modelis nuoseklus. Vis dar stebi?"},
        "lv":{"betting":"Cits leņķis — *vai seko kādiem signāliem tikai lai redzētu kā tie attīstās?* Pat nerīkojoties modelis kļūst acīmredzams ātri.","casino":"Jauns piedāvājums ar *×6 wagering* — tīrākie nosacījumi šomēnes. Padomāju par tevi.","nodeposit":"Kaut kas nokrita — *bez depozīta, ×8 wagering, beidzas svētdienā*. Tīrākie nedēļās.","exclusive":"*4 value tarpi šonedēļ*, katrs aizvērās 2 stundu laikā. Modelis konsekvents. Vēl skaties?"},
    },
    "step6":{
        "en":"Before I shift to just sharing market updates — *is there anything I could say or show that would make the first step feel obvious?* Genuine question.",
        "es":"Antes de pasar solo a compartir actualizaciones del mercado — *¿hay algo que pudiera decir o mostrar que haría que el primer paso pareciera obvio?* Pregunta genuina.",
        "hr":"Prije nego prijeđem samo na dijeljenje tržišnih ažuriranja — *ima li nešto što bih mogao reći ili pokazati što bi učinilo da prvi korak izgleda očit?* Iskreno pitanje.",
        "lt":"Prieš pereidamas prie tik rinkos atnaujinimų — *ar yra kažkas ką galėčiau pasakyti ar parodyti kas priverstų pirmą žingsnį atrodyti akivaizdžiai?* Nuoširdus klausimas.",
        "lv":"Pirms pāriešu tikai uz tirgus atjauninājumu dalīšanos — *vai ir kaut kas ko varētu teikt vai parādīt kas liktu pirmajam solim izskatīties acīmredzamam?* Patiess jautājums.",
    },
    "celebration":{
        "en":{"betting":"That's the move. 🎯 *Size bets at 1–3% of bankroll per bet* — the edge compounds over time, not in one hit. What's your bankroll sitting at?","casino":"Let's go. 💎 *Check your wagering progress tracker* in your account — low volatility slots clear fastest. Which platform did you go with?","nodeposit":"Perfect entry. 🎁 *Play lowest volatility slots* — they clear wagering most efficiently. How much did you get in the bonus?","exclusive":"Both sides activated. 🔥 *Start with betting signals* — lower variance edge. What's your first signal from the channel?"},
        "es":{"betting":"Ese es el movimiento. 🎯 *Apuesta 1–3% del bankroll por apuesta* — el edge se compone con el tiempo. ¿Cuánto tienes en el bankroll?","casino":"Vamos. 💎 *Revisa el tracker de progreso de wagering* — los slots de baja volatilidad liberan más rápido. ¿Con qué plataforma fuiste?","nodeposit":"Entrada perfecta. 🎁 *Juega slots de menor volatilidad* — liberan el wagering más eficientemente. ¿Cuánto obtuviste en el bono?","exclusive":"Ambos lados activados. 🔥 *Empieza con las señales de apuestas* — menor varianza. ¿Cuál es tu primera señal del canal?"},
        "hr":{"betting":"To je potez. 🎯 *Kladi 1–3% bankrolla po okladi* — edge se komponira s vremenom. Koliko ti bankroll iznosi?","casino":"Idemo. 💎 *Provjeri tracker napretka wageringa* — slotovi niske volatilnosti najbrže oslobađaju. Koju platformu si odabrao?","nodeposit":"Savršen ulaz. 🎁 *Igraj slotove najniže volatilnosti* — najučinkovitije oslobađaju wagering. Koliko si dobio u bonusu?","exclusive":"Obje strane aktivirane. 🔥 *Počni sa signalima klađenja* — niža varijanca. Koji je tvoj prvi signal iz kanala?"},
        "lt":{"betting":"Tai judėjimas. 🎯 *Statyk 1–3% bankolio vienam betui* — pranašumas kaupiasi laikui bėgant. Koks tavo bankolis?","casino":"Eime. 💎 *Patikrink wagering pažangos stebyklą* — mažo nepastovumo slotai greičiausiai išvalo. Kokią platformą pasirinkote?","nodeposit":"Puikus įėjimas. 🎁 *Žaisk mažiausio nepastovumo slotus* — efektyviausiai išvalo wagering. Kiek gavai bonuse?","exclusive":"Abi pusės aktyvuotos. 🔥 *Pradėk nuo lažybų signalų* — mažesnė dispersija. Koks tavo pirmas signalas iš kanalo?"},
        "lv":{"betting":"Tas ir gājiens. 🎯 *Liec 1–3% bankrola par likmi* — priekšrocība uzkrājas laika gaitā. Cik liels tavs bankrols?","casino":"Ejam. 💎 *Pārbaudi wagering progresa izsekotāju* — zemas nepastāvības sloti ātrāk notīra. Kuru platformu izvēlējies?","nodeposit":"Nevainojama ieeja. 🎁 *Spēlē zemākās nepastāvības slotus* — visefektīvāk notīra wagering. Cik saņēmi bonusā?","exclusive":"Abas puses aktivizētas. 🔥 *Sāc ar likmju signāliem* — zemāka dispersija. Kāds ir tavs pirmais signāls no kanāla?"},
    },
    "repeat":{
        "r1h":{"en":"How's the first session? *Don't close out early if in profit* — wagering clears faster when you're not chasing.","es":"¿Cómo va la primera sesión? *No cierres pronto si estás en positivo* — el wagering se libera más rápido cuando no persigues.","hr":"Kako ide prva sesija? *Ne zatvaraj rano ako si u plusu* — wagering se oslobađa brže kad ne juriš.","lt":"Kaip pirmoji sesija? *Neuždaryk anksti jei esi pliuse* — wagering išvalomas greičiau kai nesivyji.","lv":"Kā iet pirmā sesija? *Neaizver agri ja esi plusā* — wagering notīrās ātrāk kad nevajā."},
        "r6h":{"en":"Next move: *check your promotions tab* — reload bonus often appears in the first 24–48h. Usually a match offer. Found anything?","es":"Siguiente movimiento: *revisa tu pestaña de promociones* — el bono de recarga suele aparecer en las primeras 24–48h. ¿Encontraste algo?","hr":"Sljedeći potez: *provjeri karticu promocija* — reload bonus često se pojavljuje u prvih 24–48h. Pronašao si nešto?","lt":"Kitas žingsnis: *patikrink akcijų skirtuką* — reload bonusas dažnai atsiranda per pirmąsias 24–48 val. Radai ką nors?","lv":"Nākamais gājiens: *pārbaudi akciju cilni* — reload bonuss bieži parādās pirmajās 24–48h. Atradi kaut ko?"},
        "r24h":{"en":"How did it land? *First result doesn't define the edge* — the pattern over 20+ bets does. What was the outcome?","es":"¿Cómo fue? *El primer resultado no define el edge* — el patrón en 20+ apuestas sí. ¿Cuál fue el resultado?","hr":"Kako je palo? *Prvi rezultat ne definira edge* — obrazac u 20+ oklada da. Kakav je bio ishod?","lt":"Kaip sekėsi? *Pirmas rezultatas neapibrėžia pranašumo* — modelis per 20+ statymų apibrėžia. Koks buvo rezultatas?","lv":"Kā nokrita? *Pirmais rezultāts nenosaka priekšrocību* — modelis 20+ likmēs nosaka. Kāds bija rezultāts?"},
        "r3d":{"en":"Ready for round two? *The second deposit bonus is usually the best value* — platforms are most generous before they know your pattern. What's your reload situation?","es":"¿Listo para la ronda dos? *El bono del segundo depósito suele ser el mejor valor* — las plataformas son más generosas antes de conocer tu patrón. ¿Cuál es tu situación de recarga?","hr":"Spreman za rundu dva? *Bonus za drugi depozit je obično najbolja vrijednost* — platforme su najdarežljivije prije nego znaju tvoj obrazac. Kakva je tvoja situacija s nadopunom?","lt":"Pasiruošęs antrajam ratui? *Antrojo depozito bonusas paprastai geriausias* — platformos dosnesnės kol nežino tavo modelio. Kokia tavo reload situacija?","lv":"Gatavs otrajai kārtai? *Otrā depozīta bonuss parasti ir labākā vērtība* — platformas щedras pirms zina tavu modeli. Kāda ir tava reload situācija?"},
        "r7d":{"en":"Week in — you have real data now. *What's your P&L looking like?* I can help optimize the next move based on what's actually working.","es":"Una semana — tienes datos reales ahora. *¿Cómo está tu P&L?* Puedo ayudar a optimizar el siguiente movimiento basándome en lo que realmente funciona.","hr":"Tjedan unutra — imaš prave podatke sada. *Kako izgleda tvoj P&L?* Mogu pomoći optimizirati sljedeći potez na osnovu onoga što zaista funkcionira.","lt":"Savaitė viduje — dabar turi realius duomenis. *Kaip atrodo tavo P&L?* Galiu padėti optimizuoti kitą žingsnį pagal tai kas tikrai veikia.","lv":"Nedēļa iekšā — tagad tev ir reāli dati. *Kā izskatās tavs P&L?* Varu palīdzēt optimizēt nākamo gājienu balstoties uz to kas tiešām darbojas."},
    },
}

def _fb(key, lang, interest=None, barrier=None):
    d = _FB.get(key,{})
    if key == "step1":
        return d.get(lang,d.get("en",{})).get(interest,"")
    if key == "barrier":
        bd = d.get(barrier,"unknown"); return bd.get(lang,bd.get("en",""))
    if key == "step5":
        return d.get(lang,d.get("en",{})).get(interest,"")
    if key == "celebration":
        return d.get(lang,d.get("en",{})).get(interest,"")
    if key == "repeat":
        rd = d.get(barrier or "r1h",{}); return rd.get(lang,rd.get("en",""))
    return d.get(lang,d.get("en",""))

# ── Step generators ───────────────────────────────────────────────────────────
async def generate_step1(lang,interest,psychotype,user_profile,history,objections) -> str:
    extra="STEP 1: Break down HOW the channel benefits them. Real math. End with ONE personal question."
    return await _generate(_base_system(lang,interest,psychotype,user_profile,objections,extra,history=history),history=history) or _fb("step1",lang,interest)

async def generate_step2(lang,interest,psychotype,user_profile,history,objections,barrier) -> str:
    extra=f"STEP 2: Address barrier '{barrier}'. Meet them where they are. No high pressure."
    return await _generate(_base_system(lang,interest,psychotype,user_profile,objections,extra,history=history),history=history) or _fb("barrier",lang,interest,barrier)

async def generate_step3(lang,interest,psychotype,user_profile,history,objections,barrier) -> str:
    extra=f"STEP 3: Social proof for barrier '{barrier}'. Specific relatable story. End with question."
    return await _generate(_base_system(lang,interest,psychotype,user_profile,objections,extra,history=history),history=history) or _fb("step3",lang)

async def generate_step4(lang,interest,psychotype,user_profile,history,objections,barrier) -> str:
    extra="STEP 4: Final push. Specific deadline. Respectful. Leave door open."
    return await _generate(_base_system(lang,interest,psychotype,user_profile,objections,extra,history=history),history=history) or _fb("step4",lang)

async def generate_step5(lang,interest,psychotype,user_profile,history,objections,barrier) -> str:
    extra="STEP 5: Fresh angle, 24h later. Don't repeat previous arguments. New hook."
    return await _generate(_base_system(lang,interest,psychotype,user_profile,objections,extra,history=history),history=history) or _fb("step5",lang,interest)

async def generate_step6(lang,interest,psychotype,user_profile,history,objections,barrier) -> str:
    extra="STEP 6: Before switching to maintenance mode. Ask what would make first step feel obvious."
    return await _generate(_base_system(lang,interest,psychotype,user_profile,objections,extra,history=history),history=history) or _fb("step6",lang)

async def generate_ftd_celebration(lang,interest,psychotype,user_profile,history) -> str:
    extra="FTD CELEBRATION: 1 sentence celebration, then immediately pivot to concrete next step. Ask about their specific situation."
    return await _generate(_base_system(lang,interest,psychotype,user_profile,{},extra,history=history),history=history) or _fb("celebration",lang,interest)

async def generate_repeat_push(step,lang,interest,psychotype,user_profile,history,ftd_count) -> str:
    extra=f"REPEAT FTD step={step}, ftd_count={ftd_count}. Practical advice for active user. Ask about real results."
    return await _generate(_base_system(lang,interest,psychotype,user_profile,{},extra,history=history),history=history) or _fb("repeat",lang,interest,step)

# ── Helpers ───────────────────────────────────────────────────────────────────
def _user_active_since(user_id,since_ts):
    user=get_user(user_id); last_str=user.get("last_active","")
    if not last_str: return False
    try:
        la=datetime.fromisoformat(last_str)
        if la.tzinfo is None: la=la.replace(tzinfo=timezone.utc)
        return la.timestamp()>since_ts
    except Exception: return False

def _user_ftd_done(user_id): return bool(get_user(user_id).get("ftd_done"))
def _get_ftd_count(user_id): return get_user(user_id).get("ftd_count",0)

async def _get_ctx(user_id):
    return get_profile(user_id),get_ai_history(user_id),get_psychotype(user_id),get_objections(user_id)

async def _send(context,user_id,chat_id,text) -> bool:
    if not text: return False
    try:
        await context.bot.send_chat_action(chat_id=chat_id,action="typing")
        await asyncio.sleep(2.0)
        await context.bot.send_message(chat_id=chat_id,text=text,parse_mode=ParseMode.MARKDOWN)
        add_ai_message(user_id,"assistant",text); mark_push_sent(user_id); return True
    except TelegramError as e: logger.warning(f"Onboarding send [{user_id}]: {e}"); return False

# ── Job functions ─────────────────────────────────────────────────────────────
async def onboarding_step1_job(context):
    d=context.job.data; user_id,chat_id=d["user_id"],d["chat_id"]
    lang,interest=d["lang"],d["interest"]
    if _user_ftd_done(user_id): return
    # Если пользователь уже написал сам — _handle_ai_chat ведёт диалог, job не нужен
    if get_user(user_id).get("ai_msg_count", 0) > 0: return
    profile,history,psychotype,objections=await _get_ctx(user_id)
    text=await generate_step1(lang,interest,psychotype,profile,history,objections)
    await _send(context,user_id,chat_id,text); logger.info(f"ob1 → {user_id}")

async def onboarding_barrier_classify_job(context):
    d=context.job.data; user_id=d["user_id"]
    if _user_ftd_done(user_id): return
    profile,history,psychotype,objections=await _get_ctx(user_id)
    barrier=await classify_barrier(history,d["lang"],d["interest"],psychotype)
    update_user(user_id,onboarding_barrier=barrier); logger.info(f"barrier → {user_id}: {barrier}")

async def onboarding_step2_job(context):
    d=context.job.data; user_id,chat_id=d["user_id"],d["chat_id"]
    lang,interest,start_ts=d["lang"],d["interest"],d["start_ts"]
    if _user_ftd_done(user_id): return
    if _user_active_since(user_id,start_ts+20*60): logger.info(f"ob2 skip active {user_id}"); return
    # Если через диалог уже идёт онбординг (3+ сообщений) — job не нужен
    if get_user(user_id).get("ai_msg_count", 0) >= 3: return
    profile,history,psychotype,objections=await _get_ctx(user_id)
    barrier=get_user(user_id).get("onboarding_barrier","unknown")
    text=await generate_step2(lang,interest,psychotype,profile,history,objections,barrier)
    await _send(context,user_id,chat_id,text); logger.info(f"ob2 [{barrier}] → {user_id}")

async def onboarding_step3_job(context):
    d=context.job.data; user_id,chat_id=d["user_id"],d["chat_id"]
    lang,interest,start_ts=d["lang"],d["interest"],d["start_ts"]
    if _user_ftd_done(user_id): return
    if _user_active_since(user_id,start_ts+50*60): return
    profile,history,psychotype,objections=await _get_ctx(user_id)
    barrier=get_user(user_id).get("onboarding_barrier","unknown")
    text=await generate_step3(lang,interest,psychotype,profile,history,objections,barrier)
    await _send(context,user_id,chat_id,text); logger.info(f"ob3 [{barrier}] → {user_id}")

async def onboarding_step4_job(context):
    d=context.job.data; user_id,chat_id=d["user_id"],d["chat_id"]
    lang,interest,start_ts=d["lang"],d["interest"],d["start_ts"]
    if _user_ftd_done(user_id): return
    if _user_active_since(user_id,start_ts+90*60): return
    profile,history,psychotype,objections=await _get_ctx(user_id)
    barrier=get_user(user_id).get("onboarding_barrier","unknown")
    text=await generate_step4(lang,interest,psychotype,profile,history,objections,barrier)
    await _send(context,user_id,chat_id,text); logger.info(f"ob4 [{barrier}] → {user_id}")

async def onboarding_step5_job(context):
    d=context.job.data; user_id,chat_id=d["user_id"],d["chat_id"]
    lang,interest,start_ts=d["lang"],d["interest"],d["start_ts"]
    if _user_ftd_done(user_id): return
    if _user_active_since(user_id,start_ts+5*3600): return
    profile,history,psychotype,objections=await _get_ctx(user_id)
    barrier=await classify_barrier(history,lang,interest,psychotype)
    update_user(user_id,onboarding_barrier=barrier)
    text=await generate_step5(lang,interest,psychotype,profile,history,objections,barrier)
    await _send(context,user_id,chat_id,text); logger.info(f"ob5 [{barrier}] → {user_id}")

async def onboarding_step6_job(context):
    d=context.job.data; user_id,chat_id=d["user_id"],d["chat_id"]
    lang,interest,start_ts=d["lang"],d["interest"],d["start_ts"]
    if _user_ftd_done(user_id): return
    if _user_active_since(user_id,start_ts+22*3600): return
    profile,history,psychotype,objections=await _get_ctx(user_id)
    barrier=get_user(user_id).get("onboarding_barrier","unknown")
    text=await generate_step6(lang,interest,psychotype,profile,history,objections,barrier)
    await _send(context,user_id,chat_id,text); logger.info(f"ob6 [{barrier}] → {user_id}")

async def ftd_celebration_job(context):
    d=context.job.data; user_id,chat_id=d["user_id"],d["chat_id"]
    lang,interest=d["lang"],d["interest"]
    profile,history,psychotype,_=await _get_ctx(user_id)
    text=await generate_ftd_celebration(lang,interest,psychotype,profile,history)
    await _send(context,user_id,chat_id,text); logger.info(f"celebration → {user_id}")

async def repeat_push_job(context):
    d=context.job.data; user_id,chat_id=d["user_id"],d["chat_id"]
    lang,interest,step=d["lang"],d["interest"],d["step"]
    profile,history,psychotype,_=await _get_ctx(user_id)
    text=await generate_repeat_push(step,lang,interest,psychotype,profile,history,_get_ftd_count(user_id))
    await _send(context,user_id,chat_id,text); logger.info(f"repeat [{step}] → {user_id}")

# ── PUBLIC API ────────────────────────────────────────────────────────────────
def schedule_onboarding(job_queue,user_id,chat_id,lang,interest) -> None:
    start_ts=datetime.now(timezone.utc).timestamp()
    base={"user_id":user_id,"chat_id":chat_id,"lang":lang,"interest":interest,"start_ts":start_ts}
    job_queue.run_once(onboarding_step1_job,            when=90,      data=base,name=f"ob1_{user_id}")
    job_queue.run_once(onboarding_barrier_classify_job, when=15*60,   data=base,name=f"obc_{user_id}")
    job_queue.run_once(onboarding_step2_job,            when=30*60,   data=base,name=f"ob2_{user_id}")
    job_queue.run_once(onboarding_step3_job,            when=2*3600,  data=base,name=f"ob3_{user_id}")
    job_queue.run_once(onboarding_step4_job,            when=6*3600,  data=base,name=f"ob4_{user_id}")
    job_queue.run_once(onboarding_step5_job,            when=24*3600, data=base,name=f"ob5_{user_id}")
    job_queue.run_once(onboarding_step6_job,            when=48*3600, data=base,name=f"ob6_{user_id}")
    logger.info(f"Adaptive onboarding scheduled → {user_id} [{lang}/{interest}]")

def schedule_ftd_flow(job_queue,user_id,chat_id,lang,interest) -> None:
    base={"user_id":user_id,"chat_id":chat_id,"lang":lang,"interest":interest}
    job_queue.run_once(ftd_celebration_job,when=5,data=base,name=f"cel_{user_id}")
    for step,delay in [("r1h",3600),("r6h",6*3600),("r24h",24*3600),("r3d",3*86400),("r7d",7*86400)]:
        job_queue.run_once(repeat_push_job,when=delay,data={**base,"step":step},name=f"rpt_{step}_{user_id}")
    logger.info(f"FTD repeat flow scheduled → {user_id}")
