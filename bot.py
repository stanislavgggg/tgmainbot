
bot.py — OddsVault Bot v10

ИСПРАВЛЕНИЯ:

1. /start: HOOK (представление Валерии) → пауза → QUIZ. Не объединять в одно.
1. GEO-квиз: отправляется через send_message (не edit), timeout увеличен
1. Fallback не повторяется бесконечно: счётчик fallback_count, после 2 → переходим к tease
1. API key диагностика при старте — видно сразу если не прописан
1. handle_message логирует каждый входящий запрос для отладки
1. ask_valeria: логирует реальную ошибку API, не глотает молча
   “””
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
   from conversation import (ask_valeria_conversational, get_post_sub_opener,
   get_silence_push, should_send_silence_push,
   detect_interest_from_text, detect_geo_from_text,
   OPENING_QUESTION)
   from ftd_onboarding import (schedule_onboarding, schedule_ftd_flow,
   detect_ftd_signal)
   from daily_signal import daily_signal_job
   from ab_test import (assign_variant, get_hook_text, track_event,
   get_ab_stats, format_ab_stats_message, VARIANT_C_SKIPS_HOOK)
   from bonus_calculator import (should_show_calculator, get_calculator_trigger_text,
   get_calc_intro, get_deposit_buttons, get_stake_buttons,
   format_casino_result, format_betting_result, parse_deposit_callback)
   from referral import (should_offer_referral, get_referral_offer_text,
   track_referral_offer, track_referral_click,
   get_referrer_from_start, get_thanks_text, is_positive_message)
   from adrenaline import adrenaline_check_job, get_odds_api_status
   import messages as M
   from config import ANTHROPIC_KEY

logging.basicConfig(format=”%(asctime)s [%(levelname)s] %(name)s: %(message)s”, level=logging.INFO)
logger = logging.getLogger(**name**)

# ── Lock ──────────────────────────────────────────────────────────────────────

LOCK_FILE = “bot.lock”
def _check_lock():
if os.path.exists(LOCK_FILE):
try:
with open(LOCK_FILE) as f: old_pid = int(f.read().strip())
os.kill(old_pid, 0); logger.error(f”Already running PID {old_pid}”); sys.exit(1)
except (ProcessLookupError, ValueError): os.remove(LOCK_FILE)
with open(LOCK_FILE,“w”) as f: f.write(str(os.getpid()))
atexit.register(lambda: os.path.exists(LOCK_FILE) and os.remove(LOCK_FILE))
_check_lock()

# ── Helpers ───────────────────────────────────────────────────────────────────

def _typing_delay(text): return round(1.2 + min(len(text)/140, 2.0), 1)

async def _send_image(context, chat_id, interest, caption=””):
images = INTEREST_IMAGES.get(interest) or INTEREST_IMAGES.get(“betting”, [])
if not images: return False
try:
with open(random.choice(images), “rb”) as photo:
await context.bot.send_photo(chat_id=chat_id, photo=photo,
caption=caption or None, parse_mode=ParseMode.MARKDOWN if caption else None)
return True
except (FileNotFoundError, TelegramError) as e:
logger.warning(f”Image failed: {e}”); return False

def _cta_keyboard(lang, interest, geo):
channel = resolve_channel(geo, interest)
if channel:
url   = f”https://t.me/{channel[‘username’].lstrip(’@’)}”
title = channel.get(“title”, “📲 OddsVault”)
else:
url, title = “https://t.me/ApuestasGuruES”, “📲 OddsVault”
return InlineKeyboardMarkup([
[InlineKeyboardButton(title, url=url)],
[InlineKeyboardButton(
M.CTA_BUTTON_JOINED.get(lang, M.CTA_BUTTON_JOINED.get(“en”, “✅ Already in”)),
callback_data=“user_joined”)],
])

def _prepare_context(user_id, user_text):
obj = classify_objection(user_text)
if obj: log_objection(user_id, obj)
return update_psychotype(user_id, user_text), get_objections(user_id), get_used_techniques(user_id)

async def _send_tease(bot, user_id, chat_id, lang, interest, geo=“OTHER”):
“”“Отправляет TEASE и сразу за ним CTA — всегда, без ожидания ответа пользователя.”””
update_user(user_id, state=State.TEASE, funnel_stage=“tease”, stage_replies=0)
text = M.get(M.TEASE, lang, interest)
await bot.send_chat_action(chat_id, “typing”)
await asyncio.sleep(_typing_delay(text) * 0.7)
await bot.send_message(chat_id=chat_id, text=text, parse_mode=ParseMode.MARKDOWN)
# CTA приходит сразу после TEASE — всегда, без ожидания ответа
await asyncio.sleep(3.5)
await _send_cta(bot, user_id, chat_id, lang, interest, geo)

async def _send_cta(bot, user_id, chat_id, lang, interest, geo):
update_user(user_id, state=State.CTA, funnel_stage=“cta”)
cta_text = M.CTA_TEXT.get(lang, M.CTA_TEXT.get(“en”, “🔐 The vault is right there.”))
await bot.send_message(chat_id=chat_id, text=cta_text, parse_mode=ParseMode.MARKDOWN,
reply_markup=_cta_keyboard(lang, interest, geo))

# ════════════════════════════════════════════════════════════════════════════

# /start — HOOK с картинкой + кнопки языков → QUIZ (интерес)

# 

# Картинка: файл 1name.png лежит в корне репо рядом с bot.py

# Или используй HOOK_IMAGE_URL (прямая ссылка на картинку).

# 

# Поток: send_photo(caption=HOOK, кнопки языков) → пользователь выбирает

# язык → lang_chosen → QUIZ → interest_chosen → GEO-квиз → geo_chosen → AI

# ════════════════════════════════════════════════════════════════════════════

# Путь к картинке (лежит рядом с bot.py в репо)

HOOK_IMAGE_PATH = os.path.join(os.path.dirname(**file**), “1name.png”)

# Fallback: прямой URL если файл не найден (замени на свой хостинг)

HOOK_IMAGE_URL  = “https://raw.githubusercontent.com/stanislavgggg/tgmainbot/4891019e49ee730aad0db5bcd065708a1b44c471/1name.png”

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
user_id    = update.effective_user.id
first_name = update.effective_user.first_name or “”
tg_lang    = update.effective_user.language_code
chat_id    = update.effective_chat.id

```
# Реферальный параметр
start_param = context.args[0] if context.args else ""
if start_param:
    referrer_id = get_referrer_from_start(start_param)
    if referrer_id and referrer_id != user_id:
        track_referral_click(referrer_id)
        logger.info(f"Referral: {user_id} from {referrer_id}")

geo_hint = infer_geo_from_tg_lang(tg_lang) or "OTHER"
lang     = resolve_lang(geo_hint, tg_lang)
variant  = assign_variant()

update_user(user_id,
    state=State.LANG, funnel_stage="new",
    first_name=first_name,
    username=update.effective_user.username or "",
    lang=lang, geo=geo_hint,
    reengage_1_sent=False, reengage_2_sent=False,
    ai_msg_count=0, stage_replies=0,
    commitment_sent=False, cta_replies=0,
    fallback_count=0, ab_variant=variant,
    positive_msg_count=0,
)
logger.info(f"START user={user_id} lang={lang} geo={geo_hint} variant={variant}")

hook_text = get_hook_text(variant, lang)
await asyncio.sleep(0.8)

# Отправляем фото + HOOK текст
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

# Сразу после фото — открывающий вопрос (без кнопок)
await asyncio.sleep(1.5)
await context.bot.send_chat_action(chat_id, "typing")
await asyncio.sleep(1.2)
opening = OPENING_QUESTION.get(lang, OPENING_QUESTION["en"])
await context.bot.send_message(
    chat_id=chat_id, text=opening, parse_mode=ParseMode.MARKDOWN)

# Переходим в WARM1 — пользователь теперь в диалоге
update_user(user_id, state=State.WARM1, funnel_stage="discovery")
```

# ════════════════════════════════════════════════════════════════════════════

# Выбор интереса → GEO-квиз

# ════════════════════════════════════════════════════════════════════════════

async def interest_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
query    = update.callback_query
await query.answer()
interest = query.data[len(“int_”):]
user_id  = query.from_user.id
user     = get_user(user_id)
lang     = user.get(“lang”, “en”)
chat_id  = query.message.chat_id

```
update_user(user_id, interest=interest, state=State.QUIZ)
logger.info(f"INTEREST user={user_id} interest={interest} lang={lang}")
track_event(user_id, "quiz_answered")

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
```

# ════════════════════════════════════════════════════════════════════════════

# Выбор ГЕО → AI opener → WARM1

# ════════════════════════════════════════════════════════════════════════════

async def geo_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
query   = update.callback_query
await query.answer()
geo     = query.data[len(“geo_”):]
user_id = query.from_user.id
user    = get_user(user_id)
tg_lang = update.effective_user.language_code
chat_id = query.message.chat_id

```
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

# stage_replies=1 т.к. opener уже считается первым сообщением Валерии
# Это не даст повторить ту же фразу при первом ответе пользователя
update_user(user_id, stage_replies=1, opener_sent=True)

await asyncio.sleep(_typing_delay(opener) * 0.5)
await context.bot.send_message(chat_id=chat_id, text=opener, parse_mode=ParseMode.MARKDOWN)
```

# ════════════════════════════════════════════════════════════════════════════

# Commitment buttons

# ════════════════════════════════════════════════════════════════════════════

async def commitment_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
query   = update.callback_query
await query.answer()
full_cb = query.data
user_id = query.from_user.id
user    = get_user(user_id)
lang    = user.get(“lang”, “en”)
interest= user.get(“interest”, “betting”)
geo     = user.get(“geo”, “OTHER”)
chat_id = query.message.chat_id

```
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
user_geo = get_user(user_id).get("geo", "OTHER")
await _send_tease(context.bot, user_id, chat_id, lang, interest, geo=user_geo)
```

# ════════════════════════════════════════════════════════════════════════════

# “Уже вступил” → проверка подписки

# ════════════════════════════════════════════════════════════════════════════

async def user_joined(update: Update, context: ContextTypes.DEFAULT_TYPE):
query   = update.callback_query
user_id = query.from_user.id
user    = get_user(user_id)
lang    = user.get(“lang”, “en”)
interest= user.get(“interest”, “betting”)
geo     = user.get(“geo”, “OTHER”)
chat_id = query.message.chat_id

```
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

# Трекаем клик на канал — останавливает онбординг пуши
track_channel_click(user_id)

update_user(user_id, state=State.AI_CHAT, funnel_stage="subscribed", verified_member=True)
await context.bot.send_chat_action(chat_id, "typing")
await asyncio.sleep(1.5)

# Живой opener — начинает диалог, не "Well done"
opener = get_post_sub_opener(lang, interest)
if not opener:
    opener = M.get(M.POST_SUB, lang, interest)
await context.bot.send_message(
    chat_id=chat_id, text=opener, parse_mode=ParseMode.MARKDOWN)

# Онбординг запускается но умно — пуши отменяются если юзер активен
schedule_onboarding(
    job_queue=context.job_queue,
    user_id=user_id,
    chat_id=chat_id,
    lang=lang,
    interest=interest,
)
logger.info(f"Onboarding started → {user_id} [{lang}/{interest}/{geo}]")
```

# ════════════════════════════════════════════════════════════════════════════

# Fallback lang buttons (если показывались)

# ════════════════════════════════════════════════════════════════════════════

async def lang_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
query   = update.callback_query
await query.answer()
lang    = query.data[len(“lang_”):]
user_id = query.from_user.id
chat_id = query.message.chat_id

```
update_user(user_id, lang=lang, state=State.QUIZ)

# Убираем кнопки языков с фото (edit_message_reply_markup работает для фото)
try:
    await query.edit_message_reply_markup(reply_markup=None)
except Exception:
    pass

# Отправляем QUIZ новым сообщением (нельзя edit_message_text на photo)
quiz = M.QUIZ.get(lang, M.QUIZ.get("en", "What interests you?"))
btns = M.QUIZ_BUTTONS.get(lang, M.QUIZ_BUTTONS.get("en", []))
kb   = [[InlineKeyboardButton(lbl, callback_data=cb)] for lbl, cb in btns]
await context.bot.send_message(
    chat_id=chat_id,
    text=quiz,
    parse_mode=ParseMode.MARKDOWN,
    reply_markup=InlineKeyboardMarkup(kb))
```

# ════════════════════════════════════════════════════════════════════════════

# Главный handler входящих сообщений

# ════════════════════════════════════════════════════════════════════════════

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
if not update.message or not update.message.text: return
user_id   = update.effective_user.id
user      = get_user(user_id)
state     = user.get(“state”)
user_text = update.message.text.strip()

```
logger.info(f"MSG user={user_id} state={state} text={user_text[:40]!r}")

if state is None:
    await start(update, context); return

lang     = user.get("lang", "en")
interest = user.get("interest", "betting")
geo      = user.get("geo", "OTHER")

# ── Детектор ГЕО из текста (если пользователь написал страну) ────────────
# Работает в любом состоянии — обновляет канал и язык на правильные
if geo in ("OTHER", "") and state not in (State.LANG, State.QUIZ):
    detected_geo = _detect_geo_from_text(user_text)
    if detected_geo and detected_geo != geo:
        new_lang = resolve_lang(detected_geo)
        update_user(user_id, geo=detected_geo, lang=new_lang)
        geo  = detected_geo
        lang = new_lang
        logger.info(f"GEO detected from text: {detected_geo} → lang={new_lang}")

# Silent profile update
if len(user_text) > 8:
    asyncio.create_task(_update_profile_silent(user_id, user_text, lang))

# ── Детектор переключения языка (в любом состоянии) ──────────────────────
new_lang = _detect_lang_switch(user_text)
if new_lang and new_lang != lang:
    update_user(user_id, lang=new_lang)
    lang = new_lang
    ack_switch = {
        "en": "Switching to English — got it. 👌",
        "es": "Cambio al español — entendido. 👌",
        "hr": "Prelazim na hrvatski — razumijem. 👌",
        "lt": "Pereinu į lietuvių — suprantu. 👌",
        "lv": "Pāreju uz latviešu — saprotu. 👌",
    }
    await update.message.reply_text(ack_switch.get(new_lang, "Switching language. 👌"))
    # Если в квизе — перезапускаем кнопки на новом языке
    if state in (State.LANG, State.QUIZ):
        quiz_text = M.QUIZ.get(new_lang, M.QUIZ.get("en", ""))
        btns      = M.QUIZ_BUTTONS.get(new_lang, M.QUIZ_BUTTONS.get("en", []))
        kb        = [[InlineKeyboardButton(lbl, callback_data=cb)] for lbl, cb in btns]
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=quiz_text, parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(kb))
    return

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
    # FTD детектор — пользователь написал что сделал депозит
    if detect_ftd_signal(user_text):
        ftd_count = user.get("ftd_count", 0) + 1
        is_new_ftd = not user.get("ftd_done")
        update_user(user_id, ftd_done=True, ftd_count=ftd_count)
        logger.info(f"FTD {'#1' if is_new_ftd else f'#{ftd_count}'} → {user_id}: {user_text[:40]!r}")
        schedule_ftd_flow(
            job_queue=context.job_queue,
            user_id=user_id,
            chat_id=update.effective_chat.id,
            lang=lang,
            interest=interest,
        )
    await _handle_ai_chat(update, context, user_id, lang, interest, geo, user_text, user)
```

async def _update_profile_silent(user_id, text, lang):
try:
updates = await extract_profile_update(text, get_profile(user_id), lang)
if updates:
update_profile(user_id, updates)
logger.info(f”Profile {user_id}: {updates}”)
except Exception as e:
logger.debug(f”Profile skip: {e}”)

def _detect_lang_switch(text: str):
“””
Детектирует когда пользователь просит переключить язык.
Возвращает код языка или None.
“””
t = text.lower().strip()
# English triggers
if any(t == p or t.startswith(p) for p in [
“switch to english”, “english please”, “speak english”,
“in english”, “change to english”, “английский”, “по-английски”,
]):
return “en”
# Spanish triggers
if any(t == p or t.startswith(p) for p in [
“switch to spanish”, “en español”, “español”, “habla español”,
“cambiar a español”, “speak spanish”,
]):
return “es”
# Croatian triggers
if any(t == p or t.startswith(p) for p in [
“switch to croatian”, “hrvatski”, “na hrvatskom”, “speak croatian”,
]):
return “hr”
# Lithuanian triggers
if any(t == p or t.startswith(p) for p in [
“switch to lithuanian”, “lietuviškai”, “lietuvių”, “speak lithuanian”,
]):
return “lt”
# Latvian triggers
if any(t == p or t.startswith(p) for p in [
“switch to latvian”, “latviešu”, “latviski”, “speak latvian”,
]):
return “lv”
return None

def _detect_geo_from_text(text: str):
“””
Детектирует страну из свободного текста.
Если geo=OTHER — обновляем на правильный канал и язык.
“””
t = text.lower()
if any(w in t for w in [“spain”,“españa”,“espana”,“spanish”,“español”,“madrid”,“barcelona”,“seville”,“valencia”,“bilbao”]):
return “ES”
if any(w in t for w in [“croatia”,“hrvatska”,“croatian”,“zagreb”,“split”,“dubrovnik”,“rijeka”]):
return “HR”
if any(w in t for w in [“serbia”,“srbija”,“serbian”,“belgrade”,“beograd”,“novi sad”,“bosnia”,“balkan”,“macedon”,“montenegro”,“slovenia”]):
return “RS”
if any(w in t for w in [“lithuania”,“lietuva”,“lithuanian”,“vilnius”,“kaunas”,“klaipeda”]):
return “LT”
if any(w in t for w in [“latvia”,“latvija”,“latvian”,“riga”,“daugavpils”]):
return “LV”
return None

# ════════════════════════════════════════════════════════════════════════════

# WARMING handler

# Ключевое исправление: если API недоступен (нет ключа) — fallback_count растёт,

# после 2 fallback’ов принудительно переходим к TEASE с статичным текстом.

# ════════════════════════════════════════════════════════════════════════════

async def _handle_warming(update, context, user_id, lang, interest, geo, user_text, user):
“””
Диалоговый warming. Использует ask_valeria_conversational.
AI сам определяет interest и GEO из ответов пользователя.
Переходит к tease когда накоплено достаточно контекста (обычно 2-3 обмена).
“””
chat_id    = update.effective_chat.id
history    = get_ai_history(user_id)
replies    = user.get(“stage_replies”, 0) + 1
funnel     = user.get(“funnel_stage”, “discovery”)
psychotype = get_psychotype(user_id)
objections = get_objections(user_id)
profile    = get_profile(user_id)
ftd_done   = bool(user.get(“ftd_done”))

```
obj_type = classify_objection(user_text)
if obj_type:
    log_objection(user_id, obj_type)

update_user(user_id, stage_replies=replies)

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
)

response = result["text"]
add_ai_message(user_id, "user", user_text)
add_ai_message(user_id, "assistant", response)
add_tone(user_id, detect_tone(user_text, history))

# Обновляем interest и GEO если AI их определил
updates = {}
if result["detected_interest"] and not user.get("interest_confirmed"):
    updates["interest"]          = result["detected_interest"]
    updates["interest_confirmed"] = True
    interest                     = result["detected_interest"]
    logger.info(f"Interest detected from text: {interest} for {user_id}")
if result["detected_geo"] and (not geo or geo == "OTHER"):
    from membership import resolve_lang as _resolve_lang
    new_geo  = result["detected_geo"]
    new_lang = _resolve_lang(new_geo)
    updates["geo"]  = new_geo
    updates["lang"] = new_lang
    lang            = new_lang
    geo             = new_geo
    logger.info(f"GEO detected from text: {new_geo} → lang={new_lang} for {user_id}")
if updates:
    update_user(user_id, **updates)

await asyncio.sleep(_typing_delay(response) * 0.5)
await update.message.reply_text(response, parse_mode=ParseMode.MARKDOWN)

# Переход к tease — либо AI сигнализировал, либо 3+ обмена
if result["move_to_tease"] or replies >= 3:
    await asyncio.sleep(2.5)
    await _send_tease(context.bot, user_id, chat_id, lang, interest, geo=geo)
```

def _is_fallback_response(response: str, lang: str) -> bool:
fallback_starts = [
“There are patterns in how lines move”,
“Hay patrones en cómo se mueven”,
“Postoje obrasci u tome kako se kvote”,
“Yra modeliai kaip koeficientai”,
“Ir modeļi kā koeficienti”,
]
return any(response.strip().startswith(s) for s in fallback_starts)

# ════════════════════════════════════════════════════════════════════════════

# TEASE handler

# ════════════════════════════════════════════════════════════════════════════

async def _handle_tease(update, context, user_id, lang, interest, geo, user_text):
“””
Пользователь написал что-то на TEASE этапе.
Валерия отвечает на возражение и СРАЗУ переходит в CTA.
Нет смысла держать в TEASE — время продавать.
“””
chat_id = update.effective_chat.id
history = get_ai_history(user_id)
psychotype, objections, used_techniques = _prepare_context(user_id, user_text)
profile = get_profile(user_id)

```
await context.bot.send_chat_action(chat_id, "typing")
response, refined, _, technique_used = await ask_valeria(
    user_message=user_text, history=history, lang=lang, interest=interest,
    funnel_stage="cta",  # сразу CTA промпт — TEASE уже был показан
    psychotype=psychotype, objections=objections,
    used_techniques=used_techniques, geo=geo, user_profile=profile)

if technique_used: log_technique(user_id, technique_used)
add_ai_message(user_id, "user", user_text)
add_ai_message(user_id, "assistant", response)
add_tone(user_id, detect_tone(user_text, history))
if refined != interest: update_user(user_id, interest=refined); interest = refined

await asyncio.sleep(_typing_delay(response) * 0.5)
await update.message.reply_text(response, parse_mode=ParseMode.MARKDOWN)

# Всегда переходим в CTA после ответа на TEASE
await asyncio.sleep(2.0)
await context.bot.send_chat_action(chat_id, "typing")
await asyncio.sleep(1.0)
await _send_cta(context.bot, user_id, chat_id, lang, interest, geo)
```

# ════════════════════════════════════════════════════════════════════════════

# CTA handler

# ════════════════════════════════════════════════════════════════════════════

async def _handle_cta(update, context, user_id, lang, interest, geo, user_text):
“””
Пользователь написал на CTA этапе.
Обрабатываем возражение. Кнопку напоминаем раз в 3 сообщения.
“””
chat_id  = update.effective_chat.id
history  = get_ai_history(user_id)
user     = get_user(user_id)
psychotype, objections, used_techniques = _prepare_context(user_id, user_text)
profile  = get_profile(user_id)

```
await context.bot.send_chat_action(chat_id, "typing")
response, _, _, technique_used = await ask_valeria(
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

# Кнопку напоминаем раз в 3 сообщения — не спамим
if cta_replies % 3 == 0:
    await asyncio.sleep(2.0)
    await _send_cta(context.bot, user_id, chat_id, lang, interest, geo)
```

# ════════════════════════════════════════════════════════════════════════════

# AI Chat (subscribed) — чистый диалог через ask_valeria_conversational

# ════════════════════════════════════════════════════════════════════════════

async def _handle_ai_chat(update, context, user_id, lang, interest, geo, user_text, user):
chat_id      = update.effective_chat.id
funnel_stage = user.get(“funnel_stage”, “subscribed”)
history      = get_ai_history(user_id)
msg_count    = user.get(“ai_msg_count”, 0)
psychotype   = get_psychotype(user_id)
objections   = get_objections(user_id)
profile      = get_profile(user_id)
ftd_done     = bool(user.get(“ftd_done”))
ftd_count    = user.get(“ftd_count”, 0)

```
obj_type = classify_objection(user_text)
if obj_type:
    log_objection(user_id, obj_type)

add_ai_message(user_id, "user", user_text)
update_user(user_id, ai_msg_count=msg_count + 1)
await context.bot.send_chat_action(chat_id, "typing")

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

# Обновляем interest если AI переключил
if result["detected_interest"] and result["detected_interest"] != interest:
    update_user(user_id, interest=result["detected_interest"])
    interest = result["detected_interest"]

# Трекаем позитивные сообщения → реферал после 5
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

# Калькулятор на 3-м, 8-м, 15-м сообщении для casino/nodeposit
new_count = msg_count + 1
if should_show_calculator(interest, funnel_stage, new_count):
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
```

# ════════════════════════════════════════════════════════════════════════════

# /stats, /help, /admin_fetch_ids, /debug

# ════════════════════════════════════════════════════════════════════════════

async def calc_deposit_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
“”“Пользователь выбрал размер депозита в калькуляторе.”””
query   = update.callback_query; await query.answer()
user_id = query.from_user.id
user    = get_user(user_id)
lang    = user.get(“lang”, “en”)
interest= user.get(“interest”, “betting”)
chat_id = query.message.chat_id

```
deposit = parse_deposit_callback(query.data)
if deposit is None: return

try: await query.edit_message_reply_markup(reply_markup=None)
except Exception: pass

# Для betting — показываем stake buttons
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

# Для casino/nodeposit — сразу результат
await context.bot.send_chat_action(chat_id, "typing")
await asyncio.sleep(1.5)
result_text = format_casino_result(lang, deposit, interest)
await context.bot.send_message(
    chat_id=chat_id, text=result_text, parse_mode=ParseMode.MARKDOWN)
add_ai_message(user_id, "assistant", result_text)
```

async def calc_stake_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
“”“Пользователь выбрал размер ставки (для betting).”””
query   = update.callback_query; await query.answer()
user_id = query.from_user.id
user    = get_user(user_id)
lang    = user.get(“lang”, “en”)
chat_id = query.message.chat_id

```
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
```

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
users = get_all_users()
by_state, by_lang, by_geo, subscribed = {}, {}, {}, 0
for u in users:
s = u.get(“state”,”?”); by_state[s] = by_state.get(s,0)+1
l = u.get(“lang”,”?”);  by_lang[l]  = by_lang.get(l,0)+1
g = u.get(“geo”,”?”);   by_geo[g]   = by_geo.get(g,0)+1
if u.get(“funnel_stage”) == “subscribed”: subscribed += 1
text = (f”📊 *OddsVault Stats*\n\nTotal: *{len(users)}* | Subscribed: *{subscribed}*\n\n”
“By state:\n” + “\n”.join(f”  {s}: {c}” for s,c in sorted(by_state.items())) +
“\n\nBy lang:\n” + “\n”.join(f”  {l}: {c}” for l,c in sorted(by_lang.items())) +
“\n\nBy GEO:\n” + “\n”.join(f”  {g}: {c}” for g,c in sorted(by_geo.items())))
await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

async def admin_ab_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
“”“A/B тест статистика.”””
stats = get_ab_stats()
text  = format_ab_stats_message(stats)
await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
user = get_user(update.effective_user.id)
lang = user.get(“lang”, “en”)
texts = {“en”:“ℹ️ I’m Valeria. Use /start to begin.”,
“es”:“ℹ️ Soy Valeria. Usa /start para empezar.”,
“hr”:“ℹ️ Ja sam Valerija. Koristi /start za početak.”,
“lt”:“ℹ️ Aš esu Valerija. Naudok /start pradėti.”,
“lv”:“ℹ️ Es esmu Valerija. Izmanto /start lai sāktu.”}
await update.message.reply_text(texts.get(lang, texts[“en”]))

async def admin_fetch_ids(update: Update, context: ContextTypes.DEFAULT_TYPE):
await update.message.reply_text(“🔍 Fetching channel IDs…”)
ids = await fetch_channel_ids(context.bot)
if not ids:
await update.message.reply_text(“❌ No IDs found. Is bot admin in channels?”); return
lines = [f”`{k}`: `{v}`” for k, v in ids.items()]
await update.message.reply_text(
“📋 *Channel IDs* — copy to membership.py:\n\n” + “\n”.join(lines),
parse_mode=ParseMode.MARKDOWN)

async def debug_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
“”“Диагностика: тестирует реальный вызов Anthropic API.”””
user_id = update.effective_user.id
user    = get_user(user_id)

```
key_status = "✅ SET" if ANTHROPIC_KEY else "❌ MISSING"

# Реальный тест API
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
    f"`fallback_count`: `{user.get('fallback_count',0)}`"
)
await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
```

# ════════════════════════════════════════════════════════════════════════════

# Jobs

# ════════════════════════════════════════════════════════════════════════════

async def reengage_job(context: ContextTypes.DEFAULT_TYPE):
now = datetime.now(timezone.utc).timestamp()
for user in get_all_users():
user_id = user.get(“id”)
if not user_id: continue
if user.get(“funnel_stage”,“new”) in (“new”,“subscribed”): continue
if user.get(“funnel_stage”) not in (“cta”,“tease”,“warming”): continue
try:
lt = datetime.fromisoformat(user[“last_active”])
if lt.tzinfo is None: lt = lt.replace(tzinfo=timezone.utc)
elapsed = now - lt.timestamp()
except Exception: continue

```
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
```

async def subscribed_push_job(context: ContextTypes.DEFAULT_TYPE):
“””
Умный silence push — один точечный вопрос если молчат >4 часов.
Не серия. Не монолог. Один вопрос → ждём ответа.
“””
for user in get_all_users():
user_id = user.get(“id”)
if not user_id or user.get(“funnel_stage”) != “subscribed”:
continue

```
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
```

# ════════════════════════════════════════════════════════════════════════════

# Entry point

# ════════════════════════════════════════════════════════════════════════════

def main():
token = os.getenv(“BOT_TOKEN”, BOT_TOKEN)
if not token:
logger.error(“BOT_TOKEN not set!”); sys.exit(1)

```
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
app.add_handler(CommandHandler("admin_ab",        admin_ab_stats))

app.add_handler(CallbackQueryHandler(lang_chosen,       pattern=r"^lang_"))
app.add_handler(CallbackQueryHandler(interest_chosen,   pattern=r"^int_"))
app.add_handler(CallbackQueryHandler(geo_chosen,        pattern=r"^geo_"))
app.add_handler(CallbackQueryHandler(commitment_chosen, pattern=r"^cm_"))
app.add_handler(CallbackQueryHandler(user_joined,       pattern=r"^user_joined$"))
app.add_handler(CallbackQueryHandler(calc_deposit_chosen, pattern=r"^calc_dep_"))
app.add_handler(CallbackQueryHandler(calc_stake_chosen,   pattern=r"^calc_stake_"))

app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

app.job_queue.run_repeating(reengage_job,        interval=30*60,  first=60)
app.job_queue.run_repeating(subscribed_push_job, interval=60*60,  first=120)
app.job_queue.run_repeating(daily_signal_job,    interval=60*60,  first=300)   # каждый час, проверяет таймзону
app.job_queue.run_repeating(adrenaline_check_job,interval=15*60,  first=180)   # каждые 15 мин

logger.info("OddsVault Bot v10 🚀  Valeria is online.")
app.run_polling(drop_pending_updates=True)
```

if **name** == “**main**”:
main()
