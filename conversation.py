"""
conversation.py — OddsVault Bot v14.1

ИЗМЕНЕНИЯ:
  - get_silence_push(lang, ftd_done, barrier) — CRO #3: barrier-aware тексты
  - get_post_sub_opener(lang, interest, ab_variant) — CRO #4: A/B на post-sub
  - ask_valeria_conversational поддерживает funnel_stage="subscribed_waiting"
    для maintenance mode (12+ сообщений без FTD)
"""

import asyncio
import logging
import random
import re
from typing import Optional

from ai_agent import (
    _post_with_retry, _build_profile_ctx, _build_obj_summary,
    ANTHROPIC_URL, MODEL, ANTHROPIC_KEY,
    _sanitize_history, _fallback_response,
    _safe_web_search, _clean_for_telegram, _strip_thinking,
)
from conversation_analyzer import build_conversation_context

logger = logging.getLogger(__name__)

# ════════════════════════════════════════════════════════════════════════════
#  ДЕТЕКТОР INTEREST ИЗ СВОБОДНОГО ТЕКСТА
# ════════════════════════════════════════════════════════════════════════════

_INTEREST_SIGNALS: dict[str, list[str]] = {
    "betting": [
        "bet", "odds", "match", "football", "soccer", "sport", "league",
        "stake", "tipster", "prediction", "apuesta", "cuota", "partido",
        "klađenje", "kvota", "utakmica", "lažybos", "koeficient", "likmes",
        "la liga", "premier", "champions", "bundesliga", "serie a",
        "ставки", "коэффициент", "матч",
    ],
    "casino": [
        "casino", "slot", "roulette", "blackjack", "spin", "bonus",
        "wagering", "cashback", "live", "table", "kazino", "bonusas",
        "spēle", "slotovi", "bonos", "ruleta",
    ],
    "nodeposit": [
        "free", "no deposit", "without deposit", "sin depósito",
        "bez depozita", "be depozito", "bez depozīta", "freebie",
        "gratis", "nemokamas", "bezmaksas", "besplatno",
    ],
    "exclusive": [
        "arbitrage", "arb", "value", "edge", "ev", "sharp", "both",
        "all", "everything", "combined", "mix", "arbitražas",
        "всё", "комбо",
    ],
}

def detect_interest_from_text(text: str) -> Optional[str]:
    lower = text.lower()
    scores: dict[str, int] = {i: 0 for i in _INTEREST_SIGNALS}
    for interest, signals in _INTEREST_SIGNALS.items():
        for s in signals:
            if s in lower:
                scores[interest] += 1
    best = max(scores, key=lambda k: scores[k])
    return best if scores[best] > 0 else None


# ════════════════════════════════════════════════════════════════════════════
#  ДЕТЕКТОР GEO ИЗ СВОБОДНОГО ТЕКСТА
# ════════════════════════════════════════════════════════════════════════════

_GEO_SIGNALS: dict[str, list[str]] = {
    "ES": [
        "spain", "españa", "espana", "spanish", "español", "madrid",
        "barcelona", "sevilla", "valencia", "bilbao", "la liga",
        "primera division", "atletico",
    ],
    "HR": [
        "croatia", "hrvatska", "croatian", "zagreb", "split",
        "dubrovnik", "rijeka", "hnl", "dinamo", "hajduk",
    ],
    "RS": [
        "serbia", "srbija", "serbian", "belgrade", "beograd",
        "novi sad", "bosnia", "balkan", "makedoni", "crna gora",
        "slovenija", "slovenia",
    ],
    "LT": [
        "lithuania", "lietuva", "lithuanian", "vilnius", "kaunas",
        "klaipeda", "a lyga",
    ],
    "LV": [
        "latvia", "latvija", "latvian", "riga", "daugavpils",
        "virsliga",
    ],
}

def detect_geo_from_text(text: str) -> Optional[str]:
    lower = text.lower()
    for geo, signals in _GEO_SIGNALS.items():
        if any(s in lower for s in signals):
            return geo
    return None


# ════════════════════════════════════════════════════════════════════════════
#  ГЛАВНАЯ ФУНКЦИЯ ДИАЛОГА
# ════════════════════════════════════════════════════════════════════════════

async def ask_valeria_conversational(
    user_message: str,
    history: list,
    lang: str,
    interest: Optional[str],
    geo: Optional[str],
    funnel_stage: str,
    psychotype: str = "neutral",
    user_profile: Optional[dict] = None,
    objections: Optional[dict] = None,
    ftd_done: bool = False,
    ftd_count: int = 0,
    search_context: Optional[str] = None,
    current_angle: int = 0,
) -> dict:
    """
    funnel_stage:
      "discovery"          — до подписки
      "warming"            — warming с известным interest
      "subscribed"         — после подписки, pre-FTD активный диалог
      "subscribed_waiting" — maintenance mode: 12+ сообщений без FTD
    """
    user_profile = user_profile or {}
    objections   = objections or {}

    if not ANTHROPIC_KEY:
        return {
            "text":              _fallback_response(lang, interest or "betting", funnel_stage),
            "detected_interest": None,
            "detected_geo":      None,
            "next_stage":        None,
            "move_to_tease":     False,
            "move_to_cta":       False,
        }

    detected_interest = detect_interest_from_text(user_message) if not interest else None
    detected_geo      = detect_geo_from_text(user_message) if not geo or geo == "OTHER" else None

    effective_interest = interest or detected_interest or "betting"
    effective_geo      = detected_geo or geo or "OTHER"

    lang_names = {
        "en": "English — casual, direct",
        "es": "Spanish (Spain, casual tú)",
        "hr": "Croatian — warm, direct",
        "lt": "Lithuanian — warm, direct",
        "lv": "Latvian — warm, direct",
    }
    language = lang_names.get(lang, "English — casual, direct")

    interest_ctx = {
        "betting":   "sports betting, value bets, odds movements, line analysis",
        "casino":    "casino bonuses, wagering math, RTP, cashback",
        "nodeposit": "no-deposit bonuses, free spins, zero-risk entry",
        "exclusive": "arbitrage, value bets, bonus EV, combined strategy",
    }.get(effective_interest, "betting & bonuses")

    psychotype_instr = {
        "cynic":   "CYNIC: One verifiable fact only. No pitch.",
        "skeptic": "SKEPTIC: Specific numbers, social proof.",
        "passive": "PASSIVE: One tiny step. Dead simple.",
        "curious": "CURIOUS: Real depth. Pull toward action.",
        "neutral": "NEUTRAL: Hook → gap → next step.",
    }.get(psychotype, "NEUTRAL: Hook → gap → next step.")

    search_section = ""
    if search_context:
        search_section = f"\nReal market data (use naturally, never cite source):\n{search_context}"
    else:
        search_section = (
            "\nNo real-time data available."
            "\nSTRICTLY FORBIDDEN: inventing specific team names, scores, odds, or bonus codes."
            "\nBAD: 'Bayern opened -1.5 (-110), sharp money moved it to -2.5.'"
            "\nBAD: 'Liverpool -1.5 moved from +105 to -115 across 6 books.'"
            "\nGOOD: 'Sharp money hit a line this week — 15-min window before books caught up.'"
            "\nGeneral patterns and mechanisms only. Zero invented specifics."
        )

    # Контекст продукта из канала — только реальные данные
    from product_selector import build_product_context
    product_context = build_product_context(
        geo=effective_geo,
        interest=effective_interest,
        funnel_stage=funnel_stage,
        ftd_done=ftd_done,
    )

    # ── Conversation analysis (Belfort personalization) ───────────────────
    conversation_ctx = build_conversation_context(history)

    # ── Stage instructions ────────────────────────────────────────────────────

    if funnel_stage == "discovery":
        angle_hints = [
            "Ask how they found this (curiosity hook)",
            "Drop a specific number — 'Sharp money moved €2.3M before the line shifted. 15-minute window.'",
            "Binary choice — 'You more of a sports person or casino?'",
            "Pain angle — 'Most people here got burned going it alone first.'",
            "Final push — make the cost of NOT joining feel real, then tease",
        ]
        current_hint = angle_hints[min(current_angle, len(angle_hints) - 1)]

        stage_instr = f"""DISCOVERY — exchange #{current_angle + 1} with this user.

YOUR ONLY JOB: detect one signal, then move to tease. Not to chat. Not to be interesting. To convert.

CURRENT ANGLE (#{current_angle + 1}): {current_hint}
Use this angle now. Don't repeat angles already used (exchanges 1-{current_angle} are done).

━━━ SIGNAL DETECTION — ANY of these = move to tease on THIS message ━━━
• Named a sport, team, league, casino game, or bonus type
• Said they bet, play, gamble, or want to
• Asked how to start, join, deposit, or win anything
• Mentioned losing money, bad luck, or frustration with results
• Said "any", "all", "both", "everything", "I don't know" → treat as betting interest
• Gave a short/vague/nonsense answer → passive user, tease anyway
• Any positive reaction to anything you said

━━━ AFTER SIGNAL DETECTED ━━━
1. Give ONE insight that makes them feel the cost of not having access.
2. Tag [READY:tease] on the same message.
3. Stop. No follow-up question.

━━━ NO SIGNAL AFTER 4 EXCHANGES ━━━
Exchange 5+ → [READY:tease] regardless. No exceptions. No more questions.

━━━ HARD RULES ━━━
• Never use the same angle twice.
• Never ask about money, deposits, or bankroll before tease.
• Never give a full answer to "how" questions — partial only, rest is "in the channel".
• Short/vague/nonsense answer = passive user = tease faster, not slower."""

    elif funnel_stage == "warming":
        stage_instr = f"""WARMING — interest confirmed: {effective_interest}. Exchange #{current_angle + 1}.

MAXIMUM 2 exchanges here. Then [READY:tease]. No exceptions.

━━━ YOUR ONE JOB ━━━
Make them feel what they're missing. Create the gap. Then [READY:tease].

━━━ INSIGHT TO DROP (pick one) ━━━
• betting:   "Sharp money hits 15-45 min before public sees it. By the time it's on Twitter, line already moved."
• casino:    "Not all games count equally toward wagering. Wrong game = you clear 3x slower, bonus expires worthless."
• nodeposit: "Most aggregator sites are 2 weeks behind. Half the offers they list are already expired."
• exclusive: "Stacking a value bet signal with a reload bonus — that's where edge actually compounds."

━━━ PARTIAL ANSWER RULE ━━━
They ask HOW → give 20% → "the full picture is in the channel" → [READY:tease]

━━━ IMMEDIATE [READY:tease] ━━━
• Positive response to any insight
• They ask about access or next steps
• Exchange 2+ — mandatory, no exceptions
• Any short answer — move them"""

    elif funnel_stage == "subscribed_waiting":
        # Maintenance mode: давление снято, даём ценность
        stage_instr = f"""MAINTENANCE MODE — user has been chatting for a while without depositing.

GOAL: Keep them warm. Give real value. No pressure on deposit.

━━━ RULES ━━━
• MAX 3 sentences. Friendly and genuine.
• Answer their question like a knowledgeable friend.
• Mention the channel only if it directly answers their question.
• ZERO urgency language. ZERO "window closing" or deadlines.
• End with ONE low-pressure question about their situation or interest.

This is relationship maintenance, not sales."""

    else:  # subscribed — pre-FTD active
        if ftd_done:
            stage_instr = f"""SUBSCRIBED — {ftd_count} deposit(s) done.
Goals: keep active, optimize strategy, push toward repeat deposit.
Give real practical advice. Ask about actual results. Make next action obvious.
MAX 3 sentences."""
        else:
            stage_instr = """SUBSCRIBED — no deposit yet. Goal: FIRST DEPOSIT.

Every reply moves toward this. One step at a time.

━━━ RULES ━━━
• MAX 2 sentences. Hard limit. Never exceed.
• They ask HOW → answer 30% → "the signals cover the rest, check the channel."
• Make inaction feel expensive in one concrete sentence.
• Make the next action feel obvious and small."""

    system = f"""You are Valeria — private insider for betting signals and bonus math.
You're texting someone 1-on-1 on Telegram. Real conversation. Not a bot script.

LANGUAGE: {language} — write ONLY in this language, always.
INTEREST: {interest_ctx}
GEO: {effective_geo}
PSYCHOTYPE: {psychotype_instr}
{_build_obj_summary(objections)}
{_build_profile_ctx(user_profile)}
{search_section}
{f"══ CHANNEL & PRODUCT CONTEXT ══{chr(10)}{product_context}" if product_context else ""}

{conversation_ctx}

━━━ STAGE ━━━
{stage_instr}

━━━ FORMAT ━━━
• 2-3 short sentences max. Telegram, not email.
• *bold* exactly one key fact per message.
• Max 1 emoji. Zero if they use zero.

━━━ VOICE ━━━
• Insider sharing intel — not a salesperson.
• Dry and direct. Warmth ok. Hype forbidden.
• Never: "Great!", "Awesome!", "Interesting!", "Of course!"
• Never: reference being AI, a bot, or following a script.
• Never: promise profits or specific ROI.
• NEVER invent specific team names, odds, scores, or bonus codes.

━━━ HIDDEN TAGS (end of message only) ━━━
[READY:warming]  — signal detected
[READY:tease]    — gap created, show the channel
[INTEREST:xxx]   — betting / casino / nodeposit / exclusive
[GEO:xx]         — ES / HR / RS / LT / LV"""

    try:
        clean_history = _sanitize_history(history[-14:])
        messages = clean_history + [{"role": "user", "content": user_message}]

        data = await _post_with_retry(
            ANTHROPIC_URL,
            {"model": MODEL, "max_tokens": 350, "system": system, "messages": messages},
            {"x-api-key": ANTHROPIC_KEY, "anthropic-version": "2023-06-01",
             "content-type": "application/json"},
            timeout=25,
        )
        raw = next(
            (b["text"].strip() for b in data.get("content", []) if b.get("type") == "text"),
            "",
        )
    except Exception as e:
        logger.error(f"ask_valeria_conversational error: {e}")
        raw = ""

    if not raw:
        raw = _fallback_response(lang, effective_interest, funnel_stage)

    next_stage = tag_interest = tag_geo = None

    if m := re.search(r"\[READY:(\w+)\]", raw):
        next_stage = m.group(1)
    raw = re.sub(r"\[READY:\w+\]", "", raw).strip()

    if m := re.search(r"\[INTEREST:(\w+)\]", raw):
        tag_interest = m.group(1)
        if tag_interest not in ("betting", "casino", "nodeposit", "exclusive"):
            tag_interest = None
    raw = re.sub(r"\[INTEREST:\w+\]", "", raw).strip()

    if m := re.search(r"\[GEO:(\w+)\]", raw):
        tag_geo = m.group(1)
        if tag_geo not in ("ES", "HR", "RS", "LT", "LV"):
            tag_geo = None
    raw = re.sub(r"\[GEO:\w+\]", "", raw).strip()

    raw = _clean_for_telegram(_strip_thinking(raw))

    return {
        "text":              raw,
        "detected_interest": tag_interest or detected_interest,
        "detected_geo":      tag_geo or detected_geo,
        "next_stage":        next_stage,
        "move_to_tease":     next_stage == "tease",
        "move_to_cta":       False,
    }


# ════════════════════════════════════════════════════════════════════════════
#  POST-SUBSCRIPTION OPENER  (CRO #4 — A/B тест)
# ════════════════════════════════════════════════════════════════════════════

# A — вопрос об опыте (вовлекающий, для активных)
_POST_SUB_A: dict[str, dict[str, str]] = {
    "en": {
        "betting":   "Good. Now — *have you actually placed bets before*, or are you starting fresh? Makes a difference in where I'd point you first.",
        "casino":    "Good. Quick one — *what's your usual approach with bonuses?* Do you pick them based on size, wagering, or just what's available?",
        "nodeposit": "Good. *Have you cleared a no-deposit before?* Knowing your experience helps me point you to the right one first.",
        "exclusive": "Good. *Which side do you know better — the betting signals or the bonus math?* I'll start where it's most useful.",
    },
    "es": {
        "betting":   "Bien. Ahora — *¿has hecho apuestas antes*, o empiezas desde cero? Cambia mucho a dónde te apunto primero.",
        "casino":    "Bien. Rápido — *¿cuál es tu enfoque habitual con los bonos?* ¿Los eliges por tamaño, wagering, o lo que esté disponible?",
        "nodeposit": "Bien. *¿Has liberado un sin depósito antes?* Saber tu experiencia me ayuda a apuntarte al correcto primero.",
        "exclusive": "Bien. *¿Qué lado conoces mejor — las señales de apuestas o la matemática de bonos?* Empiezo por donde sea más útil.",
    },
    "hr": {
        "betting":   "Dobro. Sad — *jesi li ikad kladi prije*, ili počinješ ispočetka? Dosta mijenja gdje bih te prvo uputio.",
        "casino":    "Dobro. Kratko — *kakav je tvoj uobičajeni pristup bonusima?* Biraš ih po veličini, wageringu, ili što je dostupno?",
        "nodeposit": "Dobro. *Jesi li ikad oslobodio bez depozita?* Poznavanje tvog iskustva pomaže mi da te uputim na pravi prvi.",
        "exclusive": "Dobro. *Koju stranu bolje poznaješ — signale klađenja ili matematiku bonusa?* Počinjem tamo gdje je najkorisnije.",
    },
    "lt": {
        "betting":   "Gerai. Dabar — *ar esi statęs anksčiau*, ar pradedi nuo nulio? Labai keičia kur pirmiausia nukreipčiau.",
        "casino":    "Gerai. Greitai — *koks tavo įprastas požiūris į bonusus?* Renkiesi pagal dydį, wagering, ar kas yra prieinama?",
        "nodeposit": "Gerai. *Ar esi išvalius be depozito anksčiau?* Žinodama tavo patirtį galiu nukreipti į tinkamą pirmą.",
        "exclusive": "Gerai. *Kurią pusę geriau žinai — lažybų signalus ar bonusų matematiką?* Pradėsiu ten kur naudingiausia.",
    },
    "lv": {
        "betting":   "Labi. Tagad — *vai esi likis likmes iepriekš*, vai sāc no nulles? Mainās kur tevi vispirms norādītu.",
        "casino":    "Labi. Ātri — *kāda ir tava parastā pieeja bonusiem?* Izvēlies pēc lieluma, wagering, vai kas ir pieejams?",
        "nodeposit": "Labi. *Vai esi notīrījis bez depozīta iepriekš?* Zinot tavu pieredzi palīdz norādīt uz pareizo pirmo.",
        "exclusive": "Labi. *Kuru pusi zini labāk — likmju signālus vai bonusu matemātiku?* Sākšu tur kur noderīgāk.",
    },
}

# B — директивный первый шаг (убирает трение, для пассивных)
_POST_SUB_B: dict[str, dict[str, str]] = {
    "en": {
        "betting":   "*First thing:* open the channel and find the pinned post — it has the current signal format explained. Takes 2 minutes. What's your usual stake size when something looks good?",
        "casino":    "*First thing:* check the pinned post in the channel — it shows which bonuses have the best wagering terms right now. Do you already have an account on any of the platforms listed?",
        "nodeposit": "*First thing:* the pinned post in the channel has 2-3 active no-deposit offers with exact terms. Zero commitment, zero risk. Have you made an account on any of them before?",
        "exclusive": "*First thing:* the channel has a pinned breakdown of how signals and bonus stacking work together. Read that first — it'll make everything click. Which side interests you more right now?",
    },
    "es": {
        "betting":   "*Primero:* abre el canal y busca el mensaje fijado — explica el formato de señal actual. Toma 2 minutos. ¿Cuál es tu apuesta habitual cuando algo te parece bueno?",
        "casino":    "*Primero:* revisa el mensaje fijado en el canal — muestra qué bonos tienen los mejores términos de wagering ahora mismo. ¿Ya tienes cuenta en alguna de las plataformas listadas?",
        "nodeposit": "*Primero:* el mensaje fijado en el canal tiene 2-3 ofertas sin depósito activas con los términos exactos. Sin compromiso, sin riesgo. ¿Has creado cuenta en alguna antes?",
        "exclusive": "*Primero:* el canal tiene un desglose fijado de cómo funcionan juntos las señales y el stacking de bonos. Lee eso primero. ¿Qué lado te interesa más ahora?",
    },
    "hr": {
        "betting":   "*Prvo:* otvori kanal i pronađi pinanu poruku — objašnjava trenutni format signala. Traje 2 minute. Koliki ti je tipičan ulog kad nešto izgleda dobro?",
        "casino":    "*Prvo:* provjeri pinanu poruku u kanalu — pokazuje koji bonusi imaju najbolje uvjete wageringa sada. Imaš li već račun na nekoj od navedenih platformi?",
        "nodeposit": "*Prvo:* pinana poruka u kanalu ima 2-3 aktivne ponude bez depozita s točnim uvjetima. Bez obveze, bez rizika. Jesi li ikad stvorio račun na nekoj od njih?",
        "exclusive": "*Prvo:* kanal ima pinani pregled kako signali i bonus stacking funkcioniraju zajedno. Pročitaj to prvo. Koja te strana više zanima sada?",
    },
    "lt": {
        "betting":   "*Pirmas dalykas:* atidaro kanalą ir rask prisegtą žinutę — joje paaiškinta dabartinio signalo formatas. Užtrunka 2 minutes. Koks tavo įprastas statymas kai kažkas atrodo gerai?",
        "casino":    "*Pirmas dalykas:* patikrink prisegtą žinutę kanale — parodo kurie bonusai šiuo metu turi geriausias wagering sąlygas. Ar jau turi paskyrą kurioje nors iš išvardytų platformų?",
        "nodeposit": "*Pirmas dalykas:* prisegtoje kanalo žinutėje yra 2-3 aktyvūs be depozito pasiūlymai su tiksliais sąlygomis. Jokių įsipareigojimų, jokios rizikos. Ar anksčiau kūrei paskyrą kurioje nors iš jų?",
        "exclusive": "*Pirmas dalykas:* kanale yra prisegta apžvalga kaip signalai ir bonus stacking veikia kartu. Perskaityk tai pirmiausia. Kuri pusė tave labiau domina dabar?",
    },
    "lv": {
        "betting":   "*Pirmā lieta:* atver kanālu un atrodi piesaistīto ziņu — tajā izskaidrots pašreizējais signāla formāts. Aizņem 2 minūtes. Kāda ir tava parastā likme kad kaut kas izskatās labi?",
        "casino":    "*Pirmā lieta:* pārbaudi piesaistīto ziņu kanālā — tā parāda kuriem bonusiem šobrīd ir labākie wagering nosacījumi. Vai tev jau ir konts kādā no uzskaitītajām platformām?",
        "nodeposit": "*Pirmā lieta:* kanāla piesaistītajā ziņā ir 2-3 aktīvi bez depozīta piedāvājumi ar precīziem nosacījumiem. Nekādu saistību, nekāda riska. Vai iepriekš esi izveidojis kontu kādā no tām?",
        "exclusive": "*Pirmā lieta:* kanālā ir piesaistīts kopsavilkums kā signāli un bonusu stacking darbojas kopā. Izlasi to vispirms. Kura puse tevi vairāk interesē tagad?",
    },
}

# C — социальное доказательство (для скептиков)
_POST_SUB_C: dict[str, dict[str, str]] = {
    "en": {
        "betting":   "You're in with people who've been tracking this for a while. *Most start by watching the signals for a week* before acting — enough to see the pattern. Have you followed any tipster signals before?",
        "casino":    "You're in with people who treat bonus math seriously. *Most clear their first bonus in 2-3 sessions* when they use the right game selection. Have you played bonus rounds before?",
        "nodeposit": "You're in with people who know how to extract real value from free offers. *Most get their first cashout within a week.* Have you tried a no-deposit bonus before?",
        "exclusive": "You're in with people running both signals and bonuses as a system. *Most see the compounding effect after 3-4 weeks.* Which side are you more experienced with?",
    },
    "es": {
        "betting":   "Estás con gente que lleva un tiempo rastreando esto. *La mayoría empieza solo siguiendo las señales una semana* antes de actuar. ¿Has seguido señales de algún tipster antes?",
        "casino":    "Estás con gente que toma en serio la matemática de bonos. *La mayoría libera su primer bono en 2-3 sesiones* con la selección de juego correcta. ¿Has jugado rondas de bono antes?",
        "nodeposit": "Estás con gente que sabe extraer valor real de las ofertas gratuitas. *La mayoría obtiene su primer retiro en una semana.* ¿Has probado un bono sin depósito antes?",
        "exclusive": "Estás con gente que ejecuta señales y bonos como un sistema. *La mayoría ve el efecto compuesto después de 3-4 semanas.* ¿Con qué lado tienes más experiencia?",
    },
    "hr": {
        "betting":   "Ti si s ljudima koji ovo prate neko vrijeme. *Većina počinje prateći signale tjedan dana* prije djelovanja. Jesi li ikad pratio tipster signale?",
        "casino":    "Ti si s ljudima koji ozbiljno shvaćaju matematiku bonusa. *Većina oslobodi prvi bonus u 2-3 sesije* s pravim odabirom igara. Jesi li ikad igrao bonus runde?",
        "nodeposit": "Ti si s ljudima koji znaju izvući pravu vrijednost iz besplatnih ponuda. *Većina dobije isplatu unutar tjedna.* Jesi li ikad probao bonus bez depozita?",
        "exclusive": "Ti si s ljudima koji vode signale i bonuse kao sustav. *Većina vidi efekt složenog rasta nakon 3-4 tjedna.* S kojom stranom imaš više iskustva?",
    },
    "lt": {
        "betting":   "Tu esi su žmonėmis kurie tai seka jau kurį laiką. *Dauguma pradeda stebėdami signalus savaitę* prieš veikdami. Ar anksčiau sekei kokio nors tipster signalus?",
        "casino":    "Tu esi su žmonėmis kurie rimtai žiūri į bonusų matematiką. *Dauguma išvalo pirmą bonusą per 2-3 sesijas* su teisingu žaidimų pasirinkimu. Ar anksčiau žaidei bonus raundus?",
        "nodeposit": "Tu esi su žmonėmis kurie moka išgauti tikrą vertę iš nemokamų pasiūlymų. *Dauguma gauna pirmą išmokėjimą per savaitę.* Ar anksčiau bandei be depozito bonusą?",
        "exclusive": "Tu esi su žmonėmis kurie valdo signalus ir bonusus kaip sistemą. *Dauguma mato sudėtinį efektą po 3-4 savaičių.* Su kuria puse turi daugiau patirties?",
    },
    "lv": {
        "betting":   "Tu esi ar cilvēkiem kas to seko jau kādu laiku. *Vairākums sāk sekojot signāliem nedēļu* pirms rīkojas. Vai iepriekš esi sekojis kāda tipster signāliem?",
        "casino":    "Tu esi ar cilvēkiem kas nopietni uztver bonusu matemātiku. *Vairākums notīra pirmo bonusu 2-3 sesijās* ar pareizo spēļu izvēli. Vai iepriekš esi spēlējis bonusu kārtās?",
        "nodeposit": "Tu esi ar cilvēkiem kas prot iegūt reālu vērtību no bezmaksas piedāvājumiem. *Vairākums saņem pirmo izmaksu nedēļas laikā.* Vai iepriekš esi mēģinājis bonusu bez depozīta?",
        "exclusive": "Tu esi ar cilvēkiem kas vada signālus un bonusus kā sistēmu. *Vairākums redz saliktās procentu efektu pēc 3-4 nedēļām.* Ar kuru pusi tev ir vairāk pieredzes?",
    },
}

def get_post_sub_opener(lang: str, interest: str, ab_variant: str = "A") -> str:
    """
    CRO #4: A/B тест post-sub онбординга.
    ab_variant из user["ab_variant"], передаётся из bot.py/user_joined.
    """
    if ab_variant == "B":
        table = _POST_SUB_B
    elif ab_variant == "C":
        table = _POST_SUB_C
    else:
        table = _POST_SUB_A

    lang_data = table.get(lang, table.get("en", {}))
    return lang_data.get(interest, lang_data.get("betting", ""))


# ════════════════════════════════════════════════════════════════════════════
#  SILENCE DETECTOR
# ════════════════════════════════════════════════════════════════════════════

from datetime import datetime, timezone

def hours_since_last_message(user_id: int) -> float:
    from storage import get_user
    user = get_user(user_id)
    last_str = user.get("last_user_message_at", user.get("last_active", ""))
    if not last_str:
        return 999
    try:
        la = datetime.fromisoformat(last_str)
        if la.tzinfo is None:
            la = la.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - la).total_seconds() / 3600
    except Exception:
        return 999

def should_send_silence_push(user_id: int, silence_hours: float = 4.0) -> bool:
    from storage import get_user
    hours = hours_since_last_message(user_id)
    if hours < silence_hours:
        return False
    user = get_user(user_id)
    last_push_str = user.get("last_push_at", "")
    if not last_push_str:
        return True
    try:
        lp = datetime.fromisoformat(last_push_str)
        if lp.tzinfo is None:
            lp = lp.replace(tzinfo=timezone.utc)
        hours_since_push = (datetime.now(timezone.utc) - lp).total_seconds() / 3600
        return hours_since_push >= silence_hours
    except Exception:
        return True


# ════════════════════════════════════════════════════════════════════════════
#  SILENCE PUSH GENERATOR  (CRO #3 — barrier-aware)
# ════════════════════════════════════════════════════════════════════════════

_PUSH_PRE_FTD_GENERIC: dict[str, list[str]] = {
    "en": [
        "Still thinking things over? What's the one question you still have?",
        "Something came up in the channel today that fits what you mentioned. Still around?",
        "No rush — but the window I mentioned is still open. What's holding you back?",
    ],
    "es": [
        "¿Todavía pensándolo? ¿Cuál es la única pregunta que todavía tienes?",
        "Algo salió en el canal hoy que encaja con lo que mencionaste. ¿Sigues por aquí?",
        "Sin prisa — pero la ventana que mencioné sigue abierta. ¿Qué te frena?",
    ],
    "hr": [
        "Još razmišljaš? Koje je jedino pitanje koje još imaš?",
        "Nešto se pojavilo u kanalu danas što odgovara onome što si spominjao. Jesi li još tu?",
        "Nema žurbe — ali prozor koji sam spominjala je još otvoren. Što te drži?",
    ],
    "lt": [
        "Vis dar galvoji? Koks yra vienintelis klausimas kurio vis dar turi?",
        "Šiandien kanale pasirodė kažkas kas atitinka tai ką minėjai. Vis dar čia?",
        "Neskubėk — bet langas kurį minėjau vis dar atviras. Kas tave laiko?",
    ],
    "lv": [
        "Vēl domā? Kāds ir viens jautājums kuru joprojām esi?",
        "Šodien kanālā parādījās kaut kas kas atbilst tam ko pieminēji. Vēl esi šeit?",
        "Nav steiga — bet logs kuru minēju joprojām ir atvērts. Kas tevi kavē?",
    ],
}

# Barrier-специфичные тексты — адресуем конкретное возражение
_PUSH_BARRIER: dict[str, dict[str, str]] = {
    "no_money": {
        "en": "Quick one — the channel has a no-deposit path. *Zero of your own money*, real upside potential. Worth 2 minutes to check the pinned post.",
        "es": "Rápido — el canal tiene un camino sin depósito. *Cero de tu propio dinero*, potencial real. Vale 2 minutos revisar el mensaje fijado.",
        "hr": "Brzo — kanal ima put bez depozita. *Nula vašeg novca*, pravi potencijal rasta. Vrijedi 2 minute provjeriti prikvačenu poruku.",
        "lt": "Greitai — kanalas turi be depozito kelią. *Nulis savo pinigų*, realus potencialas. Verta 2 minutės patikrinti prisegtą žinutę.",
        "lv": "Ātri — kanālam ir bez depozīta ceļš. *Nulle savu naudas*, reāls potenciāls. Vērts 2 minūtes pārbaudīt piesaistīto ziņu.",
    },
    "no_trust": {
        "en": "Fair question. *Check the channel archive for last month* — real signals, real outcomes, all public. No interpretation needed. What specifically felt off?",
        "es": "Pregunta justa. *Revisa el archivo del canal del mes pasado* — señales reales, resultados reales, todo público. ¿Qué exactamente te generó desconfianza?",
        "hr": "Pošteno pitanje. *Provjeri arhivu kanala za prošli mjesec* — pravi signali, pravi rezultati, sve javno. Što točno ti se činilo sumnjivim?",
        "lt": "Sąžiningas klausimas. *Patikrink kanalo archyvą už praeitą mėnesį* — tikri signalai, tikri rezultatai, viskas viešai. Kas konkrečiai atrodė įtartina?",
        "lv": "Godīgs jautājums. *Pārbaudi kanāla arhīvu par pagājušo mēnesi* — īsti signāli, īsti rezultāti, viss publiski. Kas konkrēti šķita aizdomīgs?",
    },
    "dont_understand": {
        "en": "One sentence: *channel posts a signal → you act → you track the result*. Which of those three steps is still unclear?",
        "es": "Una frase: *el canal publica una señal → tú actúas → rastrear el resultado*. ¿Cuál de esos tres pasos no está claro?",
        "hr": "Jedna rečenica: *kanal objavljuje signal → ti djeluješ → pratiš rezultat*. Koji od ta tri koraka još nije jasan?",
        "lt": "Vienu sakiniu: *kanalas paskelbia signalą → tu veiksni → seki rezultatą*. Kuris iš tų trijų žingsnių vis dar neaiškus?",
        "lv": "Vienā teikumā: *kanāls publicē signālu → tu rīkojies → seko rezultātam*. Kurš no tiem trim soļiem nav skaidrs?",
    },
    "not_urgent": {
        "en": "No rush. Just so you know — *the gaps we track close within hours*, not days. When you're ready, they'll be there. What's your timeline?",
        "es": "Sin prisa. Solo para que sepas — *los gaps se cierran en horas*, no días. Cuando estés listo, estarán ahí. ¿Cómo ves tu cronograma?",
        "hr": "Nema žurbe. Samo da znaš — *jazovi se zatvaraju u satima*, ne danima. Kad budeš spreman, bit će tamo. Kakav je tvoj raspored?",
        "lt": "Neskubėk. Tiesiog žinok — *tarpai užsidaro per valandas*, ne dienas. Kai būsi pasiruošęs, jie bus ten. Koks tavo laiko grafikas?",
        "lv": "Nav steiga. Tikai lai zini — *tarpas aizveras stundu laikā*, nevis dienās. Kad būsi gatavs, tie būs tur. Kāds ir tavs laika grafiks?",
    },
    "already_elsewhere": {
        "en": "Multiple accounts is the play here — *more books = more gaps to exploit*. What platform are you currently using? I can tell you if there's overlap with what's in the channel.",
        "es": "Múltiples cuentas es la jugada aquí — *más casas = más gaps*. ¿Qué plataforma usas actualmente? Puedo decirte si hay superposición con el canal.",
        "hr": "Više računa je pravi potez ovdje — *više kladionica = više jazova*. Koju platformu trenutno koristiš? Mogu ti reći postoji li preklapanje s kanalom.",
        "lt": "Kelios sąskaitos čia yra tikras žingsnis — *daugiau bukmeikerių = daugiau tarpų*. Kokią platformą šiuo metu naudoji? Galiu pasakyti ar yra persidengimas su kanalu.",
        "lv": "Vairāki konti šeit ir īstais gājiens — *vairāk grāmatu = vairāk tarpas*. Kuru platformu pašlaik izmanto? Varu pateikt vai ir pārklāšanās ar kanālu.",
    },
    "skeptical": {
        "en": "Still not sure? *Check the channel archive for last month* — real signals, real outcomes, all public. What would it take to try it once?",
        "es": "¿Todavía no estás seguro? *Revisa el archivo del canal del mes pasado* — señales reales, resultados reales, todo público. ¿Qué haría falta para probar una vez?",
        "hr": "Još nisi siguran? *Provjeri arhivu kanala za prošli mjesec* — pravi signali, pravi rezultati, sve javno. Što bi trebalo za pokušaj jednom?",
        "lt": "Vis dar nesitiki? *Patikrink kanalo archyvą už praeitą mėnesį* — tikri signalai, tikri rezultatai, viskas viešai. Kas reikėtų išbandyti kartą?",
        "lv": "Vēl neesi pārliecināts? *Pārbaudi kanāla arhīvu par pagājušo mēnesi* — īsti signāli, īsti rezultāti, viss publiski. Kas būtu vajadzīgs izmēģināt vienu reizi?",
    },
    "tried_before": {
        "en": "So you know how it works — the question is *whether the signals you had were actually sharp*. Most tipster services use public info. This one doesn't. What went wrong last time?",
        "es": "Así que sabes cómo funciona — la pregunta es *si las señales que tenías eran realmente sharp*. La mayoría usa información pública. Éste no. ¿Qué salió mal la última vez?",
        "hr": "Dakle znaš kako funkcionira — pitanje je *jesu li signali bili zaista sharp*. Većina tipster servisa koristi javne informacije. Ovaj ne. Što je pošlo po krivu prošli put?",
        "lt": "Taigi žinai kaip tai veikia — klausimas yra *ar signalai buvo tikrai sharp*. Dauguma tipster paslaugų naudoja viešą informaciją. Ši ne. Kas nepavyko paskutinį kartą?",
        "lv": "Tātad zini kā tas darbojas — jautājums ir *vai signāli bija tiešām sharp*. Vairākums tipster pakalpojumu izmanto publisku informāciju. Šis ne. Kas nogāja greizi pēdējo reizi?",
    },
}

_PUSH_POST_FTD: dict[str, list[str]] = {
    "en": [
        "How's it going with the first session? Anything I can help optimize?",
        "Results from yesterday — good, bad, or mixed?",
        "Ready for the next move or still processing the first one?",
    ],
    "es": [
        "¿Cómo va con la primera sesión? ¿Algo que pueda ayudar a optimizar?",
        "Resultados de ayer — ¿buenos, malos o mixtos?",
        "¿Listo para el siguiente movimiento o todavía procesando el primero?",
    ],
    "hr": [
        "Kako ide s prvom sesijom? Ima li nešto što mogu pomoći optimizirati?",
        "Rezultati od jučer — dobri, loši ili mješoviti?",
        "Spreman za sljedeći potez ili još obrađuješ prvi?",
    ],
    "lt": [
        "Kaip sekasi su pirmąja sesija? Ar yra kažkas ką galiu padėti optimizuoti?",
        "Vakarykščiai rezultatai — geri, blogi ar mišrūs?",
        "Pasiruošęs kitam žingsniui ar vis dar apdoroji pirmąjį?",
    ],
    "lv": [
        "Kā iet ar pirmo sesiju? Vai ir kaut kas ko varu palīdzēt optimizēt?",
        "Vakardienas rezultāti — labi, slikti vai jaukti?",
        "Gatavs nākamajam gājienam vai vēl apstrādā pirmo?",
    ],
}

def get_silence_push(lang: str, ftd_done: bool, barrier: str = "unknown") -> str:
    """
    CRO #3: barrier-aware silence push.

    Если barrier известен — возвращаем текст адресующий конкретное возражение.
    Если barrier = "unknown" — generic текст.
    """
    if ftd_done:
        options = _PUSH_POST_FTD.get(lang, _PUSH_POST_FTD["en"])
        return random.choice(options)

    if barrier and barrier != "unknown":
        barrier_map = _PUSH_BARRIER.get(barrier)
        if barrier_map:
            text = barrier_map.get(lang, barrier_map.get("en", ""))
            if text:
                return text

    options = _PUSH_PRE_FTD_GENERIC.get(lang, _PUSH_PRE_FTD_GENERIC["en"])
    return random.choice(options)
