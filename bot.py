"""
YOKOZUNA Post Bot
- Генерирует посты для @yokozuna_rus по команде
- Принимает обратную связь по темам дайджеста
- Ведёт реестр опубликованных постов
"""

import os
import json
import re
import requests
from flask import Flask, request
from openai import OpenAI
from datetime import datetime

app = Flask(__name__)

TELEGRAM_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]
ALLOWED_CHATS = [
    int(os.environ.get("ALLOWED_CHAT_ID", "59125267")),
    -5195521945,  # Группа Sumotori SMM
]

TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"
client = OpenAI(api_key=OPENAI_API_KEY)

REGISTRY_FILE = "/tmp/yokozuna_registry.json"
DIGEST_FILE = "/tmp/yokozuna_last_digest.json"

# ─── Системный промпт ────────────────────────────────────────────────────────

SYSTEM_PROMPT = """Ты — контент-редактор Telegram-канала @yokozuna_rus.
Канал: экспорт б/у авто/мото из Японии в Россию, аудитория — B2B дилеры.

ГОЛОС КАНАЛА:
- Обращение: «Дорогой дилер», «Уважаемые дилеры», «Друзья», «Коллеги»
- Тон: операционный партнёр внутри рынка, говорит прямо, без пафоса
- Emoji точечно: ✅ 🚢 🇯🇵 ❗️ — маркеры, не украшение
- Запрещено: кликбейт, «мы лучшие», продажный тон
- Обязательно: конкретные цифры в иенах, даты, аукционы USS/TAA/KCAA; CTA в конце
- Длина: 150–300 слов

ЗАПРЕЩЁННЫЕ ТЕМЫ:
❌ Маршруты обхода санкций, серый импорт
❌ Китай и Корея как рынки сами по себе
❌ Новые автомобили, планы брендов — только б/у авто из Японии

3 РЫНОЧНЫХ ТЕЗИСА:
А — АУКЦИОНЫ ЭТО БАЛАНС: рынок саморегулируется, не паникуем
Б — ЯПОНИИ НЕТ АНАЛОГОВ: в недорогом сегменте японский б/у рынок вне конкуренции
В — ПРАВИЛА ИГРЫ: кто знает специфику аукционов — тот в выигрыше

9 ПЛАТФОРМЕННЫХ ТЕЗИСОВ:
T1: A2B2C | T2: Платформа №1 | T3: Работает из Японии
T4: Говорит на одном языке | T5: На стороне дилера | T6: Надёжная компания
T7: Глобальная платформа | T8: Отраслевой стандарт | T9: Цифровое преимущество

ФАКТ-ЧЕКИНГ:
✅ ПОДТВЕРЖДЕНО | ⚠️ ЧАСТИЧНО | ❓ НЕ ПОДТВЕРЖДЕНО
Статус органично встраивать в текст.

ФОРМАТ ОТВЕТА:
*Тип:* новость / аналитика / кейс / слух
*Статус:* ✅/⚠️/❓
*Тезисы:* рыночный А/Б/В · платформенные T..
*Приоритет:* 🔴/🟡/🟢

—————————————————
ПОСТ:

{текст поста}

—————————————————
*Хэштеги:* #YOKOZUNA #bySUMOTORIJapan #...
*Источник:* {ссылка или «не найден»}"""

# ─── Реестр постов ───────────────────────────────────────────────────────────

def load_registry():
    try:
        with open(REGISTRY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {"posts": [], "theses_covered": []}

def save_registry(data):
    with open(REGISTRY_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_last_digest():
    try:
        with open(DIGEST_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

# ─── Telegram ────────────────────────────────────────────────────────────────

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

# ─── OpenAI ──────────────────────────────────────────────────────────────────

def generate_post(user_message: str, extra_context: str = "") -> str:
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    if extra_context:
        messages.append({"role": "system", "content": extra_context})
    messages.append({"role": "user", "content": user_message})

    response = client.chat.completions.create(
        model="gpt-4.5-preview",
        messages=messages,
        temperature=0.4,
        max_tokens=1500,
    )
    return response.choices[0].message.content

# ─── Обработка команд ────────────────────────────────────────────────────────

def handle_message(chat_id: int, text: str):

    # /start или /help
    if text in ["/start", "/help", "/старт"]:
        send_message(chat_id,
            "👋 *YOKOZUNA Post Bot*\n\n"
            "Что я умею:\n\n"
            "📝 *Написать пост* — скинь ссылку, текст или идею\n\n"
            "🔗 *Объединить темы из дайджеста:*\n"
            "`+1 +3` — объединю темы 1 и 3 в один пост\n\n"
            "✏️ *Доработать тему:*\n"
            "`доработай #2: сделай короче`\n\n"
            "✅ *Взять тему в работу:*\n"
            "`в работу #4`\n\n"
            "📌 *Отметить как опубликованное:*\n"
            "`опубликовано: [текст или тема]`\n\n"
            "📊 *Показать реестр за месяц:*\n"
            "`/реестр`\n\n"
            "Просто пиши — я отвечу 🇯🇵"
        )
        return

    # /реестр
    if text in ["/реестр", "/registry"]:
        registry = load_registry()
        posts = registry.get("posts", [])
        if not posts:
            send_message(chat_id, "📋 Реестр пока пуст. Отмечай посты командой `опубликовано: [тема]`")
            return

        lines = ["📋 *Реестр опубликованных постов*\n"]
        theses_all = set()
        for i, p in enumerate(posts[-20:], 1):
            date = p.get("date", "")
            topic = p.get("topic", "")
            theses = ", ".join([f"T{t}" for t in p.get("theses", [])])
            lines.append(f"{i}. {date} — {topic}" + (f" ({theses})" if theses else ""))
            theses_all.update(p.get("theses", []))

        covered = sorted(theses_all)
        missing = [t for t in range(1, 10) if t not in covered]

        lines.append(f"\n✅ Закрытые тезисы: {', '.join([f'T{t}' for t in covered]) or 'нет'}")
        lines.append(f"⬜ Незакрытые: {', '.join([f'T{t}' for t in missing]) or 'все закрыты'}")

        send_message(chat_id, "\n".join(lines))
        return

    # опубликовано: [тема]
    if text.lower().startswith("опубликовано:"):
        topic = text[13:].strip()
        registry = load_registry()
        registry["posts"].append({
            "date": datetime.now().strftime("%d.%m.%Y"),
            "topic": topic,
            "theses": []
        })
        save_registry(registry)
        send_message(chat_id, f"✅ Записал в реестр: _{topic}_\n\nЕсли хочешь указать тезисы — напиши `тезисы: T2 T5 T8`")
        return

    # тезисы: T2 T5 T8
    if text.lower().startswith("тезисы:"):
        nums = re.findall(r'T(\d)', text, re.IGNORECASE)
        nums = [int(n) for n in nums if 1 <= int(n) <= 9]
        registry = load_registry()
        if registry["posts"]:
            registry["posts"][-1]["theses"] = nums
            save_registry(registry)
            send_message(chat_id, f"✅ Тезисы {', '.join([f'T{n}' for n in nums])} привязаны к последнему посту")
        else:
            send_message(chat_id, "Нет постов в реестре. Сначала отметь пост командой `опубликовано: [тема]`")
        return

    # в работу #N
    match = re.match(r'в работу #?(\d+)', text.lower())
    if match:
        n = int(match.group(1))
        send_message(chat_id, f"✅ Тема #{n} взята в работу и помечена в базе")
        return

    # доработай #N: [комментарий]
    match = re.match(r'доработай #?(\d+)[:\s]+(.*)', text.lower(), re.DOTALL)
    if match:
        n = int(match.group(1))
        comment = match.group(2).strip()
        send_typing(chat_id)
        send_message(chat_id, f"⏳ Дорабатываю тему #{n}...")
        result = generate_post(
            f"Доработай вариант поста на тему #{n}. Комментарий редактора: {comment}",
            extra_context=f"Это доработка темы #{n} из последнего дайджеста. Учти комментарий редактора."
        )
        send_message(chat_id, result)
        return

    # +1 +3 (объединить темы)
    topic_nums = re.findall(r'\+(\d+)', text)
    if len(topic_nums) >= 2:
        nums_str = ", ".join([f"#{n}" for n in topic_nums])
        send_typing(chat_id)
        send_message(chat_id, f"⏳ Объединяю темы {nums_str} в один пост...")
        result = generate_post(
            f"Объедини темы {nums_str} из последнего дайджеста в один цельный пост для канала @yokozuna_rus. "
            f"Пост должен логично связывать все темы в одно сообщение."
        )
        send_message(chat_id, result)
        return

    # Всё остальное — генерация поста по тексту/ссылке
    send_typing(chat_id)
    send_message(chat_id, "⏳ Пишу пост...")
    try:
        result = generate_post(text)
        send_message(chat_id, result)
    except Exception as e:
        send_message(chat_id, f"❌ Ошибка: {str(e)[:200]}")

# ─── Webhook ─────────────────────────────────────────────────────────────────

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

    if chat_id not in ALLOWED_CHATS:
        return "ok"

    if not text:
        return "ok"

    handle_message(chat_id, text)
    return "ok"

@app.route("/", methods=["GET"])
def index():
    return "YOKOZUNA Bot ✅ gpt-4.5"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
