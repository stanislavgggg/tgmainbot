"""
config.py — channel URLs & all localised strings.

HOW TO EDIT:
  1. Replace every "https://t.me/YOUR_CHANNEL_HERE" with your real channel / group links.
  2. Add or remove categories per language as needed.
  3. All user-facing copy lives here — easy to A/B test.
"""

import os

# ─────────────────────────────────────────────────────────────────
#  Bot token (override via env var BOT_TOKEN on Railway)
# ─────────────────────────────────────────────────────────────────
BOT_TOKEN = os.getenv("BOT_TOKEN", "8840016683:AAFRXj04QarjrC0OfVefeCTCaTWz4HnO6Sk")


# ─────────────────────────────────────────────────────────────────
#  Channel / group links per language & category
#
#  Keys: betting | casino | nodeposit | exclusive
#  "url"       — primary deep-link (shown as main CTA button)
#  "extra_url" — optional second link (e.g. website)
# ─────────────────────────────────────────────────────────────────
CHANNELS = {
    # ── Spanish (ES) ─────────────────────────────────────────────
    "es": {
        "betting": {
            "url":       "https://t.me/ApuestasGuru",          # ← your channel
            "extra_url": "",
        },
        "casino": {
            "url":       "https://t.me/ApuestasGuru",
            "extra_url": "",
        },
        "nodeposit": {
            "url":       "https://t.me/ApuestasGuru",
            "extra_url": "",
        },
        "exclusive": {
            "url":       "https://t.me/ApuestasGuru",
            "extra_url": "",
        },
    },

    # ── Croatian (HR) ────────────────────────────────────────────
    "hr": {
        "betting": {
            "url":       "https://t.me/BetCroatia",
            "extra_url": "",
        },
        "casino": {
            "url":       "https://t.me/BetCroatia",
            "extra_url": "",
        },
        "nodeposit": {
            "url":       "https://t.me/BetCroatia",
            "extra_url": "",
        },
        "exclusive": {
            "url":       "https://t.me/BetCroatia",
            "extra_url": "",
        },
    },

    # ── Lithuanian (LT) ──────────────────────────────────────────
    "lt": {
        "betting": {
            "url":       "https://t.me/LuckyGuru",
            "extra_url": "",
        },
        "casino": {
            "url":       "https://t.me/LuckyGuru",
            "extra_url": "",
        },
        "nodeposit": {
            "url":       "https://t.me/LuckyGuru",
            "extra_url": "",
        },
        "exclusive": {
            "url":       "https://t.me/LuckyGuru",
            "extra_url": "",
        },
    },

    # ── Latvian (LV) ─────────────────────────────────────────────
    "lv": {
        "betting": {
            "url":       "https://t.me/LuckyLatvia",
            "extra_url": "",
        },
        "casino": {
            "url":       "https://t.me/LuckyLatvia",
            "extra_url": "",
        },
        "nodeposit": {
            "url":       "https://t.me/LuckyLatvia",
            "extra_url": "",
        },
        "exclusive": {
            "url":       "https://t.me/LuckyLatvia",
            "extra_url": "",
        },
    },
}


# ─────────────────────────────────────────────────────────────────
#  All localised UI strings & message copy
# ─────────────────────────────────────────────────────────────────
MESSAGES = {

    # ── Spanish ──────────────────────────────────────────────────
    "es": {
        "category_prompt": (
            "🇪🇸 *¡Hola!* Aquí compartimos información sobre apuestas deportivas, "
            "bonos y noticias del sector.\n\n"
            "📌 *¿Qué te interesa hoy?*"
        ),
        "channel_info": {
            "betting": (
                "⚽ *Apuestas Deportivas — ApuestasGuru*\n\n"
                "Nuestro canal comparte:\n"
                "• 📊 Análisis de cuotas y tendencias del mercado\n"
                "• 🔍 Comparativas de las mejores casas de apuestas\n"
                "• 📰 Noticias y estadísticas deportivas\n"
                "• 🎯 Tips educativos sobre cómo leer las cuotas\n\n"
                "💡 _Información pública y educativa. Apuesta con responsabilidad._"
            ),
            "casino": (
                "🎰 *Casino Info — ApuestasGuru*\n\n"
                "Compartimos información sobre:\n"
                "• 🎁 Bonos de bienvenida disponibles públicamente\n"
                "• 🔄 Programas de fidelidad y recompensas\n"
                "• 📋 Reseñas y comparativas de plataformas\n"
                "• 💎 Torneos y eventos especiales\n\n"
                "💡 _Contenido informativo. Siempre verifica los T&C._"
            ),
            "nodeposit": (
                "🎁 *Bonos Sin Depósito — ApuestasGuru*\n\n"
                "Recopilamos información sobre:\n"
                "• ✅ Bonos sin depósito disponibles en España\n"
                "• 🆓 Giros gratis sin depósito\n"
                "• 📌 Códigos promocionales públicos\n"
                "• ⚡ Ofertas por tiempo limitado\n\n"
                "💡 _Información recopilada de fuentes públicas._"
            ),
            "exclusive": (
                "🔥 *Ofertas Exclusivas — ApuestasGuru*\n\n"
                "Lo mejor que encontramos esta semana:\n"
                "• 🏆 Mejores cuotas del mercado español\n"
                "• 💰 Bonos con las mejores condiciones\n"
                "• 🎯 Análisis de value betting\n"
                "• 📈 Tendencias del mercado\n\n"
                "💡 _Todo el contenido es informativo y educativo._"
            ),
        },
        "join_button": "📲 Ir al Canal",
        "more_button":  "🌐 Ver más info",
        "back":         "Cambiar idioma",
    },

    # ── Croatian ─────────────────────────────────────────────────
    "hr": {
        "category_prompt": (
            "🇭🇷 *Pozdrav!* Dijelimo informacije o sportskom klađenju, "
            "bonusima i vijestima iz industrije.\n\n"
            "📌 *Što vas zanima danas?*"
        ),
        "channel_info": {
            "betting": (
                "⚽ *Sportsko Klađenje — BetCroatia*\n\n"
                "Naš kanal dijeli:\n"
                "• 📊 Analiza kvota i tržišnih trendova\n"
                "• 🔍 Usporedbe kladionica\n"
                "• 📰 Sportske vijesti i statistike\n"
                "• 🎯 Edukativni savjeti za razumijevanje kvota\n\n"
                "💡 _Javne i edukativne informacije. Kladite se odgovorno._"
            ),
            "casino": (
                "🎰 *Casino Info — BetCroatia*\n\n"
                "Dijelimo informacije o:\n"
                "• 🎁 Javno dostupnim dobrodošlicama bonusima\n"
                "• 🔄 Programima lojalnosti\n"
                "• 📋 Recenzijama i usporedbama platformi\n"
                "• 💎 Turnirima i posebnim događajima\n\n"
                "💡 _Informativni sadržaj. Uvijek provjerite uvjete._"
            ),
            "nodeposit": (
                "🎁 *Bonusi Bez Depozita — BetCroatia*\n\n"
                "Skupljamo informacije o:\n"
                "• ✅ Bonusima bez depozita dostupnim u HR\n"
                "• 🆓 Besplatnim okretajima bez depozita\n"
                "• 📌 Javnim promocijskim kodovima\n"
                "• ⚡ Vremenski ograničenim ponudama\n\n"
                "💡 _Informacije prikupljene iz javnih izvora._"
            ),
            "exclusive": (
                "🔥 *Ekskluzivne Ponude — BetCroatia*\n\n"
                "Najbolje što smo pronašli ovaj tjedan:\n"
                "• 🏆 Najbolje kvote na hrvatskom tržištu\n"
                "• 💰 Bonusi s najboljim uvjetima\n"
                "• 🎯 Analiza value bettinga\n"
                "• 📈 Trendovi na tržištu\n\n"
                "💡 _Sav sadržaj je informativan i edukativni._"
            ),
        },
        "join_button": "📲 Idi na Kanal",
        "more_button":  "🌐 Više informacija",
        "back":         "Promijeni jezik",
    },

    # ── Lithuanian ───────────────────────────────────────────────
    "lt": {
        "category_prompt": (
            "🇱🇹 *Sveiki!* Dalinamės informacija apie sporto lažybas, "
            "premijas ir pramonės naujienas.\n\n"
            "📌 *Kas jus domina šiandien?*"
        ),
        "channel_info": {
            "betting": (
                "⚽ *Sporto Lažybos — LuckyGuru*\n\n"
                "Mūsų kanalas dalinasi:\n"
                "• 📊 Koeficientų analizė ir rinkos tendencijos\n"
                "• 🔍 Lažybų kontorų palyginimas\n"
                "• 📰 Sporto naujienos ir statistika\n"
                "• 🎯 Edukacinis turinys apie koeficientus\n\n"
                "💡 _Vieša ir edukacinė informacija. Lažinkitės atsakingai._"
            ),
            "casino": (
                "🎰 *Kazino Informacija — LuckyGuru*\n\n"
                "Dalinamės informacija apie:\n"
                "• 🎁 Viešai prieinamas sveikinamąsias premijas\n"
                "• 🔄 Lojalumo programas\n"
                "• 📋 Platformų apžvalgas ir palyginimus\n"
                "• 💎 Turnyrus ir specialius renginius\n\n"
                "💡 _Informacinis turinys. Visada patikrinkite sąlygas._"
            ),
            "nodeposit": (
                "🎁 *Premijos Be Depozito — LuckyGuru*\n\n"
                "Renkame informaciją apie:\n"
                "• ✅ Be depozito premijas, prieinamas LT\n"
                "• 🆓 Nemokamus sukimus be depozito\n"
                "• 📌 Viešus reklaminius kodus\n"
                "• ⚡ Riboto laiko pasiūlymus\n\n"
                "💡 _Informacija surinkta iš viešų šaltinių._"
            ),
            "exclusive": (
                "🔥 *Išskirtiniai Pasiūlymai — LuckyGuru*\n\n"
                "Geriausi šios savaitės radiniai:\n"
                "• 🏆 Geriausi koeficientai Lietuvos rinkoje\n"
                "• 💰 Premijos su geriausiomis sąlygomis\n"
                "• 🎯 Value betting analizė\n"
                "• 📈 Rinkos tendencijos\n\n"
                "💡 _Visas turinys yra informacinis ir edukacinis._"
            ),
        },
        "join_button": "📲 Eiti į Kanalą",
        "more_button":  "🌐 Daugiau informacijos",
        "back":         "Keisti kalbą",
    },

    # ── Latvian ──────────────────────────────────────────────────
    "lv": {
        "category_prompt": (
            "🇱🇻 *Sveiki!* Mēs dalāmies ar informāciju par sporta likmēm, "
            "bonusiem un nozares ziņām.\n\n"
            "📌 *Kas jūs interesē šodien?*"
        ),
        "channel_info": {
            "betting": (
                "⚽ *Sporta Likmes — Lucky Latvia*\n\n"
                "Mūsu kanāls dalās ar:\n"
                "• 📊 Koeficientu analīze un tirgus tendences\n"
                "• 🔍 Bookmaker salīdzinājums\n"
                "• 📰 Sporta ziņas un statistika\n"
                "• 🎯 Izglītojošs saturs par koeficientiem\n\n"
                "💡 _Publiska un izglītojoša informācija. Derējiet atbildīgi._"
            ),
            "casino": (
                "🎰 *Kazino Informācija — Lucky Latvia*\n\n"
                "Dalāmies ar informāciju par:\n"
                "• 🎁 Publiski pieejamiem laipnošanas bonusiem\n"
                "• 🔄 Lojalitātes programmām\n"
                "• 📋 Platformu atsauksmēm un salīdzinājumiem\n"
                "• 💎 Turnīriem un īpašiem notikumiem\n\n"
                "💡 _Informatīvs saturs. Vienmēr pārbaudiet noteikumus._"
            ),
            "nodeposit": (
                "🎁 *Bonusi Bez Depozīta — Lucky Latvia*\n\n"
                "Apkopojam informāciju par:\n"
                "• ✅ Bonusiem bez depozīta, kas pieejami LV\n"
                "• 🆓 Bezmaksas griezieniem bez depozīta\n"
                "• 📌 Publiskajiem promo kodiem\n"
                "• ⚡ Ierobežota laika piedāvājumiem\n\n"
                "💡 _Informācija apkopota no publiskiem avotiem._"
            ),
            "exclusive": (
                "🔥 *Ekskluzīvi Piedāvājumi — Lucky Latvia*\n\n"
                "Labākais, ko atradām šonedēļ:\n"
                "• 🏆 Labākie koeficienti Latvijas tirgū\n"
                "• 💰 Bonusi ar labākajiem noteikumiem\n"
                "• 🎯 Value betting analīze\n"
                "• 📈 Tirgus tendences\n\n"
                "💡 _Viss saturs ir informatīvs un izglītojošs._"
            ),
        },
        "join_button": "📲 Doties uz Kanālu",
        "more_button":  "🌐 Vairāk informācijas",
        "back":         "Mainīt valodu",
    },
}
