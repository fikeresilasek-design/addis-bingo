cat << 'EOF' > bingo.py
import telebot, sqlite3, requests, time, hmac, hashlib
from telebot import types

TOKEN = "8011067020:AAEUVoevMaKiUNMv_HMZRLnWyAL6gYrU7IQ"
bot = telebot.TeleBot(TOKEN)

# Admin ID
ADMIN_ID = 6650340402 

BIN_KEY = "TI1gPHBFK0XEblbS9wzBpLswG4V2CEDbxySNrAjdrW5rWUyDsl0Vxao24drHByTq"
BIN_SECRET = "Pu69cI4dep7y1KLRwrekEQeknCPV50uNIwlLlBNHmIxg7JIEREtyiFvwrIi2V7N7"

# --- DB FUNCTIONS ---
def init_db():
    conn = sqlite3.connect("bingo.db")
    cur = conn.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS users (uid INTEGER PRIMARY KEY, balance REAL)")
    cur.execute("CREATE TABLE IF NOT EXISTS tx (txid TEXT PRIMARY KEY)")
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
        r = requests.get(f"{url}?{query}&signature={sig}", headers={'X-MBX-APIKEY': BIN_KEY}, timeout=20)
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
    game_url = f"https://fikeresilasek-design.github.io/addis-bingo/?balance={bal}"
    
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    btn_play = types.KeyboardButton(text="🎮 Play Bingo", web_app=types.WebAppInfo(url=game_url))
    btn_bal = types.KeyboardButton(text="💰 Balance")
    btn_dep = types.KeyboardButton(text="📥 Deposit")
    btn_wd = types.KeyboardButton(text="📤 Withdraw")
    btn_inv = types.KeyboardButton(text="👥 Invite")
    btn_sup = types.KeyboardButton(text="👨‍💻 Support Team")
    
    markup.add(btn_play)
    markup.row(btn_bal, btn_dep)
    markup.row(btn_wd, btn_inv)
    markup.add(btn_sup)

    welcome_text = (
        "🌍 Welcome to World Bingo!\n\n"
        "The most exciting Web3 Bingo game on Telegram. Play against others and win USDT!\n\n"
        "📖 How to Play:\n"
        "1. Deposit Funds: Use the 📥 Deposit button to add USDT.\n"
        "2. Open Game: Click 🎮 Play Bingo to enter the arena.\n"
        "3. Choose Lobby: Pick one of the 4 lobbies that fits your budget.\n"
        "4. Win: Get a Bingo and your winnings are added instantly!\n\n"
        f"💰 Your Balance: {bal} USDT"
    )
    logo_url = "https://raw.githubusercontent.com/fikeresilasek-design/addis-bingo/main/logo.png"

    try:
        bot.send_photo(message.chat.id, logo_url, caption=welcome_text, parse_mode="Markdown", reply_markup=markup)
    except:
        bot.send_message(message.chat.id, welcome_text, parse_mode="Markdown", reply_markup=markup)

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
    addrs = {
        "d_poly": "0xbaa8040ed8403fdc1974669c21a2dc77c020dd39", 
        "d_bep": "0xbaa8040ed8403fdc1974669c21a2dc77c020dd39", 
        "d_trc": "TCEfnjzzMRBm5iraPPgxp315UR31Pev7uo"
    }
    method_names = {"d_poly": "Polygon", "d_bep": "BEP20", "d_trc": "TRC20"}
    
    bot.send_message(call.message.chat.id, f"{addrs[call.data]}", parse_mode="Markdown")
    
    force_reply = types.ForceReply(selective=True)
    msg = bot.send_message(call.message.chat.id, f"☝️ Tap address to copy.\n\nNetwork: {method_names[call.data]}\n⚠️ REPLY to this message with your TXID to verify deposit:", reply_markup=force_reply)
    bot.register_next_step_handler(msg, process_dep)

def process_dep(message):
    if not message.reply_to_message:
        bot.send_message(message.chat.id, "❌ Error: You must REPLY to the deposit instruction message with your TXID.")
        return

    txid = message.text.strip()
    bot.send_message(message.chat.id, "🔍 Verifying...")
    res = check_binance(txid)
    if res == "used": bot.send_message(message.chat.id, "❌ Already used.")
    elif res:
        update_bal(message.chat.id, res)
        bot.send_message(message.chat.id, f"✅ Added {res} USDT!")
        try:
            bot.send_message(ADMIN_ID, f"💰 Deposit: @{message.from_user.username} - {res} USDT")
        except: pass
    else: bot.send_message(message.chat.id, "❌ Not found. Please make sure the transaction is completed on Binance.")

@bot.message_handler(func=lambda m: m.text == "📤 Withdraw")
def withdraw_menu(message):
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(types.InlineKeyboardButton("Binance ID", callback_data="w_bin"), types.InlineKeyboardButton("Polygon", callback_data="w_poly"), types.InlineKeyboardButton("BEP20", callback_data="w_bep"), types.InlineKeyboardButton("TRC20", callback_data="w_trc"))
    bot.send_message(message.chat.id, "🏧 Select Method:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("w_"))
def handle_w(call):
    method = call.data.split("_")[1].upper()
    msg = bot.send_message(call.message.chat.id, f"How much USDT via {method}?")
    bot.register_next_step_handler(msg, lambda m: process_wd(m, method))

def process_wd(message, method):
    try:
        amt = float(message.text)
        bal = get_actual_bal(message.chat.id)
        if amt > bal: bot.send_message(message.chat.id, "❌ Unsuccessful balance.")
        else:
            msg = bot.send_message(message.chat.id, f"Enter your {method} Address:")
            bot.register_next_step_handler(msg, lambda m: finalize_wd(m, amt, method))
    except: bot.send_message(message.chat.id, "❌ Error.")

def finalize_wd(message, amount, method):
    update_bal(message.chat.id, -amount)
    user_id = message.chat.id
    username = message.from_user.username if message.from_user.username else "No Username"
    address = message.text.strip()
    
    bot.send_message(user_id, "✅ Withdrawal Request Sent! Please wait for approval.")

    # Fixed Indentation below
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("✅ Accept", callback_data=f"approve_{user_id}_{amount}"),
        types.InlineKeyboardButton("❌ Reject", callback_data=f"reject_{user_id}_{amount}")
    )
    
    admin_msg = (
        f"💸 New Withdrawal Request\n\n"
        f"👤 User: @{username} (ID: {user_id})\n"
        f"💰 Amount: {amount} USDT\n"
        f"⛓ Method: {method}\n"
        f"📍 Address: {address}"
    )
    
    try:
        bot.send_message(ADMIN_ID, admin_msg, parse_mode="Markdown", reply_markup=markup)
    except Exception as e:
        print(f"ERROR: Could not send message to Admin. Error: {e}")

@bot.callback_query_handler(func=lambda call: call.data.startswith(("approve_", "reject_")))
def admin_approval(call):
    action, uid, amt = call.data.split("_")
    uid = int(uid)
    
    if action == "approve":
        bot.edit_message_text(f"{call.message.text}\n\n✅ STATUS: APPROVED", ADMIN_ID, call.message.message_id)
        bot.send_message(uid, f"✅ Your withdrawal of {amt} USDT has been Accepted!")
    
    elif action == "reject":
        update_bal(uid, float(amt))
        bot.edit_message_text(f"{call.message.text}\n\n❌ STATUS: REJECTED (Refunded)", ADMIN_ID, call.message.message_id)
        bot.send_message(uid, f"❌ Your withdrawal of {amt} USDT was Rejected. Balance refunded.")

@bot.message_handler(func=lambda m: m.text == "👨‍💻 Support Team")
def support(message):
    bot.send_message(message.chat.id, "🆘 Support: @whoami2721")

@bot.message_handler(func=lambda m: m.text == "👥 Invite")
def invite(message):
    bot_info = bot.get_me()
    invite_link = f"https://t.me/{bot_info.username}?start={message.chat.id}"
    invite_text = (
        "<b>🎁 Invite Friends & Win!</b>\n\n"
        "Share your link with friends. When they join, they become your referrals.\n\n"
        f"🔗 <b>Your Invite Link:</b>\n{invite_link}"
    )
    bot.send_message(message.chat.id, invite_text, parse_mode="HTML")

# Fixed Main variable below
if __name__ == "__main__":
    init_db()
    bot.infinity_polling()
EOF
