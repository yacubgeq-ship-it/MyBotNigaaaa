import os, random, math, time, telebot, threading, json, pathlib
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, LabeledPrice, ReplyKeyboardMarkup, KeyboardButton

TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN: raise ValueError("Не задан BOT_TOKEN")

ADMIN_IDS = [8211650013, 6940877915]
DATA_DIR = pathlib.Path("/app/data"); DATA_DIR.mkdir(parents=True, exist_ok=True)
DATA_FILE = DATA_DIR / "database.json"

data = {"players": {}, "promos": {}, "activations": [], "history": [], "clans": {}, "next_id": 1, "active_games": {}, "roulette_bets": {}, "duels": {}}
db_lock = threading.Lock()

def load_data():
    global data
    if DATA_FILE.exists():
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                for key in loaded: data[key] = loaded[key]
        except Exception as e: print(f"⚠️ Ошибка загрузки: {e}")

def save_data():
    with db_lock:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)

load_data()

def migrate_data():
    global data
    changed = False
    current_max = max([p.get("short_id", 0) for p in data["players"].values() if isinstance(p.get("short_id"), int)], default=0)
    if data.get("next_id", 1) <= current_max: data["next_id"] = current_max + 1
    for uid, pdata in data["players"].items():
        if "short_id" not in pdata or pdata["short_id"] == 0:
            pdata["short_id"] = data["next_id"]; data["next_id"] += 1; changed = True
        if "bank" not in pdata: pdata["bank"] = 0; pdata["deposit"] = 0; pdata["deposit_start"] = 0; changed = True
        if "biz_territory" not in pdata: pdata["biz_territory"] = 0; pdata["biz_building"] = 1; pdata["biz_tax"] = 0; pdata["biz_last_collect"] = int(time.time()); changed = True
        if "title" not in pdata: pdata["title"] = "Нет"; changed = True
        if "quests" not in pdata: pdata["quests"] = {}; changed = True
        if "donate_status" not in pdata: pdata["donate_status"] = "Нет"; changed = True
        if "last_bonus" not in pdata: pdata["last_bonus"] = 0; changed = True
    if "roulette_bets" not in data: data["roulette_bets"] = {}
    if "duels" not in data: data["duels"] = {}
    if "promos" not in data: data["promos"] = {}
    if "activations" not in data: data["activations"] = []
    if changed: save_data()

migrate_data()
bot = telebot.TeleBot(TOKEN)

MULT = {3: 1.15, 5: 1.25, 9: 1.45}
BIZ_TERRITORY_COST = {0: 10000, 1: 50000, 2: 250000, 3: 1000000, 4: 5000000, 5: 25000000}
BIZ_BUILDING_COST = {1: 20000, 2: 100000, 3: 500000, 4: 2000000, 5: 10000000}

def get_balance(uid): return data["players"].get(str(uid), {}).get("balance", 0)
def get_nick(uid): return data["players"].get(str(uid), {}).get("username", "Player")
def get_user_short_id(uid): return data["players"].get(str(uid), {}).get("short_id", "0")

def get_user_by_short_id(sid):
    for uid, pdata in data["players"].items():
        if str(pdata.get("short_id")) == str(sid): return uid
    return None

def get_user_by_username(uname):
    uname = uname.replace("@", "").lower()
    for uid, pdata in data["players"].items():
        if pdata.get("username", "").lower() == uname: return uid
    return None

def get_win_multiplier(uid):
    status = data["players"].get(str(uid), {}).get("donate_status", "Нет")
    if status == "VIP": return 1.05
    if status == "Premium": return 1.15
    if status == "Ultra": return 1.25
    return 1.0

def add_balance(uid, amt):
    uid = str(uid)
    if uid not in data["players"]: register_user_by_id(uid)
    data["players"][uid]["balance"] += amt; save_data()

def register_user(user):
    uid = str(user.id)
    if uid not in data["players"]:
        sid = data["next_id"]; data["next_id"] += 1
        data["players"][uid] = {"username": user.username or user.first_name, "balance": 1000, "last_bonus": 0, "short_id": sid, "clan_id": None, "role": "none", "bank": 0, "deposit": 0, "deposit_start": 0, "biz_territory": 0, "biz_building": 1, "biz_tax": 0, "biz_last_collect": int(time.time()), "title": "Нет", "quests": {}, "donate_status": "Нет"}
        save_data()

def register_user_by_id(uid):
    if uid not in data["players"]:
        sid = data["next_id"]; data["next_id"] += 1
        data["players"][uid] = {"username": "Player", "balance": 1000, "last_bonus": 0, "short_id": sid, "clan_id": None, "role": "none", "bank": 0, "deposit": 0, "deposit_start": 0, "biz_territory": 0, "biz_building": 1, "biz_tax": 0, "biz_last_collect": int(time.time()), "title": "Нет", "quests": {}, "donate_status": "Нет"}
        save_data()

# ==================== ГЛАВНОЕ МЕНЮ (кнопки снизу) ====================

def get_main_keyboard():
    """Постоянная клавиатура снизу, как в магазинах"""
    kb = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    kb.row(KeyboardButton("👤 Профиль"), KeyboardButton("💰 Баланс"))
    kb.row(KeyboardButton("🎁 Бонус"), KeyboardButton("🎮 Игры"))
    kb.row(KeyboardButton("🛡 Кланы"), KeyboardButton("💎 Донат"))
    kb.row(KeyboardButton("🏦 Банк"), KeyboardButton("🏢 Бизнес"))
    kb.row(KeyboardButton("📖 Помощь"), KeyboardButton("🏆 Топ"))
    return kb

# ==================== СТАРТ И ПОМОЩЬ ====================

@bot.message_handler(commands=["start"])
def start(message):
    register_user(message.from_user)
    bot.send_message(message.chat.id,
        f"🎮 **MON1 GAME RPG** 🎮\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 Добро пожаловать, **{get_nick(message.from_user.id)}**!\n\n"
        f"💰 Ваш баланс: **{get_balance(message.from_user.id)} 🪙**\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"Используй кнопки внизу 👇 или пиши команды.",
        parse_mode="Markdown",
        reply_markup=get_main_keyboard())

@bot.message_handler(commands=['help'])
@bot.message_handler(func=lambda m: m.text and m.text.lower().strip() in ['помощь', 'help', '📖 помощь'])
def help_command(message):
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(InlineKeyboardButton("🎮 Игры", callback_data="help_games"), InlineKeyboardButton("💼 Экономика", callback_data="help_eco"))
    kb.add(InlineKeyboardButton("🛡 Кланы", callback_data="help_clans"), InlineKeyboardButton("💎 Донат", callback_data="help_donate"))
    bot.reply_to(message, "📖 **МЕНЮ ПОМОЩИ**\n━━━━━━━━━━━━━━━━━━━━\nВыберите раздел кнопками ниже:", reply_markup=kb, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data.startswith("help_"))
def help_callbacks(call):
    section = call.data.split("_")[1]
    if section == "games": text = "🎮 **ИГРЫ**\n━━━━━━━━━━━━━━━━━━━━\n• `слот 1000` — испытание\n• `мины 1000 5` — поле (3, 5, 9 бомб)\n• `краш 1000` — растущий коэф.\n• `джокер 1000` — лесенка удачи\n• `1000 5 красное` — колесо (запуск `го`)"
    elif section == "eco": text = "💼 **ЭКОНОМИКА**\n━━━━━━━━━━━━━━━━━━━━\n• `б` — баланс\n• `бонус` — ежедневный бонус\n• `профиль` — профиль\n• `узнать ид` — ID игрока\n• `топ` — топ-10\n• `банк` — банк\n• `мой бизнес` — бизнес\n• `квесты` — задания\n• `перевод 1000 ник`\n• `промо КОД`\n• `сменить ник НОВЫЙ_НИК`"
    elif section == "clans": text = "🛡 **КЛАНЫ**\n━━━━━━━━━━━━━━━━━━━━\n• `создать клан ИМЯ` (10000)\n• `вступить клан ID`\n• `мой клан`\n• `выйти из клана`\n• `топ кланов`\n• `клан казна положить/снять СУММА`"
    elif section == "donate": text = "💎 **ДОНАТ**\n━━━━━━━━━━━━━━━━━━━━\n• `донат` — пополнить\n• `донат статус` — купить статус\n• `мой статус` — узнать статус"
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=call.message.reply_markup, parse_mode="Markdown")
    bot.answer_callback_query(call.id)

@bot.message_handler(func=lambda m: m.text and m.text.lower().strip() in ['игры', '🎮 игры'])
def games_menu(message):
    text = (
        "🎮 **ИГРЫ**\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "• `слот 1000` — слоты\n"
        "• `мины 1000 5` — мины (3 / 5 / 9 бомб)\n"
        "• `краш 1000` — краш\n"
        "• `джокер 1000` — джокер\n"
        "• `1000 5 красное` — рулетка (потом `го`)\n"
        "• `дуэль @ник 1000` — камень-ножницы-бумага\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "Просто напиши команду с суммой ставки."
    )
    bot.reply_to(message, text, parse_mode="Markdown")

# ==================== БОНУС ====================

@bot.message_handler(func=lambda m: m.text and m.text.lower().strip() in ['бонус', '🎁 бонус'])
def daily_bonus(message):
    uid = str(message.from_user.id)
    if uid not in data["players"]: register_user(message.from_user)
    p = data["players"][uid]
    now = int(time.time())
    last = p.get("last_bonus", 0)
    if now - last < 86400:
        left = 86400 - (now - last)
        return bot.reply_to(message, f"⏳ **Подождите!**\nСледующий бонус через **{left // 3600} ч. {(left % 3600) // 60} мин.**", parse_mode="Markdown")
    reward = random.randint(1000, 3000)
    add_balance(uid, reward)
    data["players"][uid]["last_bonus"] = now; save_data()
    bot.reply_to(message, f"🎁 **ЕЖЕДНЕВНЫЙ БОНУС**\n━━━━━━━━━━━━━━━━━━━━\nВы получили: **{reward} 🪙**\n━━━━━━━━━━━━━━━━━━━━\nПриходите завтра!", parse_mode="Markdown")
    # ==================== ДОНАТ И СТАТУСЫ ====================

@bot.message_handler(commands=['donate'])
@bot.message_handler(func=lambda m: m.text and m.text.lower().strip() in ['донат', '💎 донат'])
def donate_menu(message):
    text = "💎 **ПОПОЛНЕНИЕ БАЛАНСА**\n━━━━━━━━━━━━━━━━━━━━\n1 ⭐ = 1000 🪙\n\nВыберите пакет:"
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton("25 ⭐ = 25000 🪙", callback_data="donate_pack_25"))
    kb.add(InlineKeyboardButton("50 ⭐ = 50000 🪙", callback_data="donate_pack_50"))
    kb.add(InlineKeyboardButton("100 ⭐ = 100000 🪙", callback_data="donate_pack_100"))
    kb.add(InlineKeyboardButton("✏️ Ввести свою сумму", callback_data="donate_custom"))
    bot.reply_to(message, text, reply_markup=kb, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data.startswith("donate_"))
def donate_process(call):
    if call.data == "donate_custom":
        msg = bot.send_message(call.message.chat.id, "✏️ Введите количество звезд (от 1 до 10000):")
        bot.register_next_step_handler(msg, process_custom_stars)
        return
    stars = int(call.data.split("_")[2])
    coins = stars * 1000
    prices = [LabeledPrice(label=f"{coins} монет", amount=stars)]
    try:
        bot.send_invoice(chat_id=call.message.chat.id, title=f"Покупка {coins} монет", description=f"Вы получите {coins} монет на баланс.", invoice_payload=f"pay_{stars}", provider_token="", currency="XTR", prices=prices)
        bot.answer_callback_query(call.id, "✅ Счет выставлен!")
    except Exception as e: bot.answer_callback_query(call.id, f"Ошибка: {e}", show_alert=True)

def process_custom_stars(message):
    try:
        stars = int(message.text)
        if stars < 1 or stars > 10000: return bot.reply_to(message, "❌ От 1 до 10000 звезд.")
        coins = stars * 1000
        prices = [LabeledPrice(label=f"{coins} монет", amount=stars)]
        bot.send_invoice(chat_id=message.chat.id, title=f"Покупка {coins} монет", description=f"Вы получите {coins} монет на баланс.", invoice_payload=f"pay_{stars}", provider_token="", currency="XTR", prices=prices)
    except (ValueError, TypeError): bot.reply_to(message, "❌ Введите число.")

@bot.pre_checkout_query_handler(func=lambda query: True)
def process_pre_checkout_query(pre_checkout_query):
    bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)

@bot.message_handler(content_types=['successful_payment'])
def got_payment(message):
    payload = message.successful_payment.invoice_payload
    if payload.startswith("status_"):
        status = payload.split("_")[1]
        uid = str(message.from_user.id)
        if uid not in data["players"]: register_user(message.from_user)
        data["players"][uid]["donate_status"] = status
        save_data()
        bot.send_message(message.chat.id, f"🎉 **ОПЛАТА УСПЕШНА!**\n━━━━━━━━━━━━━━━━━━━━\nВы получили статус **{status}**!", parse_mode="Markdown")
        return

    stars = int(payload.split("_")[1])
    coins = stars * 1000
    uid = str(message.from_user.id)
    if uid not in data["players"]: register_user(message.from_user)
    add_balance(uid, coins)

    current_status = data["players"][uid].get("donate_status", "Нет")
    if stars >= 750 and current_status != "Ultra": 
        data["players"][uid]["donate_status"] = "Ultra"
        bot.send_message(message.chat.id, f"🎉 **ОПЛАТА УСПЕШНА!**\n━━━━━━━━━━━━━━━━━━━━\nВы получили **{coins} 🪙** и статус **Ultra**!", parse_mode="Markdown")
    elif stars >= 450 and current_status not in ["Premium", "Ultra"]: 
        data["players"][uid]["donate_status"] = "Premium"
        bot.send_message(message.chat.id, f"🎉 **ОПЛАТА УСПЕШНА!**\n━━━━━━━━━━━━━━━━━━━━\nВы получили **{coins} 🪙** и статус **Premium**!", parse_mode="Markdown")
    elif stars >= 200 and current_status not in ["VIP", "Premium", "Ultra"]: 
        data["players"][uid]["donate_status"] = "VIP"
        bot.send_message(message.chat.id, f"🎉 **ОПЛАТА УСПЕШНА!**\n━━━━━━━━━━━━━━━━━━━━\nВы получили **{coins} 🪙** и статус **VIP**!", parse_mode="Markdown")
    else: 
        bot.send_message(message.chat.id, f"🎉 **ОПЛАТА УСПЕШНА!**\n━━━━━━━━━━━━━━━━━━━━\nВы получили **{coins} 🪙**.", parse_mode="Markdown")
    save_data()

@bot.message_handler(commands=['donate_status'])
@bot.message_handler(func=lambda m: m.text and m.text.lower().strip() == 'донат статус')
def donate_status_menu(message):
    text = "💎 **ДОНАТ-СТАТУСЫ**\n━━━━━━━━━━━━━━━━━━━━\n👑 **VIP** (200 ⭐) — +5% к выигрышу\n💎 **Premium** (450 ⭐) — +15% к выигрышу\n⚡ **Ultra** (750 ⭐) — +25% к выигрышу + просмотр профилей"
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton("👑 VIP (200 ⭐)", callback_data="buy_status_VIP"))
    kb.add(InlineKeyboardButton("💎 Premium (450 ⭐)", callback_data="buy_status_Premium"))
    kb.add(InlineKeyboardButton("⚡ Ultra (750 ⭐)", callback_data="buy_status_Ultra"))
    bot.reply_to(message, text, reply_markup=kb, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data.startswith("buy_status_"))
def buy_status(call):
    status = call.data.split("_")[2]
    stars = {"VIP": 200, "Premium": 450, "Ultra": 750}[status]
    prices = [LabeledPrice(label=f"Статус {status}", amount=stars)]
    try:
        bot.send_invoice(chat_id=call.message.chat.id, title=f"Покупка статуса {status}", description=f"Вы получите статус {status}.", invoice_payload=f"status_{status}", provider_token="", currency="XTR", prices=prices)
        bot.answer_callback_query(call.id, "✅ Счет выставлен!")
    except Exception as e: bot.answer_callback_query(call.id, f"Ошибка: {e}", show_alert=True)

@bot.message_handler(func=lambda m: m.text and m.text.lower().strip() == "мой статус")
def my_status(message):
    uid = str(message.from_user.id)
    status = data["players"].get(uid, {}).get("donate_status", "Нет")
    bot.reply_to(message, f"💎 **ВАШ СТАТУС**\n━━━━━━━━━━━━━━━━━━━━\n{status}", parse_mode="Markdown")

# ==================== БАЗОВЫЕ КОМАНДЫ ====================

@bot.message_handler(func=lambda m: m.text and m.text.lower().strip() in ['б', 'баланс', '💰 баланс'])
def balance_command(message):
    uid = str(message.from_user.id)
    if uid not in data["players"]: register_user(message.from_user)
    bot.reply_to(message, f"💰 **БАЛАНС**\n━━━━━━━━━━━━━━━━━━━━\n{get_balance(uid)} 🪙", parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text and m.text.lower().strip() in ['узнать ид', 'мой ид', 'мой id'])
def get_id_command(message):
    uid = str(message.from_user.id)
    target_uid = uid
    if message.reply_to_message:
        target_uid = str(message.reply_to_message.from_user.id)
        caller_status = data["players"].get(uid, {}).get("donate_status", "Нет")
        if uid not in [str(a) for a in ADMIN_IDS] and caller_status != "Ultra":
            return bot.reply_to(message, "❌ **ДОСТУП ЗАПРЕЩЕН**\nСмотреть чужой ID могут только админы и Ultra.", parse_mode="Markdown")
    if target_uid not in data["players"]: register_user_by_id(target_uid)
    sid = get_user_short_id(target_uid)
    bot.reply_to(message, f"🆔 **ID ИГРОКА**\n━━━━━━━━━━━━━━━━━━━━\n`{sid}`", parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text and m.text.lower().startswith("сменить ник"))
def change_nick(message):
    uid = str(message.from_user.id)
    try:
        new_nick = message.text[12:].strip()
        if len(new_nick) < 3 or len(new_nick) > 15: return bot.reply_to(message, "❌ Ник от 3 до 15 символов.")
        data["players"][uid]["username"] = new_nick
        save_data()
        bot.reply_to(message, f"✅ **НИК ИЗМЕНЕН**\n━━━━━━━━━━━━━━━━━━━━\nНовый ник: **{new_nick}**", parse_mode="Markdown")
    except: bot.reply_to(message, "❌ `сменить ник НОВЫЙ_НИК`")

@bot.message_handler(func=lambda m: m.text and m.text.lower().strip() in ['профиль', '👤 профиль'])
def profile_command(message):
    uid = str(message.from_user.id)
    target_uid = uid
    if message.reply_to_message:
        target_uid = str(message.reply_to_message.from_user.id)
        caller_status = data["players"].get(uid, {}).get("donate_status", "Нет")
        if uid not in [str(a) for a in ADMIN_IDS] and caller_status != "Ultra":
            return bot.reply_to(message, "❌ **ДОСТУП ЗАПРЕЩЕН**\nСмотреть чужой профиль могут только админы и Ultra.", parse_mode="Markdown")
    if target_uid not in data["players"]: register_user_by_id(target_uid)
    p = data["players"][target_uid]
    clan_name = "Нет"
    if p.get("clan_id"):
        clan = data["clans"].get(str(p["clan_id"]))
        if clan: clan_name = clan.get("name", "Нет")
    text = (f"👤 **ПРОФИЛЬ ИГРОКА**\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🆔 ID: `{p.get('short_id', '?')}`\n"
            f"👤 Ник: {p.get('username', '?')}\n"
            f"💎 Статус: {p.get('donate_status', 'Нет')}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"💰 Баланс: {p.get('balance', 0)} 🪙\n"
            f"🏦 Банк: {p.get('bank', 0)} 🪙\n"
            f"💎 Депозит: {p.get('deposit', 0)} 🪙\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🛡 Клан: {clan_name}\n"
            f"🏢 Бизнес: {p.get('biz_territory', 0)} м²")
    bot.reply_to(message, text, parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text and m.text.lower().strip() in ["топ", "топ игроков", "🏆 топ"])
def top_cmd(message):
    sp = sorted(data["players"].items(), key=lambda x: x[1].get("balance", 0), reverse=True)[:10]
    text = "🏆 **ТОП-10 ИГРОКОВ**\n━━━━━━━━━━━━━━━━━━━━\n" + "".join([f"{i}. {p.get('username', '?')} — {p.get('balance', 0)} 🪙\n" for i, (u, p) in enumerate(sp, 1)])
    bot.reply_to(message, text, parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text and m.text.lower().strip() == "чаты")
def chats_cmd(message):
    bot.reply_to(message, "💬 **НАШИ ЧАТЫ**\n━━━━━━━━━━━━━━━━━━━━\n📢 Канал: https://t.me/mon1bots\n💬 Чат: https://t.me/mon1not", parse_mode="Markdown")
    # ==================== ДУЭЛИ (Камень-Ножницы-Бумага) ====================

RPS_MAP = {
    "камень": "🪨", "ножницы": "✂️", "бумага": "📄",
    "к": "🪨", "н": "✂️",
    "rock": "🪨", "scissors": "✂️", "paper": "📄"
}
RPS_CHOICES = {"камень": "камень", "ножницы": "ножницы", "бумага": "бумага",
               "к": "камень", "н": "ножницы",
               "rock": "камень", "scissors": "ножницы", "paper": "бумага"}

def rps_winner(c1, c2):
    if c1 == c2: return 0
    wins = {"камень": "ножницы", "ножницы": "бумага", "бумага": "камень"}
    if wins[c1] == c2: return 1
    return 2

def find_pending_duel_for(uid):
    uid = str(uid)
    for duel_id, duel in data["duels"].items():
        if duel["status"] == "pending" and duel["opponent"] == uid:
            return duel_id, duel
    return None, None

def find_active_duel_for(uid):
    uid = str(uid)
    for duel_id, duel in data["duels"].items():
        if duel["status"] == "choosing" and uid in (duel["challenger"], duel["opponent"]):
            return duel_id, duel
    return None, None

def resolve_rps_duel(duel_id, duel):
    c1 = duel.get("choice1")
    c2 = duel.get("choice2")
    if not c1 or not c2: return

    amount = duel["amount"]
    pot = amount * 2
    ch = duel["challenger"]
    op = duel["opponent"]

    result = rps_winner(c1, c2)
    emoji1 = RPS_MAP.get(c1, c1)
    emoji2 = RPS_MAP.get(c2, c2)

    if result == 0:
        add_balance(ch, amount); add_balance(op, amount)
        duel["status"] = "draw"; save_data()
        text = (f"⚔️ **ДУЭЛЬ — НИЧЬЯ**\n━━━━━━━━━━━━━━━━━━━━\n"
                f"👤 {get_nick(ch)}: {emoji1} **{c1}**\n"
                f"👤 {get_nick(op)}: {emoji2} **{c2}**\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"🤝 Ставки возвращены ({amount} 🪙 каждому)")
    else:
        if result == 1: winner, loser = ch, op; w_choice, l_choice = c1, c2; w_emoji, l_emoji = emoji1, emoji2
        else: winner, loser = op, ch; w_choice, l_choice = c2, c1; w_emoji, l_emoji = emoji2, emoji1
        add_balance(winner, pot)
        duel["status"] = "finished"; duel["winner"] = winner; save_data()
        pot_str = f"{pot:,}".replace(",", " ")
        text = (f"⚔️ **РЕЗУЛЬТАТ ДУЭЛИ**\n━━━━━━━━━━━━━━━━━━━━\n"
                f"🏆 **{get_nick(winner)}**: {w_emoji} **{w_choice}**\n"
                f"💀 **{get_nick(loser)}**: {l_emoji} **{l_choice}**\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"💰 Банк: **{pot_str} 🪙**")
    try:
        bot.send_message(int(ch), text, parse_mode="Markdown")
        bot.send_message(int(op), text, parse_mode="Markdown")
    except: pass

def send_choice_buttons(uid, duel_id):
    kb = InlineKeyboardMarkup(row_width=3)
    kb.add(
        InlineKeyboardButton("🪨 Камень", callback_data=f"rps_{duel_id}_камень"),
        InlineKeyboardButton("✂️ Ножницы", callback_data=f"rps_{duel_id}_ножницы"),
        InlineKeyboardButton("📄 Бумага", callback_data=f"rps_{duel_id}_бумага")
    )
    try:
        bot.send_message(int(uid), "⚔️ **Выбери свой ход:**", reply_markup=kb, parse_mode="Markdown")
    except: pass

@bot.message_handler(func=lambda m: m.text and m.text.lower().startswith("дуэль "))
def duel_challenge(message):
    uid = str(message.from_user.id)
    if uid not in data["players"]: register_user(message.from_user)
    
    parts = message.text.split()
    if len(parts) < 3:
        return bot.reply_to(message, "❌ Формат: `дуэль @ник 1000` или `дуэль ID 1000`", parse_mode="Markdown")
    
    try:
        amount = int(parts[-1])
        if amount < 100: return bot.reply_to(message, "❌ Минимальная ставка — 100 🪙")
        if get_balance(uid) < amount: return bot.reply_to(message, "❌ Недостаточно средств")
        
        target_raw = parts[1]
        if target_raw.startswith("@"):
            target_uid = get_user_by_username(target_raw)
        else:
            target_uid = get_user_by_short_id(target_raw)
        
        if not target_uid or target_uid == uid:
            return bot.reply_to(message, "❌ Игрок не найден")
        
        if find_pending_duel_for(target_uid)[0] or find_active_duel_for(target_uid)[0]:
            return bot.reply_to(message, "❌ У этого игрока уже есть активная дуэль")
        if find_active_duel_for(uid)[0]:
            return bot.reply_to(message, "❌ У тебя уже есть активная дуэль")
        
        duel_id = str(int(time.time() * 1000))
        data["duels"][duel_id] = {
            "challenger": uid, "opponent": target_uid, "amount": amount,
            "status": "pending", "choice1": None, "choice2": None, "created": int(time.time())
        }
        save_data()

        amount_str = f"{amount:,}".replace(",", " ")
        kb = InlineKeyboardMarkup(row_width=2)
        kb.add(
            InlineKeyboardButton("✅ Принять", callback_data=f"duel_accept_{duel_id}"),
            InlineKeyboardButton("❌ Отклонить", callback_data=f"duel_reject_{duel_id}")
        )

        try:
            bot.send_message(int(target_uid),
                f"⚔️ **ВЫЗОВ НА ДУЭЛЬ (КНБ)**\n━━━━━━━━━━━━━━━━━━━━\n"
                f"👤 **{get_nick(uid)}** вызывает тебя!\n"
                f"💰 Ставка: **{amount_str} 🪙**\n"
                f"🎮 Камень · Ножницы · Бумага\n━━━━━━━━━━━━━━━━━━━━\n"
                f"Напиши `принять` или нажми кнопку.\nУ тебя **2 минуты**.",
                reply_markup=kb, parse_mode="Markdown")
        except Exception:
            del data["duels"][duel_id]; save_data()
            return bot.reply_to(message, "❌ Не удалось отправить вызов.\nСоперник, скорее всего, ещё не запускал бота.")

        bot.reply_to(message, f"⚔️ Вызов (КНБ) отправлен **{get_nick(target_uid)}**\nСтавка: **{amount_str} 🪙**\nОжидай ответа...", parse_mode="Markdown")

        def auto_cancel(duel_id=duel_id, uid=uid, target_uid=target_uid):
            time.sleep(120)
            if duel_id in data["duels"] and data["duels"][duel_id]["status"] == "pending":
                data["duels"][duel_id]["status"] = "expired"; save_data()
                try:
                    bot.send_message(int(uid), "⌛️ Твой вызов на дуэль истёк.")
                    bot.send_message(int(target_uid), "⌛️ Вызов на дуэль истёк.")
                except: pass
        threading.Thread(target=auto_cancel, daemon=True).start()

    except ValueError:
        bot.reply_to(message, "❌ Неверная сумма ставки")

@bot.message_handler(func=lambda m: m.text and m.text.lower().strip() in ["принять", "accept", "да"])
def duel_accept_text(message):
    uid = str(message.from_user.id)
    duel_id, duel = find_pending_duel_for(uid)
    if not duel: return bot.reply_to(message, "❌ У тебя нет входящих вызовов на дуэль.")

    challenger = duel["challenger"]; opponent = duel["opponent"]; amount = duel["amount"]
    if get_balance(challenger) < amount or get_balance(opponent) < amount:
        duel["status"] = "cancelled"; save_data()
        return bot.reply_to(message, "❌ Недостаточно средств у одного из игроков. Дуэль отменена.")

    add_balance(challenger, -amount); add_balance(opponent, -amount)
    duel["status"] = "choosing"; duel["choice1"] = None; duel["choice2"] = None; save_data()

    bot.reply_to(message, "✅ Дуэль принята! Выбери ход кнопками ниже.")
    send_choice_buttons(challenger, duel_id)
    send_choice_buttons(opponent, duel_id)

@bot.message_handler(func=lambda m: m.text and m.text.lower().strip() in ["отклонить", "no", "отмена"])
def duel_reject_text(message):
    uid = str(message.from_user.id)
    duel_id, duel = find_pending_duel_for(uid)
    if not duel: return bot.reply_to(message, "❌ Нет входящих вызовов.")
    duel["status"] = "rejected"; save_data()
    try:
        bot.send_message(int(duel["challenger"]), f"❌ {get_nick(uid)} отклонил твой вызов.")
    except: pass
    bot.reply_to(message, "❌ Вызов отклонён.")

@bot.callback_query_handler(func=lambda call: call.data.startswith("duel_"))
def duel_callback(call):
    parts = call.data.split("_")
    action = parts[1]
    duel_id = parts[2]
    if duel_id not in data["duels"]:
        return bot.answer_callback_query(call.id, "Дуэль не найдена", show_alert=True)
    
    duel = data["duels"][duel_id]
    uid = str(call.from_user.id)

    if action == "accept":
        if duel["opponent"] != uid or duel["status"] != "pending":
            return bot.answer_callback_query(call.id, "Нельзя принять", show_alert=True)
        challenger = duel["challenger"]; amount = duel["amount"]
        if get_balance(challenger) < amount or get_balance(uid) < amount:
            duel["status"] = "cancelled"; save_data()
            return bot.answer_callback_query(call.id, "Недостаточно средств", show_alert=True)
        add_balance(challenger, -amount); add_balance(uid, -amount)
        duel["status"] = "choosing"; save_data()
        bot.answer_callback_query(call.id, "Дуэль принята!")
        bot.edit_message_text("✅ Дуэль принята! Выберите ход.", call.message.chat.id, call.message.message_id)
        send_choice_buttons(challenger, duel_id)
        send_choice_buttons(uid, duel_id)
    elif action == "reject":
        if duel["opponent"] != uid or duel["status"] != "pending":
            return bot.answer_callback_query(call.id, "Нельзя отклонить", show_alert=True)
        duel["status"] = "rejected"; save_data()
        bot.answer_callback_query(call.id, "Отклонено")
        bot.edit_message_text("❌ Вызов отклонён.", call.message.chat.id, call.message.message_id)
        try:
            bot.send_message(int(duel["challenger"]), f"❌ {get_nick(uid)} отклонил твой вызов.")
        except: pass

@bot.callback_query_handler(func=lambda call: call.data.startswith("rps_"))
def rps_choice_callback(call):
    parts = call.data.split("_")
    duel_id = parts[1]
    choice = parts[2]
    uid = str(call.from_user.id)
    
    if duel_id not in data["duels"]:
        return bot.answer_callback_query(call.id, "Дуэль не найдена", show_alert=True)
    
    duel = data["duels"][duel_id]
    if duel["status"] != "choosing":
        return bot.answer_callback_query(call.id, "Дуэль уже завершена", show_alert=True)
    
    if uid == duel["challenger"]:
        if duel.get("choice1"): return bot.answer_callback_query(call.id, "Ты уже выбрал", show_alert=True)
        duel["choice1"] = choice
    elif uid == duel["opponent"]:
        if duel.get("choice2"): return bot.answer_callback_query(call.id, "Ты уже выбрал", show_alert=True)
        duel["choice2"] = choice
    else:
        return bot.answer_callback_query(call.id, "Это не твоя дуэль", show_alert=True)
    
    save_data()
    bot.answer_callback_query(call.id, f"Выбрано: {choice}")
    bot.edit_message_text(f"✅ Ты выбрал: **{choice}**\nОжидаем соперника...", call.message.chat.id, call.message.message_id, parse_mode="Markdown")
    
    if duel.get("choice1") and duel.get("choice2"):
        resolve_rps_duel(duel_id, duel)

@bot.message_handler(func=lambda m: m.text and m.text.lower().strip() in ["камень", "ножницы", "бумага", "к", "н", "rock", "scissors", "paper"])
def rps_choice_text(message):
    uid = str(message.from_user.id)
    duel_id, duel = find_active_duel_for(uid)
    if not duel: return
    
    choice = RPS_CHOICES.get(message.text.lower().strip())
    if not choice: return
    
    if uid == duel["challenger"]:
        if duel.get("choice1"): return bot.reply_to(message, "Ты уже выбрал ход.")
        duel["choice1"] = choice
    else:
        if duel.get("choice2"): return bot.reply_to(message, "Ты уже выбрал ход.")
        duel["choice2"] = choice
    
    save_data()
    bot.reply_to(message, f"✅ Ты выбрал: **{choice}**", parse_mode="Markdown")
    
    if duel.get("choice1") and duel.get("choice2"):
        resolve_rps_duel(duel_id, duel)
        # ==================== АДМИН-ПАНЕЛЬ ====================

@bot.message_handler(commands=['admin'])
@bot.message_handler(func=lambda m: m.text and m.text.lower().strip() in ['админ', 'админка'])
def admin_panel(message):
    if message.from_user.id not in ADMIN_IDS: return
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(InlineKeyboardButton("📊 Статистика", callback_data="adm_stats"), InlineKeyboardButton("💰 Выдать деньги", callback_data="adm_give"))
    kb.add(InlineKeyboardButton("👑 Выдать статус", callback_data="adm_setstatus"), InlineKeyboardButton("🗑 Обнулить игрока", callback_data="adm_reset"))
    kb.add(InlineKeyboardButton("🎁 Создать промо", callback_data="adm_promo"), InlineKeyboardButton("❌ Удалить промо", callback_data="adm_delpromo"))
    kb.add(InlineKeyboardButton("📢 Рассылка", callback_data="adm_broadcast"))
    bot.reply_to(message, "⚙️ **АДМИН-ПАНЕЛЬ**\n━━━━━━━━━━━━━━━━━━━━\nВыберите действие:", reply_markup=kb, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data.startswith("adm_"))
def admin_callbacks(call):
    if call.from_user.id not in ADMIN_IDS: return bot.answer_callback_query(call.id, "❌ Нет прав.")
    act = call.data.split("_")[1]
    if act == "stats":
        total_players = len(data["players"]); total_money = sum(p.get("balance", 0) for p in data["players"].values()); total_clans = len(data["clans"])
        text = f"📊 **СТАТИСТИКА**\n━━━━━━━━━━━━━━━━━━━━\n👥 Игроков: {total_players}\n💰 Общий баланс: {total_money} 🪙\n🛡 Кланов: {total_clans}"
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("⬅️ Назад", callback_data="adm_back")), parse_mode="Markdown")
    elif act == "give":
        msg = bot.send_message(call.message.chat.id, "Введите `ID СУММА` (например: `3 5000`):"); bot.register_next_step_handler(msg, admin_give_step); bot.answer_callback_query(call.id)
    elif act == "setstatus":
        msg = bot.send_message(call.message.chat.id, "Введите `ID СТАТУС` (например: `3 Ultra`).\nДоступные статусы: `VIP`, `Premium`, `Ultra`, `Нет`:"); bot.register_next_step_handler(msg, admin_setstatus_step); bot.answer_callback_query(call.id)
    elif act == "reset":
        msg = bot.send_message(call.message.chat.id, "Введите `ID` игрока для обнуления баланса (например: `3`):"); bot.register_next_step_handler(msg, admin_reset_step); bot.answer_callback_query(call.id)
    elif act == "promo":
        msg = bot.send_message(call.message.chat.id, "Введите `КОД СУММА` (например: `NEWYEAR 1000`):"); bot.register_next_step_handler(msg, admin_promo_step); bot.answer_callback_query(call.id)
    elif act == "delpromo":
        msg = bot.send_message(call.message.chat.id, "Введите `КОД` промокода для удаления:"); bot.register_next_step_handler(msg, admin_delpromo_step); bot.answer_callback_query(call.id)
    elif act == "broadcast":
        msg = bot.send_message(call.message.chat.id, "Введите текст для рассылки всем игрокам:"); bot.register_next_step_handler(msg, admin_broadcast_step); bot.answer_callback_query(call.id)
    elif act == "back":
        admin_panel(call.message)

def admin_give_step(message):
    if message.from_user.id not in ADMIN_IDS: return
    try:
        sid, amount = message.text.split(); amount = int(amount)
        target_uid = get_user_by_short_id(sid)
        if not target_uid: return bot.reply_to(message, "❌ Игрок не найден.")
        add_balance(target_uid, amount); bot.reply_to(message, f"✅ Выдано {amount} 🪙 игроку с ID {sid}.")
    except: bot.reply_to(message, "❌ Ошибка формата.")

def admin_setstatus_step(message):
    if message.from_user.id not in ADMIN_IDS: return
    try:
        sid, status = message.text.split()
        if status not in ["VIP", "Premium", "Ultra", "Нет"]: return bot.reply_to(message, "❌ Неверный статус.")
        target_uid = get_user_by_short_id(sid)
        if not target_uid: return bot.reply_to(message, "❌ Игрок не найден.")
        data["players"][target_uid]["donate_status"] = status; save_data()
        bot.reply_to(message, f"✅ Статус **{status}** выдан игроку ID {sid}.")
    except: bot.reply_to(message, "❌ Ошибка формата.")

def admin_reset_step(message):
    if message.from_user.id not in ADMIN_IDS: return
    try:
        sid = message.text.strip(); target_uid = get_user_by_short_id(sid)
        if not target_uid: return bot.reply_to(message, "❌ Игрок не найден.")
        data["players"][target_uid]["balance"] = 0
        data["players"][target_uid]["bank"] = 0
        data["players"][target_uid]["deposit"] = 0
        data["players"][target_uid]["deposit_start"] = 0
        save_data()
        bot.reply_to(message, f"✅ Баланс и банк игрока с ID {sid} обнулены.")
    except: bot.reply_to(message, "❌ Ошибка.")

def admin_promo_step(message):
    if message.from_user.id not in ADMIN_IDS: return
    try:
        code, amount = message.text.upper().split(); amount = int(amount)
        data["promos"][code] = amount; save_data()
        bot.reply_to(message, f"✅ Промокод {code} на {amount} 🪙 создан.")
    except: bot.reply_to(message, "❌ Ошибка формата.")

def admin_delpromo_step(message):
    if message.from_user.id not in ADMIN_IDS: return
    code = message.text.upper().strip()
    if code in data["promos"]:
        del data["promos"][code]; save_data()
        bot.reply_to(message, f"✅ Промокод {code} удален.")
    else:
        bot.reply_to(message, "❌ Не найден.")

def admin_broadcast_step(message):
    if message.from_user.id not in ADMIN_IDS: return
    text = message.text
    success = 0
    for uid in list(data["players"].keys()):
        try:
            bot.send_message(uid, text)
            success += 1
        except: pass
    bot.reply_to(message, f"✅ Рассылка отправлена {success} игрокам.")

# ==================== СТАРЫЕ АДМИН-КОМАНДЫ ====================

@bot.message_handler(commands=['wipe'])
def wipe_command(message):
    if message.from_user.id not in ADMIN_IDS: return
    global data
    data = {"players": {}, "promos": {}, "activations": [], "history": [], "clans": {}, "next_id": 1, "active_games": {}, "roulette_bets": {}, "duels": {}}
    save_data()
    bot.reply_to(message, "💥 **База данных очищена!**", parse_mode="Markdown")

@bot.message_handler(commands=['give'])
def give_command(message):
    if message.from_user.id not in ADMIN_IDS: return
    try:
        parts = message.text.split()
        target_sid = parts[1]
        amount = int(parts[2])
        target_uid = get_user_by_short_id(target_sid)
        if not target_uid: return bot.reply_to(message, f"❌ Игрок {target_sid} не найден.")
        add_balance(target_uid, amount)
        bot.reply_to(message, f"✅ Выдано {amount} 🪙 игроку {get_nick(target_uid)}.", parse_mode="Markdown")
    except: bot.reply_to(message, "❌ `/give ID СУММА`", parse_mode="Markdown")

@bot.message_handler(commands=['reset'])
def reset_user_command(message):
    if message.from_user.id not in ADMIN_IDS: return
    try:
        sid = message.text.split()[1]
        target_uid = get_user_by_short_id(sid)
        if not target_uid: return bot.reply_to(message, "❌ Игрок не найден.")
        data["players"][target_uid]["balance"] = 0
        data["players"][target_uid]["bank"] = 0
        save_data()
        bot.reply_to(message, f"✅ Игрок {sid} обнулён.")
    except: bot.reply_to(message, "❌ `/reset ID`")

@bot.message_handler(commands=['get_profile'])
def get_profile_command(message):
    if message.from_user.id not in ADMIN_IDS: return
    try:
        sid = message.text.split()[1]
        target_uid = get_user_by_short_id(sid)
        if not target_uid: return bot.reply_to(message, "❌ Не найден.")
        p = data["players"][target_uid]
        bot.reply_to(message, f"Профиль {sid}:\n{p}")
    except: bot.reply_to(message, "❌ `/get_profile ID`")

# ==================== ПРОМОКОДЫ ====================

@bot.message_handler(commands=['createpromo'])
def create_promo(message):
    if message.from_user.id not in ADMIN_IDS: return
    try:
        code, amount = message.text.split()[1:]
        data["promos"][code.upper()] = int(amount)
        save_data()
        bot.reply_to(message, f"✅ Промо {code.upper()} на {amount} создан.")
    except: bot.reply_to(message, "❌ `/createpromo КОД СУММА`")

@bot.message_handler(commands=['deletepromo'])
def delete_promo(message):
    if message.from_user.id not in ADMIN_IDS: return
    try:
        code = message.text.split()[1].upper()
        if code in data["promos"]:
            del data["promos"][code]
            save_data()
            bot.reply_to(message, f"✅ Промо {code} удалён.")
        else:
            bot.reply_to(message, "❌ Не найден.")
    except: bot.reply_to(message, "❌ `/deletepromo КОД`")

@bot.message_handler(func=lambda m: m.text and m.text.lower().startswith("промо"))
def activate_promo(message):
    uid = str(message.from_user.id)
    try:
        code = message.text.split()[1].upper()
        if code not in data["promos"]:
            return bot.reply_to(message, "❌ Промокод не найден.")
        activation_key = f"{uid}_{code}"
        if activation_key in data["activations"]:
            return bot.reply_to(message, "❌ Вы уже активировали этот промокод.")
        amount = data["promos"][code]
        add_balance(uid, amount)
        data["activations"].append(activation_key)
        save_data()
        bot.reply_to(message, f"🎉 Промокод **{code}** активирован! Вы получили {amount} 🪙.", parse_mode="Markdown")
    except:
        bot.reply_to(message, "❌ Использование: `промо КОД`")

print("BOT STARTED")
bot.infinity_polling(skip_pending=True)