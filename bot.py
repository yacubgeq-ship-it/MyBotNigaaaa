import os, random, math, time, telebot, threading, json, pathlib
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, LabeledPrice, ReplyKeyboardMarkup, KeyboardButton

TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN: raise ValueError("Не задан BOT_TOKEN")

ADMIN_IDS = [8158495271]   # твой ID

DATA_DIR = pathlib.Path("/app/data")
DATA_DIR.mkdir(parents=True, exist_ok=True)
DATA_FILE = DATA_DIR / "database.json"

data = {
    "players": {}, 
    "promos": {}, 
    "activations": [], 
    "history": [], 
    "clans": {}, 
    "next_id": 1, 
    "active_games": {}, 
    "roulette_bets": {}, 
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
            print(f"⚠️ Ошибка загрузки: {e}")

def save_data():
    with db_lock:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)

load_data()

def migrate_data():
    global data
    changed = False
    current_max = max([p.get("short_id", 0) for p in data["players"].values() if isinstance(p.get("short_id"), int)], default=0)
    if data.get("next_id", 1) <= current_max:
        data["next_id"] = current_max + 1
    for uid, pdata in data["players"].items():
        if "short_id" not in pdata or pdata["short_id"] == 0:
            pdata["short_id"] = data["next_id"]
            data["next_id"] += 1
            changed = True
        if "bank" not in pdata:
            pdata["bank"] = 0
            pdata["deposit"] = 0
            pdata["deposit_start"] = 0
            changed = True
        if "biz_territory" not in pdata:
            pdata["biz_territory"] = 0
            pdata["biz_building"] = 1
            pdata["biz_tax"] = 0
            pdata["biz_last_collect"] = int(time.time())
            changed = True
        if "title" not in pdata:
            pdata["title"] = "Нет"
            changed = True
        if "quests" not in pdata:
            pdata["quests"] = {}
            changed = True
        if "donate_status" not in pdata:
            pdata["donate_status"] = "Нет"
            changed = True
        if "last_bonus" not in pdata:
            pdata["last_bonus"] = 0
            changed = True
    if "roulette_bets" not in data:
        data["roulette_bets"] = {}
    if "duels" not in data:
        data["duels"] = {}
    if "promos" not in data:
        data["promos"] = {}
    if "activations" not in data:
        data["activations"] = []
    if changed:
        save_data()

migrate_data()
bot = telebot.TeleBot(TOKEN)

MULT = {3: 1.15, 5: 1.25, 9: 1.45}
BIZ_TERRITORY_COST = {0: 10000, 1: 50000, 2: 250000, 3: 1000000, 4: 5000000, 5: 25000000}
BIZ_BUILDING_COST = {1: 20000, 2: 100000, 3: 500000, 4: 2000000, 5: 10000000}

def get_balance(uid):
    return data["players"].get(str(uid), {}).get("balance", 0)

def get_nick(uid):
    return data["players"].get(str(uid), {}).get("username", "Player")

def get_user_short_id(uid):
    return data["players"].get(str(uid), {}).get("short_id", "0")

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

def get_win_multiplier(uid):
    status = data["players"].get(str(uid), {}).get("donate_status", "Нет")
    if status == "VIP":
        return 1.05
    if status == "Premium":
        return 1.15
    if status == "Ultra":
        return 1.25
    return 1.0

def add_balance(uid, amt):
    uid = str(uid)
    if uid not in data["players"]:
        register_user_by_id(uid)
    data["players"][uid]["balance"] += amt
    save_data()

def register_user(user):
    uid = str(user.id)
    if uid not in data["players"]:
        sid = data["next_id"]
        data["next_id"] += 1
        data["players"][uid] = {
            "username": user.username or user.first_name,
            "balance": 1000,
            "last_bonus": 0,
            "short_id": sid,
            "clan_id": None,
            "role": "none",
            "bank": 0,
            "deposit": 0,
            "deposit_start": 0,
            "biz_territory": 0,
            "biz_building": 1,
            "biz_tax": 0,
            "biz_last_collect": int(time.time()),
            "title": "Нет",
            "quests": {},
            "donate_status": "Нет"
        }
        save_data()

def register_user_by_id(uid):
    if uid not in data["players"]:
        sid = data["next_id"]
        data["next_id"] += 1
        data["players"][uid] = {
            "username": "Player",
            "balance": 1000,
            "last_bonus": 0,
            "short_id": sid,
            "clan_id": None,
            "role": "none",
            "bank": 0,
            "deposit": 0,
            "deposit_start": 0,
            "biz_territory": 0,
            "biz_building": 1,
            "biz_tax": 0,
            "biz_last_collect": int(time.time()),
            "title": "Нет",
            "quests": {},
            "donate_status": "Нет"
        }
        save_data()

# ==================== ГЛАВНОЕ МЕНЮ ====================

def get_main_keyboard():
    kb = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    kb.row(KeyboardButton("👤 Профиль"), KeyboardButton("💰 Баланс"))
    kb.row(KeyboardButton("🎁 Бонус"), KeyboardButton("🎮 Игры"))
    kb.row(KeyboardButton("🛡 Кланы"), KeyboardButton("💎 Донат"))
    kb.row(KeyboardButton("🏦 Банк"), KeyboardButton("🏢 Бизнес"))
    kb.row(KeyboardButton("📖 Помощь"), KeyboardButton("🏆 Топ"))
    return kb

# ==================== СТАРТ ====================

@bot.message_handler(commands=["start"])
def start(message):
    register_user(message.from_user)
    bot.send_message(
        message.chat.id,
        f"🎮 **MON1 GAME RPG** 🎮\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 Добро пожаловать, **{get_nick(message.from_user.id)}**!\n\n"
        f"💰 Ваш баланс: **{get_balance(message.from_user.id)} 🪙**\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"Используй кнопки внизу 👇",
        parse_mode="Markdown",
        reply_markup=get_main_keyboard()
        )
    @bot.message_handler(commands=['help'])
@bot.message_handler(func=lambda m: m.text and m.text.lower().strip() in ['помощь', 'help', '📖 помощь'])
def help_command(message):
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(InlineKeyboardButton("🎮 Игры", callback_data="help_games"), InlineKeyboardButton("💼 Экономика", callback_data="help_eco"))
    kb.add(InlineKeyboardButton("🛡 Кланы", callback_data="help_clans"), InlineKeyboardButton("💎 Донат", callback_data="help_donate"))
    bot.reply_to(message, "📖 **МЕНЮ ПОМОЩИ**\n━━━━━━━━━━━━━━━━━━━━\nВыберите раздел:", reply_markup=kb, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data.startswith("help_"))
def help_callbacks(call):
    section = call.data.split("_")[1]
    if section == "games":
        text = "🎮 **ИГРЫ**\n━━━━━━━━━━━━━━━━━━━━\n• `слот 1000`\n• `мины 1000 5`\n• `краш 1000`\n• `джокер 1000`\n• `1000 5 красное` + `го`\n• `дуэль @ник 1000`"
    elif section == "eco":
        text = "💼 **ЭКОНОМИКА**\n━━━━━━━━━━━━━━━━━━━━\n• `б` — баланс\n• `бонус`\n• `профиль`\n• `топ`\n• `банк`\n• `мой бизнес`\n• `перевод 1000 ник`"
    elif section == "clans":
        text = "🛡 **КЛАНЫ**\n━━━━━━━━━━━━━━━━━━━━\n• `создать клан ИМЯ`\n• `вступить клан ID`\n• `мой клан`\n• `топ кланов`"
    elif section == "donate":
        text = "💎 **ДОНАТ**\n━━━━━━━━━━━━━━━━━━━━\n• `донат`\n• `донат статус`\n• `мой статус`"
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=call.message.reply_markup, parse_mode="Markdown")
    bot.answer_callback_query(call.id)

@bot.message_handler(func=lambda m: m.text and m.text.lower().strip() in ['игры', '🎮 игры'])
def games_menu(message):
    text = (
        "🎮 **ИГРЫ**\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "• `слот 1000` — слоты\n"
        "• `мины 1000 5` — мины\n"
        "• `краш 1000` — краш\n"
        "• `джокер 1000` — джокер\n"
        "• `1000 5 красное` — рулетка (потом `го`)\n"
        "• `дуэль @ник 1000` — КНБ\n"
        "━━━━━━━━━━━━━━━━━━━━"
    )
    bot.reply_to(message, text, parse_mode="Markdown")

# ==================== БОНУС ====================

@bot.message_handler(func=lambda m: m.text and m.text.lower().strip() in ['бонус', '🎁 бонус'])
def daily_bonus(message):
    uid = str(message.from_user.id)
    if uid not in data["players"]:
        register_user(message.from_user)
    p = data["players"][uid]
    now = int(time.time())
    last = p.get("last_bonus", 0)
    if now - last < 86400:
        left = 86400 - (now - last)
        return bot.reply_to(message, f"⏳ Следующий бонус через **{left // 3600} ч. {(left % 3600) // 60} мин.**", parse_mode="Markdown")
    reward = random.randint(1000, 3000)
    add_balance(uid, reward)
    data["players"][uid]["last_bonus"] = now
    save_data()
    bot.reply_to(message, f"🎁 **ЕЖЕДНЕВНЫЙ БОНУС**\n━━━━━━━━━━━━━━━━━━━━\nВы получили: **{reward} 🪙**", parse_mode="Markdown")

# ==================== ДОНАТ ====================

@bot.message_handler(commands=['donate'])
@bot.message_handler(func=lambda m: m.text and m.text.lower().strip() in ['донат', '💎 донат'])
def donate_menu(message):
    text = "💎 **ПОПОЛНЕНИЕ**\n━━━━━━━━━━━━━━━━━━━━\n1 ⭐ = 1000 🪙\n\nВыберите пакет:"
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton("25 ⭐ = 25000 🪙", callback_data="donate_pack_25"))
    kb.add(InlineKeyboardButton("50 ⭐ = 50000 🪙", callback_data="donate_pack_50"))
    kb.add(InlineKeyboardButton("100 ⭐ = 100000 🪙", callback_data="donate_pack_100"))
    kb.add(InlineKeyboardButton("✏️ Своя сумма", callback_data="donate_custom"))
    bot.reply_to(message, text, reply_markup=kb, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data.startswith("donate_"))
def donate_process(call):
    if call.data == "donate_custom":
        msg = bot.send_message(call.message.chat.id, "✏️ Введите количество звёзд (1–10000):")
        bot.register_next_step_handler(msg, process_custom_stars)
        return
    stars = int(call.data.split("_")[2])
    coins = stars * 1000
    prices = [LabeledPrice(label=f"{coins} монет", amount=stars)]
    try:
        bot.send_invoice(
            chat_id=call.message.chat.id,
            title=f"Покупка {coins} монет",
            description=f"Вы получите {coins} монет",
            invoice_payload=f"pay_{stars}",
            provider_token="",
            currency="XTR",
            prices=prices
        )
        bot.answer_callback_query(call.id, "✅ Счёт выставлен")
    except Exception as e:
        bot.answer_callback_query(call.id, f"Ошибка: {e}", show_alert=True)

def process_custom_stars(message):
    try:
        stars = int(message.text)
        if stars < 1 or stars > 10000:
            return bot.reply_to(message, "❌ От 1 до 10000 звёзд")
        coins = stars * 1000
        prices = [LabeledPrice(label=f"{coins} монет", amount=stars)]
        bot.send_invoice(
            chat_id=message.chat.id,
            title=f"Покупка {coins} монет",
            description=f"Вы получите {coins} монет",
            invoice_payload=f"pay_{stars}",
            provider_token="",
            currency="XTR",
            prices=prices
        )
    except:
        bot.reply_to(message, "❌ Введите число")

@bot.pre_checkout_query_handler(func=lambda query: True)
def process_pre_checkout_query(pre_checkout_query):
    bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)

@bot.message_handler(content_types=['successful_payment'])
def got_payment(message):
    payload = message.successful_payment.invoice_payload
    uid = str(message.from_user.id)
    if uid not in data["players"]:
        register_user(message.from_user)

    if payload.startswith("status_"):
        status = payload.split("_")[1]
        data["players"][uid]["donate_status"] = status
        save_data()
        bot.send_message(message.chat.id, f"🎉 Вы получили статус **{status}**!", parse_mode="Markdown")
        return

    stars = int(payload.split("_")[1])
    coins = stars * 1000
    add_balance(uid, coins)

    current = data["players"][uid].get("donate_status", "Нет")
    if stars >= 750 and current != "Ultra":
        data["players"][uid]["donate_status"] = "Ultra"
        bot.send_message(message.chat.id, f"🎉 Получено **{coins} 🪙** + статус **Ultra**!", parse_mode="Markdown")
    elif stars >= 450 and current not in ["Premium", "Ultra"]:
        data["players"][uid]["donate_status"] = "Premium"
        bot.send_message(message.chat.id, f"🎉 Получено **{coins} 🪙** + статус **Premium**!", parse_mode="Markdown")
    elif stars >= 200 and current not in ["VIP", "Premium", "Ultra"]:
        data["players"][uid]["donate_status"] = "VIP"
        bot.send_message(message.chat.id, f"🎉 Получено **{coins} 🪙** + статус **VIP**!", parse_mode="Markdown")
    else:
        bot.send_message(message.chat.id, f"🎉 Получено **{coins} 🪙**", parse_mode="Markdown")
    save_data()

@bot.message_handler(func=lambda m: m.text and m.text.lower().strip() == "мой статус")
def my_status(message):
    uid = str(message.from_user.id)
    status = data["players"].get(uid, {}).get("donate_status", "Нет")
    bot.reply_to(message, f"💎 Ваш статус: **{status}**", parse_mode="Markdown")

# ==================== БАЗОВЫЕ КОМАНДЫ ====================

@bot.message_handler(func=lambda m: m.text and m.text.lower().strip() in ['б', 'баланс', '💰 баланс'])
def balance_command(message):
    uid = str(message.from_user.id)
    if uid not in data["players"]:
        register_user(message.from_user)
    bot.reply_to(message, f"💰 **БАЛАНС**\n━━━━━━━━━━━━━━━━━━━━\n{get_balance(uid)} 🪙", parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text and m.text.lower().strip() in ['профиль', '👤 профиль'])
def profile_command(message):
    uid = str(message.from_user.id)
    if uid not in data["players"]:
        register_user(message.from_user)
    p = data["players"][uid]
    clan_name = "Нет"
    if p.get("clan_id"):
        clan = data["clans"].get(str(p["clan_id"]))
        if clan:
            clan_name = clan.get("name", "Нет")
    text = (
        f"👤 **ПРОФИЛЬ**\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🆔 ID: `{p.get('short_id')}`\n"
        f"👤 Ник: {p.get('username')}\n"
        f"💎 Статус: {p.get('donate_status', 'Нет')}\n"
        f"💰 Баланс: {p.get('balance', 0)} 🪙\n"
        f"🏦 Банк: {p.get('bank', 0)} 🪙\n"
        f"🛡 Клан: {clan_name}"
    )
    bot.reply_to(message, text, parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text and m.text.lower().strip() in ["топ", "топ игроков", "🏆 топ"])
def top_cmd(message):
    sp = sorted(data["players"].items(), key=lambda x: x[1].get("balance", 0), reverse=True)[:10]
    text = "🏆 **ТОП-10**\n━━━━━━━━━━━━━━━━━━━━\n"
    for i, (u, p) in enumerate(sp, 1):
        text += f"{i}. {p.get('username', '?')} — {p.get('balance', 0)} 🪙\n"
    bot.reply_to(message, text, parse_mode="Markdown")
    # ==================== ДУЭЛИ ====================

RPS_MAP = {
    "камень": "🪨", "ножницы": "✂️", "бумага": "📄",
    "к": "🪨", "н": "✂️"
}
RPS_CHOICES = {
    "камень": "камень", "ножницы": "ножницы", "бумага": "бумага",
    "к": "камень", "н": "ножницы"
}

def rps_winner(c1, c2):
    if c1 == c2:
        return 0
    wins = {"камень": "ножницы", "ножницы": "бумага", "бумага": "камень"}
    return 1 if wins[c1] == c2 else 2

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
    if not c1 or not c2:
        return
    amount = duel["amount"]
    pot = amount * 2
    ch = duel["challenger"]
    op = duel["opponent"]
    result = rps_winner(c1, c2)
    emoji1 = RPS_MAP.get(c1, c1)
    emoji2 = RPS_MAP.get(c2, c2)

    if result == 0:
        add_balance(ch, amount)
        add_balance(op, amount)
        duel["status"] = "draw"
        save_data()
        text = f"⚔️ **НИЧЬЯ**\n{get_nick(ch)}: {emoji1}\n{get_nick(op)}: {emoji2}\nСтавки возвращены."
    else:
        if result == 1:
            winner, loser = ch, op
            w_choice, l_choice = c1, c2
            w_emoji, l_emoji = emoji1, emoji2
        else:
            winner, loser = op, ch
            w_choice, l_choice = c2, c1
            w_emoji, l_emoji = emoji2, emoji1
        add_balance(winner, pot)
        duel["status"] = "finished"
        save_data()
        text = f"⚔️ **ПОБЕДА**\n🏆 {get_nick(winner)}: {w_emoji}\n💀 {get_nick(loser)}: {l_emoji}\n💰 Банк: {pot} 🪙"

    try:
        bot.send_message(int(ch), text, parse_mode="Markdown")
        bot.send_message(int(op), text, parse_mode="Markdown")
    except:
        pass

def send_choice_buttons(uid, duel_id):
    kb = InlineKeyboardMarkup(row_width=3)
    kb.add(
        InlineKeyboardButton("🪨 Камень", callback_data=f"rps_{duel_id}_камень"),
        InlineKeyboardButton("✂️ Ножницы", callback_data=f"rps_{duel_id}_ножницы"),
        InlineKeyboardButton("📄 Бумага", callback_data=f"rps_{duel_id}_бумага")
    )
    try:
        bot.send_message(int(uid), "⚔️ Выбери ход:", reply_markup=kb)
    except:
        pass

@bot.message_handler(func=lambda m: m.text and m.text.lower().startswith("дуэль "))
def duel_challenge(message):
    uid = str(message.from_user.id)
    if uid not in data["players"]:
        register_user(message.from_user)
    parts = message.text.split()
    if len(parts) < 3:
        return bot.reply_to(message, "❌ Формат: `дуэль @ник 1000`")
    try:
        amount = int(parts[-1])
        if amount < 100:
            return bot.reply_to(message, "❌ Минимум 100 🪙")
        if get_balance(uid) < amount:
            return bot.reply_to(message, "❌ Недостаточно средств")
        target_raw = parts[1]
        if target_raw.startswith("@"):
            target_uid = get_user_by_username(target_raw)
        else:
            target_uid = get_user_by_short_id(target_raw)
        if not target_uid or str(target_uid) == uid:
            return bot.reply_to(message, "❌ Игрок не найден")
        duel_id = str(int(time.time() * 1000))
        data["duels"][duel_id] = {
            "challenger": uid,
            "opponent": str(target_uid),
            "amount": amount,
            "status": "pending",
            "choice1": None,
            "choice2": None
        }
        save_data()
        kb = InlineKeyboardMarkup()
        kb.add(
            InlineKeyboardButton("✅ Принять", callback_data=f"duel_accept_{duel_id}"),
            InlineKeyboardButton("❌ Отклонить", callback_data=f"duel_reject_{duel_id}")
        )
        try:
            bot.send_message(
                int(target_uid),
                f"⚔️ **Вызов на дуэль**\nОт: **{get_nick(uid)}**\nСтавка: **{amount} 🪙**",
                reply_markup=kb,
                parse_mode="Markdown"
            )
            bot.reply_to(message, f"✅ Вызов отправлен игроку {get_nick(target_uid)}")
        except:
            del data["duels"][duel_id]
            save_data()
            bot.reply_to(message, "❌ Не удалось отправить вызов")
    except:
        bot.reply_to(message, "❌ Ошибка формата")

@bot.message_handler(func=lambda m: m.text and m.text.lower().strip() in ["принять", "accept"])
def duel_accept_text(message):
    uid = str(message.from_user.id)
    duel_id, duel = find_pending_duel_for(uid)
    if not duel:
        return bot.reply_to(message, "❌ Нет входящих вызовов")
    amount = duel["amount"]
    if get_balance(duel["challenger"]) < amount or get_balance(uid) < amount:
        duel["status"] = "cancelled"
        save_data()
        return bot.reply_to(message, "❌ Недостаточно средств")
    add_balance(duel["challenger"], -amount)
    add_balance(uid, -amount)
    duel["status"] = "choosing"
    save_data()
    bot.reply_to(message, "✅ Дуэль принята!")
    send_choice_buttons(duel["challenger"], duel_id)
    send_choice_buttons(uid, duel_id)

@bot.callback_query_handler(func=lambda call: call.data.startswith("duel_"))
def duel_callback(call):
    parts = call.data.split("_")
    action = parts[1]
    duel_id = parts[2]
    if duel_id not in data["duels"]:
        return bot.answer_callback_query(call.id, "Дуэль не найдена")
    duel = data["duels"][duel_id]
    uid = str(call.from_user.id)
    if action == "accept":
        if duel["opponent"] != uid or duel["status"] != "pending":
            return bot.answer_callback_query(call.id, "Нельзя")
        amount = duel["amount"]
        add_balance(duel["challenger"], -amount)
        add_balance(uid, -amount)
        duel["status"] = "choosing"
        save_data()
        bot.answer_callback_query(call.id, "Принято")
        send_choice_buttons(duel["challenger"], duel_id)
        send_choice_buttons(uid, duel_id)
    elif action == "reject":
        duel["status"] = "rejected"
        save_data()
        bot.answer_callback_query(call.id, "Отклонено")

@bot.callback_query_handler(func=lambda call: call.data.startswith("rps_"))
def rps_choice_callback(call):
    parts = call.data.split("_")
    duel_id = parts[1]
    choice = parts[2]
    uid = str(call.from_user.id)
    if duel_id not in data["duels"]:
        return
    duel = data["duels"][duel_id]
    if duel["status"] != "choosing":
        return
    if uid == duel["challenger"]:
        duel["choice1"] = choice
    elif uid == duel["opponent"]:
        duel["choice2"] = choice
    else:
        return
    save_data()
    bot.answer_callback_query(call.id, f"Выбрано: {choice}")
    if duel.get("choice1") and duel.get("choice2"):
        resolve_rps_duel(duel_id, duel)

# ==================== АДМИН ====================

@bot.message_handler(commands=['admin'])
@bot.message_handler(func=lambda m: m.text and m.text.lower().strip() in ['админ', 'админка'])
def admin_panel(message):
    if message.from_user.id not in ADMIN_IDS:
        return
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("📊 Статистика", callback_data="adm_stats"),
        InlineKeyboardButton("💰 Выдать", callback_data="adm_give")
    )
    bot.reply_to(message, "⚙️ **АДМИН-ПАНЕЛЬ**", reply_markup=kb, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data.startswith("adm_"))
def admin_callbacks(call):
    if call.from_user.id not in ADMIN_IDS:
        return
    act = call.data.split("_")[1]
    if act == "stats":
        total = len(data["players"])
        money = sum(p.get("balance", 0) for p in data["players"].values())
        text = f"📊 Игроков: {total}\n💰 Общий баланс: {money} 🪙"
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="Markdown")
    elif act == "give":
        msg = bot.send_message(call.message.chat.id, "Введите: `ID СУММА`")
        bot.register_next_step_handler(msg, admin_give_step)

def admin_give_step(message):
    if message.from_user.id not in ADMIN_IDS:
        return
    try:
        sid, amount = message.text.split()
        amount = int(amount)
        target = get_user_by_short_id(sid)
        if not target:
            return bot.reply_to(message, "❌ Игрок не найден")
        add_balance(target, amount)
        bot.reply_to(message, f"✅ Выдано {amount} 🪙")
    except:
        bot.reply_to(message, "❌ Ошибка")
        # ==================== ИГРЫ (основные) ====================

@bot.message_handler(func=lambda m: m.text and m.text.lower().startswith("слот"))
def slot_machine(message):
    uid = str(message.from_user.id)
    try:
        bet = int(message.text.split()[1])
        if bet <= 0 or get_balance(uid) < bet:
            return bot.reply_to(message, "❌ Недостаточно средств")
        add_balance(uid, -bet)
        symbols = ["🍒", "🍋", "🍊", "🍉", "⭐", "7️⃣"]
        result = [random.choice(symbols) for _ in range(3)]
        win = 0
        if result[0] == result[1] == result[2]:
            win = bet * 5
        elif result[0] == result[1] or result[1] == result[2]:
            win = bet * 2
        if win > 0:
            win = int(win * get_win_multiplier(uid))
            add_balance(uid, win)
            bot.reply_to(message, f"🎰 {' '.join(result)}\n✅ Выигрыш: **{win} 🪙**", parse_mode="Markdown")
        else:
            bot.reply_to(message, f"🎰 {' '.join(result)}\n❌ Ничего")
    except:
        bot.reply_to(message, "❌ Формат: `слот 1000`")

@bot.message_handler(func=lambda m: m.text and m.text.lower().startswith("краш"))
def start_crash(message):
    uid = str(message.from_user.id)
    try:
        bet = int(message.text.split()[1])
        if bet <= 0 or get_balance(uid) < bet:
            return bot.reply_to(message, "❌ Недостаточно средств")
        add_balance(uid, -bet)
        multiplier = round(random.uniform(1.0, 5.0), 2)
        if random.random() < 0.4:  # шанс краша
            bot.reply_to(message, f"💥 Краш на **{multiplier}x**\nВы проиграли {bet} 🪙")
        else:
            win = int(bet * multiplier * get_win_multiplier(uid))
            add_balance(uid, win)
            bot.reply_to(message, f"🚀 Улетел до **{multiplier}x**\nВыигрыш: **{win} 🪙**", parse_mode="Markdown")
    except:
        bot.reply_to(message, "❌ Формат: `краш 1000`")

# ==================== БАНК ====================

@bot.message_handler(func=lambda m: m.text and m.text.lower().strip() in ["банк", "🏦 банк"])
def bank_info(message):
    uid = str(message.from_user.id)
    if uid not in data["players"]:
        register_user(message.from_user)
    p = data["players"][uid]
    text = (
        f"🏦 **БАНК**\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"💰 На счету: {p.get('bank', 0)} 🪙\n"
        f"💎 Депозит: {p.get('deposit', 0)} 🪙\n\n"
        f"`банк положить 1000`\n"
        f"`банк снять 1000`"
    )
    bot.reply_to(message, text, parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text and m.text.lower().startswith("банк положить"))
def bank_dep(message):
    uid = str(message.from_user.id)
    try:
        amount = int(message.text.split()[2])
        if amount <= 0 or get_balance(uid) < amount:
            return bot.reply_to(message, "❌ Недостаточно средств")
        add_balance(uid, -amount)
        data["players"][uid]["bank"] = data["players"][uid].get("bank", 0) + amount
        save_data()
        bot.reply_to(message, f"✅ Положено {amount} 🪙 в банк")
    except:
        bot.reply_to(message, "❌ `банк положить 1000`")

@bot.message_handler(func=lambda m: m.text and m.text.lower().startswith("банк снять"))
def bank_wd(message):
    uid = str(message.from_user.id)
    try:
        amount = int(message.text.split()[2])
        bank = data["players"][uid].get("bank", 0)
        if amount <= 0 or bank < amount:
            return bot.reply_to(message, "❌ Недостаточно в банке")
        data["players"][uid]["bank"] -= amount
        add_balance(uid, amount)
        save_data()
        bot.reply_to(message, f"✅ Снято {amount} 🪙 из банка")
    except:
        bot.reply_to(message, "❌ `банк снять 1000`")

# ==================== БИЗНЕС ====================

@bot.message_handler(func=lambda m: m.text and m.text.lower().strip() in ["мой бизнес", "🏢 бизнес", "бизнес"])
def my_business(message):
    uid = str(message.from_user.id)
    if uid not in data["players"]:
        register_user(message.from_user)
    p = data["players"][uid]
    t = p.get("biz_territory", 0)
    if t == 0:
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("🏗 Построить (10000 🪙)", callback_data="biz_build"))
        return bot.reply_to(message, "🏢 У вас нет бизнеса.", reply_markup=kb)
    text = f"🏢 **Бизнес**\nТерритория: {t} м²\nЗдание: ур. {p.get('biz_building', 1)}"
    bot.reply_to(message, text, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data == "biz_build")
def biz_build(call):
    uid = str(call.from_user.id)
    cost = 10000
    if get_balance(uid) < cost:
        return bot.answer_callback_query(call.id, "Недостаточно средств", show_alert=True)
    add_balance(uid, -cost)
    data["players"][uid]["biz_territory"] = 1
    data["players"][uid]["biz_building"] = 1
    save_data()
    bot.answer_callback_query(call.id, "Бизнес построен!")
    bot.edit_message_text("🏢 Бизнес успешно построен!", call.message.chat.id, call.message.message_id)

# ==================== КЛАНЫ (базовые) ====================

@bot.message_handler(func=lambda m: m.text and m.text.lower().strip() in ["мой клан", "🛡 кланы", "кланы"])
def my_clan_info(message):
    uid = str(message.from_user.id)
    p = data["players"].get(uid, {})
    if not p.get("clan_id"):
        return bot.reply_to(message, "❌ Вы не состоите в клане.\nСоздать: `создать клан Название`")
    clan = data["clans"].get(str(p["clan_id"]))
    if not clan:
        return bot.reply_to(message, "❌ Клан не найден")
    text = f"🛡 **Клан: {clan.get('name')}**\nКазна: {clan.get('treasury', 0)} 🪙"
    bot.reply_to(message, text, parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text and m.text.lower().startswith("создать клан"))
def create_clan(message):
    uid = str(message.from_user.id)
    if uid not in data["players"]:
        register_user(message.from_user)
    p = data["players"][uid]
    if p.get("clan_id"):
        return bot.reply_to(message, "❌ Вы уже в клане")
    cost = 10000
    if get_balance(uid) < cost:
        return bot.reply_to(message, f"❌ Нужно {cost} 🪙")
    try:
        name = message.text[12:].strip()
        if len(name) < 3:
            return bot.reply_to(message, "❌ Название слишком короткое")
        add_balance(uid, -cost)
        clan_id = str(data.get("next_id", 1))
        data["clans"][clan_id] = {
            "name": name,
            "owner_id": uid,
            "treasury": 0,
            "members": [uid]
        }
        p["clan_id"] = clan_id
        p["role"] = "создатель"
        save_data()
        bot.reply_to(message, f"✅ Клан **{name}** создан!\nID: `{clan_id}`", parse_mode="Markdown")
    except:
        bot.reply_to(message, "❌ `создать клан Название`")

# ==================== ЗАПУСК ====================

print("BOT STARTED")
bot.infinity_polling(skip_pending=True)
