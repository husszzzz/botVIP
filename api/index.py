import telebot
from telebot import types
from flask import Flask, request

TOKEN = '8774379921:AAGs5CJSRYuQq4hexglNndaUmiONy7aWf3Q'
bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

# --- قاعدة البيانات المؤقتة ---
users_db = {}
user_steps = {}

def get_user(user_id):
    if user_id not in users_db:
        users_db[user_id] = {'points': 0, 'balance': 0.0, 'is_admin': False}
    return users_db[user_id]

# --- الأزرار الرئيسية ---
def main_menu(user_id):
    user = get_user(user_id)
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🎁 خدمات مجانية", callback_data="sec_free"),
        types.InlineKeyboardButton("🪙 رشق بالنقاط", callback_data="sec_points")
    )
    markup.add(
        types.InlineKeyboardButton("💎 خدمات V.I.P", callback_data="sec_vip"),
        types.InlineKeyboardButton("👤 حسابي", callback_data="my_account")
    )
    
    # يظهر زر المطور فقط إذا كان الشخص يمتلك صلاحية المالك
    if user['is_admin']:
        markup.add(types.InlineKeyboardButton("⚙️ لوحة المطور", callback_data="admin_panel"))
    return markup

def back_btn():
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔙 العودة للقائمة", callback_data="back_main"))
    return markup

# --- مسارات Vercel ---
@app.route('/api/webhook', methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return 'OK', 200
    return 'Forbidden', 403

# --- الأوامر والرسائل ---
@bot.message_handler(commands=['start'])
def start_msg(message):
    uid = message.chat.id
    get_user(uid) # لتسجيل المستخدم إذا كان جديداً
    bot.send_message(
        uid, 
        f"أهلاً بك يا <b>{message.from_user.first_name}</b> في بوت المتجر!\n\n"
        "🚀 نوفر لك أفضل خدمات الرشق والزيادات:\n👇 اختر القسم الذي تريده:",
        parse_mode="HTML",
        reply_markup=main_menu(uid)
    )

# --- معالجة الأزرار (الـ Inline) ---
@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    uid = call.message.chat.id
    data = call.data
    user = get_user(uid)

    if data == "back_main":
        bot.edit_message_text(
            "👇 القائمة الرئيسية:", uid, call.message.message_id, 
            reply_markup=main_menu(uid)
        )

    elif data == "my_account":
        text = (
            f"👤 <b>معلومات حسابك:</b>\n\n"
            f"🆔 الايدي: <code>{uid}</code>\n"
            f"🪙 نقاطك: <b>{user['points']}</b>\n"
            f"💎 رصيدك المدفوع: <b>${user['balance']:.2f}</b>"
        )
        bot.edit_message_text(text, uid, call.message.message_id, parse_mode="HTML", reply_markup=back_btn())

    elif data == "sec_free":
        bot.edit_message_text("🎁 <b>الخدمات المجانية:</b>\n\n(قريباً سيتم إضافة الرشق المجاني)", uid, call.message.message_id, parse_mode="HTML", reply_markup=back_btn())
        
    elif data == "sec_points":
        bot.edit_message_text("🪙 <b>خدمات النقاط:</b>\n\nاجمع النقاط لطلب الرشق:\n- متابعين انستا\n- مشاهدات تيك توك", uid, call.message.message_id, parse_mode="HTML", reply_markup=back_btn())
        
    elif data == "sec_vip":
        bot.edit_message_text("💎 <b>خدمات V.I.P المدفوعة:</b>\n\n(خدمات سريعة جداً وبدون نقص، تواصل مع المطور للشحن)", uid, call.message.message_id, parse_mode="HTML", reply_markup=back_btn())

    elif data == "admin_panel" and user['is_admin']:
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("➕ إضافة/خصم نقاط", callback_data="adm_points"),
            types.InlineKeyboardButton("🔗 إنشاء رابط هدية (كود)", callback_data="adm_gift"),
            types.InlineKeyboardButton("🛠️ تعديل الخدمات", callback_data="adm_services"),
            types.InlineKeyboardButton("🔙 رجوع", callback_data="back_main")
        )
        bot.edit_message_text("⚙️ <b>لوحة تحكم المالك:</b>\n\nاختر الإجراء المطلوب:", uid, call.message.message_id, parse_mode="HTML", reply_markup=markup)

# --- معالجة النصوص (الكلمة السرية) ---
@bot.message_handler(func=lambda msg: True)
def handle_text(message):
    uid = message.chat.id
    text = message.text

    # الخطوة 1: استلام الكود الأول
    if text == "BHGHV5H":
        user_steps[uid] = "wait_pass"
        bot.send_message(uid, "اوكي")
        return

    # الخطوة 2: استلام الرمز السري
    if uid in user_steps and user_steps[uid] == "wait_pass":
        if text == "123":
            get_user(uid)['is_admin'] = True
            bot.send_message(uid, "✅ <b>تم تفعيل صلاحيات المالك بنجاح!</b>\nأرسل /start لفتح لوحة المطور.", parse_mode="HTML")
        else:
            bot.send_message(uid, "❌ الرمز خاطئ، تم الإلغاء.")
        
        # مسح الخطوة حتى لا يعلق البوت
        user_steps.pop(uid, None)
        return
