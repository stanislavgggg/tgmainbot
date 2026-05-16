"""
bot.py — OddsVault Bot v14

Архитектура:
  - Диалоговый flow (conversation.py) вместо скриптов
  - 21 сценарий (scenarios.py) покрывает все пользовательские пути
  - Адаптивный онбординг с классификатором барьера (ftd_onboarding.py)
  - FTD celebration + repeat machine
  - Daily signal, Adrenaline mode, A/B тест, Bonus calculator, Referral
"""
import asyncio, logging, os, random, sys, atexit
from datetime import datetime, timezone
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.error import TelegramError
from telegram.ext import (Application, CallbackQueryHandler, CommandHandler,
                          ContextTypes, MessageHandler, filters)
from config import BOT_TOKEN, State
from storage import (add_ai_message, add_tone, get_all_users, get_ai_history, get_user,
                     update_user, update_user_no_active, mark_push_sent,
                     classify_objection, log_objection,
                     get_objections, update_psychotype, get_psychotype,
                     get_profile, update_profile)
from ai_agent import detect_tone, extract_profile_update, ANTHROPIC_KEY
from membership import (check_membership, MemberStatus, resolve_channel, resolve_lang,
                        infer_geo_from_tg_lang, get_channel_link, get_channel_title,
                        fetch_channel_ids)
from scenarios import (classify_post_ftd_message, get_win_response, get_loss_response,
                        get_vip_message, get_returning_opener, VIP_FTD_THRESHOLD)
from conversation import (ask_valeria_conversational, get_post_sub_opener,
                           get_silence_push, should_send_silence_push,
                           detect_interest_from_text, detect_geo_from_text)
from ftd_onboarding import schedule_onboarding, schedule_ftd_flow, detect_ftd_signal
from daily_signal import daily_signal_job
from ab_test import (assign_variant, get_hook_text, track_event,
                     get_ab_stats, format_ab_stats_message)
from bonus_calculator import (should_show_calculator, get_calculator_trigger_text,
                               get_calc_intro, get_deposit_buttons, get_stake_buttons,
                               format_casino_result, format_betting_result, parse_deposit_callback)
from referral import (should_offer_referral, get_referral_offer_text,
                       track_referral_offer, track_referral_click,
                       get_referrer_from_start, is_positive_message)
from adrenaline import adrenaline_check_job
import messages as M

logging.basicConfig(format="%(asctime)s [%(levelname)s] %(name)s: %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# ── Lock ──────────────────────────────────────────────────────────────────────
LOCK_FILE = "bot.lock"
def _check_lock():
    if os.path.exists(LOCK_FILE):
        try:
            with open(LOCK_FILE) as f: old_pid = int(f.read().strip())
            os.kill(old_pid, 0); logger.error(f"Already running PID {old_pid}"); sys.exit(1)
        except (ProcessLookupError, ValueError): os.remove(LOCK_FILE)
    with open(LOCK_FILE,"w") as f: f.write(str(os.getpid()))
    atexit.register(lambda: os.path.exists(LOCK_FILE) and os.remove(LOCK_FILE))
_check_lock()

# ── Reengage angles — 5 углов атаки по очереди ───────────────────────────────
_REENGAGE_ANGLES: dict[str, list[str]] = {
    "en": [
        "Still around? How did you end up finding this in the first place?",
        "*Sharp money moved before the line shifted* — 15-minute window most people miss. Still relevant to you?",
        "Quick one — you more of a sports person or casino?",
        "Most people who find this got burned going it alone first. That the case for you?",
        "Last one from me — what's the one thing that would actually make this worth looking at?",
    ],
    "es": [
        "¿Sigues por aquí? ¿Cómo terminaste encontrando esto?",
        "*El dinero sharp se movió antes de que la cuota cambiara* — ventana de 15 minutos que la mayoría pierde. ¿Sigue siendo relevante para ti?",
        "Rápido — ¿eres más de deportes o casino?",
        "La mayoría que llega aquí se quemó yendo solo primero. ¿Ese es tu caso?",
        "La última de mi parte — ¿qué haría que realmente valiera la pena echar un vistazo?",
    ],
    "hr": [
        "Jesi li još tu? Kako si uopće završio pronalazeći ovo?",
        "*Novac se pomaknuo prije nego što se kvota promijenila* — 15-minutni prozor koji većina propušta. Je li još relevantno za tebe?",
        "Kratko — jesi više sports tip ili casino?",
        "Većina koji nađu ovo prvo su se opekli idući sami. Je li to tvoj slučaj?",
        "Zadnje od mene — što bi zapravo učinilo da vrijedi pogledati?",
    ],
    "lt": [
        "Vis dar čia? Kaip apskritai radai šitą?",
        "*Pinigai pajudėjo prieš koeficientui pasikeičiant* — 15 minučių langas kurį dauguma praleidžia. Vis dar aktualu?",
        "Greitai — esi labiau sporto ar kazino žmogus?",
        "Dauguma kurie randa šitą pirmiausia nudegė eidami vieni. Ar tavo atvejis?",
        "Paskutinis iš manęs — kas tikrai privertų tai verta pažiūrėti?",
    ],
    "lv": [
        "Vēl esi šeit? Kā tu vispār atradi šito?",
        "*Nauda pakustējās pirms koeficients mainījās* — 15 minūšu logs ko vairākums palaiž garām. Vēl aktuāli?",
        "Ātri — tu esi vairāk sporta vai kazino cilvēks?",
        "Vairākums kas atrod šito vispirms apdedzinājās ejot vieni. Vai tā ir tava situācija?",
        "Pēdējais no manis — kas tiešām liktu to vērts apskatīt?",
    ],
}

# ── Helpers ───────────────────────────────────────────────────────────────────
def _typing_delay(text): return round(1.2 + min(len(text)/140, 2.0), 1)

def _cta_keyboard(lang, interest, geo):
    channel = resolve_channel(geo, interest)
    if channel:
        url   = f"https://t.me/{channel['username'].lstrip('@')}"
        title = channel.get("title", "📲 OddsVault")
    else:
        url, title = "https://t.me/ApuestasGuruES", "📲 OddsVault"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(title, url=url)],
        [InlineKeyboardButton(
            M.CTA_BUTTON_JOINED.get(lang, M.CTA_BUTTON_JOINED.get("en", "✅ Already in")),
            callback_data="user_joined")],
    ])

def _prepare_context(user_id, user_text):
    obj = classify_objection(user_text)
    if obj: log_objection(user_id, obj)
    return update_psychotype(user_id, user_text), get_objections(user_id)

async def _send_tease(bot, user_id, chat_id, lang, interest, geo="OTHER", job_queue=None):
    """
    Отправляет TEASE. CTA приходит через 8 секунд если пользователь не ответил.
    Передай job_queue для асинхронного CTA (рекомендуется).
    """
    update_user(user_id, state=State.TEASE, funnel_stage="tease", stage_replies=0)
    text = M.get(M.TEASE, lang, interest)
    await bot.send_chat_action(chat_id, "typing")
    await asyncio.sleep(_typing_delay(text) * 0.7)
    await bot.send_message(chat_id=chat_id, text=text, parse_mode=ParseMode.MARKDOWN)

    # CTA через паузу — только если пользователь не ответил сам
    if job_queue:
        job_queue.run_once(
            _delayed_cta_job, when=8,
            data={"user_id": user_id, "chat_id": chat_id,
                  "lang": lang, "interest": interest, "geo": geo},
            name=f"cta_{user_id}")
    else:
        await asyncio.sleep(8)
        current = get_user(user_id)
        if current.get("stage_replies", 0) == 0 and current.get("state") == State.TEASE:
            await _send_cta(bot, user_id, chat_id, lang, interest, geo)

async def _delayed_cta_job(context: ContextTypes.DEFAULT_TYPE):
    """CTA только если пользователь не ответил сам после TEASE."""
    d = context.job.data
    user_id, chat_id = d["user_id"], d["chat_id"]
    lang, interest, geo = d["lang"], d["interest"], d["geo"]
    user = get_user(user_id)
    if user.get("stage_replies", 0) > 0:
        return
    if user.get("state") != State.TEASE:
        return
    await _send_cta(context.bot, user_id, chat_id, lang, interest, geo)

async def _send_cta(bot, user_id, chat_id, lang, interest, geo):
    update_user(user_id, state=State.CTA, funnel_stage="cta")
    cta_text = M.CTA_TEXT.get(lang, M.CTA_TEXT.get("en", "🔐 The vault is right there."))
    await bot.send_message(chat_id=chat_id, text=cta_text, parse_mode=ParseMode.MARKDOWN,
                           reply_markup=_cta_keyboard(lang, interest, geo))


# ════════════════════════════════════════════════════════════════════════════
#  /start
# ════════════════════════════════════════════════════════════════════════════
HOOK_IMAGE_PATH = os.path.join(os.path.dirname(__file__), "1name.png")
HOOK_IMAGE_URL  = "https://raw.githubusercontent.com/stanislavgggg/tgmainbot/4891019e49ee730aad0db5bcd065708a1b44c471/1name.png"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id    = update.effective_user.id
    first_name = update.effective_user.first_name or ""
    tg_lang    = update.effective_user.language_code
    chat_id    = update.effective_chat.id

    start_param = context.args[0] if context.args else ""
    if start_param:
        referrer_id = get_referrer_from_start(start_param)
        if referrer_id and referrer_id != user_id:
            track_referral_click(referrer_id)
            logger.info(f"Referral: {user_id} from {referrer_id}")

    existing = get_user(user_id)
    geo_hint  = infer_geo_from_tg_lang(tg_lang) or "OTHER"
    lang      = existing.get("lang") or resolve_lang(geo_hint, tg_lang)

    # ── S7: Возвращающийся пользователь ──────────────────────────────────────
    prev_stage = existing.get("funnel_stage", "new")
    if prev_stage not in ("new", "") and existing.get("stage_replies", 0) > 0:
        interest = existing.get("interest", "betting")
        geo      = existing.get("geo", geo_hint)
        opener   = get_returning_opener(lang)
        logger.info(f"RETURNING user={user_id} prev_stage={prev_stage}")
        await context.bot.send_chat_action(chat_id, "typing")
        await asyncio.sleep(1.2)
        await context.bot.send_message(
            chat_id=chat_id, text=opener, parse_mode=ParseMode.MARKDOWN)
        if prev_stage == "subscribed":
            update_user(user_id, state=State.AI_CHAT)
        else:
            update_user(user_id, state=State.WARM1, stage_replies=0,
                        reengage_1_sent=False, reengage_2_sent=False,
                        current_angle=0)
        return

    # ── Новый пользователь ────────────────────────────────────────────────────
    variant = assign_variant()
    update_user(user_id,
        state=State.WARM1, funnel_stage="discovery",
        first_name=first_name,
        username=update.effective_user.username or "",
        lang=lang, geo=geo_hint,
        reengage_1_sent=False, reengage_2_sent=False,
        ai_msg_count=0, stage_replies=0,
        commitment_sent=False, cta_replies=0,
        fallback_count=0, ab_variant=variant,
        positive_msg_count=0,
        current_angle=0,
    )
    logger.info(f"START new user={user_id} lang={lang} geo={geo_hint} variant={variant}")

    hook_text = get_hook_text(variant, lang)
    await asyncio.sleep(0.8)

    sent = False
    if os.path.exists(HOOK_IMAGE_PATH):
        try:
            with open(HOOK_IMAGE_PATH, "rb") as photo:
                await context.bot.send_photo(
                    chat_id=chat_id, photo=photo,
                    caption=hook_text, parse_mode=ParseMode.MARKDOWN)
            sent = True
        except TelegramError as e:
            logger.warning(f"Photo file failed: {e}")
    if not sent:
        try:
            await context.bot.send_photo(
                chat_id=chat_id, photo=HOOK_IMAGE_URL,
                caption=hook_text, parse_mode=ParseMode.MARKDOWN)
            sent = True
        except TelegramError as e:
            logger.warning(f"Photo URL failed: {e}")
    if not sent:
        await context.bot.send_message(
            chat_id=chat_id, text=hook_text, parse_mode=ParseMode.MARKDOWN)

    track_event(user_id, "hook_shown")
    update_user(user_id, state=State.WARM1, funnel_stage="discovery")


# ════════════════════════════════════════════════════════════════════════════
#  "Уже вступил" → проверка подписки
# ════════════════════════════════════════════════════════════════════════════
async def user_joined(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    user_id = query.from_user.id
    user    = get_user(user_id)
    lang    = user.get("lang", "en")
    interest= user.get("interest", "betting")
    geo     = user.get("geo", "OTHER")
    chat_id = query.message.chat_id

    checking = {
        "en": "Checking... ⏳", "es": "Comprobando... ⏳",
        "hr": "Provjeravam... ⏳", "lt": "Tikrinu... ⏳", "lv": "Pārbauda... ⏳",
    }
    await query.answer(checking.get(lang, "Checking... ⏳"))

    status = await check_membership(bot=context.bot, user_id=user_id, geo=geo, interest=interest)

    if status == MemberStatus.NOT_MEMBER:
        not_yet = {
            "en": "Hmm, looks like you're not in yet. Join first — then come back here. 👇",
            "es": "Hmm, parece que aún no estás dentro. Únete primero y vuelve aquí. 👇",
            "hr": "Hmm, čini se da još nisi unutra. Pridruži se prvo i vrati se ovdje. 👇",
            "lt": "Hmm, atrodo dar neprisijungei. Prisijunk pirmiausia ir grįžk čia. 👇",
            "lv": "Hmm, izskatās ka vēl neesi iekšā. Pievienojies vispirms un atgriezies. 👇",
        }
        await context.bot.send_message(
            chat_id=chat_id, text=not_yet.get(lang, not_yet["en"]),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=_cta_keyboard(lang, interest, geo))
        return

    update_user(user_id, state=State.AI_CHAT, funnel_stage="subscribed", verified_member=True)
    await context.bot.send_chat_action(chat_id, "typing")
    await asyncio.sleep(1.5)

    opener = get_post_sub_opener(lang, interest) or M.get(M.POST_SUB, lang, interest)
    await context.bot.send_message(
        chat_id=chat_id, text=opener, parse_mode=ParseMode.MARKDOWN)

    schedule_onboarding(
        job_queue=context.job_queue, user_id=user_id,
        chat_id=chat_id, lang=lang, interest=interest)
    logger.info(f"Subscribed → {user_id} [{lang}/{interest}/{geo}]")


# ════════════════════════════════════════════════════════════════════════════
#  Главный handler входящих сообщений
# ════════════════════════════════════════════════════════════════════════════
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text: return
    user_id   = update.effective_user.id
    user      = get_user(user_id)
    state     = user.get("state")
    user_text = update.message.text.strip()

    logger.info(f"MSG user={user_id} state={state} text={user_text[:40]!r}")

    if state is None:
        await start(update, context); return

    lang     = user.get("lang", "en")
    interest = user.get("interest", "betting")
    geo      = user.get("geo", "OTHER")

    # Детектор GEO из текста
    if geo in ("OTHER", ""):
        detected_geo = detect_geo_from_text(user_text)
        if detected_geo and detected_geo != geo:
            new_lang = resolve_lang(detected_geo)
            update_user(user_id, geo=detected_geo, lang=new_lang)
            geo = detected_geo; lang = new_lang
            logger.info(f"GEO from text: {detected_geo} → lang={new_lang}")

    # Silent profile update
    if len(user_text) > 8:
        asyncio.create_task(_update_profile_silent(user_id, user_text, lang))

    # Детектор переключения языка
    new_lang = _detect_lang_switch(user_text)
    if new_lang and new_lang != lang:
        update_user(user_id, lang=new_lang); lang = new_lang
        ack = {"en":"Switching to English. 👌","es":"Cambio al español. 👌",
               "hr":"Prelazim na hrvatski. 👌","lt":"Pereinu į lietuvių. 👌","lv":"Pāreju uz latviešu. 👌"}
        await update.message.reply_text(ack.get(new_lang, "👌"))
        return

    # Роутинг по состоянию
    if state in (State.WARM1, State.WARM2):
        await _handle_warming(update, context, user_id, lang, interest, geo, user_text, user)
    elif state == State.TEASE:
        await _handle_tease(update, context, user_id, lang, interest, geo, user_text)
    elif state == State.CTA:
        await _handle_cta(update, context, user_id, lang, interest, geo, user_text)
    elif state in (State.AI_CHAT, State.SUBSCRIBED):
        if detect_ftd_signal(user_text):
            ftd_count = user.get("ftd_count", 0) + 1
            update_user(user_id, ftd_done=True, ftd_count=ftd_count)
            logger.info(f"FTD #{ftd_count} → {user_id}")
            schedule_ftd_flow(context.job_queue, user_id,
                              update.effective_chat.id, lang, interest)
        await _handle_ai_chat(update, context, user_id, lang, interest, geo, user_text, user)
    else:
        logger.warning(f"Unknown state={state} for {user_id} → WARM1")
        update_user(user_id, state=State.WARM1, funnel_stage="discovery")
        await _handle_warming(update, context, user_id, lang, interest, geo, user_text, user)


async def _update_profile_silent(user_id, text, lang):
    try:
        updates = await extract_profile_update(text, get_profile(user_id), lang)
        if updates:
            update_profile(user_id, updates)
            logger.info(f"Profile {user_id}: {updates}")
    except Exception as e:
        logger.debug(f"Profile skip: {e}")


def _detect_lang_switch(text: str):
    t = text.lower().strip()
    if any(t == p or t.startswith(p) for p in [
        "switch to english", "english please", "speak english",
        "in english", "change to english", "английский", "по-английски",
    ]):
        return "en"
    if any(t == p or t.startswith(p) for p in [
        "switch to spanish", "en español", "español", "habla español",
        "cambiar a español", "speak spanish",
    ]):
        return "es"
    if any(t == p or t.startswith(p) for p in [
        "switch to croatian", "hrvatski", "na hrvatskom", "speak croatian",
    ]):
        return "hr"
    if any(t == p or t.startswith(p) for p in [
        "switch to lithuanian", "lietuviškai", "lietuvių", "speak lithuanian",
    ]):
        return "lt"
    if any(t == p or t.startswith(p) for p in [
        "switch to latvian", "latviešu", "latviski", "speak latvian",
    ]):
        return "lv"
    return None


# ════════════════════════════════════════════════════════════════════════════
#  WARMING handler
# ════════════════════════════════════════════════════════════════════════════
async def _handle_warming(update, context, user_id, lang, interest, geo, user_text, user):
    chat_id    = update.effective_chat.id
    history    = get_ai_history(user_id)
    replies    = user.get("stage_replies", 0) + 1
    funnel     = user.get("funnel_stage", "discovery")
    psychotype = get_psychotype(user_id)
    objections = get_objections(user_id)
    profile    = get_profile(user_id)
    ftd_done   = bool(user.get("ftd_done"))

    obj_type = classify_objection(user_text)
    if obj_type:
        log_objection(user_id, obj_type)

    # Инкрементируем угол атаки — AI знает на каком шаге разговор
    current_angle = user.get("current_angle", 0)
    update_user(user_id, stage_replies=replies, current_angle=current_angle + 1)

    await context.bot.send_chat_action(chat_id, "typing")

    result = await ask_valeria_conversational(
        user_message=user_text,
        history=history,
        lang=lang,
        interest=interest if interest != "betting" or user.get("interest_confirmed") else None,
        geo=geo if geo and geo != "OTHER" else None,
        funnel_stage=funnel,
        psychotype=psychotype,
        user_profile=profile,
        objections=objections,
        ftd_done=ftd_done,
        current_angle=current_angle,
    )

    response = result["text"]
    add_ai_message(user_id, "user", user_text)
    add_ai_message(user_id, "assistant", response)
    add_tone(user_id, detect_tone(user_text, history))

    # Обновляем interest и GEO если AI их определил
    updates = {}
    if result["detected_interest"] and not user.get("interest_confirmed"):
        updates["interest"]           = result["detected_interest"]
        updates["interest_confirmed"] = True
        interest                      = result["detected_interest"]
        logger.info(f"Interest detected: {interest} for {user_id}")
    if result["detected_geo"] and (not geo or geo == "OTHER"):
        from membership import resolve_lang as _resolve_lang
        new_geo  = result["detected_geo"]
        new_lang = _resolve_lang(new_geo)
        updates["geo"]  = new_geo
        updates["lang"] = new_lang
        lang = new_lang
        geo  = new_geo
        logger.info(f"GEO detected: {new_geo} → lang={new_lang} for {user_id}")
    if updates:
        update_user(user_id, **updates)

    await asyncio.sleep(_typing_delay(response) * 0.5)
    await update.message.reply_text(response, parse_mode=ParseMode.MARKDOWN)

    # Tease trigger
    interest_known = bool(
        result["detected_interest"] or
        user.get("interest_confirmed") or
        interest not in (None, "betting")
    )

    # Если AI решил tease — пушим
    # Если угол >= 4 (5-я реплика) — пушим принудительно независимо от интереса
    force_tease = (current_angle >= 4)
    should_tease = (result["move_to_tease"] and interest_known and replies >= 1) or force_tease

    if should_tease:
        # При force_tease используем дефолтный interest если не определили
        if force_tease and not interest_known:
            interest = interest or "betting"
        await asyncio.sleep(3.0)
        fresh = get_user(user_id)
        if fresh.get("stage_replies", 0) == replies:
            await _send_tease(context.bot, user_id, chat_id, lang, interest,
                              geo=geo, job_queue=context.job_queue)


# ════════════════════════════════════════════════════════════════════════════
#  TEASE handler
# ════════════════════════════════════════════════════════════════════════════
async def _handle_tease(update, context, user_id, lang, interest, geo, user_text):
    chat_id    = update.effective_chat.id
    history    = get_ai_history(user_id)
    psychotype = get_psychotype(user_id)
    objections = get_objections(user_id)
    profile    = get_profile(user_id)
    psychotype, objections = _prepare_context(user_id, user_text)[0], get_objections(user_id)

    await context.bot.send_chat_action(chat_id, "typing")
    result = await ask_valeria_conversational(
        user_message=user_text, history=history, lang=lang,
        interest=interest, geo=geo, funnel_stage="warming",
        psychotype=psychotype, user_profile=profile, objections=objections)

    response = result["text"]
    add_ai_message(user_id, "user", user_text)
    add_ai_message(user_id, "assistant", response)
    add_tone(user_id, detect_tone(user_text, history))

    await asyncio.sleep(_typing_delay(response) * 0.5)
    await update.message.reply_text(response, parse_mode=ParseMode.MARKDOWN)

    await asyncio.sleep(2.0)
    await _send_cta(context.bot, user_id, chat_id, lang, interest, geo)


async def _handle_cta(update, context, user_id, lang, interest, geo, user_text):
    chat_id    = update.effective_chat.id
    history    = get_ai_history(user_id)
    user       = get_user(user_id)
    psychotype, objections = _prepare_context(user_id, user_text)[0], get_objections(user_id)
    profile    = get_profile(user_id)

    await context.bot.send_chat_action(chat_id, "typing")
    result = await ask_valeria_conversational(
        user_message=user_text, history=history, lang=lang,
        interest=interest, geo=geo, funnel_stage="warming",
        psychotype=psychotype, user_profile=profile, objections=objections)

    response = result["text"]
    add_ai_message(user_id, "user", user_text)
    add_ai_message(user_id, "assistant", response)
    add_tone(user_id, detect_tone(user_text, history))

    cta_replies = user.get("cta_replies", 0) + 1
    update_user(user_id, cta_replies=cta_replies)

    await asyncio.sleep(_typing_delay(response) * 0.5)
    await update.message.reply_text(response, parse_mode=ParseMode.MARKDOWN)

    if cta_replies % 3 == 0:
        await asyncio.sleep(2.0)
        await _send_cta(context.bot, user_id, chat_id, lang, interest, geo)


# ════════════════════════════════════════════════════════════════════════════
#  AI Chat (subscribed)
# ════════════════════════════════════════════════════════════════════════════
async def _handle_ai_chat(update, context, user_id, lang, interest, geo, user_text, user):
    chat_id    = update.effective_chat.id
    history    = get_ai_history(user_id)
    msg_count  = user.get("ai_msg_count", 0)
    psychotype = get_psychotype(user_id)
    objections = get_objections(user_id)
    profile    = get_profile(user_id)
    ftd_done   = bool(user.get("ftd_done"))
    ftd_count  = user.get("ftd_count", 0)

    obj_type = classify_objection(user_text)
    if obj_type:
        log_objection(user_id, obj_type)

    add_ai_message(user_id, "user", user_text)
    update_user(user_id, ai_msg_count=msg_count + 1,
                last_user_message_at=datetime.now(timezone.utc).isoformat())
    await context.bot.send_chat_action(chat_id, "typing")

    # ── S16/S17: Win/Loss ────────────────────────────────────────────────────
    if ftd_done:
        msg_type = classify_post_ftd_message(user_text)
        if msg_type == "won":
            text = get_win_response(lang, interest)
            if text:
                await asyncio.sleep(_typing_delay(text) * 0.5)
                await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
                add_ai_message(user_id, "assistant", text)
                return
        elif msg_type == "lost":
            text = get_loss_response(lang, interest)
            if text:
                await asyncio.sleep(_typing_delay(text) * 0.5)
                await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
                add_ai_message(user_id, "assistant", text)
                return

    # ── S19: VIP ─────────────────────────────────────────────────────────────
    is_vip = ftd_count >= VIP_FTD_THRESHOLD
    if is_vip and msg_count == 0:
        vip_msg = get_vip_message(lang, ftd_count)
        if vip_msg:
            await asyncio.sleep(1.0)
            await update.message.reply_text(vip_msg, parse_mode=ParseMode.MARKDOWN)
            add_ai_message(user_id, "assistant", vip_msg)
            return

    # ── Основной диалог ───────────────────────────────────────────────────────
    result = await ask_valeria_conversational(
        user_message=user_text,
        history=history,
        lang=lang,
        interest=interest,
        geo=geo,
        funnel_stage="subscribed",
        psychotype=psychotype,
        user_profile=profile,
        objections=objections,
        ftd_done=ftd_done,
        ftd_count=ftd_count,
    )

    response = result["text"]
    add_ai_message(user_id, "assistant", response)
    add_tone(user_id, detect_tone(user_text, history))

    if result["detected_interest"] and result["detected_interest"] != interest:
        update_user(user_id, interest=result["detected_interest"])
        interest = result["detected_interest"]

    # ── S20: Реферал ─────────────────────────────────────────────────────────
    if is_positive_message(user_text):
        pos_count = user.get("positive_msg_count", 0) + 1
        update_user(user_id, positive_msg_count=pos_count)
        if should_offer_referral(user_id, pos_count):
            await asyncio.sleep(_typing_delay(response) * 0.5)
            await update.message.reply_text(response, parse_mode=ParseMode.MARKDOWN)
            await asyncio.sleep(1.8)
            ref_text = get_referral_offer_text(lang, user_id)
            await context.bot.send_message(
                chat_id=chat_id, text=ref_text, parse_mode=ParseMode.MARKDOWN)
            add_ai_message(user_id, "assistant", ref_text)
            track_referral_offer(user_id)
            return

    # ── Калькулятор ───────────────────────────────────────────────────────────
    new_count = msg_count + 1
    if should_show_calculator(interest, "subscribed", new_count):
        await asyncio.sleep(_typing_delay(response) * 0.5)
        await update.message.reply_text(response, parse_mode=ParseMode.MARKDOWN)
        await asyncio.sleep(1.5)
        intro   = get_calc_intro(lang, interest)
        btns    = get_deposit_buttons(lang)
        kb      = [[InlineKeyboardButton(lbl, callback_data=cb)] for lbl, cb in btns]
        trigger = get_calculator_trigger_text(lang, interest)
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"{trigger}\n\n{intro}",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(kb))
        return

    await asyncio.sleep(_typing_delay(response) * 0.5)
    await update.message.reply_text(response, parse_mode=ParseMode.MARKDOWN)


# ════════════════════════════════════════════════════════════════════════════
#  Commands
# ════════════════════════════════════════════════════════════════════════════
async def calc_deposit_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query; await query.answer()
    user_id = query.from_user.id
    user    = get_user(user_id)
    lang    = user.get("lang", "en")
    interest= user.get("interest", "betting")
    chat_id = query.message.chat_id

    deposit = parse_deposit_callback(query.data)
    if deposit is None: return

    try: await query.edit_message_reply_markup(reply_markup=None)
    except Exception: pass

    if interest == "betting":
        await context.bot.send_chat_action(chat_id, "typing")
        await asyncio.sleep(1.0)
        intro = get_calc_intro(lang, "betting")
        btns  = get_stake_buttons(lang)
        kb    = [[InlineKeyboardButton(lbl, callback_data=cb)] for lbl, cb in btns]
        await context.bot.send_message(
            chat_id=chat_id, text=intro, parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(kb))
        update_user(user_id, calc_deposit=deposit)
        return

    await context.bot.send_chat_action(chat_id, "typing")
    await asyncio.sleep(1.5)
    result_text = format_casino_result(lang, deposit, interest)
    await context.bot.send_message(
        chat_id=chat_id, text=result_text, parse_mode=ParseMode.MARKDOWN)
    add_ai_message(user_id, "assistant", result_text)

async def calc_stake_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query; await query.answer()
    user_id = query.from_user.id
    user    = get_user(user_id)
    lang    = user.get("lang", "en")
    chat_id = query.message.chat_id

    stake = parse_deposit_callback(query.data)
    if stake is None: return

    try: await query.edit_message_reply_markup(reply_markup=None)
    except Exception: pass

    await context.bot.send_chat_action(chat_id, "typing")
    await asyncio.sleep(1.5)
    result_text = format_betting_result(lang, stake)
    await context.bot.send_message(
        chat_id=chat_id, text=result_text, parse_mode=ParseMode.MARKDOWN)
    add_ai_message(user_id, "assistant", result_text)

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    users = get_all_users()
    by_state, by_lang, by_geo, subscribed = {}, {}, {}, 0
    for u in users:
        s = u.get("state","?"); by_state[s] = by_state.get(s,0)+1
        l = u.get("lang","?");  by_lang[l]  = by_lang.get(l,0)+1
        g = u.get("geo","?");   by_geo[g]   = by_geo.get(g,0)+1
        if u.get("funnel_stage") == "subscribed": subscribed += 1
    text = (f"📊 *OddsVault Stats*\n\nTotal: *{len(users)}* | Subscribed: *{subscribed}*\n\n"
            "By state:\n" + "\n".join(f"  {s}: {c}" for s,c in sorted(by_state.items())) +
            "\n\nBy lang:\n" + "\n".join(f"  {l}: {c}" for l,c in sorted(by_lang.items())) +
            "\n\nBy GEO:\n" + "\n".join(f"  {g}: {c}" for g,c in sorted(by_geo.items())))
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

async def admin_ab_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    stats = get_ab_stats()
    text  = format_ab_stats_message(stats)
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_user(update.effective_user.id)
    lang = user.get("lang", "en")
    texts = {"en":"ℹ️ I'm Valeria. Use /start to begin.",
             "es":"ℹ️ Soy Valeria. Usa /start para empezar.",
             "hr":"ℹ️ Ja sam Valerija. Koristi /start za početak.",
             "lt":"ℹ️ Aš esu Valerija. Naudok /start pradėti.",
             "lv":"ℹ️ Es esmu Valerija. Izmanto /start lai sāktu."}
    await update.message.reply_text(texts.get(lang, texts["en"]))

async def admin_fetch_ids(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔍 Fetching channel IDs...")
    ids = await fetch_channel_ids(context.bot)
    if not ids:
        await update.message.reply_text("❌ No IDs found. Is bot admin in channels?"); return
    lines = [f"`{k}`: `{v}`" for k, v in ids.items()]
    await update.message.reply_text(
        "📋 *Channel IDs* — copy to membership.py:\n\n" + "\n".join(lines),
        parse_mode=ParseMode.MARKDOWN)

async def debug_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user    = get_user(user_id)
    key_status = "✅ SET" if ANTHROPIC_KEY else "❌ MISSING"
    api_test = "🔄 Testing..."
    if ANTHROPIC_KEY:
        try:
            import httpx as _httpx
            r = await _httpx.AsyncClient(timeout=10).post(
                "https://api.anthropic.com/v1/messages",
                json={"model": "claude-sonnet-4-20250514", "max_tokens": 20,
                      "messages": [{"role":"user","content":"Reply with: OK"}]},
                headers={"x-api-key": ANTHROPIC_KEY, "anthropic-version": "2023-06-01",
                         "content-type": "application/json"})
            if r.status_code == 200:
                api_test = "✅ API works"
            else:
                api_test = f"❌ API error {r.status_code}: {r.text[:120]}"
        except Exception as e:
            api_test = f"❌ Connection error: {e}"
    else:
        api_test = "❌ Skipped — no key"

    text = (
        f"🔧 *Debug*\n\n"
        f"`ANTHROPIC_KEY`: {key_status}\n"
        f"`API test`: {api_test}\n\n"
        f"`user_id`: `{user_id}`\n"
        f"`state`: `{user.get('state','—')}`\n"
        f"`funnel`: `{user.get('funnel_stage','—')}`\n"
        f"`lang`: `{user.get('lang','—')}`\n"
        f"`geo`: `{user.get('geo','—')}`\n"
        f"`interest`: `{user.get('interest','—')}`\n"
        f"`stage_replies`: `{user.get('stage_replies',0)}`\n"
        f"`current_angle`: `{user.get('current_angle',0)}`\n"
        f"`fallback_count`: `{user.get('fallback_count',0)}`"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


# ════════════════════════════════════════════════════════════════════════════
#  Jobs
# ════════════════════════════════════════════════════════════════════════════
async def reengage_job(context: ContextTypes.DEFAULT_TYPE):
    """
    S2: Возврат в разговор если человек замолчал до подписки.

    Логика углов атаки:
    - Берём current_angle из storage — знаем где остановились
    - Шлём следующий угол по очереди из _REENGAGE_ANGLES
    - Если дошли до последнего угла — добавляем CTA кнопку
    - После последнего угла больше не беспокоим

    ВАЖНО: используем update_user_no_active чтобы не сбивать last_active.
    Иначе после отправки last_active обновляется, и через 30 минут job снова
    видит 'свежего' пользователя и шлёт тот же угол повторно.
    """
    now = datetime.now(timezone.utc).timestamp()

    for user in get_all_users():
        user_id = user.get("id")
        if not user_id: continue
        if user.get("funnel_stage") not in ("discovery", "warming", "tease", "cta"): continue

        # Не трогаем если уже прошли все углы
        if user.get("reengage_exhausted"): continue

        try:
            lt = datetime.fromisoformat(user.get("last_active", ""))
            if lt.tzinfo is None: lt = lt.replace(tzinfo=timezone.utc)
            silent_hours = (now - lt.timestamp()) / 3600
        except Exception: continue

        # Минимум 4 часа молчания
        if silent_hours < 4:
            continue

        lang     = user.get("lang", "en")
        interest = user.get("interest", "betting")
        geo      = user.get("geo", "OTHER")
        funnel   = user.get("funnel_stage", "warming")

        # Текущий угол атаки — с какого места продолжаем
        current_angle = user.get("current_angle", 0)
        lang_angles   = _REENGAGE_ANGLES.get(lang, _REENGAGE_ANGLES["en"])
        idx           = min(current_angle, len(lang_angles) - 1)
        text          = lang_angles[idx]

        # Последний угол — добавляем CTA кнопку
        is_last = (idx >= len(lang_angles) - 1)
        kb = None
        if is_last:
            try:
                channel_url = await get_channel_link(geo, interest) or "https://t.me/ApuestasGuruES"
                kb = InlineKeyboardMarkup([
                    [InlineKeyboardButton(get_channel_title(geo, interest), url=channel_url)],
                    [InlineKeyboardButton(
                        M.CTA_BUTTON_JOINED.get(lang, "✅ Already in"),
                        callback_data="user_joined")],
                ])
            except Exception:
                kb = _cta_keyboard(lang, interest, geo)

        try:
            await context.bot.send_message(
                chat_id=user_id, text=text,
                parse_mode=ParseMode.MARKDOWN, reply_markup=kb)

            # Двигаем угол вперёд БЕЗ обновления last_active —
            # иначе job через 30 минут снова увидит молчание < 4ч и не пошлёт следующий угол
            next_angle = current_angle + 1
            if is_last:
                update_user_no_active(user_id, current_angle=next_angle,
                                      reengage_exhausted=True)
                logger.info(f"Reengage EXHAUSTED angle={idx} → {user_id}")
            else:
                update_user_no_active(user_id, current_angle=next_angle,
                                      reengage_1_sent=True)
                logger.info(f"Reengage angle={idx} [{funnel}] → {user_id}")

        except TelegramError as e:
            logger.warning(f"Reengage [{user_id}]: {e}")


async def subscribed_push_job(context: ContextTypes.DEFAULT_TYPE):
    """
    Умный silence push — один точечный вопрос если молчат >4 часов.
    """
    for user in get_all_users():
        user_id = user.get("id")
        if not user_id or user.get("funnel_stage") != "subscribed":
            continue

        if not should_send_silence_push(user_id, silence_hours=4.0):
            continue

        lang     = user.get("lang", "en")
        interest = user.get("interest", "betting")
        ftd_done = bool(user.get("ftd_done"))

        text = get_silence_push(lang, ftd_done)
        if not text:
            continue

        try:
            await context.bot.send_chat_action(chat_id=user_id, action="typing")
            await asyncio.sleep(2.0)
            await context.bot.send_message(
                chat_id=user_id, text=text, parse_mode=ParseMode.MARKDOWN)
            add_ai_message(user_id, "assistant", text)
            mark_push_sent(user_id)
            logger.info(f"Silence push → {user_id}")
        except TelegramError as e:
            logger.warning(f"Silence push failed [{user_id}]: {e}")
        except Exception as e:
            logger.error(f"Silence push error [{user_id}]: {e}")


# ════════════════════════════════════════════════════════════════════════════
#  Entry point
# ════════════════════════════════════════════════════════════════════════════
def main():
    token = os.getenv("BOT_TOKEN", BOT_TOKEN)
    if not token:
        logger.error("BOT_TOKEN not set!"); sys.exit(1)

    if ANTHROPIC_KEY:
        logger.info(f"✅ ANTHROPIC_KEY is set ({len(ANTHROPIC_KEY)} chars)")
    else:
        logger.error("❌ ANTHROPIC_KEY is NOT SET — all AI responses will be fallback text!")

    app = Application.builder().token(token).build()

    app.add_handler(CommandHandler("start",           start))
    app.add_handler(CommandHandler("help",            help_command))
    app.add_handler(CommandHandler("stats",           stats_command))
    app.add_handler(CommandHandler("debug",           debug_command))
    app.add_handler(CommandHandler("admin_fetch_ids", admin_fetch_ids))
    app.add_handler(CommandHandler("admin_ab",        admin_ab_stats))

    app.add_handler(CallbackQueryHandler(user_joined,         pattern=r"^user_joined$"))
    app.add_handler(CallbackQueryHandler(calc_deposit_chosen, pattern=r"^calc_dep_"))
    app.add_handler(CallbackQueryHandler(calc_stake_chosen,   pattern=r"^calc_stake_"))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    app.job_queue.run_repeating(reengage_job,         interval=30*60, first=60)
    app.job_queue.run_repeating(subscribed_push_job,  interval=60*60, first=120)
    app.job_queue.run_repeating(daily_signal_job,     interval=60*60, first=300)
    app.job_queue.run_repeating(adrenaline_check_job, interval=15*60, first=180)

    logger.info("OddsVault Bot v14 🚀  Valeria is online.")
    logger.info("Jobs: reengage(30m) / silence_push(1h) / daily_signal(1h) / adrenaline(15m)")
    logger.info("Scenarios: S1-S21 | Modules: conversation + ftd_onboarding + scenarios + daily_signal + adrenaline")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
