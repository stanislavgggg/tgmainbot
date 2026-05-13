"""
bot.py — OddsVault Bot
Воронка Белфорта: HOOK → QUIZ → WARM1 → (ждём) → WARM2 → (ждём) → TEASE → (ждём) → CTA
После подписки: AI_CHAT с FTD-пушами.
Re-engage: 24ч и 48ч если не подписался.
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
from ai_agent import ask_valeria, detect_tone
import messages as M

# ── Логгер ──────────────────────────────────────────────────────────────────
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


# ════════════════════════════════════════════════════════════════════════════
#  UTILS
# ════════════════════════════════════════════════════════════════════════════

async def _typing(context: ContextTypes.DEFAULT_TYPE, chat_id: int, seconds: float = 1.5) -> None:
    await context.bot.send_chat_action(chat_id, "typing")
    await asyncio.sleep(seconds)


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


def _get_cta_keyboard(lang: str, interest: str) -> InlineKeyboardMarkup:
    channel = CHANNELS.get(lang, CHANNELS["es"]).get(interest, CHANNELS["es"]["betting"])
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(M.CTA.get(lang, "📲 OddsVault"), url=channel["url"])],
        [InlineKeyboardButton(M.CTA_BUTTON_JOINED.get(lang, "✅ Already in"), callback_data="user_joined")],
    ])


# ════════════════════════════════════════════════════════════════════════════
#  ШАГИ ВОРОНКИ — внутренние отправщики
# ════════════════════════════════════════════════════════════════════════════

async def _deliver_warm2(bot, user_id: int, chat_id: int, lang: str) -> None:
    """Отправляет WARM2 и переводит state → WARM2."""
    update_user(user_id, state=State.WARM2)
    text = M.get(M.WARM2, lang)
    await bot.send_message(chat_id=chat_id, text=text, parse_mode=ParseMode.MARKDOWN)


async def _deliver_tease(bot, user_id: int, chat_id: int, lang: str, interest: str) -> None:
    """Отправляет TEASE и переводит state → TEASE."""
    update_user(user_id, state=State.TEASE, funnel_stage="tease")
    text = M.get(M.TEASE, lang, interest)
    await bot.send_message(chat_id=chat_id, text=text, parse_mode=ParseMode.MARKDOWN)


async def _deliver_cta(bot, user_id: int, chat_id: int, lang: str, interest: str) -> None:
    """Отправляет CTA-кнопку и переводит state → CTA."""
    update_user(user_id, state=State.CTA, funnel_stage="cta")
    cta_text = M.CTA_TEXT.get(lang, M.CTA_TEXT["es"])
    await bot.send_message(
        chat_id=chat_id,
        text=cta_text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=_get_cta_keyboard(lang, interest),
    )


# ════════════════════════════════════════════════════════════════════════════
#  HANDLERS — воронка
# ════════════════════════════════════════════════════════════════════════════

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/start — крючок + выбор языка."""
    user_id    = update.effective_user.id
    first_name = update.effective_user.first_name or ""
    username   = update.effective_user.username   or ""

    update_user(
        user_id,
        state=State.LANG,
        funnel_stage="new",
        first_name=first_name,
        username=username,
        # Сброс флагов повторного взаимодействия
        reengage_1_sent=False,
        reengage_2_sent=False,
    )

    hook_text = M.HOOK.get("es")          # language-агностичный крючок
    keyboard  = [[InlineKeyboardButton(lbl, callback_data=cb)] for lbl, cb in M.LANG_BUTTONS]

    await update.message.reply_text(
        hook_text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def lang_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Язык выбран → квиз."""
    query = update.callback_query
    await query.answer()

    lang    = query.data.split("_")[1]   # es / hr / lt / lv
    user_id = query.from_user.id

    update_user(user_id, lang=lang, state=State.QUIZ)

    quiz_text = M.QUIZ.get(lang, M.QUIZ["default"])
    buttons   = M.QUIZ_BUTTONS.get(lang, M.QUIZ_BUTTONS["es"])
    keyboard  = [[InlineKeyboardButton(lbl, callback_data=cb)] for lbl, cb in buttons]

    await query.edit_message_text(
        text=quiz_text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def interest_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Интерес выбран → WARM1 и ждём реакцию пользователя."""
    query    = update.callback_query
    await query.answer()

    interest = query.data.split("_")[1]   # betting / casino / nodeposit / exclusive
    user_id  = query.from_user.id
    user     = get_user(user_id)
    lang     = user.get("lang", "es")

    update_user(user_id, interest=interest, state=State.WARM1, funnel_stage="warming")

    warm1_text = M.get(M.WARM1, lang, interest)
    await query.edit_message_text(text=warm1_text, parse_mode=ParseMode.MARKDOWN)

    # ──  Ждём реакции пользователя  ──
    # handle_message перехватит следующее сообщение в состоянии WARM1


async def user_joined(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Нажал «Уже вступил» → POST_SUB → AI_CHAT."""
    query   = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    user    = get_user(user_id)
    lang    = user.get("lang", "es")
    interest= user.get("interest", "betting")

    update_user(user_id, state=State.SUBSCRIBED, funnel_stage="subscribed")

    post_text = M.get(M.POST_SUB, lang, interest)
    await query.edit_message_text(text=post_text, parse_mode=ParseMode.MARKDOWN)

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

    # Новый пользователь без state
    if state is None:
        await start(update, context)
        return

    lang     = user.get("lang",     "es")
    interest = user.get("interest", "betting")

    # ── WARM1: пользователь ответил на первый прогрев ──────────────────────
    if state == State.WARM1:
        await _handle_warm1_reply(update, context, user_id, lang, interest, user_text)
        return

    # ── WARM2: пользователь ответил на второй прогрев ─────────────────────
    if state == State.WARM2:
        await _handle_warm2_reply(update, context, user_id, lang, interest, user_text)
        return

    # ── TEASE: пользователь ответил на тизер ──────────────────────────────
    if state == State.TEASE:
        await _handle_tease_reply(update, context, user_id, lang, interest, user_text)
        return

    # ── CTA: пользователь пишет вместо того чтобы нажать ─────────────────
    if state == State.CTA:
        await _handle_cta_reply(update, context, user_id, lang, interest, user_text)
        return

    # ── AI_CHAT / SUBSCRIBED: свободный чат ───────────────────────────────
    if state in (State.AI_CHAT, State.SUBSCRIBED):
        await _handle_ai_chat(update, context, user_id, lang, interest, user_text, user)
        return


# ════════════════════════════════════════════════════════════════════════════
#  ОБРАБОТЧИКИ КАЖДОГО ШАГА ВОРОНКИ
# ════════════════════════════════════════════════════════════════════════════

async def _handle_warm1_reply(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    user_id: int, lang: str, interest: str, user_text: str,
) -> None:
    """Пользователь ответил на WARM1 → AI реагирует → пауза → WARM2."""
    chat_id = update.effective_chat.id
    history = get_ai_history(user_id)

    await context.bot.send_chat_action(chat_id, "typing")

    response, refined = await ask_valeria(
        user_message=user_text,
        history=history,
        lang=lang,
        interest=interest,
        funnel_stage="warming",
    )

    add_ai_message(user_id, "user", user_text)
    add_ai_message(user_id, "assistant", response)

    if refined != interest:
        update_user(user_id, interest=refined)
        interest = refined

    await update.message.reply_text(response, parse_mode=ParseMode.MARKDOWN)

    # Пауза → WARM2 (ждём следующую реакцию)
    await asyncio.sleep(3)
    await context.bot.send_chat_action(chat_id, "typing")
    await asyncio.sleep(2)
    await _deliver_warm2(context.bot, user_id, chat_id, lang)


async def _handle_warm2_reply(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    user_id: int, lang: str, interest: str, user_text: str,
) -> None:
    """Пользователь ответил на WARM2 → AI реагирует → пауза → TEASE."""
    chat_id = update.effective_chat.id
    history = get_ai_history(user_id)

    await context.bot.send_chat_action(chat_id, "typing")

    response, refined = await ask_valeria(
        user_message=user_text,
        history=history,
        lang=lang,
        interest=interest,
        funnel_stage="warming",
    )

    add_ai_message(user_id, "user", user_text)
    add_ai_message(user_id, "assistant", response)

    if refined != interest:
        update_user(user_id, interest=refined)
        interest = refined

    await update.message.reply_text(response, parse_mode=ParseMode.MARKDOWN)

    # Пауза → TEASE
    await asyncio.sleep(3)
    await context.bot.send_chat_action(chat_id, "typing")
    await asyncio.sleep(2)
    await _deliver_tease(context.bot, user_id, chat_id, lang, interest)


async def _handle_tease_reply(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    user_id: int, lang: str, interest: str, user_text: str,
) -> None:
    """Пользователь ответил на TEASE → AI реагирует → пауза → CTA."""
    chat_id = update.effective_chat.id
    history = get_ai_history(user_id)

    await context.bot.send_chat_action(chat_id, "typing")

    response, refined = await ask_valeria(
        user_message=user_text,
        history=history,
        lang=lang,
        interest=interest,
        funnel_stage="tease",
    )

    add_ai_message(user_id, "user", user_text)
    add_ai_message(user_id, "assistant", response)

    if refined != interest:
        update_user(user_id, interest=refined)
        interest = refined

    await update.message.reply_text(response, parse_mode=ParseMode.MARKDOWN)

    # Пауза → CTA
    await asyncio.sleep(2)
    await context.bot.send_chat_action(chat_id, "typing")
    await asyncio.sleep(1.5)
    await _deliver_cta(context.bot, user_id, chat_id, lang, interest)


async def _handle_cta_reply(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    user_id: int, lang: str, interest: str, user_text: str,
) -> None:
    """Пользователь пишет вместо того чтобы нажать кнопку → AI дожимает + повторяет CTA."""
    chat_id = update.effective_chat.id
    history = get_ai_history(user_id)

    await context.bot.send_chat_action(chat_id, "typing")

    response, _ = await ask_valeria(
        user_message=user_text,
        history=history,
        lang=lang,
        interest=interest,
        funnel_stage="cta",
    )

    add_ai_message(user_id, "user", user_text)
    add_ai_message(user_id, "assistant", response)

    await update.message.reply_text(response, parse_mode=ParseMode.MARKDOWN)

    # Повторяем CTA через паузу
    await asyncio.sleep(3)
    await _deliver_cta(context.bot, user_id, chat_id, lang, interest)


async def _handle_ai_chat(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    user_id: int, lang: str, interest: str, user_text: str, user: dict,
) -> None:
    """Свободный AI-чат после подписки — FTD-режим."""
    chat_id      = update.effective_chat.id
    funnel_stage = user.get("funnel_stage", "subscribed")
    history      = get_ai_history(user_id)
    msg_count    = user.get("ai_msg_count", 0)

    add_ai_message(user_id, "user", user_text)
    await context.bot.send_chat_action(chat_id, "typing")

    response, refined = await ask_valeria(
        user_message=user_text,
        history=history,
        lang=lang,
        interest=interest,
        funnel_stage=funnel_stage,
    )

    new_count = msg_count + 1
    update_kwargs: dict = {"ai_msg_count": new_count}

    if refined != interest:
        update_kwargs["interest"] = refined
        logger.info(f"User {user_id}: interest {interest} → {refined}")
        # Shift-сообщение
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

    await update.message.reply_text(response, parse_mode=ParseMode.MARKDOWN)


# ════════════════════════════════════════════════════════════════════════════
#  RE-ENGAGE JOB (каждые 30 мин)
# ════════════════════════════════════════════════════════════════════════════

async def reengage_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    now   = datetime.now(timezone.utc).timestamp()
    users = get_all_users()

    for user in users:
        user_id      = user.get("id")
        funnel_stage = user.get("funnel_stage", "new")
        lang         = user.get("lang", "es")
        interest     = user.get("interest", "betting")

        if funnel_stage == "subscribed" or funnel_stage == "new":
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

        channel      = CHANNELS.get(lang, CHANNELS["es"]).get(interest, CHANNELS["es"]["betting"])
        joined_label = M.CTA_BUTTON_JOINED.get(lang, "✅")
        cta_label    = M.CTA.get(lang, "📲 OddsVault")

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(cta_label, url=channel["url"])],
            [InlineKeyboardButton(joined_label, callback_data="user_joined")],
        ])

        # ── Re-engage 1: 24ч ──
        if not user.get("reengage_1_sent") and elapsed >= REENGAGE_DELAY_1:
            text = M.REENGAGE_1.get(lang, M.REENGAGE_1["es"])
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

        # ── Re-engage 2: 48ч ──
        elif (user.get("reengage_1_sent")
              and not user.get("reengage_2_sent")
              and elapsed >= REENGAGE_DELAY_2):
            text = M.REENGAGE_2.get(lang, M.REENGAGE_2["es"])
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

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = get_user(update.effective_user.id)
    lang = user.get("lang", "es")
    texts = {
        "es": "ℹ️ Soy Valeria. Usa /start para empezar. Comparto análisis e info del mercado — nada más.",
        "hr": "ℹ️ Ja sam Valerija. Koristi /start za početak. Dijelim tržišne analize i informacije.",
        "lt": "ℹ️ Aš esu Valerija. Naudok /start pradėti. Dalinuosi rinkos analizėmis ir informacija.",
        "lv": "ℹ️ Es esmu Valerija. Izmanto /start lai sāktu. Dalūos ar tirgus analīzēm un informāciju.",
    }
    await update.message.reply_text(texts.get(lang, texts["es"]))


# ════════════════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ════════════════════════════════════════════════════════════════════════════

def main() -> None:
    token = os.getenv("BOT_TOKEN", BOT_TOKEN)
    app   = Application.builder().token(token).build()

    # Команды
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help",  help_command))

    # Кнопки
    app.add_handler(CallbackQueryHandler(lang_chosen,     pattern=r"^lang_"))
    app.add_handler(CallbackQueryHandler(interest_chosen, pattern=r"^int_"))
    app.add_handler(CallbackQueryHandler(user_joined,     pattern=r"^user_joined$"))

    # Текстовые сообщения — весь FSM
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Планировщик re-engage (каждые 30 мин)
    app.job_queue.run_repeating(reengage_job, interval=30 * 60, first=60)

    logger.info("OddsVault Bot started 🚀  Valeria is online.")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
