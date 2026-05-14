"""
bot.py — OddsVault Bot v8
Новое:
  - Micro-commitment InlineKeyboard на warming этапе (после 1го ответа пользователя)
  - Proactive post-subscription hook (delayed job через 2 мин после "Уже вступил")
  - Тихий сбор профиля в каждом сообщении
  - Re-engage с реальным инфоповодом (если найден) + fallback на статичный
  - CTA не спамит кнопку на каждое сообщение
  - handle_message отвечает на LANG/QUIZ этапах
"""
import asyncio, logging, os, random, sys, atexit
from datetime import datetime, timezone

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.error import TelegramError
from telegram.ext import (Application, CallbackQueryHandler, CommandHandler,
                          ContextTypes, MessageHandler, filters)

from config import (BOT_TOKEN, CHANNELS, FTD_PUSH_EVERY, IMAGE_EVERY_N,
                    INTEREST_IMAGES, REENGAGE_DELAY_1, REENGAGE_DELAY_2, State)
from storage import (add_ai_message, add_tone, get_all_users, get_ai_history,
                     get_user, update_user, mark_push_sent, classify_objection,
                     log_objection, get_objections, update_psychotype, get_psychotype,
                     get_used_techniques, log_technique, get_profile, update_profile)
from ai_agent import (ask_valeria, detect_tone, generate_warm_opener,
                      get_commitment_question, respond_to_commitment,
                      generate_post_sub_hook, generate_reengage_message,
                      extract_profile_update)
import messages as M

logging.basicConfig(format="%(asctime)s [%(levelname)s] %(name)s: %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# ── Lock ──────────────────────────────────────────────────────────────────────
LOCK_FILE = "bot.lock"
def _check_lock():
    if os.path.exists(LOCK_FILE):
        try:
            with open(LOCK_FILE) as f: old_pid = int(f.read().strip())
            os.kill(old_pid, 0)
            logger.error(f"Bot already running (PID {old_pid}). Exiting.")
            sys.exit(1)
        except (ProcessLookupError, ValueError): os.remove(LOCK_FILE)
    with open(LOCK_FILE,"w") as f: f.write(str(os.getpid()))
    atexit.register(lambda: os.path.exists(LOCK_FILE) and os.remove(LOCK_FILE))
_check_lock()

# ── Lang detection ────────────────────────────────────────────────────────────
_TG_LANG_MAP = {"en":"en","es":"es","hr":"hr","lt":"lt","lv":"lv"}
def _detect_lang(code): return _TG_LANG_MAP.get(code.split("-")[0].lower()) if code else None

# ── Utils ─────────────────────────────────────────────────────────────────────
def _typing_delay(text: str) -> float:
    return round(1.5 + min(len(text)/120, 2.0), 1)

async def _send_image(context, chat_id, interest, caption=""):
    images = INTEREST_IMAGES.get(interest) or INTEREST_IMAGES.get("betting",[])
    if not images: return False
    try:
        with open(random.choice(images),"rb") as photo:
            await context.bot.send_photo(chat_id=chat_id, photo=photo,
                caption=caption or None, parse_mode=ParseMode.MARKDOWN if caption else None)
        return True
    except (FileNotFoundError, TelegramError) as e:
        logger.warning(f"Image send failed: {e}"); return False

def _cta_keyboard(lang: str, interest: str) -> InlineKeyboardMarkup:
    ch = CHANNELS.get(lang, CHANNELS.get("en",{})).get(interest, {"url":"https://t.me/ApuestasGuruES"})
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(M.CTA.get(lang, M.CTA.get("en","📲 OddsVault")), url=ch["url"])],
        [InlineKeyboardButton(M.CTA_BUTTON_JOINED.get(lang, M.CTA_BUTTON_JOINED.get("en","✅ Already in")), callback_data="user_joined")],
    ])

def _prepare_context(user_id, user_text):
    obj_type = classify_objection(user_text)
    if obj_type: log_objection(user_id, obj_type)
    return update_psychotype(user_id, user_text), get_objections(user_id), get_used_techniques(user_id)

# ── Stage senders ─────────────────────────────────────────────────────────────
async def _send_tease(bot, user_id, chat_id, lang, interest):
    update_user(user_id, state=State.TEASE, funnel_stage="tease", stage_replies=0)
    tease_text = M.get(M.TEASE, lang, interest)
    await bot.send_chat_action(chat_id, "typing")
    await asyncio.sleep(_typing_delay(tease_text)*0.7)
    await bot.send_message(chat_id=chat_id, text=tease_text, parse_mode=ParseMode.MARKDOWN)

async def _send_cta(bot, user_id, chat_id, lang, interest):
    update_user(user_id, state=State.CTA, funnel_stage="cta")
    cta_text = M.CTA_TEXT.get(lang, M.CTA_TEXT.get("en","🔐 The vault is right there."))
    await bot.send_message(chat_id=chat_id, text=cta_text, parse_mode=ParseMode.MARKDOWN,
                           reply_markup=_cta_keyboard(lang, interest))

# ── /start ────────────────────────────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id    = update.effective_user.id
    first_name = update.effective_user.first_name or ""
    username   = update.effective_user.username   or ""
    tg_lang    = update.effective_user.language_code
    chat_id    = update.effective_chat.id

    update_user(user_id, state=State.QUIZ, funnel_stage="new", first_name=first_name,
                username=username, reengage_1_sent=False, reengage_2_sent=False,
                ai_msg_count=0, stage_replies=0, commitment_sent=False, cta_replies=0)

    auto_lang = _detect_lang(tg_lang)
    if auto_lang:
        update_user(user_id, lang=auto_lang, state=State.QUIZ)
        wake_text = M.WAKE_UP.get(auto_lang, M.WAKE_UP.get("en",""))
        quiz_text = M.QUIZ.get(auto_lang, M.QUIZ.get("en","What interests you most?"))
        buttons   = M.QUIZ_BUTTONS.get(auto_lang, M.QUIZ_BUTTONS.get("en",[]))
        keyboard  = [[InlineKeyboardButton(lbl, callback_data=cb)] for lbl,cb in buttons]
        await context.bot.send_chat_action(chat_id, "typing")
        await asyncio.sleep(1.2)
        await update.message.reply_text(wake_text, parse_mode=ParseMode.MARKDOWN)
        await asyncio.sleep(1.0)
        await context.bot.send_chat_action(chat_id, "typing")
        await asyncio.sleep(1.0)
        await update.message.reply_text(quiz_text, parse_mode=ParseMode.MARKDOWN,
                                        reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        update_user(user_id, state=State.LANG)
        hook_text = M.HOOK.get("en","Hey. I'm Valeria.")
        keyboard  = [[InlineKeyboardButton(lbl, callback_data=cb)] for lbl,cb in M.LANG_BUTTONS]
        await context.bot.send_chat_action(chat_id, "typing")
        await asyncio.sleep(1.5)
        await update.message.reply_text(hook_text, parse_mode=ParseMode.MARKDOWN,
                                        reply_markup=InlineKeyboardMarkup(keyboard))

# ── Callbacks ─────────────────────────────────────────────────────────────────
async def lang_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    lang    = query.data[len("lang_"):]
    user_id = query.from_user.id
    update_user(user_id, lang=lang, state=State.QUIZ)
    quiz_text = M.QUIZ.get(lang, M.QUIZ.get("en","What interests you most?"))
    buttons   = M.QUIZ_BUTTONS.get(lang, M.QUIZ_BUTTONS.get("en",[]))
    keyboard  = [[InlineKeyboardButton(lbl, callback_data=cb)] for lbl,cb in buttons]
    await query.edit_message_text(quiz_text, parse_mode=ParseMode.MARKDOWN,
                                  reply_markup=InlineKeyboardMarkup(keyboard))

async def interest_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Interest → AI opener → WARM1."""
    query = update.callback_query; await query.answer()
    interest = query.data[len("int_"):]
    user_id  = query.from_user.id
    user     = get_user(user_id)
    lang     = user.get("lang","en")
    chat_id  = query.message.chat_id

    update_user(user_id, interest=interest, state=State.WARM1, funnel_stage="warming",
                stage_replies=0, ai_msg_count=0, commitment_sent=False)

    await query.edit_message_text(
        M.QUIZ_ACK.get(lang, M.QUIZ_ACK.get("en","Got it. Give me a moment... ⏳")),
        parse_mode=ParseMode.MARKDOWN)

    await asyncio.sleep(0.5)
    await context.bot.send_chat_action(chat_id, "typing")

    profile = get_profile(user_id)
    opener  = await generate_warm_opener(lang=lang, interest=interest, geo="", user_profile=profile)
    add_ai_message(user_id, "assistant", opener)
    await asyncio.sleep(_typing_delay(opener)*0.6)
    await context.bot.send_message(chat_id=chat_id, text=opener, parse_mode=ParseMode.MARKDOWN)

async def commitment_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """User picked an option in micro-commitment quiz."""
    query    = update.callback_query; await query.answer()
    choice   = query.data[len("cm_"):]  # e.g. "odds", "gut", "stats"
    full_cb  = query.data               # e.g. "cm_odds"
    user_id  = query.from_user.id
    user     = get_user(user_id)
    lang     = user.get("lang","en")
    interest = user.get("interest","betting")
    chat_id  = query.message.chat_id
    history  = get_ai_history(user_id)
    profile  = get_profile(user_id)

    # Mark commitment as done
    update_user(user_id, commitment_sent=True, stage_replies=user.get("stage_replies",0)+1)
    psychotype = get_psychotype(user_id)

    # Edit the question message to show choice was recorded
    chosen_labels = {
        "cm_odds":"📊 Odds movement","cm_gut":"🏆 Instinct","cm_stats":"📰 Stats & form",
        "cm_size":"💰 Bonus size","cm_wager":"🔄 Wagering","cm_time":"⏰ Validity",
        "cm_yes_nd":"✅ Yes, used before","cm_bad_nd":"🔰 Tried, didn't work","cm_never_nd":"❌ Never tried",
        "cm_edge":"📈 Consistent edge","cm_bonus":"🎰 Best bonus","cm_live":"⚡ Live thrill",
    }
    label = chosen_labels.get(full_cb, full_cb)
    try:
        await query.edit_message_reply_markup(reply_markup=None)
    except Exception:
        pass

    await context.bot.send_chat_action(chat_id, "typing")
    response = await respond_to_commitment(
        choice_data=full_cb, lang=lang, interest=interest,
        history=history, psychotype=psychotype, user_profile=profile)
    add_ai_message(user_id, "assistant", response)

    await asyncio.sleep(_typing_delay(response)*0.5)
    await context.bot.send_message(chat_id=chat_id, text=response, parse_mode=ParseMode.MARKDOWN)

    # After commitment, if enough replies → tease
    replies = user.get("stage_replies",0) + 1
    if replies >= 2:
        await asyncio.sleep(2.5)
        await _send_tease(context.bot, user_id, chat_id, lang, interest)

async def user_joined(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Already joined → POST_SUB → schedule proactive hook → AI_CHAT."""
    query = update.callback_query; await query.answer()
    user_id  = query.from_user.id
    user     = get_user(user_id)
    lang     = user.get("lang","en")
    interest = user.get("interest","betting")
    chat_id  = query.message.chat_id

    update_user(user_id, state=State.AI_CHAT, funnel_stage="subscribed")

    await context.bot.send_chat_action(chat_id, "typing")
    await asyncio.sleep(1.5)
    post_text = M.get(M.POST_SUB, lang, interest)
    await context.bot.send_message(chat_id=chat_id, text=post_text, parse_mode=ParseMode.MARKDOWN)

    # Schedule proactive hook in 2 minutes
    geo     = user.get("geo","")
    profile = get_profile(user_id)
    context.job_queue.run_once(
        _proactive_hook_job,
        when=120,  # 2 minutes
        data={"user_id":user_id,"chat_id":chat_id,"lang":lang,"interest":interest,"geo":geo,"profile":profile},
        name=f"hook_{user_id}",
    )

async def _proactive_hook_job(context: ContextTypes.DEFAULT_TYPE):
    """Runs 2 min after subscription — Valeria writes first."""
    d = context.job.data
    user_id, chat_id = d["user_id"], d["chat_id"]
    lang, interest   = d["lang"], d["interest"]
    geo, profile     = d.get("geo",""), d.get("profile",{})

    # Check user didn't already write something
    user = get_user(user_id)
    if user.get("ai_msg_count",0) > 0:
        return  # user already engaged

    try:
        hook = await generate_post_sub_hook(lang=lang, interest=interest,
                                             user_profile=profile, geo=geo)
        await context.bot.send_chat_action(chat_id=chat_id, action="typing")
        await asyncio.sleep(2.0)
        await context.bot.send_message(chat_id=chat_id, text=hook, parse_mode=ParseMode.MARKDOWN)
        add_ai_message(user_id, "assistant", hook)
        mark_push_sent(user_id)
        logger.info(f"Proactive hook → {user_id}")
    except TelegramError as e:
        logger.warning(f"Proactive hook failed [{user_id}]: {e}")
    except Exception as e:
        logger.error(f"Proactive hook error [{user_id}]: {e}")

# ── Main message handler ──────────────────────────────────────────────────────
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text: return
    user_id   = update.effective_user.id
    user      = get_user(user_id)
    state     = user.get("state")
    user_text = update.message.text.strip()

    if state is None:
        await start(update, context); return

    lang     = user.get("lang","en")
    interest = user.get("interest","betting")

    # Silent profile update (fire and forget, don't await to not block response)
    if len(user_text) > 8:
        asyncio.create_task(_update_profile_silent(user_id, user_text, lang))

    if state in (State.LANG, State.QUIZ):
        hints = {"en":"Please choose one of the options above 👆","es":"Por favor elige una de las opciones de arriba 👆","hr":"Molim odaberi jednu od gornjih opcija 👆","lt":"Prašome pasirinkite vieną iš aukščiau esančių variantų 👆","lv":"Lūdzu izvēlies vienu no augstāk esošajām opcijām 👆"}
        await update.message.reply_text(hints.get(lang, hints["en"])); return

    if state in (State.WARM1, State.WARM2):
        await _handle_warming(update, context, user_id, lang, interest, user_text)
    elif state == State.TEASE:
        await _handle_tease(update, context, user_id, lang, interest, user_text)
    elif state == State.CTA:
        await _handle_cta(update, context, user_id, lang, interest, user_text)
    elif state in (State.AI_CHAT, State.SUBSCRIBED):
        await _handle_ai_chat(update, context, user_id, lang, interest, user_text, user)

async def _update_profile_silent(user_id: int, text: str, lang: str):
    """Fire-and-forget profile extraction."""
    try:
        current_profile = get_profile(user_id)
        updates = await extract_profile_update(text, current_profile, lang)
        if updates:
            update_profile(user_id, updates)
            logger.info(f"Profile updated for {user_id}: {updates}")
    except Exception as e:
        logger.debug(f"Profile update error: {e}")

# ── Warming ───────────────────────────────────────────────────────────────────
async def _handle_warming(update, context, user_id, lang, interest, user_text):
    chat_id  = update.effective_chat.id
    history  = get_ai_history(user_id)
    user     = get_user(user_id)
    replies  = user.get("stage_replies",0) + 1
    update_user(user_id, stage_replies=replies)
    forced_next = "tease" if replies >= 3 else None
    psychotype, objections, used_techniques = _prepare_context(user_id, user_text)
    profile = get_profile(user_id)
    await context.bot.send_chat_action(chat_id, "typing")

    response, refined, ai_next, technique_used = await ask_valeria(
        user_message=user_text, history=history, lang=lang, interest=interest,
        funnel_stage="warming", stage_replies=replies, psychotype=psychotype,
        objections=objections, used_techniques=used_techniques, user_profile=profile)

    if technique_used: log_technique(user_id, technique_used)
    next_stage = forced_next if forced_next else ai_next
    add_ai_message(user_id, "user", user_text)
    add_ai_message(user_id, "assistant", response)
    add_tone(user_id, detect_tone(user_text, history))
    if refined != interest: update_user(user_id, interest=refined); interest=refined

    await asyncio.sleep(_typing_delay(response)*0.5)
    await update.message.reply_text(response, parse_mode=ParseMode.MARKDOWN)

    # Micro-commitment: send after first reply if not yet sent
    commitment_sent = user.get("commitment_sent", False)
    if not commitment_sent and replies == 1 and next_stage is None:
        await asyncio.sleep(1.5)
        q = get_commitment_question(lang, interest)
        if q:
            keyboard = [[InlineKeyboardButton(opt["label"], callback_data=opt["data"])]
                        for opt in q["options"]]
            await context.bot.send_message(
                chat_id=chat_id, text=q["text"], parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup(keyboard))
            update_user(user_id, commitment_sent=True)
        return  # Don't advance stage yet — wait for commitment answer

    if next_stage == "tease":
        await asyncio.sleep(2.5)
        await _send_tease(context.bot, user_id, chat_id, lang, interest)
    elif next_stage == "cta":
        await asyncio.sleep(2.5)
        await context.bot.send_chat_action(chat_id,"typing")
        await asyncio.sleep(1.5)
        await _send_cta(context.bot, user_id, chat_id, lang, interest)

# ── Tease ─────────────────────────────────────────────────────────────────────
async def _handle_tease(update, context, user_id, lang, interest, user_text):
    chat_id  = update.effective_chat.id
    history  = get_ai_history(user_id)
    replies  = get_user(user_id).get("stage_replies",0) + 1
    update_user(user_id, stage_replies=replies)
    forced_cta = replies >= 2
    psychotype, objections, used_techniques = _prepare_context(user_id, user_text)
    profile = get_profile(user_id)
    await context.bot.send_chat_action(chat_id, "typing")

    response, refined, ai_next, technique_used = await ask_valeria(
        user_message=user_text, history=history, lang=lang, interest=interest,
        funnel_stage="tease", stage_replies=replies, psychotype=psychotype,
        objections=objections, used_techniques=used_techniques, user_profile=profile)

    if technique_used: log_technique(user_id, technique_used)
    next_stage = "cta" if forced_cta else ai_next
    add_ai_message(user_id, "user", user_text)
    add_ai_message(user_id, "assistant", response)
    add_tone(user_id, detect_tone(user_text, history))
    if refined != interest: update_user(user_id, interest=refined); interest=refined

    await asyncio.sleep(_typing_delay(response)*0.5)
    await update.message.reply_text(response, parse_mode=ParseMode.MARKDOWN)

    if next_stage == "cta":
        await asyncio.sleep(2.5)
        await context.bot.send_chat_action(chat_id,"typing")
        await asyncio.sleep(1.5)
        await _send_cta(context.bot, user_id, chat_id, lang, interest)

# ── CTA ───────────────────────────────────────────────────────────────────────
async def _handle_cta(update, context, user_id, lang, interest, user_text):
    chat_id  = update.effective_chat.id
    history  = get_ai_history(user_id)
    user     = get_user(user_id)
    psychotype, objections, used_techniques = _prepare_context(user_id, user_text)
    profile = get_profile(user_id)
    await context.bot.send_chat_action(chat_id, "typing")

    response, _, ai_next, technique_used = await ask_valeria(
        user_message=user_text, history=history, lang=lang, interest=interest,
        funnel_stage="cta", psychotype=psychotype, objections=objections,
        used_techniques=used_techniques, user_profile=profile)

    if technique_used: log_technique(user_id, technique_used)
    add_ai_message(user_id, "user", user_text)
    add_ai_message(user_id, "assistant", response)
    add_tone(user_id, detect_tone(user_text, history))

    cta_replies = user.get("cta_replies",0) + 1
    update_user(user_id, cta_replies=cta_replies)

    await asyncio.sleep(_typing_delay(response)*0.5)
    await update.message.reply_text(response, parse_mode=ParseMode.MARKDOWN)

    # Show button every other message — not spamming
    if cta_replies % 2 == 1:
        await asyncio.sleep(2.0)
        await context.bot.send_chat_action(chat_id,"typing")
        await asyncio.sleep(1.0)
        await _send_cta(context.bot, user_id, chat_id, lang, interest)

# ── AI Chat (subscribed) ──────────────────────────────────────────────────────
async def _handle_ai_chat(update, context, user_id, lang, interest, user_text, user):
    chat_id      = update.effective_chat.id
    funnel_stage = user.get("funnel_stage","subscribed")
    history      = get_ai_history(user_id)
    msg_count    = user.get("ai_msg_count",0)
    psychotype, objections, used_techniques = _prepare_context(user_id, user_text)
    profile = get_profile(user_id)

    add_ai_message(user_id, "user", user_text)
    await context.bot.send_chat_action(chat_id, "typing")

    response, refined, _, technique_used = await ask_valeria(
        user_message=user_text, history=history, lang=lang, interest=interest,
        funnel_stage=funnel_stage, psychotype=psychotype, objections=objections,
        used_techniques=used_techniques, user_profile=profile)

    if technique_used: log_technique(user_id, technique_used)
    new_count     = msg_count + 1
    update_kwargs = {"ai_msg_count": new_count}

    if refined != interest:
        update_kwargs["interest"] = refined
        shift_key = f"{interest}_to_{refined}"
        shift_msg = M.INTEREST_SHIFT.get(shift_key,{}).get(lang)
        if shift_msg:
            update_user(user_id, **update_kwargs)
            add_ai_message(user_id, "assistant", shift_msg)
            await update.message.reply_text(shift_msg, parse_mode=ParseMode.MARKDOWN)
            return

    update_user(user_id, **update_kwargs)
    add_ai_message(user_id, "assistant", response)
    add_tone(user_id, detect_tone(user_text, history))

    # FTD push every N messages
    if funnel_stage == "subscribed" and new_count % FTD_PUSH_EVERY == 0:
        ftd_text = M.get(M.FTD_PUSH, lang, refined)
        if ftd_text:
            await asyncio.sleep(_typing_delay(response)*0.5)
            await update.message.reply_text(response, parse_mode=ParseMode.MARKDOWN)
            await asyncio.sleep(1.5)
            await context.bot.send_message(chat_id=chat_id, text=ftd_text, parse_mode=ParseMode.MARKDOWN)
            return

    # Image every N messages
    if new_count % IMAGE_EVERY_N == 0:
        if await _send_image(context, chat_id, refined, caption=response): return

    await asyncio.sleep(_typing_delay(response)*0.5)
    await update.message.reply_text(response, parse_mode=ParseMode.MARKDOWN)

# ── /stats ────────────────────────────────────────────────────────────────────
async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    users = get_all_users()
    by_state, by_lang, subscribed = {}, {}, 0
    for u in users:
        s = u.get("state","?"); by_state[s] = by_state.get(s,0)+1
        l = u.get("lang","?");  by_lang[l]  = by_lang.get(l,0)+1
        if u.get("funnel_stage") == "subscribed": subscribed += 1
    text = (f"📊 *OddsVault Stats*\n\nTotal: *{len(users)}*\nSubscribed: *{subscribed}*\n\n"
            f"By state:\n" + "\n".join(f"  {s}: {c}" for s,c in sorted(by_state.items())) +
            f"\n\nBy lang:\n" + "\n".join(f"  {l}: {c}" for l,c in sorted(by_lang.items())))
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

# ── /help ─────────────────────────────────────────────────────────────────────
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_user(update.effective_user.id)
    lang = user.get("lang","en")
    texts = {"en":"ℹ️ I'm Valeria. Use /start to begin.","es":"ℹ️ Soy Valeria. Usa /start para empezar.","hr":"ℹ️ Ja sam Valerija. Koristi /start za početak.","lt":"ℹ️ Aš esu Valerija. Naudok /start pradėti.","lv":"ℹ️ Es esmu Valerija. Izmanto /start lai sāktu."}
    await update.message.reply_text(texts.get(lang, texts["en"]))

# ── Proactive push job (subscribed, silent 6h) ────────────────────────────────
async def subscribed_push_job(context: ContextTypes.DEFAULT_TYPE):
    now, SIX_HOURS = datetime.now(timezone.utc).timestamp(), 6*3600
    for user in get_all_users():
        user_id = user.get("id")
        if not user_id or user.get("funnel_stage") != "subscribed": continue
        last_active_str = user.get("last_active")
        if not last_active_str: continue
        try:
            la = datetime.fromisoformat(last_active_str)
            if la.tzinfo is None: la = la.replace(tzinfo=timezone.utc)
            if now - la.timestamp() < SIX_HOURS: continue
        except Exception: continue
        last_push_str = user.get("last_push_at")
        if last_push_str:
            try:
                lp = datetime.fromisoformat(last_push_str)
                if lp.tzinfo is None: lp = lp.replace(tzinfo=timezone.utc)
                if now - lp.timestamp() < SIX_HOURS: continue
            except Exception: pass

        lang, interest = user.get("lang","en"), user.get("interest","betting")
        geo, profile   = user.get("geo",""), get_profile(user_id)
        history        = get_ai_history(user_id)
        psychotype     = get_psychotype(user_id)
        objections     = get_objections(user_id)
        used_techniques= get_used_techniques(user_id)

        try:
            response, _, _, technique_used = await ask_valeria(
                user_message="[PROACTIVE_PUSH] Generate a short re-engagement hook. Real and current. Do not reference previous conversation.",
                history=history, lang=lang, interest=interest, funnel_stage="subscribed",
                psychotype=psychotype, objections=objections, used_techniques=used_techniques,
                geo=geo, user_profile=profile)
            if technique_used: log_technique(user_id, technique_used)
            await context.bot.send_chat_action(chat_id=user_id, action="typing")
            await asyncio.sleep(2.0)
            await context.bot.send_message(chat_id=user_id, text=response, parse_mode=ParseMode.MARKDOWN)
            add_ai_message(user_id, "assistant", response)
            mark_push_sent(user_id)
            logger.info(f"Proactive push → {user_id}")
        except TelegramError as e: logger.warning(f"Push failed [{user_id}]: {e}")
        except Exception as e: logger.error(f"Push error [{user_id}]: {e}")

# ── Re-engage job ─────────────────────────────────────────────────────────────
async def reengage_job(context: ContextTypes.DEFAULT_TYPE):
    now   = datetime.now(timezone.utc).timestamp()
    users = get_all_users()
    for user in users:
        user_id      = user.get("id")
        if not user_id: continue
        funnel_stage = user.get("funnel_stage","new")
        if funnel_stage in ("new","subscribed"): continue
        if funnel_stage not in ("cta","tease","warming"): continue
        last_active_str = user.get("last_active")
        if not last_active_str: continue
        try:
            lt = datetime.fromisoformat(last_active_str)
            if lt.tzinfo is None: lt = lt.replace(tzinfo=timezone.utc)
            elapsed = now - lt.timestamp()
        except Exception: continue

        lang, interest = user.get("lang","en"), user.get("interest","betting")
        geo, profile   = user.get("geo",""), get_profile(user_id)

        ch = CHANNELS.get(lang, CHANNELS.get("en",{})).get(interest,{"url":"https://t.me/ApuestasGuruES"})
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(M.CTA.get(lang, M.CTA.get("en","📲 OddsVault")), url=ch["url"])],
            [InlineKeyboardButton(M.CTA_BUTTON_JOINED.get(lang, M.CTA_BUTTON_JOINED.get("en","✅")), callback_data="user_joined")],
        ])

        if not user.get("reengage_1_sent") and elapsed >= REENGAGE_DELAY_1:
            # Try AI-generated message with real news hook first
            text = await generate_reengage_message(lang, interest, profile, geo, attempt=1)
            if not text:
                text = M.REENGAGE_1.get(lang, M.REENGAGE_1.get("en",""))
            if not text: continue
            try:
                await context.bot.send_message(chat_id=user_id, text=text,
                    parse_mode=ParseMode.MARKDOWN, reply_markup=keyboard)
                update_user(user_id, reengage_1_sent=True)
                logger.info(f"Re-engage 1 → {user_id}")
            except TelegramError as e: logger.warning(f"Re-engage 1 failed [{user_id}]: {e}")

        elif user.get("reengage_1_sent") and not user.get("reengage_2_sent") and elapsed >= REENGAGE_DELAY_2:
            text = await generate_reengage_message(lang, interest, profile, geo, attempt=2)
            if not text:
                text = M.REENGAGE_2.get(lang, M.REENGAGE_2.get("en",""))
            if not text: continue
            try:
                await context.bot.send_message(chat_id=user_id, text=text,
                    parse_mode=ParseMode.MARKDOWN, reply_markup=keyboard)
                update_user(user_id, reengage_2_sent=True)
                logger.info(f"Re-engage 2 → {user_id}")
            except TelegramError as e: logger.warning(f"Re-engage 2 failed [{user_id}]: {e}")

# ── Entry point ───────────────────────────────────────────────────────────────
def main():
    token = os.getenv("BOT_TOKEN", BOT_TOKEN)
    if not token: logger.error("BOT_TOKEN not set!"); sys.exit(1)
    app = Application.builder().token(token).build()

    app.add_handler(CommandHandler("start",  start))
    app.add_handler(CommandHandler("help",   help_command))
    app.add_handler(CommandHandler("stats",  stats_command))

    app.add_handler(CallbackQueryHandler(lang_chosen,        pattern=r"^lang_"))
    app.add_handler(CallbackQueryHandler(interest_chosen,    pattern=r"^int_"))
    app.add_handler(CallbackQueryHandler(commitment_chosen,  pattern=r"^cm_"))
    app.add_handler(CallbackQueryHandler(user_joined,        pattern=r"^user_joined$"))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    app.job_queue.run_repeating(reengage_job,        interval=30*60, first=60)
    app.job_queue.run_repeating(subscribed_push_job, interval=60*60, first=120)

    logger.info("OddsVault Bot v8 started 🚀  Valeria is online.")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
