import logging
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, ContextTypes
)
from telegram.constants import ParseMode
from config import CHANNELS, MESSAGES, BOT_TOKEN

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
#  /start — language selector
# ──────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    keyboard = [
        [
            InlineKeyboardButton("🇪🇸 Español",  callback_data="lang_es"),
            InlineKeyboardButton("🇭🇷 Hrvatski", callback_data="lang_hr"),
        ],
        [
            InlineKeyboardButton("🇱🇹 Lietuvių", callback_data="lang_lt"),
            InlineKeyboardButton("🇱🇻 Latviešu", callback_data="lang_lv"),
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    welcome_text = (
        "👋 *Welcome / Bienvenido / Dobrodošli / Sveiki / Laipni lūdzam!*\n\n"
        "🌍 Please select your language to get the best tips, bonuses & exclusive deals:\n\n"
        "📌 _We share betting & casino news, tips, and bonus information._"
    )

    await update.message.reply_text(
        welcome_text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=reply_markup,
    )


# ──────────────────────────────────────────────
#  Language chosen → show category menu
# ──────────────────────────────────────────────
async def language_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    lang = query.data.split("_")[1]  # es / hr / lt / lv
    context.user_data["lang"] = lang

    msg = MESSAGES[lang]

    if lang == "es":
        keyboard = [
            [InlineKeyboardButton("⚽ Apuestas Deportivas", callback_data="cat_betting")],
            [InlineKeyboardButton("🎰 Casino Bonuses",       callback_data="cat_casino")],
            [InlineKeyboardButton("🎁 Sin Depósito",         callback_data="cat_nodeposit")],
            [InlineKeyboardButton("🔥 Ofertas Exclusivas",   callback_data="cat_exclusive")],
        ]
    elif lang == "hr":
        keyboard = [
            [InlineKeyboardButton("⚽ Sportsko Klađenje",    callback_data="cat_betting")],
            [InlineKeyboardButton("🎰 Casino Bonusi",        callback_data="cat_casino")],
            [InlineKeyboardButton("🎁 Bez Depozita",         callback_data="cat_nodeposit")],
            [InlineKeyboardButton("🔥 Ekskluzivne Ponude",   callback_data="cat_exclusive")],
        ]
    elif lang == "lt":
        keyboard = [
            [InlineKeyboardButton("⚽ Sporto Lažybos",       callback_data="cat_betting")],
            [InlineKeyboardButton("🎰 Kazino Bonusai",       callback_data="cat_casino")],
            [InlineKeyboardButton("🎁 Be Depozito",          callback_data="cat_nodeposit")],
            [InlineKeyboardButton("🔥 Išskirtiniai Pasiūlymai", callback_data="cat_exclusive")],
        ]
    else:  # lv
        keyboard = [
            [InlineKeyboardButton("⚽ Sporta Likmju Padomi", callback_data="cat_betting")],
            [InlineKeyboardButton("🎰 Kazino Bonusi",        callback_data="cat_casino")],
            [InlineKeyboardButton("🎁 Bez Depozīta",         callback_data="cat_nodeposit")],
            [InlineKeyboardButton("🔥 Ekskluzīvi Piedāvājumi", callback_data="cat_exclusive")],
        ]

    await query.edit_message_text(
        text=msg["category_prompt"],
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


# ──────────────────────────────────────────────
#  Category chosen → show channel link
# ──────────────────────────────────────────────
async def category_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    lang = context.user_data.get("lang", "es")
    cat  = query.data.split("_")[1]  # betting / casino / nodeposit / exclusive

    channel = CHANNELS[lang][cat]
    msg     = MESSAGES[lang]

    # Build a rich info message + deep link button
    text = msg["channel_info"][cat]

    keyboard = [[InlineKeyboardButton(msg["join_button"], url=channel["url"])]]
    if channel.get("extra_url"):
        keyboard.append([InlineKeyboardButton(msg["more_button"], url=channel["extra_url"])])
    keyboard.append([InlineKeyboardButton("⬅️ " + msg["back"], callback_data=f"lang_{lang}")])

    await query.edit_message_text(
        text=text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(keyboard),
        disable_web_page_preview=False,
    )


# ──────────────────────────────────────────────
#  /help
# ──────────────────────────────────────────────
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "ℹ️ Use /start to choose your language and explore betting tips & bonus information.\n\n"
        "We do *not* promote gambling. We share publicly available information about promotions, "
        "odds, and industry news. Always gamble responsibly. 🛡️",
        parse_mode=ParseMode.MARKDOWN,
    )


# ──────────────────────────────────────────────
#  Entry point
# ──────────────────────────────────────────────
def main() -> None:
    token = os.getenv("BOT_TOKEN", BOT_TOKEN)
    app = Application.builder().token(token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help",  help_command))
    app.add_handler(CallbackQueryHandler(language_chosen, pattern=r"^lang_"))
    app.add_handler(CallbackQueryHandler(category_chosen, pattern=r"^cat_"))

    logger.info("Bot is running…")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
