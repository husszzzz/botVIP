import telebot
from telebot import types
from flask import Flask, request
import json
import os

TOKEN = '8774379921:AAGs5CJSRYuQq4hexglNndaUmiONy7aWf3Q'
bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

# --- إعدادات ملف JSON ---
# Vercel تسمح بالكتابة فقط في مجلد /tmp
DB_FILE = '/tmp/hassany_users.json'

def load_db():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_db(data):
    with open(DB_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def get_or_create_user(user_id):
    db = load_db()
    uid_str = str(user_id)
    if uid_str not in db:
        db[uid_str] = {'points': 0, 'balance': 0.0, 'is_admin': False}
        save_db(db)
    return db[uid_str]

def update_user_data(user_id, key, value):
    db = load_db()
    uid_str = str(user_id)
    if uid_str in db:
        db[uid_str][key] = value
        save_db(db)

# --- متغيرات التحكم المؤقتة ---
user_steps = {}

# --- الأزرار الرئيسية ---
def main_menu(user_id):
    user = get_or_create_user(user_id)
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🎁 خدمات مجانية", callback_data="sec_free"),
        types.InlineKeyboardButton("🪙 رشق بالنقاط", callback_data="sec_points")
    )
    markup.add(
        types.InlineKeyboardButton("💎 خدمات V.I.P", callback_data="sec_vip"),
        types.InlineKeyboardButton("👤 حسابي", callback_data="my_account")
    )
    
    if user.get('is_admin', False):
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
    get_or_create_user(uid) # تسجيل المستخدم بالـ JSON
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
    user = get_or_create_user(uid)

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

    elif data == "admin_panel" and user.get('is_admin', False):
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("➕ إضافة/خصم نقاط لشخص", callback_data="adm_edit_points"),
            types.InlineKeyboardButton("🔙 رجوع", callback_data="back_main")
        )
        bot.edit_message_text("⚙️ <b>لوحة تحكم المالك:</b>\n\nاختر الإجراء المطلوب:", uid, call.message.message_id, parse_mode="HTML", reply_markup=markup)

    elif data == "adm_edit_points" and user.get('is_admin', False):
        user_steps[uid] = "wait_user_id_for_points"
        bot.send_message(uid, "أرسل الآن **ايدي (ID)** الشخص الذي تريد تعديل نقاطه:", parse_mode="Markdown")

# --- معالجة النصوص وحالات الأدمن ---
@bot.message_handler(func=lambda msg: True)
def handle_text(message):
    uid = message.chat.id
    text = message.text
    user = get_or_create_user(uid)

    # 1. نظام تفعيل المالك السري
    if text == "BHGHV5H":
        user_steps[uid] = "wait_pass"
        bot.send_message(uid, "اوكي")
        return

    if uid in user_steps and user_steps[uid] == "wait_pass":
        if text == "123":
            update_user_data(uid, 'is_admin', True)
            bot.send_message(uid, "✅ <b>تم تفعيل صلاحيات المالك بنجاح!</b>\nأرسل /start لفتح لوحة المطور.", parse_mode="HTML")
        else:
            bot.send_message(uid, "❌ الرمز خاطئ.")
        user_steps.pop(uid, None)
        return

    # 2. نظام الأدمن: استلام ايدي الشخص لتعديل النقاط
    if uid in user_steps and user_steps[uid] == "wait_user_id_for_points":
        target_id = text.strip()
        db = load_db()
        if target_id not in db:
            bot.send_message(uid, "❌ هذا الشخص غير مسجل في البوت (لم يضغط /start).")
            user_steps.pop(uid, None)
            return
        
        user_steps[uid] = f"wait_amount_for_points_{target_id}"
        current_points = db[target_id]['points']
        bot.send_message(uid, f"👤 المستخدم موجود.\n🪙 نقاطه الحالية: {current_points}\n\nأرسل الآن الكمية (اكتب رقم موجب للإضافة مثل 50، أو رقم سالب للخصم مثل -50):")
        return

    # 3. نظام الأدمن: استلام كمية النقاط (إضافة أو خصم)
    if uid in user_steps and user_steps[uid].startswith("wait_amount_for_points_"):
        target_id = user_steps[uid].split("_")[-1]
        try:
            amount = int(text.strip())
            db = load_db()
            
            # تحديث النقاط (جمع الكمية الحالية مع الكمية المدخلة)
            new_points = db[target_id]['points'] + amount
            if new_points < 0: 
                new_points = 0 # منع النقاط من أن تصبح بالسالب
                
            db[target_id]['points'] = new_points
            save_db(db)
            
            action = "إضافة" if amount > 0 else "خصم"
            bot.send_message(uid, f"✅ تم {action} {abs(amount)} نقطة بنجاح.\n🪙 النقاط الجديدة للمستخدم: {new_points}")
            
            # إرسال إشعار للمستخدم نفسه
            try:
                bot.send_message(int(target_id), f"🔔 إشعار إداري:\nتم {action} {abs(amount)} نقطة من حسابك.\n🪙 رصيدك الحالي: {new_points} نقطة.")
            except:
                pass # في حال كان حظر البوت
                
        except ValueError:
            bot.send_message(uid, "❌ يرجى إرسال أرقام فقط (مثال: 100 أو -50).")
            
        user_steps.pop(uid, None)
        return
