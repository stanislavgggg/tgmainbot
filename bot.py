"""
bot.py — OddsVault Bot
Воронка Белфорта: HOOK → QUIZ → AI_WARMING → AI_TEASE → CTA → AI_CHAT
Каждый шаг воронки генерирует Valeria через Claude.
Нет скриптованных WARM1/WARM2/TEASE — только промпт + реакция на пользователя.

v3: AI-driven funnel — [NEXT:tease] и [NEXT:cta] теги управляют переходами.
"""

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


# ── Язык из Telegram ─────────────────────────────────────────────────────────
_TG_LANG_MAP: dict[str, str] = {
    "en": "en", "es": "es", "hr": "hr", "lt": "lt", "lv": "lv",
}

def _detect_lang(tg_lang_code: str | None) -> str | None:
    if not tg_lang_code:
        return None
    return _TG_LANG_MAP.get(tg_lang_code.split("-")[0].lower())


# ════════════════════════════════════════════════════════════════════════════
#  UTILS
# ════════════════════════════════════════════════════════════════════════════

async def _typing(context: ContextTypes.DEFAULT_TYPE, chat_id: int, seconds: float = 1.8) -> None:
    await context.bot.send_chat_action(chat_id, "typing")
    await asyncio.sleep(seconds)

def _typing_delay(text: str) -> float:
    return round(1.5 + min(len(text) / 120, 2.0), 1)

async def _send_image(context, chat_id: int, interest: str, caption: str = "") -> bool:
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

def _get_cta_keyboard(lang: str, interest: str) -> InlineKeyboardMarkup:
    channel = CHANNELS.get(lang, CHANNELS["en"]).get(interest, CHANNELS["en"]["betting"])
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(M.CTA.get(lang, "📲 OddsVault"), url=channel["url"])],
        [InlineKeyboardButton(M.CTA_BUTTON_JOINED.get(lang, "✅ Already in"), callback_data="user_joined")],
    ])


# ════════════════════════════════════════════════════════════════════════════
#  ВНУТРЕННИЕ ОТПРАВЩИКИ ЭТАПОВ
# ════════════════════════════════════════════════════════════════════════════

async def _deliver_cta(bot, user_id: int, chat_id: int, lang: str, interest: str) -> None:
    """Отправляет CTA-кнопку и переводит state → CTA."""
    update_user(user_id, state=State.CTA, funnel_stage="cta")
    cta_text = M.CTA_TEXT.get(lang, M.CTA_TEXT["en"])
    await bot.send_message(
        chat_id=chat_id,
        text=cta_text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=_get_cta_keyboard(lang, interest),
    )


# ════════════════════════════════════════════════════════════════════════════
#  HANDLERS
# ════════════════════════════════════════════════════════════════════════════

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id    = update.effective_user.id
    first_name = update.effective_user.first_name or ""
    username   = update.effective_user.username   or ""
    tg_lang    = update.effective_user.language_code

    update_user(
        user_id,
        state=State.LANG,
        funnel_stage="new",
        first_name=first_name,
        username=username,
        reengage_1_sent=False,
        reengage_2_sent=False,
        ai_msg_count=0,
        stage_replies=0,
    )

    auto_lang = _detect_lang(tg_lang)
    chat_id   = update.effective_chat.id

    if auto_lang:
        update_user(user_id, lang=auto_lang, state=State.QUIZ)

        wake_text = M.WAKE_UP.get(auto_lang, M.WAKE_UP["en"])
        await context.bot.send_chat_action(chat_id, "typing")
        await asyncio.sleep(_typing_delay(wake_text))
        await update.message.reply_text(wake_text, parse_mode=ParseMode.MARKDOWN)

        await asyncio.sleep(1.5)
        await context.bot.send_chat_action(chat_id, "typing")
        await asyncio.sleep(1.2)

        quiz_text = M.QUIZ.get(auto_lang, M.QUIZ["default"])
        buttons   = M.QUIZ_BUTTONS.get(auto_lang, M.QUIZ_BUTTONS["en"])
        keyboard  = [[InlineKeyboardButton(lbl, callback_data=cb)] for lbl, cb in buttons]

        await update.message.reply_text(
            quiz_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
    else:
        hook_text = M.HOOK.get("en")
        keyboard  = [[InlineKeyboardButton(lbl, callback_data=cb)] for lbl, cb in M.LANG_BUTTONS]

        await context.bot.send_chat_action(chat_id, "typing")
        await asyncio.sleep(1.5)
        await update.message.reply_text(
            hook_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard),
        )


async def lang_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    lang    = query.data[len("lang_"):]
    user_id = query.from_user.id
    update_user(user_id, lang=lang, state=State.QUIZ)

    quiz_text = M.QUIZ.get(lang, M.QUIZ.get("en", M.QUIZ["default"]))
    buttons   = M.QUIZ_BUTTONS.get(lang, M.QUIZ_BUTTONS["en"])
    keyboard  = [[InlineKeyboardButton(lbl, callback_data=cb)] for lbl, cb in buttons]

    await query.edit_message_text(
        text=quiz_text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def interest_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Интерес выбран → AI генерирует первый warming-opener."""
    query    = update.callback_query
    await query.answer()

    interest = query.data[len("int_"):]
    user_id  = query.from_user.id
    user     = get_user(user_id)
    lang     = user.get("lang", "en")
    chat_id  = query.message.chat_id

    update_user(
        user_id,
        interest=interest,
        state=State.WARM1,
        funnel_stage="warming",
        stage_replies=0,
        ai_msg_count=0,
    )

    # Подтверждение выбора
    await query.edit_message_text(
        text=M.QUIZ_ACK.get(lang, "Got it. Give me a moment... ⏳"),
        parse_mode=ParseMode.MARKDOWN,
    )

    await asyncio.sleep(1.2)
    await context.bot.send_chat_action(chat_id, "typing")

    # AI генерирует первый opener
    opener = await generate_warm_opener(lang=lang, interest=interest)

    # Сохраняем в историю как "assistant" (это монолог Valeria)
    add_ai_message(user_id, "assistant", opener)

    await asyncio.sleep(_typing_delay(opener) * 0.7)
    await context.bot.send_message(
        chat_id=chat_id,
        text=opener,
        parse_mode=ParseMode.MARKDOWN,
    )


async def user_joined(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query   = update.callback_query
    await query.answer()

    user_id  = query.from_user.id
    user     = get_user(user_id)
    lang     = user.get("lang", "en")
    interest = user.get("interest", "betting")
    chat_id  = query.message.chat_id

    update_user(user_id, state=State.SUBSCRIBED, funnel_stage="subscribed")

    await context.bot.send_chat_action(chat_id, "typing")
    await asyncio.sleep(1.5)

    post_text = M.get(M.POST_SUB, lang, interest)
    await context.bot.send_message(
        chat_id=chat_id,
        text=post_text,
        parse_mode=ParseMode.MARKDOWN,
    )

    update_user(user_id, state=State.AI_CHAT)


# ════════════════════════════════════════════════════════════════════════════
#  ГЛАВНЫЙ MESSAGE HANDLER — FSM
# ════════════════════════════════════════════════════════════════════════════

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.text:
        return

    user_id   = update.effective_user.id
    user      = get_user(user_id)
    state     = user.get("state")
    user_text = update.message.text.strip()

    if state is None:
        await start(update, context)
        return

    lang     = user.get("lang",     "en")
    interest = user.get("interest", "betting")

    # ── WARM1/WARM2: warming стадия ────────────────────────────────────────
    if state in (State.WARM1, State.WARM2):
        await _handle_funnel_reply(update, context, user_id, lang, interest, user_text, "warming")
        return

    # ── TEASE ──────────────────────────────────────────────────────────────
    if state == State.TEASE:
        await _handle_funnel_reply(update, context, user_id, lang, interest, user_text, "tease")
        return

    # ── CTA: пишет вместо кнопки ───────────────────────────────────────────
    if state == State.CTA:
        await _handle_cta_reply(update, context, user_id, lang, interest, user_text)
        return

    # ── AI_CHAT / SUBSCRIBED ───────────────────────────────────────────────
    if state in (State.AI_CHAT, State.SUBSCRIBED):
        await _handle_ai_chat(update, context, user_id, lang, interest, user_text, user)
        return


# ════════════════════════════════════════════════════════════════════════════
#  УНИВЕРСАЛЬНЫЙ ОБРАБОТЧИК ВОРОНКИ (warming + tease)
# ════════════════════════════════════════════════════════════════════════════

async def _handle_funnel_reply(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    user_id: int,
    lang: str,
    interest: str,
    user_text: str,
    current_stage: str,
) -> None:
    """
    Единый обработчик для warming и tease.
    AI сам решает когда двигаться дальше через [NEXT:tease] / [NEXT:cta].
    """
    chat_id = update.effective_chat.id
    history = get_ai_history(user_id)
    replies = get_user(user_id).get("stage_replies", 0) + 1
    update_user(user_id, stage_replies=replies)

    # Force stage if counter already at limit — override AI decision
    forced_next: str | None = None
    if current_stage == "warming" and replies >= 3:
        forced_next = "tease"
    elif current_stage == "tease" and replies >= 2:
        forced_next = "cta"

    await context.bot.send_chat_action(chat_id, "typing")

    # If forcing transition, tell AI it's already at the boundary
    effective_replies = max(replies, 3) if forced_next == "tease" else (max(replies, 2) if forced_next == "cta" else replies)

    response, refined, next_stage = await ask_valeria(
        user_message=user_text,
        history=history,
        lang=lang,
        interest=interest,
        funnel_stage=current_stage,
        stage_replies=effective_replies,
    )

    # Safety net: forced_next overrides AI
    if forced_next:
        next_stage = forced_next

    add_ai_message(user_id, "user", user_text)
    add_ai_message(user_id, "assistant", response)

    if refined != interest:
        update_user(user_id, interest=refined)
        interest = refined

    await asyncio.sleep(_typing_delay(response) * 0.6)
    await update.message.reply_text(response, parse_mode=ParseMode.MARKDOWN)

    # AI запросил переход к следующему этапу
    if next_stage == "tease" and current_stage == "warming":
        update_user(user_id, state=State.TEASE, funnel_stage="tease", stage_replies=0)
        logger.info(f"User {user_id}: funnel warming → tease")

    elif next_stage == "cta":
        await asyncio.sleep(2.5)
        await context.bot.send_chat_action(chat_id, "typing")
        await asyncio.sleep(1.5)
        await _deliver_cta(context.bot, user_id, chat_id, lang, interest)
        logger.info(f"User {user_id}: funnel {current_stage} → cta")


async def _handle_cta_reply(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    user_id: int,
    lang: str,
    interest: str,
    user_text: str,
) -> None:
    """Пользователь пишет вместо кнопки → AI дожимает + повторяет CTA."""
    chat_id = update.effective_chat.id
    history = get_ai_history(user_id)

    await context.bot.send_chat_action(chat_id, "typing")

    response, _, _ = await ask_valeria(
        user_message=user_text,
        history=history,
        lang=lang,
        interest=interest,
        funnel_stage="cta",
    )

    add_ai_message(user_id, "user", user_text)
    add_ai_message(user_id, "assistant", response)

    await asyncio.sleep(_typing_delay(response) * 0.6)
    await update.message.reply_text(response, parse_mode=ParseMode.MARKDOWN)

    # Повторяем CTA кнопку
    await asyncio.sleep(3.0)
    await context.bot.send_chat_action(chat_id, "typing")
    await asyncio.sleep(1.5)
    await _deliver_cta(context.bot, user_id, chat_id, lang, interest)


async def _handle_ai_chat(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    user_id: int,
    lang: str,
    interest: str,
    user_text: str,
    user: dict,
) -> None:
    """Свободный AI-чат после подписки — FTD-режим."""
    chat_id      = update.effective_chat.id
    funnel_stage = user.get("funnel_stage", "subscribed")
    history      = get_ai_history(user_id)
    msg_count    = user.get("ai_msg_count", 0)

    add_ai_message(user_id, "user", user_text)
    await context.bot.send_chat_action(chat_id, "typing")

    response, refined, _ = await ask_valeria(
        user_message=user_text,
        history=history,
        lang=lang,
        interest=interest,
        funnel_stage=funnel_stage,
    )

    new_count    = msg_count + 1
    update_kwargs: dict = {"ai_msg_count": new_count}

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

    tone = detect_tone(user_text, history)
    add_tone(user_id, tone)

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
        sent = await _send_image(context, chat_id, refined, caption=response)
        if sent:
            return

    await asyncio.sleep(_typing_delay(response) * 0.5)
    await update.message.reply_text(response, parse_mode=ParseMode.MARKDOWN)


# ════════════════════════════════════════════════════════════════════════════
#  /stats
# ════════════════════════════════════════════════════════════════════════════

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    users = get_all_users()
    total = len(users)
    by_state: dict[str, int] = {}
    by_lang:  dict[str, int] = {}
    subscribed = 0

    for u in users:
        s = u.get("state", "unknown")
        by_state[s] = by_state.get(s, 0) + 1
        l = u.get("lang", "?")
        by_lang[l] = by_lang.get(l, 0) + 1
        if u.get("funnel_stage") == "subscribed":
            subscribed += 1

    state_lines = "\n".join(f"  {s}: {c}" for s, c in sorted(by_state.items()))
    lang_lines  = "\n".join(f"  {l}: {c}" for l, c in sorted(by_lang.items()))

    text = (
        f"📊 *OddsVault Stats*\n\n"
        f"Total users: *{total}*\n"
        f"Subscribed: *{subscribed}*\n\n"
        f"By state:\n{state_lines}\n\n"
        f"By lang:\n{lang_lines}"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


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

        if funnel_stage in ("subscribed", "new"):
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

        channel      = CHANNELS.get(lang, CHANNELS["en"]).get(interest, CHANNELS["en"]["betting"])
        joined_label = M.CTA_BUTTON_JOINED.get(lang, "✅")
        cta_label    = M.CTA.get(lang, "📲 OddsVault")

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(cta_label, url=channel["url"])],
            [InlineKeyboardButton(joined_label, callback_data="user_joined")],
        ])

        if not user.get("reengage_1_sent") and elapsed >= REENGAGE_DELAY_1:
            text = M.REENGAGE_1.get(lang, M.REENGAGE_1["en"])
            try:
                await context.bot.send_message(
                    chat_id=user_id, text=text,
                    parse_mode=ParseMode.MARKDOWN, reply_markup=keyboard,
                )
                update_user(user_id, reengage_1_sent=True)
                logger.info(f"Re-engage 1 → {user_id}")
            except TelegramError as e:
                logger.warning(f"Re-engage 1 failed [{user_id}]: {e}")

        elif (user.get("reengage_1_sent")
              and not user.get("reengage_2_sent")
              and elapsed >= REENGAGE_DELAY_2):
            text = M.REENGAGE_2.get(lang, M.REENGAGE_2["en"])
            try:
                await context.bot.send_message(
                    chat_id=user_id, text=text,
                    parse_mode=ParseMode.MARKDOWN, reply_markup=keyboard,
                )
                update_user(user_id, reengage_2_sent=True)
                logger.info(f"Re-engage 2 → {user_id}")
            except TelegramError as e:
                logger.warning(f"Re-engage 2 failed [{user_id}]: {e}")


# ════════════════════════════════════════════════════════════════════════════
#  /help
# ════════════════════════════════════════════════════════════════════════════

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
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
    app.add_handler(CallbackQueryHandler(user_joined,     pattern=r"^user_joined$"))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    app.job_queue.run_repeating(reengage_job, interval=30 * 60, first=60)

    logger.info("OddsVault Bot started 🚀  Valeria is online.")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
