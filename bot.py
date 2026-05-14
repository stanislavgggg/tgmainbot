"""
bot.py — OddsVault Bot v10

ИСПРАВЛЕНИЯ:
  1. /start: HOOK (представление Валерии) → пауза → QUIZ. Не объединять в одно.
  2. GEO-квиз: отправляется через send_message (не edit), timeout увеличен
  3. Fallback не повторяется бесконечно: счётчик fallback_count, после 2 → переходим к tease
  4. API key диагностика при старте — видно сразу если не прописан
  5. handle_message логирует каждый входящий запрос для отладки
  6. ask_valeria: логирует реальную ошибку API, не глотает молча
"""
import asyncio, logging, os, random, sys, atexit
from datetime import datetime, timezone
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.error import TelegramError
from telegram.ext import (Application, CallbackQueryHandler, CommandHandler,
                          ContextTypes, MessageHandler, filters)
from config import (BOT_TOKEN, FTD_PUSH_EVERY, IMAGE_EVERY_N, INTEREST_IMAGES,
                    REENGAGE_DELAY_1, REENGAGE_DELAY_2, State)
from storage import (add_ai_message, add_tone, get_all_users, get_ai_history, get_user,
                     update_user, mark_push_sent, classify_objection, log_objection,
                     get_objections, update_psychotype, get_psychotype, get_used_techniques,
                     log_technique, get_profile, update_profile)
from ai_agent import (ask_valeria, detect_tone, generate_warm_opener, get_commitment_question,
                      respond_to_commitment, generate_post_sub_hook, generate_reengage_message,
                      extract_profile_update)
from membership import (check_membership, MemberStatus, resolve_channel, resolve_lang,
                        infer_geo_from_tg_lang, get_channel_link, get_channel_title,
                        GEO_QUIZ, fetch_channel_ids)
import messages as M
from config import ANTHROPIC_KEY

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

# ── Helpers ───────────────────────────────────────────────────────────────────
def _typing_delay(text): return round(1.2 + min(len(text)/140, 2.0), 1)

async def _send_image(context, chat_id, interest, caption=""):
    images = INTEREST_IMAGES.get(interest) or INTEREST_IMAGES.get("betting", [])
    if not images: return False
    try:
        with open(random.choice(images), "rb") as photo:
            await context.bot.send_photo(chat_id=chat_id, photo=photo,
                caption=caption or None, parse_mode=ParseMode.MARKDOWN if caption else None)
        return True
    except (FileNotFoundError, TelegramError) as e:
        logger.warning(f"Image failed: {e}"); return False

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
    return update_psychotype(user_id, user_text), get_objections(user_id), get_used_techniques(user_id)

async def _send_tease(bot, user_id, chat_id, lang, interest):
    update_user(user_id, state=State.TEASE, funnel_stage="tease", stage_replies=0)
    text = M.get(M.TEASE, lang, interest)
    await bot.send_chat_action(chat_id, "typing")
    await asyncio.sleep(_typing_delay(text) * 0.7)
    await bot.send_message(chat_id=chat_id, text=text, parse_mode=ParseMode.MARKDOWN)

async def _send_cta(bot, user_id, chat_id, lang, interest, geo):
    update_user(user_id, state=State.CTA, funnel_stage="cta")
    cta_text = M.CTA_TEXT.get(lang, M.CTA_TEXT.get("en", "🔐 The vault is right there."))
    await bot.send_message(chat_id=chat_id, text=cta_text, parse_mode=ParseMode.MARKDOWN,
                           reply_markup=_cta_keyboard(lang, interest, geo))


# ════════════════════════════════════════════════════════════════════════════
#  /start — HOOK (знакомство) → QUIZ (интерес)
#  ВАЖНО: два отдельных сообщения с паузой между ними
# ════════════════════════════════════════════════════════════════════════════
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id    = update.effective_user.id
    first_name = update.effective_user.first_name or ""
    tg_lang    = update.effective_user.language_code
    chat_id    = update.effective_chat.id

    # Определяем язык из tg_lang (уточним после GEO-квиза)
    geo_hint = infer_geo_from_tg_lang(tg_lang) or "OTHER"
    lang     = resolve_lang(geo_hint, tg_lang)

    update_user(user_id,
        state=State.QUIZ, funnel_stage="new",
        first_name=first_name,
        username=update.effective_user.username or "",
        lang=lang, geo=geo_hint,
        reengage_1_sent=False, reengage_2_sent=False,
        ai_msg_count=0, stage_replies=0,
        commitment_sent=False, cta_replies=0,
        fallback_count=0,
    )

    logger.info(f"START user={user_id} lang={lang} geo={geo_hint} tg_lang={tg_lang}")

    # Шаг 1: HOOK — знакомство с Валерией
    hook_text = M.HOOK.get(lang, M.HOOK.get("en", "Hey. I'm Valeria."))
    await context.bot.send_chat_action(chat_id, "typing")
    await asyncio.sleep(1.5)
    await update.message.reply_text(hook_text, parse_mode=ParseMode.MARKDOWN)

    # Шаг 2: QUIZ — что интересует (пауза для естественности)
    await asyncio.sleep(1.2)
    await context.bot.send_chat_action(chat_id, "typing")
    await asyncio.sleep(1.0)

    quiz_text = M.QUIZ.get(lang, M.QUIZ.get("en", "What interests you most?"))
    btns      = M.QUIZ_BUTTONS.get(lang, M.QUIZ_BUTTONS.get("en", []))
    kb        = [[InlineKeyboardButton(lbl, callback_data=cb)] for lbl, cb in btns]
    await update.message.reply_text(
        quiz_text, parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(kb))


# ════════════════════════════════════════════════════════════════════════════
#  Выбор интереса → GEO-квиз
# ════════════════════════════════════════════════════════════════════════════
async def interest_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query    = update.callback_query
    await query.answer()
    interest = query.data[len("int_"):]
    user_id  = query.from_user.id
    user     = get_user(user_id)
    lang     = user.get("lang", "en")
    chat_id  = query.message.chat_id

    update_user(user_id, interest=interest, state=State.QUIZ)
    logger.info(f"INTEREST user={user_id} interest={interest} lang={lang}")

    # Подтверждение выбора
    ack = M.QUIZ_ACK.get(lang, M.QUIZ_ACK.get("en", "Got it."))
    try:
        await query.edit_message_text(ack, parse_mode=ParseMode.MARKDOWN)
    except Exception:
        pass

    # GEO-квиз — НОВОЕ сообщение (не edit, чтобы точно пришло)
    await asyncio.sleep(0.6)
    await context.bot.send_chat_action(chat_id, "typing")
    await asyncio.sleep(0.8)

    geo_q = GEO_QUIZ.get(lang, GEO_QUIZ["en"])
    kb    = [[InlineKeyboardButton(lbl, callback_data=cb)] for lbl, cb in geo_q["buttons"]]
    await context.bot.send_message(
        chat_id=chat_id,
        text=geo_q["text"],
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(kb))


# ════════════════════════════════════════════════════════════════════════════
#  Выбор ГЕО → AI opener → WARM1
# ════════════════════════════════════════════════════════════════════════════
async def geo_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    await query.answer()
    geo     = query.data[len("geo_"):]
    user_id = query.from_user.id
    user    = get_user(user_id)
    tg_lang = update.effective_user.language_code
    chat_id = query.message.chat_id

    lang     = resolve_lang(geo, tg_lang)
    interest = user.get("interest", "betting")

    update_user(user_id,
        geo=geo, lang=lang,
        state=State.WARM1, funnel_stage="warming",
        stage_replies=0, ai_msg_count=0,
        commitment_sent=False, fallback_count=0)

    logger.info(f"GEO user={user_id} geo={geo} lang={lang} interest={interest}")

    # Подтверждение ГЕО
    geo_ack_map = {
        "ES":    {"es": "🇪🇸 España — perfecto.",           "en": "🇪🇸 Spain — perfect."},
        "HR":    {"hr": "🇭🇷 Hrvatska — odlično.",          "en": "🇭🇷 Croatia — great."},
        "RS":    {"hr": "🇷🇸 Srbija / Balkan — odlično.",   "en": "🇷🇸 Serbia / Balkan — great."},
        "LT":    {"lt": "🇱🇹 Lietuva — puiku.",             "en": "🇱🇹 Lithuania — great."},
        "LV":    {"lv": "🇱🇻 Latvija — lieliski.",          "en": "🇱🇻 Latvia — great."},
        "OTHER": {"en": "🌍 Got it — I'll keep it broad."},
    }
    ack_map  = geo_ack_map.get(geo, geo_ack_map["OTHER"])
    ack_text = ack_map.get(lang, ack_map.get("en", "Got it."))
    try:
        await query.edit_message_text(ack_text, parse_mode=ParseMode.MARKDOWN)
    except Exception:
        pass

    # AI opener
    await asyncio.sleep(0.4)
    await context.bot.send_chat_action(chat_id, "typing")

    profile = get_profile(user_id)
    opener  = await generate_warm_opener(lang=lang, interest=interest, geo=geo, user_profile=profile)
    add_ai_message(user_id, "assistant", opener)

    await asyncio.sleep(_typing_delay(opener) * 0.5)
    await context.bot.send_message(chat_id=chat_id, text=opener, parse_mode=ParseMode.MARKDOWN)


# ════════════════════════════════════════════════════════════════════════════
#  Commitment buttons
# ════════════════════════════════════════════════════════════════════════════
async def commitment_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    await query.answer()
    full_cb = query.data
    user_id = query.from_user.id
    user    = get_user(user_id)
    lang    = user.get("lang", "en")
    interest= user.get("interest", "betting")
    geo     = user.get("geo", "OTHER")
    chat_id = query.message.chat_id

    replies = user.get("stage_replies", 0) + 1
    update_user(user_id, commitment_sent=True, stage_replies=replies)

    try:
        await query.edit_message_reply_markup(reply_markup=None)
    except Exception:
        pass

    await context.bot.send_chat_action(chat_id, "typing")
    response = await respond_to_commitment(
        full_cb, lang, interest, get_ai_history(user_id),
        get_psychotype(user_id), get_profile(user_id))
    add_ai_message(user_id, "assistant", response)

    await asyncio.sleep(_typing_delay(response) * 0.5)
    await context.bot.send_message(chat_id=chat_id, text=response, parse_mode=ParseMode.MARKDOWN)

    # После commitment → tease
    await asyncio.sleep(2.5)
    await _send_tease(context.bot, user_id, chat_id, lang, interest)


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
            chat_id=chat_id,
            text=not_yet.get(lang, not_yet["en"]),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=_cta_keyboard(lang, interest, geo))
        return

    update_user(user_id, state=State.AI_CHAT, funnel_stage="subscribed", verified_member=True)
    await context.bot.send_chat_action(chat_id, "typing")
    await asyncio.sleep(1.5)
    await context.bot.send_message(
        chat_id=chat_id, text=M.get(M.POST_SUB, lang, interest), parse_mode=ParseMode.MARKDOWN)

    profile = get_profile(user_id)
    context.job_queue.run_once(
        _proactive_hook_job, when=120,
        data={"user_id": user_id, "chat_id": chat_id,
              "lang": lang, "interest": interest, "geo": geo, "profile": profile},
        name=f"hook_{user_id}")


async def _proactive_hook_job(context: ContextTypes.DEFAULT_TYPE):
    d = context.job.data
    user_id, chat_id = d["user_id"], d["chat_id"]
    lang, interest, geo, profile = d["lang"], d["interest"], d.get("geo","OTHER"), d.get("profile",{})
    if get_user(user_id).get("ai_msg_count", 0) > 0:
        return
    try:
        hook = await generate_post_sub_hook(lang=lang, interest=interest, user_profile=profile, geo=geo)
        await context.bot.send_chat_action(chat_id=chat_id, action="typing")
        await asyncio.sleep(2.0)
        await context.bot.send_message(chat_id=chat_id, text=hook, parse_mode=ParseMode.MARKDOWN)
        add_ai_message(user_id, "assistant", hook)
        mark_push_sent(user_id)
        logger.info(f"Proactive hook → {user_id}")
    except Exception as e:
        logger.error(f"Hook error [{user_id}]: {e}")


# ════════════════════════════════════════════════════════════════════════════
#  Fallback lang buttons (если показывались)
# ════════════════════════════════════════════════════════════════════════════
async def lang_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    lang  = query.data[len("lang_"):]
    user_id = query.from_user.id
    update_user(user_id, lang=lang, state=State.QUIZ)
    quiz = M.QUIZ.get(lang, M.QUIZ.get("en", "What interests you?"))
    btns = M.QUIZ_BUTTONS.get(lang, M.QUIZ_BUTTONS.get("en", []))
    kb   = [[InlineKeyboardButton(lbl, callback_data=cb)] for lbl, cb in btns]
    await query.edit_message_text(quiz, parse_mode=ParseMode.MARKDOWN,
                                  reply_markup=InlineKeyboardMarkup(kb))


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

    # Silent profile update
    if len(user_text) > 8:
        asyncio.create_task(_update_profile_silent(user_id, user_text, lang))

    if state in (State.LANG, State.QUIZ):
        hints = {
            "en": "Please choose one of the options above 👆",
            "es": "Por favor elige una de las opciones de arriba 👆",
            "hr": "Molim odaberi jednu od gornjih opcija 👆",
            "lt": "Prašome pasirinkite vieną iš aukščiau esančių variantų 👆",
            "lv": "Lūdzu izvēlies vienu no augstāk esošajām opcijām 👆",
        }
        await update.message.reply_text(hints.get(lang, hints["en"]))
        return

    if state in (State.WARM1, State.WARM2):
        await _handle_warming(update, context, user_id, lang, interest, geo, user_text, user)
    elif state == State.TEASE:
        await _handle_tease(update, context, user_id, lang, interest, geo, user_text)
    elif state == State.CTA:
        await _handle_cta(update, context, user_id, lang, interest, geo, user_text)
    elif state in (State.AI_CHAT, State.SUBSCRIBED):
        await _handle_ai_chat(update, context, user_id, lang, interest, geo, user_text, user)


async def _update_profile_silent(user_id, text, lang):
    try:
        updates = await extract_profile_update(text, get_profile(user_id), lang)
        if updates:
            update_profile(user_id, updates)
            logger.info(f"Profile {user_id}: {updates}")
    except Exception as e:
        logger.debug(f"Profile skip: {e}")


# ════════════════════════════════════════════════════════════════════════════
#  WARMING handler
#  Ключевое исправление: если API недоступен (нет ключа) — fallback_count растёт,
#  после 2 fallback'ов принудительно переходим к TEASE с статичным текстом.
# ════════════════════════════════════════════════════════════════════════════
async def _handle_warming(update, context, user_id, lang, interest, geo, user_text, user):
    chat_id  = update.effective_chat.id
    history  = get_ai_history(user_id)
    replies  = user.get("stage_replies", 0) + 1
    update_user(user_id, stage_replies=replies)

    psychotype, objections, used_techniques = _prepare_context(user_id, user_text)
    profile = get_profile(user_id)

    await context.bot.send_chat_action(chat_id, "typing")

    response, refined, ai_next, technique_used = await ask_valeria(
        user_message=user_text, history=history, lang=lang, interest=interest,
        funnel_stage="warming", stage_replies=replies,
        psychotype=psychotype, objections=objections, used_techniques=used_techniques,
        geo=geo, user_profile=profile)

    if technique_used:
        log_technique(user_id, technique_used)

    # Детектируем fallback (нет API key или ошибка)
    is_fallback = _is_fallback_response(response, lang)
    fallback_count = user.get("fallback_count", 0)
    if is_fallback:
        fallback_count += 1
        update_user(user_id, fallback_count=fallback_count)
        logger.warning(f"Fallback response #{fallback_count} for user {user_id} — ANTHROPIC_KEY present: {bool(ANTHROPIC_KEY)}")
    else:
        update_user(user_id, fallback_count=0)

    # После 2 подряд fallback → принудительно tease (не зависаем в петле)
    forced_next = None
    if is_fallback and fallback_count >= 2:
        forced_next = "tease"
        logger.warning(f"Force tease after {fallback_count} fallbacks for user {user_id}")
    elif replies >= 3:
        forced_next = "tease"

    next_stage = forced_next or ai_next

    add_ai_message(user_id, "user", user_text)
    add_ai_message(user_id, "assistant", response)
    add_tone(user_id, detect_tone(user_text, history))

    if refined != interest:
        update_user(user_id, interest=refined)
        interest = refined

    await asyncio.sleep(_typing_delay(response) * 0.5)
    await update.message.reply_text(response, parse_mode=ParseMode.MARKDOWN)

    # Micro-commitment после первого НЕ-fallback ответа
    if not user.get("commitment_sent") and replies == 1 and not is_fallback and next_stage is None:
        await asyncio.sleep(1.5)
        q = get_commitment_question(lang, interest)
        if q:
            kb = [[InlineKeyboardButton(o["label"], callback_data=o["data"])]
                  for o in q["options"]]
            await context.bot.send_message(
                chat_id=chat_id, text=q["text"], parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup(kb))
            update_user(user_id, commitment_sent=True)
        return

    if next_stage == "tease":
        await asyncio.sleep(2.5)
        await _send_tease(context.bot, user_id, chat_id, lang, interest)
    elif next_stage == "cta":
        await asyncio.sleep(2.5)
        await context.bot.send_chat_action(chat_id, "typing")
        await asyncio.sleep(1.5)
        await _send_cta(context.bot, user_id, chat_id, lang, interest, geo)


def _is_fallback_response(response: str, lang: str) -> bool:
    """Определяет что ответ — это fallback (AI недоступен)."""
    # Fallback фразы начинаются с этих паттернов
    fallback_starts = [
        "There are patterns in how lines move",
        "Hay patrones en cómo se mueven",
        "Postoje obrasci u tome kako se kvote",
        "Yra modeliai kaip koeficientai",
        "Ir modeļi kā koeficienti",
    ]
    r = response.strip()
    return any(r.startswith(s) for s in fallback_starts)


# ════════════════════════════════════════════════════════════════════════════
#  TEASE handler
# ════════════════════════════════════════════════════════════════════════════
async def _handle_tease(update, context, user_id, lang, interest, geo, user_text):
    chat_id  = update.effective_chat.id
    history  = get_ai_history(user_id)
    replies  = get_user(user_id).get("stage_replies", 0) + 1
    update_user(user_id, stage_replies=replies)
    forced_cta = replies >= 2
    psychotype, objections, used_techniques = _prepare_context(user_id, user_text)
    profile = get_profile(user_id)

    await context.bot.send_chat_action(chat_id, "typing")
    response, refined, ai_next, technique_used = await ask_valeria(
        user_message=user_text, history=history, lang=lang, interest=interest,
        funnel_stage="tease", stage_replies=replies,
        psychotype=psychotype, objections=objections, used_techniques=used_techniques,
        geo=geo, user_profile=profile)

    if technique_used: log_technique(user_id, technique_used)
    next_stage = "cta" if forced_cta else ai_next
    add_ai_message(user_id, "user", user_text)
    add_ai_message(user_id, "assistant", response)
    add_tone(user_id, detect_tone(user_text, history))
    if refined != interest: update_user(user_id, interest=refined); interest = refined

    await asyncio.sleep(_typing_delay(response) * 0.5)
    await update.message.reply_text(response, parse_mode=ParseMode.MARKDOWN)

    if next_stage == "cta":
        await asyncio.sleep(2.5)
        await context.bot.send_chat_action(chat_id, "typing")
        await asyncio.sleep(1.5)
        await _send_cta(context.bot, user_id, chat_id, lang, interest, geo)


# ════════════════════════════════════════════════════════════════════════════
#  CTA handler
# ════════════════════════════════════════════════════════════════════════════
async def _handle_cta(update, context, user_id, lang, interest, geo, user_text):
    chat_id  = update.effective_chat.id
    history  = get_ai_history(user_id)
    user     = get_user(user_id)
    psychotype, objections, used_techniques = _prepare_context(user_id, user_text)
    profile = get_profile(user_id)

    await context.bot.send_chat_action(chat_id, "typing")
    response, _, ai_next, technique_used = await ask_valeria(
        user_message=user_text, history=history, lang=lang, interest=interest,
        funnel_stage="cta", psychotype=psychotype, objections=objections,
        used_techniques=used_techniques, geo=geo, user_profile=profile)

    if technique_used: log_technique(user_id, technique_used)
    add_ai_message(user_id, "user", user_text)
    add_ai_message(user_id, "assistant", response)
    add_tone(user_id, detect_tone(user_text, history))

    cta_replies = user.get("cta_replies", 0) + 1
    update_user(user_id, cta_replies=cta_replies)

    await asyncio.sleep(_typing_delay(response) * 0.5)
    await update.message.reply_text(response, parse_mode=ParseMode.MARKDOWN)

    if cta_replies % 2 == 1:
        await asyncio.sleep(2.0)
        await context.bot.send_chat_action(chat_id, "typing")
        await asyncio.sleep(1.0)
        await _send_cta(context.bot, user_id, chat_id, lang, interest, geo)


# ════════════════════════════════════════════════════════════════════════════
#  AI Chat (subscribed / FTD mode)
# ════════════════════════════════════════════════════════════════════════════
async def _handle_ai_chat(update, context, user_id, lang, interest, geo, user_text, user):
    chat_id      = update.effective_chat.id
    funnel_stage = user.get("funnel_stage", "subscribed")
    history      = get_ai_history(user_id)
    msg_count    = user.get("ai_msg_count", 0)
    psychotype, objections, used_techniques = _prepare_context(user_id, user_text)
    profile = get_profile(user_id)

    add_ai_message(user_id, "user", user_text)
    await context.bot.send_chat_action(chat_id, "typing")

    response, refined, _, technique_used = await ask_valeria(
        user_message=user_text, history=history, lang=lang, interest=interest,
        funnel_stage=funnel_stage, psychotype=psychotype, objections=objections,
        used_techniques=used_techniques, geo=geo, user_profile=profile)

    if technique_used: log_technique(user_id, technique_used)
    new_count     = msg_count + 1
    update_kwargs = {"ai_msg_count": new_count}

    if refined != interest:
        update_kwargs["interest"] = refined
        shift_msg = M.INTEREST_SHIFT.get(f"{interest}_to_{refined}", {}).get(lang)
        if shift_msg:
            update_user(user_id, **update_kwargs)
            add_ai_message(user_id, "assistant", shift_msg)
            await update.message.reply_text(shift_msg, parse_mode=ParseMode.MARKDOWN)
            return

    update_user(user_id, **update_kwargs)
    add_ai_message(user_id, "assistant", response)
    add_tone(user_id, detect_tone(user_text, history))

    if funnel_stage == "subscribed" and new_count % FTD_PUSH_EVERY == 0:
        ftd = M.get(M.FTD_PUSH, lang, refined)
        if ftd:
            await asyncio.sleep(_typing_delay(response) * 0.5)
            await update.message.reply_text(response, parse_mode=ParseMode.MARKDOWN)
            await asyncio.sleep(1.5)
            await context.bot.send_message(chat_id=chat_id, text=ftd, parse_mode=ParseMode.MARKDOWN)
            return

    if new_count % IMAGE_EVERY_N == 0:
        if await _send_image(context, chat_id, refined, caption=response):
            return

    await asyncio.sleep(_typing_delay(response) * 0.5)
    await update.message.reply_text(response, parse_mode=ParseMode.MARKDOWN)


# ════════════════════════════════════════════════════════════════════════════
#  /stats, /help, /admin_fetch_ids, /debug
# ════════════════════════════════════════════════════════════════════════════
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
    """Диагностика: показывает текущее состояние пользователя и наличие API key."""
    user_id = update.effective_user.id
    user    = get_user(user_id)
    api_ok  = "✅ SET" if ANTHROPIC_KEY else "❌ MISSING — AI responses will be fallback only!"
    text = (
        f"🔧 *Debug info*\n\n"
        f"ANTHROPIC_KEY: {api_ok}\n"
        f"User ID: `{user_id}`\n"
        f"State: `{user.get('state','—')}`\n"
        f"Funnel: `{user.get('funnel_stage','—')}`\n"
        f"Lang: `{user.get('lang','—')}`\n"
        f"GEO: `{user.get('geo','—')}`\n"
        f"Interest: `{user.get('interest','—')}`\n"
        f"Stage replies: `{user.get('stage_replies',0)}`\n"
        f"Fallback count: `{user.get('fallback_count',0)}`\n"
        f"Commitment sent: `{user.get('commitment_sent',False)}`\n"
        f"AI msg count: `{user.get('ai_msg_count',0)}`"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


# ════════════════════════════════════════════════════════════════════════════
#  Jobs
# ════════════════════════════════════════════════════════════════════════════
async def reengage_job(context: ContextTypes.DEFAULT_TYPE):
    now = datetime.now(timezone.utc).timestamp()
    for user in get_all_users():
        user_id = user.get("id")
        if not user_id: continue
        if user.get("funnel_stage","new") in ("new","subscribed"): continue
        if user.get("funnel_stage") not in ("cta","tease","warming"): continue
        try:
            lt = datetime.fromisoformat(user["last_active"])
            if lt.tzinfo is None: lt = lt.replace(tzinfo=timezone.utc)
            elapsed = now - lt.timestamp()
        except Exception: continue

        lang, interest, geo = user.get("lang","en"), user.get("interest","betting"), user.get("geo","OTHER")
        profile = get_profile(user_id)
        channel_url = await get_channel_link(geo, interest) or "https://t.me/ApuestasGuruES"
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton(get_channel_title(geo, interest), url=channel_url)],
            [InlineKeyboardButton(M.CTA_BUTTON_JOINED.get(lang,"✅"), callback_data="user_joined")],
        ])

        if not user.get("reengage_1_sent") and elapsed >= REENGAGE_DELAY_1:
            text = await generate_reengage_message(lang, interest, profile, geo, attempt=1) \
                   or M.REENGAGE_1.get(lang, M.REENGAGE_1.get("en",""))
            if not text: continue
            try:
                await context.bot.send_message(chat_id=user_id, text=text,
                    parse_mode=ParseMode.MARKDOWN, reply_markup=kb)
                update_user(user_id, reengage_1_sent=True)
            except TelegramError as e: logger.warning(f"Re-engage 1 [{user_id}]: {e}")

        elif user.get("reengage_1_sent") and not user.get("reengage_2_sent") and elapsed >= REENGAGE_DELAY_2:
            text = await generate_reengage_message(lang, interest, profile, geo, attempt=2) \
                   or M.REENGAGE_2.get(lang, M.REENGAGE_2.get("en",""))
            if not text: continue
            try:
                await context.bot.send_message(chat_id=user_id, text=text,
                    parse_mode=ParseMode.MARKDOWN, reply_markup=kb)
                update_user(user_id, reengage_2_sent=True)
            except TelegramError as e: logger.warning(f"Re-engage 2 [{user_id}]: {e}")

async def subscribed_push_job(context: ContextTypes.DEFAULT_TYPE):
    now, SIX = datetime.now(timezone.utc).timestamp(), 6*3600
    for user in get_all_users():
        user_id = user.get("id")
        if not user_id or user.get("funnel_stage") != "subscribed": continue
        try:
            la = datetime.fromisoformat(user["last_active"])
            if la.tzinfo is None: la = la.replace(tzinfo=timezone.utc)
            if now - la.timestamp() < SIX: continue
        except Exception: continue
        if user.get("last_push_at"):
            try:
                lp = datetime.fromisoformat(user["last_push_at"])
                if lp.tzinfo is None: lp = lp.replace(tzinfo=timezone.utc)
                if now - lp.timestamp() < SIX: continue
            except Exception: pass

        lang, interest, geo = user.get("lang","en"), user.get("interest","betting"), user.get("geo","OTHER")
        profile = get_profile(user_id); history = get_ai_history(user_id)
        try:
            response, _, _, technique_used = await ask_valeria(
                user_message="[PROACTIVE_PUSH] Short re-engagement hook. Real and current. No reference to previous chat.",
                history=history, lang=lang, interest=interest, funnel_stage="subscribed",
                psychotype=get_psychotype(user_id), objections=get_objections(user_id),
                used_techniques=get_used_techniques(user_id), geo=geo, user_profile=profile)
            if technique_used: log_technique(user_id, technique_used)
            await context.bot.send_chat_action(chat_id=user_id, action="typing")
            await asyncio.sleep(2.0)
            await context.bot.send_message(chat_id=user_id, text=response, parse_mode=ParseMode.MARKDOWN)
            add_ai_message(user_id, "assistant", response)
            mark_push_sent(user_id)
        except TelegramError as e: logger.warning(f"Push failed [{user_id}]: {e}")
        except Exception as e: logger.error(f"Push error [{user_id}]: {e}")


# ════════════════════════════════════════════════════════════════════════════
#  Entry point
# ════════════════════════════════════════════════════════════════════════════
def main():
    token = os.getenv("BOT_TOKEN", BOT_TOKEN)
    if not token:
        logger.error("BOT_TOKEN not set!"); sys.exit(1)

    # Диагностика при старте
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

    app.add_handler(CallbackQueryHandler(lang_chosen,       pattern=r"^lang_"))
    app.add_handler(CallbackQueryHandler(interest_chosen,   pattern=r"^int_"))
    app.add_handler(CallbackQueryHandler(geo_chosen,        pattern=r"^geo_"))
    app.add_handler(CallbackQueryHandler(commitment_chosen, pattern=r"^cm_"))
    app.add_handler(CallbackQueryHandler(user_joined,       pattern=r"^user_joined$"))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    app.job_queue.run_repeating(reengage_job,        interval=30*60, first=60)
    app.job_queue.run_repeating(subscribed_push_job, interval=60*60, first=120)

    logger.info("OddsVault Bot v10 🚀  Valeria is online.")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
