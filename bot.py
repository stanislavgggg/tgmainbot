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

from config import BOT_TOKEN, CHANNELS, State, REENGAGE_DELAY_1, REENGAGE_DELAY_2
from storage import get_user, update_user, add_ai_message, get_all_users
from ai_agent import ask_valeria
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

    # Определяем язык интерфейса Telegram как подсказку
    tg_lang = (update.effective_user.language_code or "")[:2].lower()
    hook_text = M.HOOK.get(tg_lang, M.HOOK["default"])

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

    # Убираем кнопки квиза
    await query.edit_message_text(
        text=warm1_text,
        parse_mode=ParseMode.MARKDOWN,
    )

    # Через 2.5с отправляем WARM2
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

    # Через 3с отправляем тизер
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

    # Через 2с отправляем CTA
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

    # Текст-тизер уже отправлен, просто добавляем кнопки отдельным сообщением
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

    update_user(user_id, state=State.SUBSCRIBED, funnel_stage="subscribed")

    post_text = M.get(M.POST_SUB, lang)

    await query.edit_message_text(
        text=post_text,
        parse_mode=ParseMode.MARKDOWN,
    )

    # Переводим в режим AI-чата
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

    # Если пользователь ещё не прошёл воронку — игнорируем / отправляем на /start
    if state not in (State.AI_CHAT, State.SUBSCRIBED, None):
        return

    # Если совсем новый — запускаем start
    if state is None:
        await start(update, context)
        return

    lang = user.get("lang", "es")
    interest = user.get("interest", "betting")
    funnel_stage = user.get("funnel_stage", "subscribed")
    history = user.get("ai_history", [])
    user_text = update.message.text.strip()

    # Сохраняем сообщение пользователя
    add_ai_message(user_id, "user", user_text)

    # Индикатор печати
    await context.bot.send_chat_action(update.effective_chat.id, "typing")

    response = await ask_valeria(
        user_message=user_text,
        history=history,
        lang=lang,
        interest=interest,
        funnel_stage=funnel_stage,
    )

    add_ai_message(user_id, "assistant", response)

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

        # Пропускаем подписавшихся
        if funnel_stage == "subscribed":
            continue

        # Пропускаем тех, кто не дошёл до CTA
        if funnel_stage not in ("cta", "tease", "warming"):
            continue

        last_active_str = user.get("last_active")
        if not last_active_str:
            continue

        try:
            last_active = datetime.fromisoformat(last_active_str)
            # Если без timezone — считаем UTC
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

    # Handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CallbackQueryHandler(lang_chosen,      pattern=r"^lang_"))
    app.add_handler(CallbackQueryHandler(interest_chosen,  pattern=r"^int_"))
    app.add_handler(CallbackQueryHandler(user_joined,      pattern=r"^user_joined$"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Re-engage планировщик: каждые 30 минут
    job_queue = app.job_queue
    job_queue.run_repeating(reengage_job, interval=30 * 60, first=60)

    logger.info("Bot started with full funnel FSM 🚀")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
