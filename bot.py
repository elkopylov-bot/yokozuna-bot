"""
YOKOZUNA Post Bot
Принимает сообщения от пользователя → генерирует готовый пост для @yokozuna_rus
"""

import os
import requests
from flask import Flask, request
from openai import OpenAI

app = Flask(__name__)

TELEGRAM_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]
ALLOWED_CHAT_ID = int(os.environ.get("ALLOWED_CHAT_ID", "59125267"))

TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"
client = OpenAI(api_key=OPENAI_API_KEY)

# ─── Системный промпт ────────────────────────────────────────────────────────

SYSTEM_PROMPT = """Ты — контент-редактор Telegram-канала @yokozuna_rus.
Канал: экспорт авто/мото из Японии в Россию, аудитория — B2B дилеры.

ГОЛОС КАНАЛА:
- Обращение: «Дорогой дилер», «Уважаемые дилеры», «Друзья», «Коллеги»
- Тон: операционный партнёр внутри рынка, говорит прямо, без пафоса
- Emoji точечно: ✅ 🚢 🇯🇵 ❗️ — маркеры, не украшение
- Запрещено: кликбейт, «мы лучшие», продажный тон, заглавные буквы без причины
- Обязательно: конкретные цифры (иены, даты, аукционы USS/TAA/KCAA), CTA в конце
- Длина поста: 150–300 слов

3 РЫНОЧНЫХ ТЕЗИСА (угол подачи):
А — АУКЦИОНЫ ЭТО БАЛАНС: рынок саморегулируется, не паникуем. Вырос курс — цены на аукционах скорректируются. Любую тревожную новость подавать спокойно.
Б — ЯПОНИИ НЕТ АНАЛОГОВ: в недорогом сегменте японский б/у рынок вне конкуренции. Проверенное временем качество.
В — ПРАВИЛА ИГРЫ: у японских аукционов своя специфика. Кто знает правила — тот в выигрыше. YOKOZUNA помогает дилеру знать и использовать эти правила.

9 ПЛАТФОРМЕННЫХ ТЕЗИСОВ:
T1: A2B2C | T2: Платформа №1 для дилеров | T3: Работает из Японии
T4: Говорит на одном языке | T5: На стороне дилера | T6: Надёжная компания
T7: Глобальная платформа | T8: Отраслевой стандарт | T9: Цифровое преимущество

ФАКТ-ЧЕКИНГ:
✅ ПОДТВЕРЖДЕНО — есть прямая ссылка на первоисточник с конкретными данными
⚠️ ЧАСТИЧНО — источник косвенный или данные неполные
❓ НЕ ПОДТВЕРЖДЕНО — тема обсуждается, но первоисточника нет. Такие темы тоже ценны: «все об этом говорят, но официального подтверждения пока нет — следим»

ЗАДАЧА:
Пользователь присылает материал — ссылку, текст, набор фактов или мысль.
Ты:
1. Анализируешь содержание
2. Определяешь статус факт-чекинга
3. Выбираешь рыночный тезис (А/Б/В) и платформенные тезисы (T1–T9)
4. Пишешь готовый пост в голосе канала

ФОРМАТ ОТВЕТА (строго этот):

*Тип:* новость / аналитика / кейс / слух
*Статус:* ✅/⚠️/❓ пояснение одной строкой
*Тезисы:* рыночный А/Б/В · платформенные T..
*Приоритет:* 🔴 высокий / 🟡 средний / 🟢 низкий

—————————————————
ПОСТ:

{готовый текст для публикации в канале, в голосе канала}

—————————————————
*Хэштеги:* #YOKOZUNA #bySUMOTORIJapan #...
*Источник:* {прямая ссылка или «не найден»}"""

# ─── Вспомогательные функции ─────────────────────────────────────────────────

def send_message(chat_id: int, text: str):
    chunks = [text[i:i+4000] for i in range(0, len(text), 4000)]
    for chunk in chunks:
        requests.post(
            f"{TELEGRAM_API}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": chunk,
                "parse_mode": "Markdown",
                "disable_web_page_preview": True,
            },
            timeout=15
        )

def send_typing(chat_id: int):
    requests.post(
        f"{TELEGRAM_API}/sendChatAction",
        json={"chat_id": chat_id, "action": "typing"},
        timeout=5
    )

def generate_post(user_message: str) -> str:
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message}
        ],
        temperature=0.4,
        max_tokens=1500,
    )
    return response.choices[0].message.content

# ─── Webhook handler ─────────────────────────────────────────────────────────

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json(silent=True)
    if not data:
        return "ok"

    message = data.get("message") or data.get("channel_post")
    if not message:
        return "ok"

    chat_id = message["chat"]["id"]
    text = message.get("text", "").strip()

    # Только авторизованный пользователь
    if chat_id != ALLOWED_CHAT_ID:
        return "ok"

    if not text:
        return "ok"

    if text == "/start":
        send_message(chat_id,
            "👋 Привет!\n\n"
            "Скидывай мне:\n"
            "• ссылку на новость\n"
            "• текст или набор фактов\n"
            "• пост конкурента\n"
            "• свою мысль про рынок\n\n"
            "Я в ответ пришлю готовый пост для @yokozuna\_rus 🇯🇵"
        )
        return "ok"

    send_typing(chat_id)
    send_message(chat_id, "⏳ Пишу пост...")

    try:
        post = generate_post(text)
        send_message(chat_id, post)
    except Exception as e:
        send_message(chat_id, f"❌ Ошибка: {str(e)[:300]}")

    return "ok"

@app.route("/", methods=["GET"])
def index():
    return "YOKOZUNA Bot is running ✅"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
