import telebot
from telebot import types
from flask import Flask, request

# --- التوكن والايدي مالتك جاهزات ---
TOKEN = '8774379921:AAGs5CJSRYuQq4hexglNndaUmiONy7aWf3Q'
ADMIN_ID = 6799794121

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

# --- قاعدة بيانات مؤقتة ---
users_db = {}

# --- الأزرار ---
def get_main_keyboard(user_id):
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🎁 خدمات مجانية", callback_data="menu_free"),
        types.InlineKeyboardButton("🪙 رشق بالنقاط", callback_data="menu_points")
    )
    markup.add(
        types.InlineKeyboardButton("💎 خدمات V.I.P", callback_data="menu_paid"),
        types.InlineKeyboardButton("👤 حسابي", callback_data="menu_account")
    )
    if user_id == ADMIN_ID:
        markup.add(types.InlineKeyboardButton("⚙️ لوحة المطور", callback_data="menu_admin"))
    return markup

def get_back_button():
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔙 العودة للقائمة", callback_data="main_menu"))
    return markup

# --- تشغيل Vercel ---
@app.route('/api/webhook', methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return 'OK', 200
    return 'Forbidden', 403

@app.route('/api/set_webhook', methods=['GET'])
def set_webhook():
    webhook_url = f"{request.host_url.rstrip('/')}/api/webhook"
    bot.remove_webhook()
    bot.set_webhook(url=webhook_url)
    return f"✅ البوت اشتغل طيارة! الرابط: {webhook_url}", 200

# --- الأوامر ---
@bot.message_handler(commands=['start'])
def start_command(message):
    user_id = message.from_user.id
    
    if user_id not in users_db:
        users_db[user_id] = {'points': 0, 'balance': 0.0}

    welcome = (
        f"🙋‍♂️ أهلاً بك يا {message.from_user.first_name} في بوت Hassany Store!\n\n"
        "🚀 نوفر لك أفضل خدمات الرشق والزيادات:\n"
        "👇 اختر القسم الذي تريده:"
    )
    bot.send_message(user_id, welcome, reply_markup=get_main_keyboard(user_id))

@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    user_id = call.from_user.id
    data = call.data
    
    if user_id not in users_db:
        users_db[user_id] = {'points': 0, 'balance': 0.0}
    user = users_db[user_id]

    if data == "main_menu":
        bot.edit_message_text("👇 القائمة الرئيسية:", user_id, call.message.message_id, reply_markup=get_main_keyboard(user_id))

    elif data == "menu_account":
        account_text = (
            f"👤 **معلومات حسابك:**\n\n"
            f"🆔 الايدي: `{user_id}`\n"
            f"🪙 نقاطك: {user['points']} نقطة\n"
            f"💎 رصيدك: ${user['balance']:.2f}\n"
        )
        bot.edit_message_text(account_text, user_id, call.message.message_id, parse_mode="Markdown", reply_markup=get_back_button())
        
    elif data == "menu_free":
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(types.InlineKeyboardButton("🎁 50 متابع انستا", callback_data="fake_order"), get_back_button().keyboard[0][0])
        bot.edit_message_text("الخدمات المجانية المتاحة:", user_id, call.message.message_id, reply_markup=markup)

    elif data == "fake_order":
        bot.answer_callback_query(call.id, "✅ تم استلام طلبك!", show_alert=True)
        
    elif data == "menu_admin" and user_id == ADMIN_ID:
        bot.edit_message_text("⚙️ **لوحة تحكم المطور:**\nبما أننا نستخدم Vercel فقط، الأرصدة تتصفر عند إغلاق السيرفر.", user_id, call.message.message_id, reply_markup=get_back_button())
