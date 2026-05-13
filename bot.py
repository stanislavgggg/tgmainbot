"""
bot.py — Telegram-бот с полной воронкой FSM.

Воронка:
  /start → HOOK (крючок)
    → выбор языка → QUIZ (квиз)
      → выбор интереса → WARM1 (прогрев 1)
        → WARM2 (прогрев 2)
          → TEASE (тизер)
            → CTA (кнопка канала)
              → "Уже вступил" → POST_SUB → AI_CHAT

Re-engage (scheduler):
  24ч — REENGAGE_1 (если не подписался)
  48ч — REENGAGE_2 (если всё ещё не подписался)
"""

import logging
import asyncio
import os
import random
from datetime import datetime, timezone

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
from telegram.constants import ParseMode
from telegram.error import TelegramError

from config import (
    BOT_TOKEN, CHANNELS, State,
    REENGAGE_DELAY_1, REENGAGE_DELAY_2,
    INTEREST_IMAGES,
)
from storage import get_user, update_user, add_ai_message, get_all_users
from ai_agent import ask_valeria, detect_tone
import messages as M

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ── утилита: задержка между сообщениями ────────────────────────────────────────
async def _typing_delay(context, chat_id: int, seconds: float = 1.5):
    await context.bot.send_chat_action(chat_id, "typing")
    await asyncio.sleep(seconds)


# ── Отправка случайной картинки по интересу ────────────────────────────────────
async def _send_image(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    interest: str,
    caption: str = None,
) -> bool:
    """
    Отправляет случайную картинку по интересу.
    Возвращает True если успешно, False если картинок нет / ошибка.
    """
    images = INTEREST_IMAGES.get(interest, [])

    # Фолбэк на betting если нет картинок для интереса
    if not images:
        images = INTEREST_IMAGES.get("betting", [])

    if not images:
        return False

    img_path = random.choice(images)

    try:
        with open(img_path, "rb") as photo:
            await context.bot.send_photo(
                chat_id=chat_id,
                photo=photo,
                caption=caption,
                parse_mode=ParseMode.MARKDOWN if caption else None,
            )
        return True
    except FileNotFoundError:
        logger.warning(f"Image not found: {img_path}")
        return False
    except TelegramError as e:
        logger.warning(f"Failed to send image: {e}")
        return False


# ══════════════════════════════════════════════════════════════════════════════
#  ШАГ 1: /start — крючок + выбор языка
# ══════════════════════════════════════════════════════════════════════════════
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    first_name = update.effective_user.first_name or ""
    username = update.effective_user.username or ""

    update_user(
        user_id,
        state=State.LANG,
        funnel_stage="new",
        first_name=first_name,
        username=username,
    )

    hook_text = M.HOOK["default"]

    keyboard = [[InlineKeyboardButton(label, callback_data=cb)] for label, cb in M.LANG_BUTTONS]

    await update.message.reply_text(
        hook_text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


# ══════════════════════════════════════════════════════════════════════════════
#  ШАГ 2: Язык выбран → показываем квиз
# ══════════════════════════════════════════════════════════════════════════════
async def lang_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    lang = query.data.split("_")[1]  # es / hr / lt / lv
    user_id = query.from_user.id
    update_user(user_id, lang=lang, state=State.QUIZ)

    quiz_text = M.QUIZ.get(lang, M.QUIZ["default"])
    buttons = M.QUIZ_BUTTONS.get(lang, M.QUIZ_BUTTONS["es"])
    keyboard = [[InlineKeyboardButton(label, callback_data=cb)] for label, cb in buttons]

    await query.edit_message_text(
        text=quiz_text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


# ══════════════════════════════════════════════════════════════════════════════
#  ШАГ 3: Интерес выбран → WARM1
# ══════════════════════════════════════════════════════════════════════════════
async def interest_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    interest = query.data.split("_")[1]  # betting / casino / nodeposit / exclusive
    user_id = query.from_user.id
    user = get_user(user_id)
    lang = user.get("lang", "es")

    update_user(user_id, interest=interest, state=State.WARM1, funnel_stage="warming")

    warm1_text = M.get(M.WARM1, lang, interest)

    await query.edit_message_text(
        text=warm1_text,
        parse_mode=ParseMode.MARKDOWN,
    )

    await _typing_delay(context, query.message.chat_id, 2.5)
    await _send_warm2(context.bot, user_id, query.message.chat_id, lang, interest)


async def _send_warm2(bot, user_id: int, chat_id: int, lang: str, interest: str):
    update_user(user_id, state=State.WARM2)
    warm2_text = M.get(M.WARM2, lang)

    await bot.send_message(
        chat_id=chat_id,
        text=warm2_text,
        parse_mode=ParseMode.MARKDOWN,
    )

    await asyncio.sleep(3)
    await _send_tease(bot, user_id, chat_id, lang, interest)


async def _send_tease(bot, user_id: int, chat_id: int, lang: str, interest: str):
    update_user(user_id, state=State.TEASE, funnel_stage="tease")
    tease_text = M.get(M.TEASE, lang, interest)

    await bot.send_message(
        chat_id=chat_id,
        text=tease_text,
        parse_mode=ParseMode.MARKDOWN,
    )

    await asyncio.sleep(2)
    await _send_cta(bot, user_id, chat_id, lang, interest)


async def _send_cta(bot, user_id: int, chat_id: int, lang: str, interest: str):
    update_user(user_id, state=State.CTA, funnel_stage="cta")

    channel = CHANNELS.get(lang, CHANNELS["es"]).get(interest, CHANNELS["es"]["betting"])
    cta_label = M.CTA.get(lang, M.CTA["es"])
    joined_label = M.CTA_BUTTON_JOINED.get(lang, M.CTA_BUTTON_JOINED["es"])

    keyboard = [
        [InlineKeyboardButton(cta_label, url=channel["url"])],
        [InlineKeyboardButton(joined_label, callback_data="user_joined")],
    ]

    await bot.send_message(
        chat_id=chat_id,
        text="👇",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


# ══════════════════════════════════════════════════════════════════════════════
#  ШАГ 4: "Я уже подписался" → POST_SUB → AI_CHAT
# ══════════════════════════════════════════════════════════════════════════════
async def user_joined(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    user = get_user(user_id)
    lang = user.get("lang", "es")
    interest = user.get("interest", "betting")

    update_user(user_id, state=State.SUBSCRIBED, funnel_stage="subscribed")

    post_text = M.get(M.POST_SUB, lang, interest)

    await query.edit_message_text(
        text=post_text,
        parse_mode=ParseMode.MARKDOWN,
    )

    update_user(user_id, state=State.AI_CHAT)


# ══════════════════════════════════════════════════════════════════════════════
#  AI-чат: любое текстовое сообщение → Валерия отвечает
# ══════════════════════════════════════════════════════════════════════════════
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.text:
        return

    user_id = update.effective_user.id
    user = get_user(user_id)
    state = user.get("state")

    if state not in (State.AI_CHAT, State.SUBSCRIBED, None):
        return

    if state is None:
        await start(update, context)
        return

    lang         = user.get("lang", "es")
    interest     = user.get("interest", "betting")
    funnel_stage = user.get("funnel_stage", "subscribed")
    history      = user.get("ai_history", [])
    msg_count    = user.get("ai_msg_count", 0)
    user_text    = update.message.text.strip()

    add_ai_message(user_id, "user", user_text)

    await context.bot.send_chat_action(update.effective_chat.id, "typing")

    # Получаем ответ + уточнённый интерес
    response, refined_interest = await ask_valeria(
        user_message=user_text,
        history=history,
        lang=lang,
        interest=interest,
        funnel_stage=funnel_stage,
    )

    new_msg_count = msg_count + 1

    # Обновляем данные пользователя
    update_kwargs = {"ai_msg_count": new_msg_count}
    if refined_interest != interest:
        update_kwargs["interest"] = refined_interest
        logger.info(f"User {user_id}: interest {interest} → {refined_interest}")
    update_user(user_id, **update_kwargs)

    add_ai_message(user_id, "assistant", response)

    # Сохраняем тон
    tone = detect_tone(user_text, history)
    logger.debug(f"User {user_id}: tone={tone}")

    # ── FTD-пуш каждые 5 сообщений у подписанных ──────────────────────────────
    FTD_PUSH_EVERY = 5
    if funnel_stage == "subscribed" and new_msg_count % FTD_PUSH_EVERY == 0:
        ftd_text = M.get(M.POST_SUB, lang, refined_interest)
        if ftd_text:
            await asyncio.sleep(1.5)
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=ftd_text,
                parse_mode=ParseMode.MARKDOWN,
            )
            return

    # ── Пуш при смене интереса ─────────────────────────────────────────────────
    if refined_interest != interest:
        shift_key = f"{interest}_to_{refined_interest}"
        shift_msg = M.INTEREST_SHIFT.get(shift_key, {}).get(lang)
        if shift_msg:
            await update.message.reply_text(
                shift_msg,
                parse_mode=ParseMode.MARKDOWN,
            )
            return

    # ── Каждые 4 сообщения отправляем картинку с текстом ──────────────────────
    IMAGE_EVERY_N = 4
    if new_msg_count % IMAGE_EVERY_N == 0:
        sent = await _send_image(
            context=context,
            chat_id=update.effective_chat.id,
            interest=refined_interest,
            caption=response,
        )
        if sent:
            return
        # Если картинок нет — падаем в обычный текст

    # ── Обычный текстовый ответ ────────────────────────────────────────────────
    await update.message.reply_text(
        response,
        parse_mode=ParseMode.MARKDOWN,
    )


# ══════════════════════════════════════════════════════════════════════════════
#  Re-engage джоб (запускается планировщиком каждые 30 мин)
# ══════════════════════════════════════════════════════════════════════════════
async def reengage_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    now = datetime.now(timezone.utc).timestamp()
    users = get_all_users()

    for user in users:
        user_id = user["id"]
        funnel_stage = user.get("funnel_stage", "new")
        lang = user.get("lang", "es")
        interest = user.get("interest", "betting")

        if funnel_stage == "subscribed":
            continue

        if funnel_stage not in ("cta", "tease", "warming"):
            continue

        last_active_str = user.get("last_active")
        if not last_active_str:
            continue

        try:
            last_active = datetime.fromisoformat(last_active_str)
            if last_active.tzinfo is None:
                last_active = last_active.replace(tzinfo=timezone.utc)
            elapsed = now - last_active.timestamp()
        except Exception:
            continue

        channel = CHANNELS.get(lang, CHANNELS["es"]).get(interest, CHANNELS["es"]["betting"])
        joined_label = M.CTA_BUTTON_JOINED.get(lang, M.CTA_BUTTON_JOINED["es"])
        keyboard = [[InlineKeyboardButton(joined_label, callback_data="user_joined")]]

        # Re-engage 1: 24ч
        if not user.get("reengage_1_sent") and elapsed >= REENGAGE_DELAY_1:
            text = M.get(M.REENGAGE_1, lang)
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=text,
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=InlineKeyboardMarkup(
                        [[InlineKeyboardButton(M.CTA.get(lang, "📲"), url=channel["url"])],
                         keyboard[0]]
                    ),
                )
                update_user(user_id, reengage_1_sent=True)
                logger.info(f"Re-engage 1 sent to {user_id}")
            except TelegramError as e:
                logger.warning(f"Re-engage 1 failed for {user_id}: {e}")

        # Re-engage 2: 48ч
        elif user.get("reengage_1_sent") and not user.get("reengage_2_sent") and elapsed >= REENGAGE_DELAY_2:
            text = M.get(M.REENGAGE_2, lang)
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=text,
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=InlineKeyboardMarkup(
                        [[InlineKeyboardButton(M.CTA.get(lang, "📲"), url=channel["url"])],
                         keyboard[0]]
                    ),
                )
                update_user(user_id, reengage_2_sent=True)
                logger.info(f"Re-engage 2 sent to {user_id}")
            except TelegramError as e:
                logger.warning(f"Re-engage 2 failed for {user_id}: {e}")


# ══════════════════════════════════════════════════════════════════════════════
#  /help
# ══════════════════════════════════════════════════════════════════════════════
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = get_user(update.effective_user.id)
    lang = user.get("lang", "es")

    texts = {
        "es": "ℹ️ Soy Valeria. Usa /start para comenzar. Comparto análisis e información sobre el mercado.",
        "hr": "ℹ️ Ja sam Valerija. Koristi /start za početak. Dijelim analize i informacije o tržištu.",
        "lt": "ℹ️ Aš esu Valerija. Naudok /start pradėti. Dalinuosi analizėmis ir rinkos informacija.",
        "lv": "ℹ️ Es esmu Valerija. Izmanto /start lai sāktu. Dalūos ar analīzēm un tirgus informāciju.",
    }
    await update.message.reply_text(texts.get(lang, texts["es"]))


# ══════════════════════════════════════════════════════════════════════════════
#  Entry point
# ══════════════════════════════════════════════════════════════════════════════
def main() -> None:
    token = os.getenv("BOT_TOKEN", BOT_TOKEN)
    app = Application.builder().token(token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CallbackQueryHandler(lang_chosen,     pattern=r"^lang_"))
    app.add_handler(CallbackQueryHandler(interest_chosen, pattern=r"^int_"))
    app.add_handler(CallbackQueryHandler(user_joined,     pattern=r"^user_joined$"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    job_queue = app.job_queue
    job_queue.run_repeating(reengage_job, interval=30 * 60, first=60)

    logger.info("Bot started with full funnel FSM 🚀")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
