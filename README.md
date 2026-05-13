# 🤖 Telegram Router Bot

Multilingual Telegram bot that routes users to your channels based on **language** and **content category** (betting tips, casino info, no-deposit bonuses, exclusive deals).

Channels covered:
| Language | Category | Channel |
|---|---|---|
| 🇪🇸 Spanish | Betting | ApuestasGuru |
| 🇭🇷 Croatian | Betting | BetCroatia |
| 🇱🇹 Lithuanian | Casino | LuckyGuru |
| 🇱🇻 Latvian | Casino | Lucky Latvia |

---

## 🚀 Quick Deploy (GitHub → Railway)

### 1. Push to GitHub

```bash
git init
git add .
git commit -m "initial bot"
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git
git push -u origin main
```

### 2. Deploy on Railway

1. Go to [railway.app](https://railway.app) → **New Project** → **Deploy from GitHub repo**
2. Pick your repo
3. Go to **Variables** tab and add:

```
BOT_TOKEN=8840016683:AAFRXj04QarjrC0OfVefeCTCaTWz4HnO6Sk
```

4. Railway auto-detects `railway.toml` and starts the bot as a worker.

> ⚠️ **Important:** Never commit the token to git. Set it only as an env var on Railway.

---

## ⚙️ Configuration (`config.py`)

### Updating channel links

Open `config.py` and replace the placeholder URLs in `CHANNELS`:

```python
CHANNELS = {
    "es": {
        "betting": {
            "url": "https://t.me/YourRealSpanishChannel",
        },
        ...
    },
    ...
}
```

Each category can have:
- `url` — primary CTA button link (required)
- `extra_url` — second button, e.g. your website (optional, leave `""` to hide)

### Updating message copy

All user-facing text lives in `MESSAGES` inside `config.py`. Edit freely — the structure is:

```python
MESSAGES = {
    "es": {
        "category_prompt": "...",       # shown after language select
        "channel_info": {
            "betting":   "...",          # shown after category select
            "casino":    "...",
            "nodeposit": "...",
            "exclusive": "...",
        },
        "join_button": "Go to Channel",  # CTA button label
        "more_button":  "More info",
        "back":         "Change language",
    },
    ...
}
```

---

## 🏗️ Project Structure

```
tg-router-bot/
├── bot.py           # handlers & application entry point
├── config.py        # channels, tokens, all localised copy
├── requirements.txt
├── Procfile         # Railway / Heroku process file
├── railway.toml     # Railway build config
└── .gitignore
```

---

## 📜 Telegram Policy Note

This bot complies with Telegram's rules:
- We **do not** promote gambling directly.
- We share **publicly available** bonus and odds information.
- All channel descriptions use informational/educational framing.
- No deceptive claims, no guaranteed wins language.

---

## 🛠️ Local Development

```bash
pip install -r requirements.txt
BOT_TOKEN=your_token python bot.py
```
