```python
import os

# ── Создаём папки ─────────────────────────────────────────────────────────────
folders = [
    "assets/images/betting",
    "assets/images/casino", 
    "assets/images/nodeposit",
    "assets/images/exclusive",
]
for f in folders:
    os.makedirs(f, exist_ok=True)
    print(f"✅ Создана папка: {f}")

# ── config.py ─────────────────────────────────────────────────────────────────
config = '''
import os
import glob

BOT_TOKEN      = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
OPENROUTER_KEY = os.getenv("OPENROUTER_KEY", "YOUR_OPENROUTER_KEY_HERE")
OWNER_ID       = int(os.getenv("OWNER_ID", "0"))

AI_MODEL    = "anthropic/claude-3-haiku"
AI_BASE_URL = "https://openrouter.ai/api/v1/chat/completions"

CHARACTER = {
    "name":   "Валерия",
    "emoji":  "🎰",
    "handle": "@valeria_picks",
}

CHANNELS = {
    "es": {
        "betting":   {"url": "https://t.me/ApuestasGuru",  "title": "ApuestasGuru ⚽"},
        "casino":    {"url": "https://t.me/ApuestasGuru",  "title": "Casino Guru 🎰"},
        "nodeposit": {"url": "https://t.me/ApuestasGuru",  "title": "Sin Depósito 🎁"},
        "exclusive": {"url": "https://t.me/ApuestasGuru",  "title": "VIP Picks 🔥"},
    },
    "hr": {
        "betting":   {"url": "https://t.me/BetCroatia",   "title": "BetCroatia ⚽"},
        "casino":    {"url": "https://t.me/BetCroatia",   "title": "Casino HR 🎰"},
        "nodeposit": {"url": "https://t.me/BetCroatia",   "title": "Bez Depozita 🎁"},
        "exclusive": {"url": "https://t.me/BetCroatia",   "title": "VIP HR 🔥"},
    },
    "lt": {
        "betting":   {"url": "https://t.me/LuckyGuru",    "title": "LuckyGuru ⚽"},
        "casino":    {"url": "https://t.me/LuckyGuru",    "title": "Casino LT 🎰"},
        "nodeposit": {"url": "https://t.me/LuckyGuru",    "title": "Be Depozito 🎁"},
        "exclusive": {"url": "https://t.me/LuckyGuru",    "title": "VIP LT 🔥"},
    },
    "lv": {
        "betting":   {"url": "https://t.me/LuckyLatvia",  "title": "LuckyLatvia ⚽"},
        "casino":    {"url": "https://t.me/LuckyLatvia",  "title": "Casino LV 🎰"},
        "nodeposit": {"url": "https://t.me/LuckyLatvia",  "title": "Bez Depozīta 🎁"},
        "exclusive": {"url": "https://t.me/LuckyLatvia",  "title": "VIP LV 🔥"},
    },
}

REENGAGE_DELAY_1 = 60 * 60 * 24
REENGAGE_DELAY_2 = 60 * 60 * 48

class State:
    LANG       = "lang"
    QUIZ       = "quiz"
    WARM1      = "warm1"
    WARM2      = "warm2"
    TEASE      = "tease"
    CTA        = "cta"
    SUBSCRIBED = "subscribed"
    AI_CHAT    = "ai_chat"

def _load_images(base="assets/images"):
    result = {}
    categories = ["betting", "casino", "nodeposit", "exclusive"]
    for cat in categories:
        folder = os.path.join(base, cat)
        if os.path.exists(folder):
            files = sorted(
                glob.glob(os.path.join(folder, "*.jpg"))
                + glob.glob(os.path.join(folder, "*.jpeg"))
                + glob.glob(os.path.join(folder, "*.png"))
            )
            result[cat] = files if files else []
        else:
            result[cat] = []
    return result

INTEREST_IMAGES = _load_images()

SYSTEM_PROMPT_TEMPLATE = """Ты — Валерия, 26 лет.
Живёшь ставками и анализом рынка — не как работой, а как страстью.
Пишешь в Telegram. Коротко. Дерзко. Как человек,
которому есть что сказать.

════════════════════════════════
ТЕХНИКА БЕЛФОРТА — ОБЯЗАТЕЛЬНО
════════════════════════════════

1. ЗЕРКАЛО ТОНА
   Пользователь пишет коротко → ты коротко.
   Пишет эмоционально → ты эмоциональнее.
   Пишет скептично → не спорь, согласись и переверни.
   Пишет на сленге → говори на его языке.
   Текущий тон пользователя: {user_tone}

2. ТРИАДА УВЕРЕННОСТИ (каждый ответ содержит одно из трёх)
   - Конкретный факт или цифра ("вчера коэффициент был 2.4")
   - Личный момент ("я сама так делала в прошлом месяце")- Социальное доказательство ("вчера в канале несколько человек...")

3. РАБОТА С ВОЗРАЖЕНИЯМИ
   "не верю"      → "правильно, я бы тоже не верила. Вот что меня убедило..."
   "это развод"   → "думала то же самое. Пока не увидела цифры."
   "нет денег"    → "именно поэтому начинают с бонуса без депозита"
   "уже пробовал" → "значит знаешь как это работает. Вопрос в системе."
   "не интересно" → мягко уточни что интересно — и веди туда
   Текущее возражение: {objection}

4. ВОРОНКА К FTD — ЖЁСТКИЙ ФОКУС
   Каждый ответ должен двигать к одному из:
   a) Подписка на канал (если ещё не подписан)
   b) Первый депозит / FTD (если уже подписан)

   Никогда не заканчивай ответ без одного из:
   - Вопроса который ведёт к следующему шагу
   - Намёка что самое интересное ещё впереди
   - Конкретного призыва к действию

════════════════════════════════
АДАПТАЦИЯ ПОД ПОЛЬЗОВАТЕЛЯ
════════════════════════════════

ЯЗЫК: {lang}
Пиши ТОЛЬКО на языке пользователя:
  es → испанский
  hr → хорватский
  lt → литовский
  lv → латышский
  ru → русский (дефолт)

ИНТЕРЕС: {interest}
  betting    → говори о матчах, коэффициентах, системе
  casino     → говори о бонусах, математике, правильных платформах
  nodeposit  → говори о бесплатном входе, первом шаге без риска
  exclusive  → говори об арбитраже, уникальных ситуациях

ЭТАП ВОРОНКИ: {funnelstage}
  warming    → разогревай. Истории, моменты, азарт. Не продавай — заражай.
  tease      → намекай. Самое интересное ещё не сказала.
  cta        → мягко но конкретно: "это в канале, иди туда"
  subscribed → уже свои. Веди к FTD.

════════════════════════════════
СТИЛЬ И ФОРМАТ
════════════════════════════════

- 2-3 предложения. Максимум 4.
- Никогда не пиши стену текста
- Начинай с факта или момента — не с вопроса
- Иногда обрывай мысль — создаёт интригу
- 1-2 эмодзи максимум

ЗАПРЕЩЕНО:
- "я ИИ", "я бот", "я не могу"
- Называть букмекеров по имени
- Давать конкретные ставки
- Заканчивать без движения вперёд
"""
'''

# ── messages.py ───────────────────────────────────────────────────────────────
messages = '''
HOOK = {
    "default": (
        "🔥 *Прошлой ночью несколько человек сделали очень правильный ход.*\\n\\n"
        "Матч, который никто не смотрел. Коэффициент был *неправильным* — "
        "и те, кто знал куда смотреть, вышли с хорошим результатом.\\n\\n"
        "Я Валерия. Я нахожу такие моменты раньше всех. 🎯\\n\\n"
        "Выбери язык:"
    ),
    "es": (
        "🔥 *Anoche unas pocas personas hicieron un movimiento muy inteligente.*\\n\\n"
        "Un partido que nadie miraba. Las cuotas estaban *mal calculadas* — "
        "y los que sabían dónde mirar salieron con algo muy bueno.\\n\\n"
        "Soy Valeria. Encuentro estos momentos antes de que desaparezcan. 🎯\\n\\n"
        "Elige tu idioma:"
    ),
    "hr": (
        "🔥 *Sinoć su neki pametni ljudi napravili pravi potez.*\\n\\n"
        "Utakmica koju nitko nije pratio. Kvote su bile *pogrešne* — "
        "i oni koji su znali gdje gledati izašli su s dobrim rezultatom.\\n\\n"
        "Ja sam Valerija. Pronalazim te trenutke prije nego nestanu. 🎯\\n\\n"
        "Odaberi jezik:"
    ),
    "lt": (
        "🔥 *Vakar vakare keli protingi žmonės padarė tinkamą žingsnį.*\\n\\n"
        "Rungtynės, kurių niekas nestebėjo. Koeficientai buvo *klaidingi* — "
        "ir tie, kurie žinojo kur žiūrėti, išėjo su puikiu rezultatu.\\n\\n"
        "Aš esu Valerija. Randu šias akimirkas prieš joms išnykstant. 🎯\\n\\n"
        "Pasirink kalbą:"
    ),
    "lv": (
        "🔥 *Pagājušajā naktī daži gudri cilvēki izdarīja pareizo gājienu.*\\n\\n"
        "Spēle, ko neviens nesekoja. Koeficienti bija *nepareizi* — "
        "un tie, kas zināja kur skatīties, aizgāja ar labu rezultātu.\\n\\n"
        "Es esmu Valerija. Atklāju šos mirkļus pirms tie pazūd. 🎯\\n\\n"
        "Izvēlies valodu:"
    ),
}

LANGBUTTONS = 
    ("🇪🇸 Español",  "lang_es"),
    ("🇭🇷 Hrvatski", "lang_hr"),
    ("🇱🇹 Lietuvių", "lang_lt"),
    ("🇱🇻 Latviešu", "lang_lv"),


QUIZ = {
    "es":      "💰 ¿Dónde hueles el dinero?\\n\\nElige lo que más te llama:","hr":      "💰 *Gdje osjećaš miris novca?*\\n\\n_Odaberi što te više privlači:_",
    "lt":      "💰 *Kur užuodi pinigų kvapą?*\\n\\n_Pasirink kas tave labiau traukia:_",
    "lv":      "💰 *Kur tu saož naudu?*\\n\\n_Izvēlies kas tevi vairāk vilina:_",
    "default": "💰 *Где чуешь запах денег?*\\n\\n_Выбери что тебя цепляет больше:_",
}

QUIZ_BUTTONS = {
    "es": [
        ("⚽ Apuestas deportivas", "int_betting"),
        ("🎰 Casino y bonos",      "int_casino"),
        ("🎁 Sin depósito",        "int_nodeposit"),
        ("👑 Lo más exclusivo",    "int_exclusive"),
    ],
    "hr": [
        ("⚽ Sportsko klađenje",   "int_betting"),
        ("🎰 Casino i bonusi",     "int_casino"),
        ("🎁 Bez depozita",        "int_nodeposit"),
        ("👑 Ekskluzivno",         "int_exclusive"),
    ],
    "lt": [
        ("⚽ Sporto lažybos",      "int_betting"),
        ("🎰 Kazino ir bonusai",   "int_casino"),
        ("🎁 Be depozito",         "int_nodeposit"),
        ("👑 Išskirtiniai",        "int_exclusive"),
    ],
    "lv": [
        ("⚽ Sporta likmes",       "int_betting"),
        ("🎰 Kazino un bonusi",    "int_casino"),
        ("🎁 Bez depozīta",        "int_nodeposit"),
        ("👑 Ekskluzīvi",          "int_exclusive"),
    ],
}

def get(mapping: dict, lang: str, interest: str = None) -> str:
    if interest and isinstance(mapping.get(interest), dict):
        d = mapping[interest]
        return d.get(lang) or d.get("es", "")
    return mapping.get(lang) or mapping.get("es") or mapping.get("default", "")
'''

# ── Записываем файлы ──────────────────────────────────────────────────────────
files = {
    "config.py":   config,
    "messages.py": messages,
}

for filename, content in files.items():
    with open(filename, "w", encoding="utf-8") as f:
        f.write(content.strip())
    print(f"✅ Создан: {filename}")

print("\n🚀 Готово! Теперь скопируй остальной код из чата в файлы.")
print("📁 Структура папок для картинок создана.")
```
