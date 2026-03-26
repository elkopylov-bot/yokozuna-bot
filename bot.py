"""
YOKOZUNA Bot v3
Telegram-бот для SMM-команды канала @yokozuna_rus
Flask + OpenAI gpt-4.5-preview
"""

import os
import json
import logging
import hashlib
import time
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from typing import Optional

import requests
from flask import Flask, request, jsonify
from openai import OpenAI

# ─────────────────────────────────────────────
# LOGGING
# ─────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────────
BOT_USERNAME      = "sumotori_smm_bot"
CHANNEL_RU_ID     = -1001821163646
GROUP_ID          = -5195521945
PERSONAL_ID       = 59125267

REGISTRY_FILE   = "/tmp/yokozuna_registry.json"
REMINDERS_FILE  = "/tmp/yokozuna_reminders.json"
RUBRICS_FILE    = "/tmp/yokozuna_rubrics.json"
IDEAS_FILE      = "/tmp/yokozuna_ideas.json"

RUTUBE_RSS_URL  = "https://rutube.ru/channel/74201471/rss/"
VK_DOMAIN       = "yokozuna_japan"
VK_API_VERSION  = "5.199"
VK_POSTS_COUNT  = 20

OPENAI_MODEL    = os.environ.get("OPENAI_MODEL", "gpt-4o")


# ─────────────────────────────────────────────
# ENV
# ─────────────────────────────────────────────
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
OPENAI_API_KEY     = os.environ.get("OPENAI_API_KEY", "")
VK_TOKEN           = os.environ.get("VK_TOKEN", "")
ALLOWED_CHAT_ID    = int(os.environ.get("ALLOWED_CHAT_ID", str(PERSONAL_ID)))
SYSTEM_PROMPT_ENV  = os.environ.get("SYSTEM_PROMPT", "")

TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

openai_client = OpenAI(api_key=OPENAI_API_KEY)
app = Flask(__name__)

# ─────────────────────────────────────────────
# DEFAULT SYSTEM PROMPT
# ─────────────────────────────────────────────
DEFAULT_SYSTEM_PROMPT = """Ты — ИИ-ассистент SMM-команды японской B2B-платформы YOKOZUNA для дилеров подержанных автомобилей.

YOKOZUNA — аукционная платформа №1 для дилеров, которая работает непосредственно из Японии и даёт цифровое преимущество на рынке б/у авто.

ПЛАТФОРМЕННЫЕ ТЕЗИСЫ (используй в постах):
T1 (A2B2C): YOKOZUNA соединяет аукционы Японии напрямую с дилерами и их клиентами
T2 (Платформа №1): Лидирующая платформа по объёму и сервису
T3 (Работает из Японии): Команда физически в Японии — живой доступ к рынку
T4 (Говорит на одном языке): Понимает специфику каждого рынка
T5 (На стороне дилера): Защищает интересы дилера, не аукциона
T6 (Надёжная компания): Многолетняя история, прозрачность
T7 (Глобальная платформа): Работает со странами по всему миру
T8 (Отраслевой стандарт): Устанавливает профессиональные стандарты отрасли
T9 (Цифровое преимущество): Технологии, автоматизация, скорость

РЫНОЧНЫЕ ТЕЗИСЫ:
А — Аукционы это баланс (рынок саморегулируется, цена справедлива)
Б — Японии нет аналогов (в недорогом сегменте по качеству/цене)
В — Правила игры (кто знает механику — тот выигрывает)

ФУНКЦИИ YOKOZUNA: bid groups, AI-перевод аукционных листов, трекинг-ссылка,
калькулятор себестоимости, OnePrice интеграция, отсрочка платежа,
дилерский кабинет мультименеджер, переговоры после торгов, YoToken, страховка от невывоза

ГОЛОС RU-КАНАЛА:
- Обращение: «Дорогой дилер», «Уважаемые дилеры», «Друзья», «Коллеги»
- Тон: операционный партнёр внутри рынка, прямо, без пафоса
- Emoji точечно: ✅ 🚢 🇯🇵 ❗️
- ЗАПРЕЩЕНО: кликбейт, «мы лучшие», продажный тон, новые авто, серый импорт
- ОБЯЗАТЕЛЬНО: цифры в иенах, даты, аукционы USS/TAA/KCAA, CTA в конце

ГОЛОС EN-КАНАЛА:
- Tone: authoritative industry partner, direct, data-driven
- No: clickbait, "we're the best", sales language
- Must: specific yen amounts, auction names, practical dealer value, CTA

RU РУБРИКИ:
1. «Рынок недели» — аналитика для дилера (T2, T5, еженедельно)
2. «Правила игры» — механика аукционов USS/TAA/KCAA (T8, T9, еженедельно)
3. «Подборка авто для России» — с учётом пошлин, до 160 л.с. (T1, T2, еженедельно)
4. «Как работает YOKOZUNA» — функции платформы в деле (T2, T9, еженедельно)
5. «Мы в Японии» — живой контент с ярда/аукциона/порта (T3, T6, 2 раза в месяц)
6. «Кейс дилера» — реальная сделка с цифрами (T1, T4, T5, 2 раза в месяц)
7. «Таможня и пошлины» — по событию (T5, T8)
8. «Модель месяца» — почему сейчас выгодна (T1, T2, ежемесячно)

EN РУБРИКИ:
1. «Japan Auction Insights» — аналитика рынка (T8, T2, еженедельно)
2. «How Japan Works» — механики для глобальной аудитории (T3, T9, 2 раза в месяц)
3. «Best Cars for [Market]» — подборки по рынкам с правилами ввоза (T1, T7, еженедельно)
4. «YOKOZUNA Platform» — как работает (T2, T9, еженедельно)
5. «Dealer Stories» — кейсы из разных стран (T1, T4, T7, 2 раза в месяц)
6. «Why Japan» — тезис Б для глобального рынка (T3, T6, ежемесячно)

RU поток: Telegram @yokozuna_rus, VK vk.com/yokozuna_japan, RuTube rutube.ru/channel/74201471
EN поток: YouTube (будет), Facebook, X/Twitter, LinkedIn, Telegram EN (будет)

НЕ переводить RU → EN и EN → RU автоматически.
Каждый поток пишется на своём языке с учётом специфики аудитории.
"""

SYSTEM_PROMPT = SYSTEM_PROMPT_ENV if SYSTEM_PROMPT_ENV else DEFAULT_SYSTEM_PROMPT

# ─────────────────────────────────────────────
# DEFAULT RUBRICS
# ─────────────────────────────────────────────
DEFAULT_RUBRICS = {
    "ru": {
        "Рынок недели": {
            "description": "Еженедельная аналитика для дилера. Конкретные данные: объёмы лотов, динамика цен, горячие марки. Тезисы T2, T5.",
            "tezisy": ["T2", "T5"],
            "frequency": "еженедельно",
            "timing": "T2, T5"
        },
        "Правила игры": {
            "description": "Механика аукционов USS/TAA/KCAA — как проходят торги, оценочные листы, ошибки новичков. Тезисы T8, T9.",
            "tezisy": ["T8", "T9"],
            "frequency": "еженедельно",
            "timing": "T8, T9"
        },
        "Подборка авто для России": {
            "description": "Конкретные лоты/модели с учётом пошлин РФ, ограничение 160 л.с. Цифры в иенах и рублях. Тезисы T1, T2.",
            "tezisy": ["T1", "T2"],
            "frequency": "еженедельно",
            "timing": "T1, T2"
        },
        "Как работает YOKOZUNA": {
            "description": "Функции платформы на реальных примерах: bid groups, AI-листы, трекинг, калькулятор, OnePrice, отсрочка, мультименеджер, переговоры, YoToken, страховка. Тезисы T2, T9.",
            "tezisy": ["T2", "T9"],
            "frequency": "еженедельно",
            "timing": "T2, T9",
            "functions": ["bid groups", "AI-перевод аукционных листов", "трекинг-ссылка", "калькулятор себестоимости", "OnePrice интеграция", "отсрочка платежа", "дилерский кабинет мультименеджер", "переговоры после торгов", "YoToken", "страховка от невывоза"]
        },
        "Мы в Японии": {
            "description": "Живой контент с ярда, аукциона, порта. Фото/видео-репортаж, реальные истории. Тезисы T3, T6.",
            "tezisy": ["T3", "T6"],
            "frequency": "2 раза в месяц",
            "timing": "T3, T6"
        },
        "Кейс дилера": {
            "description": "Реальная сделка с цифрами: купили на каком аукционе, за сколько иен, таможня, продажа. Тезисы T1, T4, T5.",
            "tezisy": ["T1", "T4", "T5"],
            "frequency": "2 раза в месяц",
            "timing": "T1, T4, T5"
        },
        "Таможня и пошлины": {
            "description": "Актуальная информация по таможенным правилам РФ, изменениям пошлин, логистике до Владивостока. По событию. Тезисы T5, T8.",
            "tezisy": ["T5", "T8"],
            "frequency": "по событию",
            "timing": "T5, T8"
        },
        "Модель месяца": {
            "description": "Почему конкретная модель выгодна сейчас: динамика цен на аукционах, спрос в России, расчёт себестоимости. Тезисы T1, T2.",
            "tezisy": ["T1", "T2"],
            "frequency": "ежемесячно",
            "timing": "T1, T2"
        }
    },
    "en": {
        "Japan Auction Insights": {
            "description": "Weekly market analytics: lot volumes, price trends, hot models. Tezisy T8, T2.",
            "tezisy": ["T8", "T2"],
            "frequency": "weekly",
            "timing": "T8, T2"
        },
        "How Japan Works": {
            "description": "Auction mechanics explained for global audience: grading, bidding, inspection. Tezisy T3, T9.",
            "tezisy": ["T3", "T9"],
            "frequency": "twice a month",
            "timing": "T3, T9"
        },
        "Best Cars for [Market]": {
            "description": "Curated car selections for specific markets with import rules, customs specifics, price in JPY. Tezisy T1, T7.",
            "tezisy": ["T1", "T7"],
            "frequency": "weekly",
            "timing": "T1, T7"
        },
        "YOKOZUNA Platform": {
            "description": "How the platform works in practice: features, tools, dealer advantages. Tezisy T2, T9.",
            "tezisy": ["T2", "T9"],
            "frequency": "weekly",
            "timing": "T2, T9"
        },
        "Dealer Stories": {
            "description": "Real cases from dealers in different countries: deal numbers, process, outcome. Tezisy T1, T4, T7.",
            "tezisy": ["T1", "T4", "T7"],
            "frequency": "twice a month",
            "timing": "T1, T4, T7"
        },
        "Why Japan": {
            "description": "Thesis B — Japan has no equals in affordable used car quality. Monthly global audience piece. Tezisy T3, T6.",
            "tezisy": ["T3", "T6"],
            "frequency": "monthly",
            "timing": "T3, T6"
        }
    }
}

# ─────────────────────────────────────────────
# STORAGE HELPERS
# ─────────────────────────────────────────────

def _load_json(path: str, default) -> dict:
    """Load JSON from file, return default if missing or corrupt."""
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        log.warning(f"Failed to load {path}: {e}")
    return default


def _save_json(path: str, data) -> None:
    """Save data as JSON to file."""
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        log.error(f"Failed to save {path}: {e}")


def load_registry() -> dict:
    default = {
        "ru": {"telegram": [], "vk": [], "rutube": []},
        "en": {"youtube": [], "facebook": [], "twitter": [], "linkedin": [], "telegram": []},
        "ideas": []
    }
    return _load_json(REGISTRY_FILE, default)


def save_registry(data: dict) -> None:
    _save_json(REGISTRY_FILE, data)


def load_reminders() -> list:
    return _load_json(REMINDERS_FILE, [])


def save_reminders(data: list) -> None:
    _save_json(REMINDERS_FILE, data)


def load_rubrics() -> dict:
    stored = _load_json(RUBRICS_FILE, {})
    if not stored:
        stored = DEFAULT_RUBRICS
        save_rubrics(stored)
    return stored


def save_rubrics(data: dict) -> None:
    _save_json(RUBRICS_FILE, data)


def load_ideas() -> list:
    return _load_json(IDEAS_FILE, [])


def save_ideas(data: list) -> None:
    _save_json(IDEAS_FILE, data)

# ─────────────────────────────────────────────
# TELEGRAM HELPERS
# ─────────────────────────────────────────────

def send_message(chat_id: int, text: str, parse_mode: str = "Markdown",
                 reply_to_message_id: Optional[int] = None,
                 reply_markup: Optional[dict] = None) -> Optional[dict]:
    """Send a Telegram message, splitting if > 4096 chars."""
    MAX_LEN = 4000
    chunks = [text[i:i+MAX_LEN] for i in range(0, len(text), MAX_LEN)]
    last_response = None
    for i, chunk in enumerate(chunks):
        payload = {
            "chat_id": chat_id,
            "text": chunk,
            "parse_mode": parse_mode,
            "disable_web_page_preview": True,
        }
        if reply_to_message_id:
            payload["reply_to_message_id"] = reply_to_message_id
            reply_to_message_id = None
        # Inline кнопки только к последнему чанку
        if reply_markup and i == len(chunks) - 1:
            payload["reply_markup"] = reply_markup
        try:
            r = requests.post(f"{TELEGRAM_API}/sendMessage", json=payload, timeout=30)
            r.raise_for_status()
            last_response = r.json()
        except Exception as e:
            log.error(f"sendMessage error: {e}")
            try:
                payload["parse_mode"] = None
                r = requests.post(f"{TELEGRAM_API}/sendMessage", json=payload, timeout=30)
                last_response = r.json()
            except Exception as e2:
                log.error(f"sendMessage fallback error: {e2}")
    return last_response


START_KEYBOARD = {
    "inline_keyboard": [
        [
            {"text": "🔄 Синк каналов", "callback_data": "/sync"},
            {"text": "💡 Идеи", "callback_data": "/ideas"},
        ],
        [
            {"text": "📋 Реестр RU", "callback_data": "/registry_ru"},
            {"text": "📋 Реестр EN", "callback_data": "/registry_en"},
        ],
        [
            {"text": "📅 План RU", "callback_data": "/plan_ru"},
            {"text": "📅 План EN", "callback_data": "/plan_en"},
        ],
        [
            {"text": "🔔 Напоминания", "callback_data": "/reminders"},
        ],
    ]
}


def get_bot_id() -> Optional[int]:
    try:
        r = requests.get(f"{TELEGRAM_API}/getMe", timeout=10)
        return r.json().get("result", {}).get("id")
    except Exception as e:
        log.error(f"getMe error: {e}")
        return None


# ─────────────────────────────────────────────
# AUTHORIZATION
# ─────────────────────────────────────────────

def is_authorized(chat_id: int) -> bool:
    """Allow personal chat and the designated group."""
    return chat_id in (PERSONAL_ID, GROUP_ID, ALLOWED_CHAT_ID)


def should_respond_in_group(message: dict) -> bool:
    """In group chats, only respond to @mention or reply to bot's messages."""
    chat_id = message.get("chat", {}).get("id")
    if chat_id != GROUP_ID:
        return True  # private chats always respond

    text = message.get("text", "") or message.get("caption", "")
    # Check for @mention
    if f"@{BOT_USERNAME}" in text:
        return True
    # Check for reply to bot's own message
    reply = message.get("reply_to_message")
    if reply:
        bot_id = get_bot_id()
        if bot_id and reply.get("from", {}).get("id") == bot_id:
            return True
    return False

# ─────────────────────────────────────────────
# GPT HELPERS
# ─────────────────────────────────────────────

def gpt(user_message: str, system_override: Optional[str] = None,
        temperature: float = 0.7) -> str:
    """Call OpenAI chat completion and return the text."""
    system = system_override if system_override else SYSTEM_PROMPT
    try:
        response = openai_client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user_message},
            ],
            temperature=temperature,
            max_tokens=3000,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        log.error(f"OpenAI error: {e}")
        return f"❗️ Ошибка OpenAI: {e}"

# ─────────────────────────────────────────────
# POST GENERATION
# ─────────────────────────────────────────────

def detect_stream(text: str) -> str:
    """Auto-detect ru/en stream from message text."""
    text_lower = text.lower()
    ru_hints = ["ru:", "ru :", "для рос", "рубрик", "план ru", "реестр ru"]
    en_hints = ["en:", "en :", "english", "global", "for market", "план en", "реестр en"]
    for h in ru_hints:
        if h in text_lower:
            return "ru"
    for h in en_hints:
        if h in text_lower:
            return "en"
    # Heuristic: mostly Cyrillic → ru
    cyrillic = sum(1 for c in text if '\u0400' <= c <= '\u04FF')
    return "ru" if cyrillic > len(text) * 0.1 else "en"


def generate_post(topic: str, stream: str, rubric: Optional[str] = None) -> str:
    """Generate a channel post using GPT."""
    rubrics_data = load_rubrics()
    rubric_ctx = ""
    if rubric:
        rb = rubrics_data.get(stream, {}).get(rubric, {})
        if rb:
            rubric_ctx = f"\nРубрика: {rubric}\nОписание рубрики: {rb.get('description','')}\nТезисы: {', '.join(rb.get('tezisy', []))}"

    if stream == "ru":
        prompt = f"""Сгенерируй готовый пост для Telegram-канала @yokozuna_rus (RU поток).
Тема/материал: {topic}
{rubric_ctx}

Формат ответа:
📌 ТИП: [название рубрики]
✅ ФАКТ-ЧЕКИНГ: [проверено / требует уточнения / информация из источника]
🎯 ТЕЗИСЫ: [T1-T9 и/или А/Б/В которые раскрыты]

━━━ ПОСТ ━━━
[готовый текст поста для @yokozuna_rus]

#️⃣ ХЭШТЕГИ: [хэштеги через запятую]
🔗 ИСТОЧНИК: [если есть URL]

Требования к посту:
- Голос: операционный партнёр, без пафоса
- Обращение: «Дорогой дилер» или «Коллеги» или «Друзья» (по смыслу)
- Emoji только: ✅ 🚢 🇯🇵 ❗️
- Цифры в иенах (¥), даты, аукционы USS/TAA/KCAA
- Завершить CTA (призыв к действию)
- Без кликбейта, без «мы лучшие»
"""
    else:
        prompt = f"""Generate a ready-to-publish post for the YOKOZUNA EN channel (Global stream).
Topic/material: {topic}
{rubric_ctx}

Response format:
📌 TYPE: [rubric name]
✅ FACT-CHECK: [verified / needs clarification / sourced]
🎯 THESIS: [T1-T9 and/or А/Б/В covered]

━━━ POST ━━━
[ready post text]

#️⃣ HASHTAGS: [comma-separated hashtags]
🔗 SOURCE: [URL if available]

Post requirements:
- Tone: authoritative industry partner, direct, data-driven
- Specific yen amounts, auction names (USS/TAA/KCAA), practical dealer value
- End with CTA
- No clickbait, no "we're the best"
"""
    return gpt(prompt)

# ─────────────────────────────────────────────
# CHANNEL MONITORING
# ─────────────────────────────────────────────

def fetch_rutube_posts() -> list:
    """Fetch latest posts from RuTube RSS."""
    posts = []
    try:
        r = requests.get(RUTUBE_RSS_URL, timeout=15)
        r.raise_for_status()
        root = ET.fromstring(r.content)
        ns = {"media": "http://search.yahoo.com/mrss/"}
        channel = root.find("channel")
        if channel is None:
            return posts
        for item in channel.findall("item")[:10]:
            title = item.findtext("title", "")
            link = item.findtext("link", "")
            pub_date = item.findtext("pubDate", "")
            description = item.findtext("description", "")
            posts.append({
                "title": title,
                "url": link,
                "date": pub_date,
                "description": description[:300],
                "source": "rutube",
                "stream": "ru"
            })
    except Exception as e:
        log.error(f"RuTube RSS error: {e}")
    return posts


def fetch_vk_posts() -> list:
    """Fetch latest posts from VK wall."""
    posts = []
    if not VK_TOKEN:
        log.info("VK_TOKEN not set, skipping VK monitoring")
        return posts
    try:
        params = {
            "domain": VK_DOMAIN,
            "count": VK_POSTS_COUNT,
            "access_token": VK_TOKEN,
            "v": VK_API_VERSION,
            "filter": "owner"
        }
        r = requests.get("https://api.vk.com/method/wall.get", params=params, timeout=15)
        r.raise_for_status()
        data = r.json()
        if "error" in data:
            log.error(f"VK API error: {data['error']}")
            return posts
        items = data.get("response", {}).get("items", [])
        for item in items:
            text = item.get("text", "")
            date_ts = item.get("date", 0)
            post_id = item.get("id", "")
            date_str = datetime.fromtimestamp(date_ts).strftime("%Y-%m-%d %H:%M")
            posts.append({
                "title": text[:100].replace("\n", " "),
                "text": text[:500],
                "url": f"https://vk.com/yokozuna_japan?w=wall-{abs(item.get('owner_id',0))}_{post_id}",
                "date": date_str,
                "source": "vk",
                "stream": "ru",
                "post_id": str(post_id)
            })
    except Exception as e:
        log.error(f"VK fetch error: {e}")
    return posts


def fetch_telegram_channel_posts() -> list:
    """Fetch recent posts from @yokozuna_rus via bot API (if bot is admin)."""
    posts = []
    try:
        # Try to get recent updates or use getHistory if available
        # Bot can only read messages from channels where it's admin
        # We use getUpdates with a large offset as a fallback approach
        # In production, forward channel messages to the bot or use a user bot
        # Here we attempt to read from the channel via forwardMessage workaround
        # Since standard Bot API doesn't allow channel history, we log a note
        log.info("Telegram channel monitoring: requires bot to be admin of @yokozuna_rus")
        # If there are cached updates, we can parse them
        # In production, set up channel forwarding to the bot
    except Exception as e:
        log.error(f"Telegram channel fetch error: {e}")
    return posts


def analyze_post_with_gpt(post: dict) -> dict:
    """Analyze a fetched post and categorize it."""
    prompt = f"""Проанализируй этот пост из {post.get('source', 'канала')} и определи:
1. Рубрика (из списка: Рынок недели / Правила игры / Подборка авто для России / Как работает YOKOZUNA / Мы в Японии / Кейс дилера / Таможня и пошлины / Модель месяца / другое)
2. Тезисы (T1-T9, А/Б/В)
3. Краткое резюме (1 предложение)

Заголовок: {post.get('title', '')}
Текст: {post.get('text', post.get('description', ''))[:500]}

Ответь в JSON: {{"rubric": "...", "tezisy": ["T1", "T2"], "summary": "..."}}"""
    try:
        result = gpt(prompt, temperature=0.3)
        # Extract JSON from response
        json_match = re.search(r'\{.*\}', result, re.DOTALL)
        if json_match:
            meta = json.loads(json_match.group())
            post.update(meta)
    except Exception as e:
        log.warning(f"Post analysis error: {e}")
    return post


def sync_channels() -> str:
    """Sync all channels and update registry. Returns status message."""
    registry = load_registry()
    new_counts = {"rutube": 0, "vk": 0, "telegram": 0}
    cutoff = datetime.now() - timedelta(days=30)

    # RuTube
    rutube_posts = fetch_rutube_posts()
    existing_rutube_urls = {p.get("url") for p in registry["ru"]["rutube"]}
    for post in rutube_posts:
        if post["url"] not in existing_rutube_urls:
            post = analyze_post_with_gpt(post)
            post["synced_at"] = datetime.now().isoformat()
            registry["ru"]["rutube"].append(post)
            new_counts["rutube"] += 1

    # VK
    vk_posts = fetch_vk_posts()
    existing_vk_ids = {p.get("post_id") for p in registry["ru"]["vk"]}
    for post in vk_posts:
        if post.get("post_id") not in existing_vk_ids:
            post = analyze_post_with_gpt(post)
            post["synced_at"] = datetime.now().isoformat()
            registry["ru"]["vk"].append(post)
            new_counts["vk"] += 1

    # Telegram (placeholder — requires admin access)
    tg_posts = fetch_telegram_channel_posts()
    for post in tg_posts:
        post = analyze_post_with_gpt(post)
        post["synced_at"] = datetime.now().isoformat()
        registry["ru"]["telegram"].append(post)
        new_counts["telegram"] += 1

    save_registry(registry)

    lines = ["✅ *Синхронизация завершена*\n"]
    lines.append(f"🇯🇵 RuTube: +{new_counts['rutube']} новых постов")
    lines.append(f"📱 VK: +{new_counts['vk']} новых постов" + (" (VK_TOKEN не задан)" if not VK_TOKEN else ""))
    lines.append(f"📢 Telegram: +{new_counts['telegram']} новых постов")
    total_ru = len(registry["ru"]["rutube"]) + len(registry["ru"]["vk"]) + len(registry["ru"]["telegram"])
    lines.append(f"\nВсего в реестре RU: {total_ru} постов")
    return "\n".join(lines)

# ─────────────────────────────────────────────
# REGISTRY VIEW
# ─────────────────────────────────────────────

def format_registry(stream_or_channel: str) -> str:
    """Format registry output for given stream/channel."""
    registry = load_registry()
    rubrics = load_rubrics()
    cutoff = datetime.now() - timedelta(days=30)
    lines = []

    def posts_in_30d(posts: list) -> list:
        result = []
        for p in posts:
            date_str = p.get("synced_at") or p.get("date", "")
            try:
                if "T" in date_str:
                    d = datetime.fromisoformat(date_str[:19])
                else:
                    d = datetime.strptime(date_str[:10], "%Y-%m-%d")
                if d >= cutoff:
                    result.append(p)
            except Exception:
                result.append(p)  # include if can't parse date
        return result

    arg = stream_or_channel.lower().strip()

    if arg in ("ru", "en"):
        stream = arg
        lines.append(f"📊 *Реестр {stream.upper()} — последние 30 дней*\n")
        channels = registry.get(stream, {})
        all_posts = []
        for ch, posts in channels.items():
            recent = posts_in_30d(posts)
            all_posts.extend(recent)
            lines.append(f"*{ch.upper()}*: {len(recent)} постов за 30 дней")

        # Covered tezisy
        covered = set()
        for p in all_posts:
            covered.update(p.get("tezisy", []))

        all_tezisy = {f"T{i}" for i in range(1, 10)} | {"А", "Б", "В"}
        missing = all_tezisy - covered
        lines.append(f"\n✅ Закрытые тезисы: {', '.join(sorted(covered)) or 'нет'}")
        lines.append(f"❗️ Незакрытые тезисы: {', '.join(sorted(missing)) or 'все закрыты'}")

        # Rubric coverage
        stream_rubrics = rubrics.get(stream, {})
        covered_rubrics = {p.get("rubric") for p in all_posts if p.get("rubric")}
        missing_rubrics = set(stream_rubrics.keys()) - covered_rubrics
        lines.append(f"\n📌 Незакрытые рубрики: {', '.join(missing_rubrics) or 'все закрыты'}")

        # Recent posts list
        lines.append(f"\n*Последние посты:*")
        sorted_posts = sorted(all_posts, key=lambda x: x.get("synced_at", x.get("date", "")), reverse=True)[:10]
        for p in sorted_posts:
            title = p.get("title", "")[:50]
            rubric = p.get("rubric", "—")
            source = p.get("source", "—")
            tezisy = ", ".join(p.get("tezisy", []))
            lines.append(f"• [{source}] {title} | {rubric} | {tezisy}")

    elif arg in ("telegram", "vk", "rutube", "youtube", "facebook", "twitter", "linkedin"):
        lines.append(f"📊 *Реестр {arg.upper()} — последние 30 дней*\n")
        # Search in both streams
        for stream in ("ru", "en"):
            ch_posts = registry.get(stream, {}).get(arg, [])
            recent = posts_in_30d(ch_posts)
            if recent:
                lines.append(f"Поток {stream.upper()}: {len(recent)} постов")
                for p in recent[:10]:
                    title = p.get("title", "")[:60]
                    rubric = p.get("rubric", "—")
                    lines.append(f"  • {title} | {rubric}")
    else:
        lines.append("❗️ Неверный аргумент. Используй: /реестр ru | en | telegram | vk | rutube")

    return "\n".join(lines)

# ─────────────────────────────────────────────
# CONTENT PLAN
# ─────────────────────────────────────────────

def generate_content_plan(stream: str) -> str:
    """Generate a weekly content plan for given stream."""
    registry = load_registry()
    rubrics = load_rubrics()
    ideas = load_ideas()

    # Get recent posts to find gaps
    cutoff = datetime.now() - timedelta(days=30)
    all_recent = []
    for ch, posts in registry.get(stream, {}).items():
        for p in posts:
            date_str = p.get("synced_at", p.get("date", ""))
            try:
                d = datetime.fromisoformat(date_str[:19]) if "T" in date_str else datetime.strptime(date_str[:10], "%Y-%m-%d")
                if d >= cutoff:
                    all_recent.append(p)
            except Exception:
                pass

    covered_rubrics = {p.get("rubric") for p in all_recent if p.get("rubric")}
    covered_tezisy = set()
    for p in all_recent:
        covered_tezisy.update(p.get("tezisy", []))

    stream_rubrics = rubrics.get(stream, {})
    missing_rubrics = [r for r in stream_rubrics if r not in covered_rubrics]

    pending_ideas = [i for i in ideas if not i.get("in_plan")]
    ideas_text = "\n".join([f"- {i['text']}" for i in pending_ideas[:5]]) if pending_ideas else "нет"

    if stream == "ru":
        prompt = f"""Составь контент-план на неделю для RU потока (@yokozuna_rus, VK, RuTube).

Незакрытые рубрики за 30 дней: {', '.join(missing_rubrics) or 'нет'}
Незакрытые тезисы: {', '.join(set('T1 T2 T3 T4 T5 T6 T7 T8 T9 А Б В'.split()) - covered_tezisy) or 'нет'}
Идеи из банка: {ideas_text}

Рубрики и их частота:
{json.dumps({k: v.get('frequency','') for k,v in stream_rubrics.items()}, ensure_ascii=False)}

Формат ответа — таблица (Markdown):
День | Рубрика | Тема поста | Канал | Тезисы

Правила:
- 7 строк (Пн-Вс)
- Темы конкретные, с деталями (марки, цифры, аукционы)
- Каналы: Telegram / VK / RuTube / Все RU
- Распределить рубрики согласно частоте
- Использовать незакрытые тезисы

Добавь краткие пояснения по каждому посту после таблицы."""

    else:
        prompt = f"""Create a weekly content plan for EN stream (YouTube, Facebook, X/Twitter, LinkedIn).

Uncovered rubrics (30 days): {', '.join(missing_rubrics) or 'none'}
Uncovered tezisy: {', '.join(set('T1 T2 T3 T4 T5 T6 T7 T8 T9 А Б В'.split()) - covered_tezisy) or 'none'}
Ideas: {ideas_text}

Rubrics and frequency:
{json.dumps({k: v.get('frequency','') for k,v in stream_rubrics.items()}, ensure_ascii=False)}

Response format — Markdown table:
Day | Rubric | Post Topic | Channel | Tezisy

Rules:
- 7 rows (Mon-Sun)
- Specific topics with details (car models, prices, auction names)
- Channels: YouTube / Facebook / X/Twitter / LinkedIn / All EN
- Match rubric frequency
- Cover uncovered tezisy

Add brief notes after the table."""

    return gpt(prompt, temperature=0.6)

# ─────────────────────────────────────────────
# IDEAS
# ─────────────────────────────────────────────

def save_idea(text: str, author: str) -> str:
    ideas = load_ideas()
    idea = {
        "id": len(ideas) + 1,
        "text": text,
        "author": author,
        "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "in_plan": False
    }
    ideas.append(idea)
    save_ideas(ideas)
    return f"✅ Идея #{idea['id']} сохранена: _{text}_"


def show_ideas() -> str:
    ideas = load_ideas()
    pending = [i for i in ideas if not i.get("in_plan")]
    if not pending:
        return "💡 Банк идей пуст. Добавь: `идея: [текст]`"
    lines = [f"💡 *Банк идей* ({len(pending)} шт.)\n"]
    for i in pending:
        lines.append(f"#{i['id']} [{i['date']}] {i['author']}: {i['text']}")
    return "\n".join(lines)


def add_idea_to_plan(text: str) -> str:
    ideas = load_ideas()
    for i in ideas:
        if text.lower() in i["text"].lower() and not i["in_plan"]:
            i["in_plan"] = True
            save_ideas(ideas)
            return f"✅ Идея добавлена в план: _{i['text']}_"
    return "❗️ Идея не найдена. Используй: `идея в план: [часть текста]`"

# ─────────────────────────────────────────────
# REMINDERS
# ─────────────────────────────────────────────

def create_reminder(platform: str, topic: str, author: str) -> str:
    reminders = load_reminders()
    remind_at = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d %H:%M")
    reminder = {
        "id": len(reminders) + 1,
        "platform": platform,
        "topic": topic,
        "author": author,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "remind_at": remind_at,
        "done": False,
        "notified": False
    }
    reminders.append(reminder)
    save_reminders(reminders)
    return (f"⏰ *Напоминание #{reminder['id']} создано*\n"
            f"Платформа: {platform}\n"
            f"Тема: _{topic}_\n"
            f"Напомню: {remind_at}")


def show_reminders() -> str:
    reminders = load_reminders()
    active = [r for r in reminders if not r.get("done")]
    if not active:
        return "⏰ Нет активных напоминаний."
    lines = [f"⏰ *Активные напоминания* ({len(active)} шт.)\n"]
    for r in active:
        status = "✅" if r.get("notified") else "🕐"
        lines.append(f"{status} #{r['id']} [{r['remind_at']}] {r['platform']}: {r['topic']} (от {r['author']})")
    return "\n".join(lines)


def check_and_fire_reminders() -> list:
    """Check due reminders and return list of messages to send."""
    reminders = load_reminders()
    now = datetime.now()
    messages = []
    changed = False
    for r in reminders:
        if r.get("done") or r.get("notified"):
            continue
        try:
            remind_at = datetime.strptime(r["remind_at"], "%Y-%m-%d %H:%M")
        except Exception:
            continue
        if now >= remind_at:
            msg = (f"⏰ *Напоминание #{r['id']}*\n"
                   f"Вчера планировали пост в *{r['platform']}* про _{r['topic']}_\n\n"
                   f"Опубликовали? Скинь финал чтобы зафиксировать в реестре.\n"
                   f"Напиши: `опубликовано в {r['platform']}: {r['topic']}`")
            messages.append(msg)
            r["notified"] = True
            changed = True
    if changed:
        save_reminders(reminders)
    return messages


def mark_reminder_done(platform: str, topic: str) -> str:
    reminders = load_reminders()
    for r in reminders:
        if (r["platform"].lower() == platform.lower() and
                topic.lower() in r["topic"].lower() and not r.get("done")):
            r["done"] = True
            save_reminders(reminders)
            return f"✅ Напоминание закрыто: {platform} — {r['topic']}"
    return f"❗️ Напоминание не найдено: {platform} / {topic}"

# ─────────────────────────────────────────────
# VIDEO DESCRIPTIONS
# ─────────────────────────────────────────────

def generate_video_description(stream: str, topic: str) -> str:
    """Generate video title + description + tags."""
    if stream == "ru":
        prompt = f"""Создай материалы для видео (RuTube и VK).
Тема: {topic}

Формат:
🎬 *ЗАГОЛОВОК RuTube/VK:* [основной заголовок, до 60 символов]
📱 *SHORTS-ЗАГОЛОВОК:* [краткий заголовок, до 40 символов]

📝 *ОПИСАНИЕ (150-200 слов):*
[Описание для RuTube и VK. Упоминать @yokozuna_rus. Ключевые слова: аукционы Японии, б/у авто, YOKOZUNA, дилеры. CTA в конце.]

🏷️ *ТЕГИ RU (10-15 штук):*
[теги через запятую: японские авто, аукцион USS, YOKOZUNA, б/у авто из Японии, ...]"""
    else:
        prompt = f"""Create video materials for YouTube (EN stream).
Topic: {topic}

Format:
🎬 *YOUTUBE TITLE:* [main title, up to 60 chars]
📱 *SHORTS TITLE:* [short title, up to 40 chars]

📝 *DESCRIPTION (150-200 words):*
[YouTube description. Mention YOKOZUNA platform. Keywords: Japan auction, used cars, export, dealer. Include CTA.]

🏷️ *TAGS EN (10-15):*
[comma-separated: japan used cars, auction import, YOKOZUNA, ...]

🏷️ *TAGS RU (5-10 для алгоритмов):*
[дополнительные теги на русском]"""
    return gpt(prompt, temperature=0.6)

# ─────────────────────────────────────────────
# RUBRIC UPDATE
# ─────────────────────────────────────────────

def update_rubric(rubric_name: str, changes: str) -> str:
    """Update rubric description using GPT."""
    rubrics = load_rubrics()

    # Find rubric (case-insensitive, partial match)
    found_stream = None
    found_key = None
    for stream in ("ru", "en"):
        for key in rubrics.get(stream, {}):
            if rubric_name.lower() in key.lower():
                found_stream = stream
                found_key = key
                break
        if found_key:
            break

    if not found_key:
        return (f"❗️ Рубрика '{rubric_name}' не найдена.\n"
                f"Доступные RU: {', '.join(rubrics.get('ru', {}).keys())}\n"
                f"Доступные EN: {', '.join(rubrics.get('en', {}).keys())}")

    current = rubrics[found_stream][found_key]
    prompt = f"""Обнови описание рубрики на основе правок.

Рубрика: {found_key}
Текущее описание: {current.get('description', '')}
Текущие тезисы: {', '.join(current.get('tezisy', []))}
Текущая частота: {current.get('frequency', '')}

Правки: {changes}

Верни только JSON с обновлёнными полями:
{{"description": "...", "tezisy": ["T1", "T2"], "frequency": "..."}}

Сохрани всё что не меняется, измени только то, что указано в правках."""

    try:
        result = gpt(prompt, temperature=0.3)
        json_match = re.search(r'\{.*\}', result, re.DOTALL)
        if json_match:
            updated = json.loads(json_match.group())
            current.update(updated)
            current["updated_at"] = datetime.now().isoformat()
            rubrics[found_stream][found_key] = current
            save_rubrics(rubrics)
            return (f"✅ *Рубрика обновлена: {found_key}*\n\n"
                    f"Описание: {current.get('description', '')}\n"
                    f"Тезисы: {', '.join(current.get('tezisy', []))}\n"
                    f"Частота: {current.get('frequency', '')}")
        else:
            return f"❗️ Не удалось разобрать ответ GPT: {result[:200]}"
    except Exception as e:
        return f"❗️ Ошибка обновления рубрики: {e}"

# ─────────────────────────────────────────────
# MANUAL REGISTRY ENTRY
# ─────────────────────────────────────────────

def manual_register(channel: str, topic: str, author: str) -> str:
    """Manually register a published post."""
    registry = load_registry()
    stream = detect_stream(topic)
    channel_lower = channel.lower()

    # Map channel to stream key
    ru_channels = {"telegram", "vk", "rutube"}
    en_channels = {"youtube", "facebook", "x", "twitter", "linkedin"}

    if channel_lower in ru_channels:
        stream = "ru"
        ch_key = channel_lower
    elif channel_lower in en_channels:
        stream = "en"
        ch_key = "twitter" if channel_lower == "x" else channel_lower
    else:
        stream = "ru"
        ch_key = "telegram"  # default

    post = {
        "title": topic,
        "url": "",
        "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "source": channel_lower,
        "stream": stream,
        "manual": True,
        "author": author,
        "synced_at": datetime.now().isoformat()
    }

    if ch_key not in registry.get(stream, {}):
        registry[stream][ch_key] = []
    registry[stream][ch_key].append(post)
    save_registry(registry)

    # Close related reminders
    mark_reminder_done(channel, topic)

    return (f"✅ *Зафиксировано в реестре*\n"
            f"Канал: {channel}\n"
            f"Тема: _{topic}_\n"
            f"Поток: {stream.upper()}")

# ─────────────────────────────────────────────
# POST REFINEMENT
# ─────────────────────────────────────────────

# Simple session store for multi-turn post revision
post_session = {}  # chat_id -> {posts: [str], last_msg_id: int}


def store_generated_posts(chat_id: int, posts_text: str, msg_id: int) -> None:
    # Parse numbered posts from the generated text
    chunks = re.split(r'\n(?=\*\*#\d+\*\*|#\d+[\.\s])', posts_text)
    post_session[chat_id] = {
        "posts": [posts_text],  # store full text for revision
        "full": posts_text,
        "last_msg_id": msg_id
    }


def refine_post(chat_id: int, indices_str: str, comment: str) -> str:
    session = post_session.get(chat_id)
    if not session:
        return "❗️ Нет сохранённого поста для доработки. Сначала сгенерируй пост."

    original = session.get("full", "")
    prompt = f"""Доработай пост согласно комментарию.

ОРИГИНАЛЬНЫЙ ПОСТ:
{original}

КОММЕНТАРИЙ / ПРАВКИ:
{comment}

Верни полностью переработанный пост с тем же форматом (тип, факт-чек, тезисы, пост, хэштеги)."""
    result = gpt(prompt, temperature=0.65)
    post_session[chat_id]["full"] = result
    return result


def combine_posts(chat_id: int, indices_str: str) -> str:
    session = post_session.get(chat_id)
    if not session:
        return "❗️ Нет сохранённых постов для объединения."
    original = session.get("full", "")
    prompt = f"""Объедини следующие материалы в один дайджест-пост для канала.
Темы для объединения: позиции {indices_str}

МАТЕРИАЛ:
{original}

Создай единый пост-дайджест в голосе канала с заголовком, телом и CTA."""
    return gpt(prompt, temperature=0.65)

# ─────────────────────────────────────────────
# HELP TEXT
# ─────────────────────────────────────────────

HELP_TEXT = """🤖 *YOKOZUNA SMM Bot v3*

━━━ КОМАНДЫ ━━━

`/синк` — синхронизация всех каналов (Telegram/VK/RuTube)
`/реестр ru|en|telegram|vk|rutube` — реестр постов за 30 дней
`/план ru|en` — контент-план на неделю
`/идеи` — банк идей
`/напоминания` — активные напоминания

━━━ КОНТЕНТ ━━━

`[любой текст/ссылка]` → генерация поста
`идея: [текст]` → сохранить идею в банк
`идея в план: [текст]` → добавить идею в контент-план
`доработай: [комментарий]` → переработать последний пост
`+1 +3` → объединить темы дайджеста

━━━ ВИДЕО ━━━

`описание для видео ru: тема` → материалы для RuTube/VK
`описание для видео en: тема` → материалы для YouTube

━━━ ПЛАНИРОВАНИЕ ━━━

`запланировано в X: тема` — напоминание на завтра
`запланировано в FB: тема` — напоминание на завтра
`запланировано в LinkedIn: тема` — напоминание на завтра
`опубликовано в [канал]: тема` — зафиксировать в реестре

━━━ РУБРИКИ ━━━

`уточни рубрику [название]: правки` → обновить правила рубрики

━━━ ПОТОКИ ━━━
*RU*: @yokozuna_rus, VK, RuTube
*EN*: YouTube, Facebook, X/Twitter, LinkedIn

В группе бот реагирует только на @sumotori_smm_bot или reply на свои сообщения."""

# ─────────────────────────────────────────────
# MESSAGE ROUTER
# ─────────────────────────────────────────────

def get_author_name(message: dict) -> str:
    user = message.get("from", {})
    name = user.get("first_name", "")
    last = user.get("last_name", "")
    return f"{name} {last}".strip() or "Неизвестный"


def route_message(message: dict) -> Optional[str]:
    """Route incoming message to appropriate handler. Returns response text."""
    text = (message.get("text") or message.get("caption") or "").strip()
    chat_id = message.get("chat", {}).get("id")
    msg_id = message.get("message_id")
    author = get_author_name(message)

    if not text:
        return None

    # Remove @mention prefix for parsing
    clean_text = re.sub(rf"@{BOT_USERNAME}\s*", "", text, flags=re.IGNORECASE).strip()
    lower = clean_text.lower()

    # ── /start, /help ──
    if lower in ("/start", "/help", "help", "помощь", "/помощь"):
        return HELP_TEXT

    # ── /синк / /sync ──
    if lower in ("/синк", "/sync"):
        return sync_channels()

    # ── /реестр / /registry_ru / /registry_en ──
    if lower.startswith("/реестр"):
        arg = clean_text[7:].strip() or "ru"
        return format_registry(arg)
    if lower == "/registry_ru":
        return format_registry("ru")
    if lower == "/registry_en":
        return format_registry("en")

    # ── /план / /plan_ru / /plan_en ──
    if lower.startswith("/план"):
        arg = clean_text[5:].strip().lower() or "ru"
        if arg not in ("ru", "en"):
            return "❗️ Укажи поток: `/план ru` или `/план en`"
        return generate_content_plan(arg)
    if lower == "/plan_ru":
        return generate_content_plan("ru")
    if lower == "/plan_en":
        return generate_content_plan("en")

    # ── /идеи / /ideas ──
    if lower in ("/идеи", "идеи", "/ideas"):
        return show_ideas()

    # ── /напоминания / /reminders ──
    if lower in ("/напоминания", "напоминания", "/reminders"):
        return show_reminders()

    # ── идея в план: ──
    if lower.startswith("идея в план:"):
        idea_text = clean_text[12:].strip()
        return add_idea_to_plan(idea_text)

    # ── идея: ──
    if lower.startswith("идея:"):
        idea_text = clean_text[5:].strip()
        return save_idea(idea_text, author)

    # ── запланировано в X|FB|LinkedIn: тема ──
    reminder_match = re.match(
        r"запланировано\s+в\s+([a-zA-Zа-яА-Я/]+)\s*:\s*(.+)",
        clean_text, re.IGNORECASE
    )
    if reminder_match:
        platform = reminder_match.group(1).strip()
        topic = reminder_match.group(2).strip()
        return create_reminder(platform, topic, author)

    # ── опубликовано в [канал]: тема ──
    published_match = re.match(
        r"опубликовано\s+в\s+([a-zA-Zа-яА-Я/]+)\s*:\s*(.+)",
        clean_text, re.IGNORECASE
    )
    if published_match:
        channel = published_match.group(1).strip()
        topic = published_match.group(2).strip()
        return manual_register(channel, topic, author)

    # ── описание для видео ru|en: тема ──
    video_match = re.match(
        r"описание\s+для\s+видео\s+(ru|en)\s*:\s*(.+)",
        clean_text, re.IGNORECASE
    )
    if video_match:
        stream = video_match.group(1).lower()
        topic = video_match.group(2).strip()
        return generate_video_description(stream, topic)

    # ── уточни рубрику [название]: правки ──
    rubric_match = re.match(
        r"уточни\s+рубрику\s+(.+?)\s*:\s*(.+)",
        clean_text, re.IGNORECASE | re.DOTALL
    )
    if rubric_match:
        rubric_name = rubric_match.group(1).strip()
        changes = rubric_match.group(2).strip()
        return update_rubric(rubric_name, changes)

    # ── доработай [#N]: комментарий ──
    refine_match = re.match(
        r"доработай(?:\s+#?([\d,\s+]+))?\s*:?\s*(.+)",
        clean_text, re.IGNORECASE | re.DOTALL
    )
    if refine_match:
        indices = refine_match.group(1) or ""
        comment = refine_match.group(2).strip()
        return refine_post(chat_id, indices, comment)

    # ── +N +M объединить ──
    if re.match(r"^(\+\d+\s*)+$", clean_text):
        indices = re.findall(r"\d+", clean_text)
        return combine_posts(chat_id, ", ".join(indices))

    # ── DEFAULT: generate post ──
    stream = detect_stream(clean_text)
    return generate_post(clean_text, stream)

# ─────────────────────────────────────────────
# FLASK ROUTES
# ─────────────────────────────────────────────

@app.route("/", methods=["GET"])
def health():
    return jsonify({"status": "ok", "bot": BOT_USERNAME, "version": "3.0"}), 200


@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        data = request.get_json(force=True, silent=True)
        if not data:
            return jsonify({"ok": True}), 200

        # ── Check due reminders ──
        due_messages = check_and_fire_reminders()
        for msg in due_messages:
            send_message(GROUP_ID, msg)

        # ── Handle callback_query (нажатие inline кнопки) ──
        callback = data.get("callback_query")
        if callback:
            cb_chat_id = callback["message"]["chat"]["id"]
            cb_data = callback.get("data", "")
            cb_id = callback["id"]
            # Отвечаем Telegram что обработали
            requests.post(f"{TELEGRAM_API}/answerCallbackQuery",
                          json={"callback_query_id": cb_id}, timeout=10)
            if is_authorized(cb_chat_id):
                # Создаём фейковое сообщение для route_message
                fake_msg = {"chat": {"id": cb_chat_id, "type": "private"}, "text": cb_data}
                response_text = route_message(fake_msg)
                if response_text:
                    send_message(cb_chat_id, response_text)
            return jsonify({"ok": True}), 200

        # ── Handle message ──
        message = data.get("message") or data.get("edited_message")
        if not message:
            return jsonify({"ok": True}), 200

        chat_id = message.get("chat", {}).get("id")
        msg_id = message.get("message_id")

        # Auth check
        if not is_authorized(chat_id):
            log.info(f"Unauthorized chat_id: {chat_id}")
            return jsonify({"ok": True}), 200

        # Group filter: only respond to @mention or reply
        if not should_respond_in_group(message):
            return jsonify({"ok": True}), 200

        # Route message
        response_text = route_message(message)
        if response_text:
            # Для /start добавляем inline кнопки
            text_raw = message.get("text", "").strip().lower()
            markup = START_KEYBOARD if text_raw in ("/start", "/help") else None
            sent = send_message(chat_id, response_text,
                                reply_to_message_id=msg_id,
                                reply_markup=markup)
            # Store generated post for potential revision
            if sent and response_text and "━━━ ПОСТ ━━━" in response_text:
                sent_msg_id = sent.get("result", {}).get("message_id", msg_id)
                store_generated_posts(chat_id, response_text, sent_msg_id)

    except Exception as e:
        log.error(f"Webhook error: {e}", exc_info=True)

    return jsonify({"ok": True}), 200


@app.route("/set_webhook", methods=["GET", "POST"])
def set_webhook():
    """Helper endpoint to register webhook URL."""
    webhook_url = request.args.get("url") or request.json.get("url", "") if request.is_json else ""
    if not webhook_url:
        return jsonify({"error": "Provide ?url= parameter"}), 400
    try:
        r = requests.post(
            f"{TELEGRAM_API}/setWebhook",
            json={"url": webhook_url, "allowed_updates": ["message", "edited_message"]},
            timeout=10
        )
        return jsonify(r.json()), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ─────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    log.info(f"Starting YOKOZUNA Bot v3 on port {port}")

    # Initialize storage files
    load_registry()
    load_rubrics()
    load_ideas()
    load_reminders()

    app.run(host="0.0.0.0", port=port, debug=False)
