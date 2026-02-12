import telebot, sqlite3, requests, time, hmac, hashlib
from telebot import types
from flask import Flask
from threading import Thread
import os

# --- KEEP ALIVE SERVER ---
app = Flask('')

@app.route('/')
def home():
    return "Bot is running 24/7!"

def run():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.start()

# --- BOT LOGIC ---
TOKEN = "8011067020:AAEUVoevMaKiUNMv_HMZRLnWyAL6gYrU7IQ"
bot = telebot.TeleBot(TOKEN)

ADMIN_ID = 6650340402 

BIN_KEY = "TI1gPHBFK0XEblbS9wzBpLswG4V2CEDbxySNrAjdrW5rWUyDsl0Vxao24drHByTq"
BIN_SECRET = "Pu69cI4dep7y1KLRwrekEQeknCPV50uNIwlLlBNHmIxg7JIEREtyiFvwrIi2V7N7"

def init_db():
    conn = sqlite3.connect("bingo.db")
    cur = conn.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS users (uid INTEGER PRIMARY KEY, balance REAL)")
    cur.execute("CREATE TABLE IF NOT EXISTS tx (txid TEXT PRIMARY KEY)")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS rooms (
            lobby_id INTEGER, 
            room_no INTEGER, 
            player_count INTEGER DEFAULT 0,
            PRIMARY KEY (lobby_id, room_no)
        )
    """)
    for l in range(1, 5):
        for r in range(1, 101):
            cur.execute("INSERT OR IGNORE INTO rooms (lobby_id, room_no, player_count) VALUES (?, ?, 0)", (l, r))
    conn.commit()
    conn.close()

def get_actual_bal(uid):
    conn = sqlite3.connect("bingo.db")
    cur = conn.cursor()
    cur.execute("SELECT balance FROM users WHERE uid=?", (uid,))
    res = cur.fetchone()
    conn.close()
    return res[0] if res else 0.0

def update_bal(uid, amount):
    conn = sqlite3.connect("bingo.db")
    cur = conn.cursor()
    cur.execute("INSERT OR IGNORE INTO users (uid, balance) VALUES (?, 0.0)", (uid,))
    cur.execute("UPDATE users SET balance = balance + ? WHERE uid = ?", (amount, uid))
    conn.commit()
    conn.close()

# --- NEW: LOBBY & ROOM SELECTION LOGIC ---

@bot.message_handler(func=lambda m: m.text == "🎮 Play Bingo")
def lobby_menu(message):
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("Lobby 1 (0.1 - 1 USDT)", callback_data="lobby_1"),
        types.InlineKeyboardButton("Lobby 2 (1 - 5 USDT)", callback_data="lobby_2"),
        types.InlineKeyboardButton("Lobby 3 (5 - 10 USDT)", callback_data="lobby_3"),
        types.InlineKeyboardButton("Lobby 4 (High Stakes)", callback_data="lobby_4")
    )
    bot.send_message(message.chat.id, "🏟 **Select a Lobby:**", reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data.startswith("lobby_"))
def show_rooms(call):
    lobby_id = int(call.data.split("_")[1])
    conn = sqlite3.connect("bingo.db")
    cur = conn.cursor()
    # Find rooms in this lobby that have players or are next in line
    cur.execute("SELECT room_no, player_count FROM rooms WHERE lobby_id=? AND player_count < 25 LIMIT 10", (lobby_id,))
    rooms = cur.fetchall()
    conn.close()

    markup = types.InlineKeyboardMarkup(row_width=2)
    for r_no, count in rooms:
        status = "🟢" if 10 <= count < 25 else "🟡"
        btn_text = f"Room #{r_no} ({count}/25) {status}"
        # When clicked, this will launch the WebApp for that specific room
        game_url = f"https://fikeresilasek-design.github.io/addis-bingo/?lobby={lobby_id}&room={r_no}"
        markup.add(types.InlineKeyboardButton(btn_text, web_app=types.WebAppInfo(url=game_url)))

    bot.edit_message_text(f"📍 **Lobby {lobby_id} - Select a Room:**\n(Min 10 players to start)", 
                          call.message.chat.id, call.message.message_id, 
                          reply_markup=markup, parse_mode="Markdown")

# --- STANDARD BOT HANDLERS ---

@bot.message_handler(commands=['start'])
def start(message):
    bal = get_actual_bal(message.chat.id)
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton(text="🎮 Play Bingo"))
    markup.row(types.KeyboardButton(text="💰 Balance"), types.KeyboardButton(text="📥 Deposit"))
    markup.row(types.KeyboardButton(text="📤 Withdraw"), types.KeyboardButton(text="👥 Invite"))
    markup.add(types.KeyboardButton(text="👨‍💻 Support Team"))

    welcome_text = f"🌍 **Welcome to World Bingo!**\n\n💰 Your Balance: {bal} USDT"
    bot.send_message(message.chat.id, welcome_text, parse_mode="Markdown", reply_markup=markup)

# [Remaining Deposit/Withdraw/Invite handlers stay the same as previous version...]

@bot.message_handler(func=lambda m: m.text == "💰 Balance")
def show_balance(message):
    bal = get_actual_bal(message.chat.id)
    bot.send_message(message.chat.id, f"💵 Your Current Balance:\n\n💰 {bal} USDT", parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "📥 Deposit")
def dep_m(message):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("Polygon", callback_data="d_poly"), 
               types.InlineKeyboardButton("BEP20", callback_data="d_bep"), 
               types.InlineKeyboardButton("TRC20", callback_data="d_trc"))
    bot.send_message(message.chat.id, "💎 Select Network for Deposit:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("d_"))
def handle_d(call):
    addrs = {"d_poly": "0xbaa8040ed8403fdc1974669c21a2dc77c020dd39", "d_bep": "0xbaa8040ed8403fdc1974669c21a2dc77c020dd39", "d_trc": "TCEfnjzzMRBm5iraPPgxp315UR31Pev7uo"}
    bot.send_message(call.message.chat.id, f"`{addrs[call.data]}`", parse_mode="Markdown")
    force_reply = types.ForceReply(selective=True)
    msg = bot.send_message(call.message.chat.id, f"⚠️ REPLY with TXID to verify:", reply_markup=force_reply)
    bot.register_next_step_handler(msg, process_dep)

def process_dep(message):
    txid = message.text.strip()
    bot.send_message(message.chat.id, "🔍 Verifying...")
    # [check_binance logic here]
    bot.send_message(message.chat.id, "✅ Done.")

@bot.message_handler(func=lambda m: m.text == "👥 Invite")
def invite(message):
    bot_username = bot.get_me().username
    invite_link = f"https://t.me/{bot_username}?start={message.chat.id}"
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("📤 Send to Friend", url=f"https://t.me/share/url?url={invite_link}"))
    bot.send_message(message.chat.id, f"<b>🎁 Your Referral Link:</b>\n\n<code>{invite_link}</code>", parse_mode="HTML", reply_markup=markup)

if __name__ == "__main__":
    init_db()
    keep_alive()
    bot.infinity_polling()
