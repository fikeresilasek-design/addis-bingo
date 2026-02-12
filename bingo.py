import telebot, sqlite3, requests, time, hmac, hashlib
from telebot import types
from flask import Flask, jsonify, request
from threading import Thread
import os

# --- KEEP ALIVE & API SERVER ---
app = Flask('')

@app.route('/')
def home():
    return "Web3 Bingo Server is Live!"

# This allows your Website to see room counts
@app.route('/get_rooms')
def get_rooms():
    lobby_id = request.args.get('lobby', 1)
    conn = sqlite3.connect("bingo.db")
    cur = conn.cursor()
    cur.execute("SELECT room_no, player_count FROM rooms WHERE lobby_id=?", (lobby_id,))
    data = cur.fetchall()
    conn.close()
    return jsonify(data)

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
    # Fill 4 Lobbies x 100 Rooms
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

def check_binance(target_txid):
    conn = sqlite3.connect("bingo.db")
    cur = conn.cursor()
    cur.execute("SELECT txid FROM tx WHERE txid=?", (target_txid,))
    if cur.fetchone():
        conn.close()
        return "used"
    url = "https://api.binance.com/sapi/v1/capital/deposit/hisrec"
    ts = int(time.time() * 1000)
    query = f"recvWindow=60000&timestamp={ts}"
    sig = hmac.new(BIN_SECRET.encode(), query.encode(), hashlib.sha256).hexdigest()
    try:
        r = requests.get(f"{url}?{query}&signature={sig}", headers={'X-MBX-APIKEY': BIN_KEY}, timeout=10)
        data = r.json()
        if isinstance(data, list):
            for d in data:
                if (str(d.get('txId')) == target_txid or str(d.get('id')) == target_txid) and int(d.get('status')) == 1:
                    amt = float(d['amount'])
                    cur.execute("INSERT INTO tx (txid) VALUES (?)", (target_txid,))
                    conn.commit()
                    conn.close()
                    return amt
    except: pass
    conn.close()
    return None

@bot.message_handler(commands=['start'])
def start(message):
    bal = get_actual_bal(message.chat.id)
    # The Bot now just opens the main URL. The Website handles Room selection.
    game_url = f"https://fikeresilasek-design.github.io/addis-bingo/?balance={bal}&uid={message.chat.id}"
    
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton(text="🎮 Play Bingo", web_app=types.WebAppInfo(url=game_url)))
    markup.row(types.KeyboardButton(text="💰 Balance"), types.KeyboardButton(text="📥 Deposit"))
    markup.row(types.KeyboardButton(text="📤 Withdraw"), types.KeyboardButton(text="👥 Invite"))
    markup.add(types.KeyboardButton(text="👨‍💻 Support Team"))

    welcome_text = (
        "🌍 **Welcome to World Bingo Lobby!**\n\n"
        "Enter the game to browse 400 available rooms.\n\n"
        f"💰 Your Balance: {bal} USDT"
    )
    bot.send_message(message.chat.id, welcome_text, parse_mode="Markdown", reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == "💰 Balance")
def show_balance(message):
    bal = get_actual_bal(message.chat.id)
    bot.send_message(message.chat.id, f"💵 Current Balance: {bal} USDT")

@bot.message_handler(func=lambda m: m.text == "📥 Deposit")
def dep_m(message):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("Polygon", callback_data="d_poly"), 
               types.InlineKeyboardButton("BEP20", callback_data="d_bep"), 
               types.InlineKeyboardButton("TRC20", callback_data="d_trc"))
    bot.send_message(message.chat.id, "💎 Select Network:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("d_"))
def handle_d(call):
    addrs = {"d_poly": "0xbaa8040ed8403fdc1974669c21a2dc77c020dd39", "d_bep": "0xbaa8040ed8403fdc1974669c21a2dc77c020dd39", "d_trc": "TCEfnjzzMRBm5iraPPgxp315UR31Pev7uo"}
    bot.send_message(call.message.chat.id, f"`{addrs[call.data]}`", parse_mode="Markdown")
    bot.send_message(call.message.chat.id, "⚠️ REPLY to this with TXID to verify.")

@bot.message_handler(func=lambda m: m.text == "👥 Invite")
def invite(message):
    bot_username = bot.get_me().username
    invite_link = f"https://t.me/{bot_username}?start={message.chat.id}"
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("📤 Send to Friend", url=f"https://t.me/share/url?url={invite_link}"))
    bot.send_message(message.chat.id, f"🔗 **Referral Link:**\n<code>{invite_link}</code>", parse_mode="HTML", reply_markup=markup)

if __name__ == "__main__":
    init_db()
    keep_alive()
    bot.infinity_polling()
