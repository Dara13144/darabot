import telebot
from telebot import types
import sqlite3
import qrcode
from datetime import datetime

# === BOT CONFIG ===
BOT_TOKEN = "8477889473:AAFkWVmpErgSWFAPIKSau3gDALgM_I5RtRo"
ADMIN_ID = 5836800525  # Replace with your own Telegram ID
bot = telebot.TeleBot(BOT_TOKEN)

# === DATABASE SETUP ===
conn = sqlite3.connect("topup_bot.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute('''
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    username TEXT,
    game TEXT,
    uid TEXT,
    amount TEXT,
    payment_method TEXT,
    status TEXT,
    date TEXT
)
''')
conn.commit()

# === START ===
@bot.message_handler(commands=["start"])
def start(msg):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("🔰 Top Up", "📦 My Orders")
    markup.row("💎 View Diamond & Price", "🛠 Contact Admin")
    bot.send_message(msg.chat.id, "សូមជ្រើសរើសមុខងារ:", reply_markup=markup)

# === TOP-UP MENU ===
@bot.message_handler(func=lambda m: m.text == "🔰 Top Up")
def topup_menu(msg):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("Free Fire", callback_data="game_ff"))
    markup.add(types.InlineKeyboardButton("Mobile Legends", callback_data="game_ml"))
    bot.send_message(msg.chat.id, "🎮 ជ្រើសរើសហ្គេម:", reply_markup=markup)

# === GAME SELECT → UID ===
@bot.callback_query_handler(func=lambda call: call.data.startswith("game_"))
def ask_uid(call):
    game = call.data.split("_")[1]
    bot.send_message(call.message.chat.id, f"📥 បញ្ចូល UID សម្រាប់ {game.upper()}:")
    bot.register_next_step_handler(call.message, lambda m: ask_amount(m, game))

# === UID → AMOUNT ===
def ask_amount(msg, game):
    uid = msg.text.strip()
    bot.send_message(msg.chat.id, "💎 បញ្ចូលចំនួន Diamond ឬ Amount (e.g., 4000):")
    bot.register_next_step_handler(msg, lambda m: ask_payment_method(m, game, uid))

# === AMOUNT → PAYMENT METHOD ===
def ask_payment_method(msg, game, uid):
    amount = msg.text.strip()
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("ABA", callback_data=f"pay_ABA_{game}_{uid}_{amount}"))
    markup.add(types.InlineKeyboardButton("TrueMoney", callback_data=f"pay_TM_{game}_{uid}_{amount}"))
    bot.send_message(msg.chat.id, "📤 ជ្រើសរើសវិធីបង់ប្រាក់:", reply_markup=markup)

# === PAYMENT QR + SAVE ORDER ===
@bot.callback_query_handler(func=lambda call: call.data.startswith("pay_"))
def send_qr(call):
    method, game, uid, amount = call.data.split("_")[1:]
    qr_img = generate_qr(method)

    # Save to DB
    cursor.execute('''INSERT INTO orders (user_id, username, game, uid, amount, payment_method, status, date)
                      VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                   (call.from_user.id, call.from_user.username, game, uid, amount, method, "waiting_payment", str(datetime.now())))
    conn.commit()
    order_id = cursor.lastrowid

    with open(qr_img, "rb") as f:
        caption = (
            f"💵 សូមបង់ប្រាក់ {amount}៛ ដោយប្រើ {method.upper()} សម្រាប់ UID: {uid}\n"
            f"📨 Order ID: #{order_id}\n"
            "✅ បន្ទាប់ពីបង់ប្រាក់ សូមរង់ចាំ 1-2 នាទី។"
        )
        bot.send_photo(call.message.chat.id, f, caption=caption)

# === MANUAL SIMULATED AUTO PAYMENT ===
@bot.message_handler(commands=["paydone"])
def simulate_payment(msg):
    if msg.reply_to_message:
        try:
            order_id = int(msg.reply_to_message.text.split("#")[1])
            auto_confirm(order_id)
            bot.reply_to(msg, f"✅ Order #{order_id} confirmed (simulated).")
        except:
            bot.reply_to(msg, "⚠️ Order ID extraction failed.")
    else:
        bot.reply_to(msg, "⚠️ Please reply to a message containing order ID.")

# === AUTO CONFIRM PAYMENT FUNCTION ===
def auto_confirm(order_id):
    cursor.execute("SELECT user_id, game, uid, amount FROM orders WHERE id = ? AND status = 'waiting_payment'", (order_id,))
    order = cursor.fetchone()
    if order:
        user_id, game, uid, amount = order
        # Notify buyer
        bot.send_message(user_id, f"✅ បង់ប្រាក់ជោគជ័យ!\n🎮 {game.upper()} | UID: {uid} | {amount}៛")
        # Notify admin
        bot.send_message(ADMIN_ID, f"📢 Auto Payment Detected!\nOrder #{order_id}\n🎮 {game} | UID: {uid} | {amount}៛")
        # Update status
        cursor.execute("UPDATE orders SET status = 'paid' WHERE id = ?", (order_id,))
        conn.commit()

# === USER: MY ORDERS ===
@bot.message_handler(func=lambda m: m.text == "📦 My Orders")
def my_orders(msg):
    cursor.execute("SELECT id, game, amount, status FROM orders WHERE user_id = ? ORDER BY id DESC LIMIT 5", (msg.from_user.id,))
    orders = cursor.fetchall()
    if orders:
        text = "📋 ការកម្មង់ចុងក្រោយ:\n\n"
        for o in orders:
            text += f"#{o[0]} | {o[1]} | {o[2]}៛ | {o[3]}\n"
        bot.send_message(msg.chat.id, text)
    else:
        bot.send_message(msg.chat.id, "❌ មិនមានការកម្មង់!")

# === VIEW PRICE ===
@bot.message_handler(func=lambda m: m.text == "💎 View Diamond & Price")
def view_price(msg):
    text = "💎 *Free Fire Prices*\n100💎 = 4,000៛\n200💎 = 8,000៛\n500💎 = 20,000៛\n1000💎 = 38,000៛\n\n"
    text += "💎 *Mobile Legends Prices*\n86💎 = 4,000៛\n172💎 = 8,000៛\n514💎 = 20,000៛\n1028💎 = 39,000៛"
    bot.send_message(msg.chat.id, text, parse_mode="Markdown")

# === ADMIN CONTACT ===
@bot.message_handler(func=lambda m: m.text == "🛠 Contact Admin")
def contact_admin(msg):
    bot.send_message(msg.chat.id, "📞 Telegram Admin: @YourAdminUsername")

# === QR GENERATOR ===
def generate_qr(method):
    data = "https://aba.bank" if method == "ABA" else "https://truemoney.com.kh"
    img = qrcode.make(data)
    path = f"{method}_qr.png"
    img.save(path)
    return path

# === START BOT ===
print("🤖 Telegram Bot is running with Auto Payment system.")
bot.infinity_polling()
