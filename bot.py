import os
import random
import time
import telebot
import threading
import json
import pathlib
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, LabeledPrice, ReplyKeyboardMarkup, KeyboardButton

TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise ValueError("Не задан BOT_TOKEN")

ADMIN_IDS = [8158495271]

DATA_DIR = pathlib.Path("/app/data")
DATA_DIR.mkdir(parents=True, exist_ok=True)
DATA_FILE = DATA_DIR / "database.json"

data = {
    "players": {},
    "promos": {},
    "activations": [],
    "clans": {},
    "next_id": 1,
    "duels": {}
}
db_lock = threading.Lock()

def load_data():
    global data
    if DATA_FILE.exists():
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                for key in loaded:
                    data[key] = loaded[key]
        except Exception as e:
            print(f"Ошибка загрузки: {e}")

def save_data():
    with db_lock:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)

load_data()

bot = telebot.TeleBot(TOKEN)

def get_balance(uid):
    return data["players"].get(str(uid), {}).get("balance", 0)

def get_nick(uid):
    return data["players"].get(str(uid), {}).get("username", "Player")

def get_user_short_id(uid):
    return data["players"].get(str(uid), {}).get("short_id", 0)

def get_user_by_short_id(sid):
    for uid, pdata in data["players"].items():
        if str(pdata.get("short_id")) == str(sid):
            return uid
    return None

def get_user_by_username(uname):
    uname = uname.replace("@", "").lower()
    for uid, pdata in data["players"].items():
        if pdata.get("username", "").lower() == uname:
            return uid
    return None

def add_balance(uid, amount):
    uid = str(uid)
    if uid not in data["players"]:
        register_user_by_id(uid)
    data["players"][uid]["balance"] += amount
    save_data()

def register_user(user):
    uid = str(user.id)
    if uid not in data["players"]:
        sid = data["next_id"]
        data["next_id"] += 1
        data["players"][uid] = {
            "username": user.username or user.first_name or "Player",
            "balance": 1000,
            "last_bonus": 0,
            "short_id": sid,
            "clan_id": None,
            "bank": 0,
            "donate_status": "Нет"
        }
        save_data()

def register_user_by_id(uid):
    uid = str(uid)
    if uid not in data["players"]:
        sid = data["next_id"]
        data["next_id"] += 1
        data["players"][uid] = {
            "username": "Player",
            "balance": 1000,
            "last_bonus": 0,
            "short_id": sid,
            "clan_id": None,
            "bank": 0,
            "donate_status": "Нет"
        }
        save_data()

def get_main_keyboard():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(KeyboardButton("👤 Профиль"), KeyboardButton("💰 Баланс"))
    kb.row(KeyboardButton("🎁 Бонус"), KeyboardButton("🎮 Игры"))
    kb.row(KeyboardButton("🏦 Банк"), KeyboardButton("💎 Донат"))
    kb.row(KeyboardButton("📖 Помощь"), KeyboardButton("🏆 Топ"))
    return kb

@bot.message_handler(commands=["start"])
def start(message):
    register_user(message.from_user)
    bot.send_message(
        message.chat.id,
        f"🎮 **MON1 GAME**\n\n"
        f"Добро пожаловать, **{get_nick(message.from_user.id)}**!\n"
        f"Баланс: **{get_balance(message.from_user.id)} 🪙**\n\n"
        f"Используй кнопки внизу 👇",
        parse_mode="Markdown",
        reply_markup=get_main_keyboard()
    )

@bot.message_handler(func=lambda m: m.text and m.text.lower().strip() in ["помощь", "📖 помощь", "help"])
def help_command(message):
    text = (
        "📖 **ПОМОЩЬ**\n\n"
        "• `слот 1000` — слоты\n"
        "• `краш 1000` — краш\n"
        "• `бонус` — ежедневный бонус\n"
        "• `б` — баланс\n"
        "• `профиль` — профиль\n"
        "• `банк положить 1000`\n"
        "• `банк снять 1000`\n"
        "• `донат` — пополнение"
    )
    bot.reply_to(message, text, parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text and m.text.lower().strip() in ["б", "баланс", "💰 баланс"])
def balance_command(message):
    register_user(message.from_user)
    bot.reply_to(message, f"💰 Баланс: **{get_balance(message.from_user.id)} 🪙**", parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text and m.text.lower().strip() in ["профиль", "👤 профиль"])
def profile_command(message):
    register_user(message.from_user)
    p = data["players"][str(message.from_user.id)]
    text = (
        f"👤 **Профиль**\n"
        f"ID: `{p.get('short_id')}`\n"
        f"Ник: {p.get('username')}\n"
        f"Баланс: {p.get('balance', 0)} 🪙\n"
        f"Банк: {p.get('bank', 0)} 🪙\n"
        f"Статус: {p.get('donate_status', 'Нет')}"
    )
    bot.reply_to(message, text, parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text and m.text.lower().strip() in ["бонус", "🎁 бонус"])
def daily_bonus(message):
    uid = str(message.from_user.id)
    register_user(message.from_user)
    p = data["players"][uid]
    now = int(time.time())
    if now - p.get("last_bonus", 0) < 86400:
        left = 86400 - (now - p.get("last_bonus", 0))
        return bot.reply_to(message, f"⏳ Подожди ещё {left // 3600} ч. {(left % 3600) // 60} мин.")
    reward = random.randint(1000, 3000)
    add_balance(uid, reward)
    data["players"][uid]["last_bonus"] = now
    save_data()
    bot.reply_to(message, f"🎁 Ты получил **{reward} 🪙**!", parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text and m.text.lower().strip() in ["топ", "🏆 топ"])
def top_command(message):
    players = sorted(data["players"].items(), key=lambda x: x[1].get("balance", 0), reverse=True)[:10]
    text = "🏆 **ТОП-10**\n\n"
    for i, (uid, p) in enumerate(players, 1):
        text += f"{i}. {p.get('username', '?')} — {p.get('balance', 0)} 🪙\n"
    bot.reply_to(message, text, parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text and m.text.lower().strip() in ["игры", "🎮 игры"])
def games_menu(message):
    text = (
        "🎮 **Игры**\n\n"
        "`слот 1000` — слоты\n"
        "`краш 1000` — краш\n"
        "Просто напиши команду со ставкой."
    )
    bot.reply_to(message, text, parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text and m.text.lower().startswith("слот"))
def slot_game(message):
    uid = str(message.from_user.id)
    register_user(message.from_user)
    try:
        bet = int(message.text.split()[1])
        if bet < 10 or get_balance(uid) < bet:
            return bot.reply_to(message, "❌ Недостаточно средств или ставка меньше 10")
        add_balance(uid, -bet)
        symbols = ["🍒", "🍋", "🍊", "🍉", "⭐", "7️⃣"]
        res = [random.choice(symbols) for _ in range(3)]
        win = 0
        if res[0] == res[1] == res[2]:
            win = bet * 5
        elif res[0] == res[1] or res[1] == res[2]:
            win = bet * 2
        if win > 0:
            add_balance(uid, win)
            bot.reply_to(message, f"🎰 {' '.join(res)}\n✅ Выигрыш: **{win} 🪙**", parse_mode="Markdown")
        else:
            bot.reply_to(message, f"🎰 {' '.join(res)}\n❌ Проигрыш")
    except:
        bot.reply_to(message, "❌ Формат: `слот 1000`")

@bot.message_handler(func=lambda m: m.text and m.text.lower().startswith("краш"))
def crash_game(message):
    uid = str(message.from_user.id)
    register_user(message.from_user)
    try:
        bet = int(message.text.split()[1])
        if bet < 10 or get_balance(uid) < bet:
            return bot.reply_to(message, "❌ Недостаточно средств")
        add_balance(uid, -bet)
        mult = round(random.uniform(1.01, 4.5), 2)
        if random.random() < 0.45:
            bot.reply_to(message, f"💥 Краш на {mult}x\nТы проиграл {bet} 🪙")
        else:
            win = int(bet * mult)
            add_balance(uid, win)
            bot.reply_to(message, f"🚀 Улетел до {mult}x\nВыигрыш: **{win} 🪙**", parse_mode="Markdown")
    except:
        bot.reply_to(message, "❌ Формат: `краш 1000`")

@bot.message_handler(func=lambda m: m.text and m.text.lower().strip() in ["банк", "🏦 банк"])
def bank_info(message):
    uid = str(message.from_user.id)
    register_user(message.from_user)
    bank = data["players"][uid].get("bank", 0)
    bot.reply_to(message, f"🏦 В банке: **{bank} 🪙**\n\n`банк положить 1000`\n`банк снять 1000`", parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text and m.text.lower().startswith("банк положить"))
def bank_deposit(message):
    uid = str(message.from_user.id)
    try:
        amount = int(message.text.split()[2])
        if amount <= 0 or get_balance(uid) < amount:
            return bot.reply_to(message, "❌ Недостаточно средств")
        add_balance(uid, -amount)
        data["players"][uid]["bank"] = data["players"][uid].get("bank", 0) + amount
        save_data()
        bot.reply_to(message, f"✅ Положено {amount} 🪙")
    except:
        bot.reply_to(message, "❌ `банк положить 1000`")

@bot.message_handler(func=lambda m: m.text and m.text.lower().startswith("банк снять"))
def bank_withdraw(message):
    uid = str(message.from_user.id)
    try:
        amount = int(message.text.split()[2])
        bank = data["players"][uid].get("bank", 0)
        if amount <= 0 or bank < amount:
            return bot.reply_to(message, "❌ Недостаточно в банке")
        data["players"][uid]["bank"] -= amount
        add_balance(uid, amount)
        save_data()
        bot.reply_to(message, f"✅ Снято {amount} 🪙")
    except:
        bot.reply_to(message, "❌ `банк снять 1000`")

@bot.message_handler(func=lambda m: m.text and m.text.lower().strip() in ["донат", "💎 донат"])
def donate_menu(message):
    text = "💎 **Донат**\n1 ⭐ = 1000 🪙\n\nВыбери пакет:"
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("25 ⭐ = 25000 🪙", callback_data="donate_25"))
    kb.add(InlineKeyboardButton("50 ⭐ = 50000 🪙", callback_data="donate_50"))
    kb.add(InlineKeyboardButton("100 ⭐ = 100000 🪙", callback_data="donate_100"))
    bot.reply_to(message, text, reply_markup=kb, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data.startswith("donate_"))
def donate_callback(call):
    stars = int(call.data.split("_")[1])
    coins = stars * 1000
    prices = [LabeledPrice(label=f"{coins} монет", amount=stars)]
    try:
        bot.send_invoice(
            chat_id=call.message.chat.id,
            title=f"{coins} монет",
            description=f"Пополнение на {coins} 🪙",
            invoice_payload=f"pay_{stars}",
            provider_token="",
            currency="XTR",
            prices=prices
        )
        bot.answer_callback_query(call.id)
    except Exception as e:
        bot.answer_callback_query(call.id, str(e), show_alert=True)

@bot.pre_checkout_query_handler(func=lambda q: True)
def pre_checkout(query):
    bot.answer_pre_checkout_query(query.id, ok=True)

@bot.message_handler(content_types=["successful_payment"])
def successful_payment(message):
    payload = message.successful_payment.invoice_payload
    stars = int(payload.split("_")[1])
    coins = stars * 1000
    uid = str(message.from_user.id)
    register_user(message.from_user)
    add_balance(uid, coins)
    bot.send_message(message.chat.id, f"🎉 Получено **{coins} 🪙**!", parse_mode="Markdown")

@bot.message_handler(commands=["admin"])
def admin_panel(message):
    if message.from_user.id not in ADMIN_IDS:
        return
    total = len(data["players"])
    money = sum(p.get("balance", 0) for p in data["players"].values())
    bot.reply_to(message, f"⚙️ Админ\nИгроков: {total}\nВсего монет: {money}")

print("BOT STARTED")
bot.infinity_polling(skip_pending=True)
