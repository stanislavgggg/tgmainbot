import asyncio
import logging
import os
import random
import sys
import atexit
from datetime import datetime, timezone

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
)
from telegram.constants import ParseMode
from telegram.error import TelegramError
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from config import (
    BOT_TOKEN,
    CHANNELS,
    FTD_PUSH_EVERY,
    IMAGE_EVERY_N,
    INTEREST_IMAGES,
    REENGAGE_DELAY_1,
    REENGAGE_DELAY_2,
    State,
)
from storage import (
    add_ai_message,
    add_tone,
    get_all_users,
    get_ai_history,
    get_user,
    update_user,
    classify_objection,
    log_objection,
    get_objections,
    update_psychotype,
    get_psychotype,
    get_used_techniques,
    log_technique,
)
from ai_agent import ask_valeria, detect_tone, generate_warm_opener
import messages as M

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


# ── Защита от двойного запуска ───────────────────────────────────────────────
LOCK_FILE = "bot.lock"

def _check_lock() -> None:
    if os.path.exists(LOCK_FILE):
        try:
            with open(LOCK_FILE) as f:
                old_pid = int(f.read().strip())
            os.kill(old_pid, 0)
            logger.error(f"Bot already running (PID {old_pid}). Exiting.")
            sys.exit(1)
        except (ProcessLookupError, ValueError):
            os.remove(LOCK_FILE)
    with open(LOCK_FILE, "w") as f:
        f.write(str(os.getpid()))
    atexit.register(lambda: os.path.exists(LOCK_FILE) and os.remove(LOCK_FILE))

_check_lock()


# ── Определение языка из Telegram ────────────────────────────────────────────
_TG_LANG_MAP: dict[str, str] = {
    "en": "en", "es": "es", "hr": "hr", "lt": "lt", "lv": "lv",
}

def _detect_lang(tg_lang_code: str | None) -> str | None:
    if not tg_lang_code:
        return None
    return _TG_LANG_MAP.get(tg_lang_code.split("-")[0].lower())


# ── mark_push_sent (если нет в storage) ─────────────────────────────────────
def mark_push_sent(user_id: int) -> None:
    """Обновляет только last_push_at — не трогает last_active."""
    update_user(
        user_id,
        last_push_at=datetime.now(timezone.utc).isoformat(),
    )


# ════════════════════════════════════════════════════════════════════════════
#  UTILS
# ════════════════════════════════════════════════════════════════════════════

def _typing_delay(text: str) -> float:
    return round(1.5 + min(len(text) / 120, 2.0), 1)


async def _send_image(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    interest: str,
    caption: str = "",
) -> bool:
    images = INTEREST_IMAGES.get(interest) or INTEREST_IMAGES.get("betting", [])
    if not images:
        return False
    try:
        with open(random.choice(images), "rb") as photo:
            await context.bot.send_photo(
                chat_id=chat_id,
                photo=photo,
                caption=caption or None,
                parse_mode=ParseMode.MARKDOWN if caption else None,
            )
        return True
    except (FileNotFoundError, TelegramError) as e:
        logger.warning(f"Image send failed: {e}")
        return False


def _cta_keyboard(lang: str, interest: str) -> InlineKeyboardMarkup:
    ch = CHANNELS.get(lang, CHANNELS["en"]).get(interest, CHANNELS["en"]["betting"])
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(
            M.CTA.get(lang, "📲 OddsVault"),
            url=ch["url"],
        )],
        [InlineKeyboardButton(
            M.CTA_BUTTON_JOINED.get(lang, "✅ Already in"),
            callback_data="user_joined",
        )],
    ])


def _geo_keyboard(lang: str) -> tuple[str, InlineKeyboardMarkup]:
    """
    FIX: заменяет несуществующую M.geo_quiz().
    Простой выбор региона — универсальный для всех интересов.
    """
    prompts = {
        "en": "Where are you based? This helps me find the most relevant offers for you.",
        "es": "¿Dónde estás? Esto me ayuda a encontrar las ofertas más relevantes para ti.",
        "hr": "Gdje si? To mi pomaže pronaći najrelevantnije ponude za tebe.",
        "lt": "Kur esi? Tai padeda man rasti aktualiausius pasiūlymus tau.",
        "lv": "Kur tu esi? Tas man palīdz atrast piemērotākos piedāvājumus.",
    }
    buttons = [
        [InlineKeyboardButton("🇪🇸 España",   callback_data="geo_ES")],
        [InlineKeyboardButton("🇭🇷 Hrvatska", callback_data="geo_HR")],
        [InlineKeyboardButton("🇱🇹 Lietuva",  callback_data="geo_LT")],
        [InlineKeyboardButton("🇱🇻 Latvija",  callback_data="geo_LV")],
        [InlineKeyboardButton("🌍 Other / EU", callback_data="geo_EU")],
    ]
    text = prompts.get(lang, prompts["en"])
    return text, InlineKeyboardMarkup(buttons)


# ════════════════════════════════════════════════════════════════════════════
#  ВСПОМОГАТЕЛЬНАЯ ФУНКЦИЯ: подготовить контекст для ask_valeria
# ════════════════════════════════════════════════════════════════════════════

def _prepare_valeria_context(
    user_id: int,
    user_text: str,
) -> tuple[str, dict[str, int], list[str]]:
    obj_type = classify_objection(user_text)
    if obj_type:
        log_objection(user_id, obj_type)

    psychotype      = update_psychotype(user_id, user_text)
    objections      = get_objections(user_id)
    used_techniques = get_used_techniques(user_id)
    return psychotype, objections, used_techniques


# ════════════════════════════════════════════════════════════════════════════
#  ВНУТРЕННИЕ ОТПРАВЩИКИ ЭТАПОВ
# ════════════════════════════════════════════════════════════════════════════

async def _send_tease(
    bot, user_id: int, chat_id: int, lang: str, interest: str,
) -> None:
    update_user(user_id, state=State.TEASE, funnel_stage="tease", stage_replies=0)
    tease_text = M.get(M.TEASE, lang, interest)
    await bot.send_chat_action(chat_id, "typing")
    await asyncio.sleep(_typing_delay(tease_text) * 0.7)
    await bot.send_message(
        chat_id=chat_id,
        text=tease_text,
        parse_mode=ParseMode.MARKDOWN,
    )
    logger.info(f"User {user_id}: delivered TEASE [{lang}/{interest}]")


async def _send_cta(
    bot, user_id: int, chat_id: int, lang: str, interest: str,
) -> None:
    update_user(user_id, state=State.CTA, funnel_stage="cta")
    cta_text = M.CTA_TEXT.get(lang, M.CTA_TEXT.get("en", "🔐 The vault is right there."))
    await bot.send_message(
        chat_id=chat_id,
        text=cta_text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=_cta_keyboard(lang, interest),
    )
    logger.info(f"User {user_id}: delivered CTA [{lang}/{interest}]")


# ════════════════════════════════════════════════════════════════════════════
#  /start
# ════════════════════════════════════════════════════════════════════════════

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id    = update.effective_user.id
    first_name = update.effective_user.first_name or ""
    username   = update.effective_user.username   or ""
    tg_lang    = update.effective_user.language_code
    chat_id    = update.effective_chat.id

    update_user(
        user_id,
        state=State.QUIZ,
        funnel_stage="new",
        first_name=first_name,
        username=username,
        reengage_1_sent=False,
        reengage_2_sent=False,
        ai_msg_count=0,
        stage_replies=0,
    )

    auto_lang = _detect_lang(tg_lang)

    if auto_lang:
        # Язык определён автоматически — сохраняем и сразу показываем квиз
        update_user(user_id, lang=auto_lang, state=State.QUIZ)

        wake_text = M.WAKE_UP.get(auto_lang, M.WAKE_UP.get("en", ""))
        quiz_text = M.QUIZ.get(auto_lang, M.QUIZ.get("en", "What interests you most?"))
        buttons   = M.QUIZ_BUTTONS.get(auto_lang, M.QUIZ_BUTTONS.get("en", []))
        keyboard  = [[InlineKeyboardButton(lbl, callback_data=cb)] for lbl, cb in buttons]

        await context.bot.send_chat_action(chat_id, "typing")
        await asyncio.sleep(1.2)
        await update.message.reply_text(wake_text, parse_mode=ParseMode.MARKDOWN)

        await asyncio.sleep(1.0)
        await context.bot.send_chat_action(chat_id, "typing")
        await asyncio.sleep(1.0)
        await update.message.reply_text(
            quiz_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
    else:
        # Язык неизвестен — показываем выбор языка
        update_user(user_id, state=State.LANG)
        hook_text = M.HOOK.get("en", "Hey. I'm Valeria.")
        keyboard  = [[InlineKeyboardButton(lbl, callback_data=cb)]
                     for lbl, cb in M.LANG_BUTTONS]

        await context.bot.send_chat_action(chat_id, "typing")
        await asyncio.sleep(1.5)
        await update.message.reply_text(
            hook_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard),
        )


# ════════════════════════════════════════════════════════════════════════════
#  LANG / QUIZ / GEO callback handlers
# ════════════════════════════════════════════════════════════════════════════

async def lang_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    lang    = query.data[len("lang_"):]
    user_id = query.from_user.id
    update_user(user_id, lang=lang, state=State.QUIZ)

    quiz_text = M.QUIZ.get(lang, M.QUIZ.get("en", "What interests you most?"))
    buttons   = M.QUIZ_BUTTONS.get(lang, M.QUIZ_BUTTONS.get("en", []))
    keyboard  = [[InlineKeyboardButton(lbl, callback_data=cb)] for lbl, cb in buttons]

    await query.edit_message_text(
        text=quiz_text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def interest_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Интерес выбран → GEO квиз."""
    query   = update.callback_query
    await query.answer()

    interest = query.data[len("int_"):]
    user_id  = query.from_user.id
    user     = get_user(user_id)
    lang     = user.get("lang", "en")

    # FIX: State.GEO_QUIZ → State.WARM1 (GEO_QUIZ убран, гео собирается здесь)
    update_user(user_id, interest=interest, state=State.WARM1)

    # FIX: _geo_keyboard вместо несуществующей M.geo_quiz()
    geo_text, geo_markup = _geo_keyboard(lang)

    await query.edit_message_text(
        text=geo_text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=geo_markup,
    )


async def geo_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Гео выбрано → AI opener → WARM1."""
    query   = update.callback_query
    await query.answer()

    geo      = query.data[len("geo_"):]
    user_id  = query.from_user.id
    user     = get_user(user_id)
    lang     = user.get("lang", "en")
    interest = user.get("interest", "betting")
    chat_id  = query.message.chat_id

    update_user(
        user_id,
        geo=geo,
        state=State.WARM1,
        funnel_stage="warming",
        stage_replies=0,
        ai_msg_count=0,
    )

    await query.edit_message_text(
        text=M.QUIZ_ACK.get(lang, "Got it. Give me a moment... ⏳"),
        parse_mode=ParseMode.MARKDOWN,
    )

    await asyncio.sleep(1.0)
    await context.bot.send_chat_action(chat_id, "typing")

    opener = await generate_warm_opener(lang=lang, interest=interest, geo=geo)
    add_ai_message(user_id, "assistant", opener)

    await asyncio.sleep(_typing_delay(opener) * 0.6)
    await context.bot.send_message(
        chat_id=chat_id,
        text=opener,
        parse_mode=ParseMode.MARKDOWN,
    )


async def user_joined(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """«Уже вступил» → POST_SUB → AI_CHAT."""
    query   = update.callback_query
    await query.answer()

    user_id  = query.from_user.id
    user     = get_user(user_id)
    lang     = user.get("lang", "en")
    interest = user.get("interest", "betting")
    chat_id  = query.message.chat_id

    update_user(
        user_id,
        state=State.AI_CHAT,
        funnel_stage="subscribed",
    )

    await context.bot.send_chat_action(chat_id, "typing")
    await asyncio.sleep(1.5)

    post_text = M.get(M.POST_SUB, lang, interest)
    await context.bot.send_message(
        chat_id=chat_id,
        text=post_text,
        parse_mode=ParseMode.MARKDOWN,
    )


# ════════════════════════════════════════════════════════════════════════════
#  ГЛАВНЫЙ MESSAGE HANDLER — FSM диспетчер
# ════════════════════════════════════════════════════════════════════════════

async def handle_message(
    update: Update, context: ContextTypes.DEFAULT_TYPE,
) -> None:
    if not update.message or not update.message.text:
        return

    user_id   = update.effective_user.id
    user      = get_user(user_id)
    state     = user.get("state")
    user_text = update.message.text.strip()

    if state is None:
        await start(update, context)
        return

    lang     = user.get("lang", "en")
    interest = user.get("interest", "betting")

    if state in (State.WARM1, State.WARM2):
        await _handle_warming(update, context, user_id, lang, interest, user_text)
    elif state == State.TEASE:
        await _handle_tease(update, context, user_id, lang, interest, user_text)
    elif state == State.CTA:
        await _handle_cta(update, context, user_id, lang, interest, user_text)
    elif state in (State.AI_CHAT, State.SUBSCRIBED):
        await _handle_ai_chat(update, context, user_id, lang, interest, user_text, user)
    # State.LANG, State.QUIZ, State.WARM1 без текста — ждём кнопку, игнорируем


# ════════════════════════════════════════════════════════════════════════════
#  WARMING — WARM1 / WARM2
# ════════════════════════════════════════════════════════════════════════════

async def _handle_warming(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    user_id: int,
    lang: str,
    interest: str,
    user_text: str,
) -> None:
    chat_id = update.effective_chat.id
    history = get_ai_history(user_id)
    replies = get_user(user_id).get("stage_replies", 0) + 1
    update_user(user_id, stage_replies=replies)

    forced_next = "tease" if replies >= 3 else None

    psychotype, objections, used_techniques = _prepare_valeria_context(user_id, user_text)

    await context.bot.send_chat_action(chat_id, "typing")

    response, refined, ai_next, technique_used = await ask_valeria(
        user_message=user_text,
        history=history,
        lang=lang,
        interest=interest,
        funnel_stage="warming",
        stage_replies=replies,
        psychotype=psychotype,
        objections=objections,
        used_techniques=used_techniques,
    )

    if technique_used:
        log_technique(user_id, technique_used)

    next_stage = forced_next if forced_next else ai_next

    add_ai_message(user_id, "user", user_text)
    add_ai_message(user_id, "assistant", response)
    add_tone(user_id, detect_tone(user_text, history))

    if refined != interest:
        update_user(user_id, interest=refined)
        interest = refined

    await asyncio.sleep(_typing_delay(response) * 0.5)
    await update.message.reply_text(response, parse_mode=ParseMode.MARKDOWN)

    if next_stage == "tease":
        await asyncio.sleep(2.5)
        await _send_tease(context.bot, user_id, chat_id, lang, interest)
    elif next_stage == "cta":
        await asyncio.sleep(2.5)
        await context.bot.send_chat_action(chat_id, "typing")
        await asyncio.sleep(1.5)
        await _send_cta(context.bot, user_id, chat_id, lang, interest)


# ════════════════════════════════════════════════════════════════════════════
#  TEASE
# ════════════════════════════════════════════════════════════════════════════

async def _handle_tease(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    user_id: int,
    lang: str,
    interest: str,
    user_text: str,
) -> None:
    chat_id = update.effective_chat.id
    history = get_ai_history(user_id)
    replies = get_user(user_id).get("stage_replies", 0) + 1
    update_user(user_id, stage_replies=replies)

    forced_cta = replies >= 2

    psychotype, objections, used_techniques = _prepare_valeria_context(user_id, user_text)

    await context.bot.send_chat_action(chat_id, "typing")

    response, refined, ai_next, technique_used = await ask_valeria(
        user_message=user_text,
        history=history,
        lang=lang,
        interest=interest,
        funnel_stage="tease",
        stage_replies=replies,
        psychotype=psychotype,
        objections=objections,
        used_techniques=used_techniques,
    )

    if technique_used:
        log_technique(user_id, technique_used)

    next_stage = "cta" if forced_cta else ai_next

    add_ai_message(user_id, "user", user_text)
    add_ai_message(user_id, "assistant", response)
    add_tone(user_id, detect_tone(user_text, history))

    if refined != interest:
        update_user(user_id, interest=refined)
        interest = refined

    await asyncio.sleep(_typing_delay(response) * 0.5)
    await update.message.reply_text(response, parse_mode=ParseMode.MARKDOWN)

    if next_stage == "cta":
        await asyncio.sleep(2.5)
        await context.bot.send_chat_action(chat_id, "typing")
        await asyncio.sleep(1.5)
        await _send_cta(context.bot, user_id, chat_id, lang, interest)


# ════════════════════════════════════════════════════════════════════════════
#  CTA — пишет вместо кнопки
# ════════════════════════════════════════════════════════════════════════════

async def _handle_cta(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    user_id: int,
    lang: str,
    interest: str,
    user_text: str,
) -> None:
    chat_id = update.effective_chat.id
    history = get_ai_history(user_id)

    psychotype, objections, used_techniques = _prepare_valeria_context(user_id, user_text)

    await context.bot.send_chat_action(chat_id, "typing")

    response, _, ai_next, technique_used = await ask_valeria(
        user_message=user_text,
        history=history,
        lang=lang,
        interest=interest,
        funnel_stage="cta",
        psychotype=psychotype,
        objections=objections,
        used_techniques=used_techniques,
    )

    if technique_used:
        log_technique(user_id, technique_used)

    add_ai_message(user_id, "user", user_text)
    add_ai_message(user_id, "assistant", response)
    add_tone(user_id, detect_tone(user_text, history))

    await asyncio.sleep(_typing_delay(response) * 0.5)
    await update.message.reply_text(response, parse_mode=ParseMode.MARKDOWN)

    await asyncio.sleep(3.0)
    await context.bot.send_chat_action(chat_id, "typing")
    await asyncio.sleep(1.2)
    await _send_cta(context.bot, user_id, chat_id, lang, interest)


# ════════════════════════════════════════════════════════════════════════════
#  AI_CHAT — свободный чат после подписки
# ════════════════════════════════════════════════════════════════════════════

async def _handle_ai_chat(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    user_id: int,
    lang: str,
    interest: str,
    user_text: str,
    user: dict,
) -> None:
    chat_id      = update.effective_chat.id
    funnel_stage = user.get("funnel_stage", "subscribed")
    history      = get_ai_history(user_id)
    msg_count    = user.get("ai_msg_count", 0)

    psychotype, objections, used_techniques = _prepare_valeria_context(user_id, user_text)

    add_ai_message(user_id, "user", user_text)
    await context.bot.send_chat_action(chat_id, "typing")

    response, refined, _, technique_used = await ask_valeria(
        user_message=user_text,
        history=history,
        lang=lang,
        interest=interest,
        funnel_stage=funnel_stage,
        psychotype=psychotype,
        objections=objections,
        used_techniques=used_techniques,
    )

    if technique_used:
        log_technique(user_id, technique_used)

    new_count     = msg_count + 1
    update_kwargs = {"ai_msg_count": new_count}

    # Сдвиг интереса
    if refined != interest:
        update_kwargs["interest"] = refined
        logger.info(f"User {user_id}: interest {interest} → {refined}")
        shift_key = f"{interest}_to_{refined}"
        shift_msg = M.INTEREST_SHIFT.get(shift_key, {}).get(lang)
        if shift_msg:
            update_user(user_id, **update_kwargs)
            add_ai_message(user_id, "assistant", shift_msg)
            await update.message.reply_text(shift_msg, parse_mode=ParseMode.MARKDOWN)
            return

    update_user(user_id, **update_kwargs)
    add_ai_message(user_id, "assistant", response)
    add_tone(user_id, detect_tone(user_text, history))

    # FTD-пуш каждые N сообщений
    if funnel_stage == "subscribed" and new_count % FTD_PUSH_EVERY == 0:
        ftd_text = M.get(M.FTD_PUSH, lang, refined)
        if ftd_text:
            await asyncio.sleep(_typing_delay(response) * 0.5)
            await update.message.reply_text(response, parse_mode=ParseMode.MARKDOWN)
            await asyncio.sleep(1.5)
            await context.bot.send_message(
                chat_id=chat_id,
                text=ftd_text,
                parse_mode=ParseMode.MARKDOWN,
            )
            return

    # Картинка каждые IMAGE_EVERY_N сообщений
    if new_count % IMAGE_EVERY_N == 0:
        if await _send_image(context, chat_id, refined, caption=response):
            return

    await asyncio.sleep(_typing_delay(response) * 0.5)
    await update.message.reply_text(response, parse_mode=ParseMode.MARKDOWN)


# ════════════════════════════════════════════════════════════════════════════
#  /stats
# ════════════════════════════════════════════════════════════════════════════

async def stats_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE,
) -> None:
    users      = get_all_users()
    by_state:  dict[str, int] = {}
    by_lang:   dict[str, int] = {}
    subscribed = 0

    for u in users:
        s = u.get("state", "unknown")
        by_state[s] = by_state.get(s, 0) + 1
        l = u.get("lang", "?")
        by_lang[l]  = by_lang.get(l, 0) + 1
        if u.get("funnel_stage") == "subscribed":
            subscribed += 1

    state_lines = "\n".join(f"  {s}: {c}" for s, c in sorted(by_state.items()))
    lang_lines  = "\n".join(f"  {l}: {c}" for l, c in sorted(by_lang.items()))

    text = (
        f"📊 *OddsVault Stats*\n\n"
        f"Total users: *{len(users)}*\n"
        f"Subscribed: *{subscribed}*\n\n"
        f"By state:\n{state_lines}\n\n"
        f"By lang:\n{lang_lines}"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


# ════════════════════════════════════════════════════════════════════════════
#  PROACTIVE PUSH
# ════════════════════════════════════════════════════════════════════════════

async def subscribed_push_job(
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    now       = datetime.now(timezone.utc).timestamp()
    SIX_HOURS = 6 * 3600

    for user in get_all_users():
        user_id      = user.get("id")
        funnel_stage = user.get("funnel_stage", "new")
        if funnel_stage != "subscribed":
            continue

        # 1. Юзер молчит ≥ 6 ч
        last_active_str = user.get("last_active")
        if not last_active_str:
            continue
        try:
            last_active_ts = datetime.fromisoformat(last_active_str)
            if last_active_ts.tzinfo is None:
                last_active_ts = last_active_ts.replace(tzinfo=timezone.utc)
            if now - last_active_ts.timestamp() < SIX_HOURS:
                continue
        except Exception:
            continue

        # 2. Последний пуш был ≥ 6 ч назад
        last_push_str = user.get("last_push_at")
        if last_push_str
        :try:
                last_push_ts = datetime.fromisoformat(last_push_str)
                if last_push_ts.tzinfo is None:
                    last_push_ts = last_push_ts.replace(tzinfo=timezone.utc)
                if now - last_push_ts.timestamp() < SIX_HOURS:
                    continue
            except Exception:
                pass

        lang            = user.get("lang", "en")
        interest        = user.get("interest", "betting")
        history         = get_ai_history(user_id)
        psychotype      = get_psychotype(user_id)
        objections      = get_objections(user_id)
        used_techniques = get_used_techniques(user_id)

        try:
            response, _, _, technique_used = await ask_valeria(
                user_message=(
                    "[PROACTIVE_PUSH] Generate a short re-engagement hook. "
                    "Find something real and current. "
                    "Do not reference previous conversation."
                ),
                history=history,
                lang=lang,
                interest=interest,
                funnel_stage="subscribed",
                psychotype=psychotype,
                objections=objections,
                used_techniques=used_techniques,
            )
            if technique_used:
                log_technique(user_id, technique_used)

            await context.bot.send_chat_action(chat_id=user_id, action="typing")
            await asyncio.sleep(2.0)
            await context.bot.send_message(
                chat_id=user_id,
                text=response,
                parse_mode=ParseMode.MARKDOWN,
            )
            add_ai_message(user_id, "assistant", response)
            mark_push_sent(user_id)
            logger.info(f"Proactive push → {user_id}")
        except TelegramError as e:
            logger.warning(f"Proactive push failed [{user_id}]: {e}")
        except Exception as e:
            logger.error(f"Proactive push error [{user_id}]: {e}")


# ════════════════════════════════════════════════════════════════════════════
#  RE-ENGAGE JOB
# ════════════════════════════════════════════════════════════════════════════

async def reengage_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    now   = datetime.now(timezone.utc).timestamp()
    users = get_all_users()

    for user in users:
        user_id      = user.get("id")
        funnel_stage = user.get("funnel_stage", "new")
        lang         = user.get("lang", "en")
        interest     = user.get("interest", "betting")

        if funnel_stage in ("new", "subscribed"):
            continue
        if funnel_stage not in ("cta", "tease", "warming"):
            continue

        last_active_str = user.get("last_active")
        if not last_active_str:
            continue

        try:
            last_ts = datetime.fromisoformat(last_active_str)
            if last_ts.tzinfo is None:
                last_ts = last_ts.replace(tzinfo=timezone.utc)
            elapsed = now - last_ts.timestamp()
        except Exception:
            continue

        ch = (
            CHANNELS.get(lang, CHANNELS["en"])
            .get(interest, CHANNELS["en"]["betting"])
        )
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(
                M.CTA.get(lang, "📲 OddsVault"),
                url=ch["url"],
            )],
            [InlineKeyboardButton(
                M.CTA_BUTTON_JOINED.get(lang, "✅"),
                callback_data="user_joined",
            )],
        ])

        if not user.get("reengage_1_sent") and elapsed >= REENGAGE_DELAY_1:
            text = M.REENGAGE_1.get(lang, M.REENGAGE_1.get("en", ""))
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=text,
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=keyboard,
                )
                update_user(user_id, reengage_1_sent=True)
                logger.info(f"Re-engage 1 → {user_id}")
            except TelegramError as e:
                logger.warning(f"Re-engage 1 failed [{user_id}]: {e}")

        elif (
            user.get("reengage_1_sent")
            and not user.get("reengage_2_sent")
            and elapsed >= REENGAGE_DELAY_2
        ):
            text = M.REENGAGE_2.get(lang, M.REENGAGE_2.get("en", ""))
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=text,
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=keyboard,
                )
                update_user(user_id, reengage_2_sent=True)
                logger.info(f"Re-engage 2 → {user_id}")
            except TelegramError as e:
                logger.warning(f"Re-engage 2 failed [{user_id}]: {e}")


# ════════════════════════════════════════════════════════════════════════════
#  /help
# ════════════════════════════════════════════════════════════════════════════

async def help_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE,
) -> None:
    user = get_user(update.effective_user.id)
    lang = user.get("lang", "en")
    texts = {
        "en": "ℹ️ I'm Valeria. Use /start to begin.",
        "es": "ℹ️ Soy Valeria. Usa /start para empezar.",
        "hr": "ℹ️ Ja sam Valerija. Koristi /start za početak.",
        "lt": "ℹ️ Aš esu Valerija. Naudok /start pradėti.",
        "lv": "ℹ️ Es esmu Valerija. Izmanto /start lai sāktu.",
    }
    await update.message.reply_text(texts.get(lang, texts["en"]))


# ════════════════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ════════════════════════════════════════════════════════════════════════════

def main() -> None:
    token = os.getenv("BOT_TOKEN", BOT_TOKEN)
    app   = Application.builder().token(token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help",  help_command))
    app.add_handler(CommandHandler("stats", stats_command))

    app.add_handler(CallbackQueryHandler(lang_chosen,     pattern=r"^lang_"))
    app.add_handler(CallbackQueryHandler(interest_chosen, pattern=r"^int_"))
    app.add_handler(CallbackQueryHandler(geo_chosen,      pattern=r"^geo_"))
    app.add_handler(CallbackQueryHandler(user_joined,     pattern=r"^user_joined$"))

    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND, handle_message,
    ))

    app.job_queue.run_repeating(reengage_job,        interval=30 * 60, first=60)
    app.job_queue.run_repeating(subscribed_push_job, interval=60 * 60, first=120)

    logger.info("OddsVault Bot v6.0 started 🚀  Valeria is online.")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
