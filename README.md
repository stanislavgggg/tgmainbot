# 🔐 OddsVault Bot

**Персонаж:** Valeria — аналитик ставок и бонусов. Умный друг, не бот.  
**Воронка:** Белфорт — HOOK → QUIZ → WARM1 → WARM2 → TEASE → CTA → AI_CHAT  
**Каналы:** ApuestasGuru (ES) · BetCroatia (HR) · LuckyGuru (LT) · LuckyLatvia (LV)

---

## Структура проекта

```
oddsvault/
├── bot.py          # FSM-воронка, все handlers
├── config.py       # токены, каналы, State enum, константы
├── messages.py     # все тексты на 4 языках
├── ai_agent.py     # Valeria — Anthropic Claude API
├── storage.py      # хранилище пользователей (JSON / in-memory)
├── requirements.txt
├── Procfile
├── railway.toml
└── images/         # папка для картинок по интересам (создай сам)
    ├── betting/
    ├── casino/
    ├── nodeposit/
    └── exclusive/
```

---

## Переменные окружения (Railway → Variables)

| Переменная | Обязательна | Описание |
|---|---|---|
| `BOT_TOKEN` | ✅ | Токен бота от @BotFather |
| `ANTHROPIC_API_KEY` | ✅ | Ключ Claude API для Valeria |
| `DB_FILE` | ❌ | Путь к JSON-базе (default: `users.json`) |

---

## Деплой на Railway

```bash
# 1. Залить на GitHub
git init
git add .
git commit -m "OddsVault Bot v1"
git remote add origin https://github.com/YOUR/REPO.git
git push -u origin main

# 2. Railway → New Project → GitHub repo
# 3. Variables → добавить BOT_TOKEN и ANTHROPIC_API_KEY
# 4. Deploy → бот стартует автоматически
```

---

## Воронка (как работает)

```
/start
  ↓
HOOK — Valeria представляется, крючок
  ↓
Выбор языка (ES / HR / LT / LV)
  ↓
QUIZ — «что тебя интересует?»
  ↓ пользователь выбирает интерес
WARM1 — история, момент, вопрос
  ↓ ЖДЁМ РЕАКЦИИ пользователя
AI отвечает на ответ → WARM2
  ↓ ЖДЁМ РЕАКЦИИ пользователя
AI отвечает на ответ → TEASE (FOMO, дедлайн)
  ↓ ЖДЁМ РЕАКЦИИ пользователя
AI отвечает → CTA (кнопка канала)
  ↓
  ├─ нажал кнопку канала
  │     ↓
  └─ «Уже вступил» → POST_SUB → AI_CHAT
          ↓
        Свободный AI-чат (Valeria как эксперт)
        FTD-пуш каждые 5 сообщений
        Картинка каждые 4 сообщения

Re-engage (если не подписался):
  24ч → REENGAGE_1
  48ч → REENGAGE_2
```

---

## Как добавить картинки

Создай папку `images/` и подпапки по интересам:
```
images/betting/img1.jpg
images/casino/img1.jpg
...
```

Затем в `config.py` заполни:
```python
INTEREST_IMAGES = {
    "betting":   ["images/betting/img1.jpg", "images/betting/img2.jpg"],
    "casino":    ["images/casino/img1.jpg"],
    ...
}
```

---

## Как изменить тексты

Всё в `messages.py`. Структура:
- `HOOK` — первое сообщение
- `QUIZ` / `QUIZ_BUTTONS` — квиз
- `WARM1[lang][interest]` — прогрев 1
- `WARM2[lang]` — прогрев 2
- `TEASE[lang][interest]` — тизер
- `CTA_TEXT` / `CTA` / `CTA_BUTTON_JOINED` — кнопки
- `POST_SUB[lang][interest]` — после подписки
- `REENGAGE_1/2[lang]` — повторные пуши
- `FTD_PUSH[lang][interest]` — каждые 5 сообщений

---

## Про Telegram Policy

Бот **не рекламирует казино**. Valeria делится:
- Публично доступной информацией о бонусах
- Аналитикой коэффициентов
- Образовательным контентом о рынке

Нет: «зарегистрируйся», «выиграй деньги», «лучший казино».  
Есть: «вот что я нашла», «вот анализ», «интересное движение на рынке».

---

## Локальный запуск

```bash
pip install -r requirements.txt
export BOT_TOKEN=your_token
export ANTHROPIC_API_KEY=your_key
python bot.py
```
