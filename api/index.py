import telebot
from telebot import types
from flask import Flask, request
import json
import os
import random
import string
import re

TOKEN = '8774379921:AAGs5CJSRYuQq4hexglNndaUmiONy7aWf3Q'
ADMIN_ID = 6799794121 # ايدي المطور لاستلام الطلبات
bot = telebot.TeleBot(TOKEN, parse_mode="HTML")
app = Flask(__name__)

DB_FILE = '/tmp/hassany_store_db.json'

# --- قاعدة البيانات ---
def load_db():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, 'r', encoding='utf-8') as f: return json.load(f)
    return {'users': {}, 'services': {'free': [], 'points': [], 'paid': []}, 'codes': {}}

def save_db(db):
    with open(DB_FILE, 'w', encoding='utf-8') as f: json.dump(db, f, ensure_ascii=False, indent=4)

def get_user(user_id, name, username):
    db = load_db()
    uid = str(user_id)
    if uid not in db['users']:
        db['users'][uid] = {'name': name, 'username': username, 'points': 0, 'is_admin': False}
        save_db(db)
    return db['users'][uid]

# --- متغيرات مؤقتة للمطور ---
user_steps = {}
temp_service = {}
temp_code = {}

# --- القائمة الرئيسية (أزرار شفافة كبيرة عمودية) ---
def main_menu(user_id):
    db = load_db()
    is_admin = db['users'].get(str(user_id), {}).get('is_admin', False)
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("🎁 الخـدمــات المجـانيــة", callback_data="cat_free"),
        types.InlineKeyboardButton("🪙 الخـدمــات بالنقــاط", callback_data="cat_points"),
        types.InlineKeyboardButton("💎 الخـدمــات المدفـوعــة", callback_data="cat_paid"),
        types.InlineKeyboardButton("👤 معـلومـات الحســاب", callback_data="my_account"),
        types.InlineKeyboardButton("💳 شحـن حسابـك بالنقـاط", callback_data="charge_points")
    )
    if is_admin or user_id == ADMIN_ID:
        markup.add(types.InlineKeyboardButton("⚙️ لـوحـة المطــور ⚙️", callback_data="admin_panel"))
    return markup

def back_btn():
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔙 العودة للقائمة", callback_data="back_main"))
    return markup

# --- مسارات Vercel ---
@app.route('/api/webhook', methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        update = telebot.types.Update.de_json(request.get_data().decode('utf-8'))
        bot.process_new_updates([update])
        return 'OK', 200
    return 'Forbidden', 403

# --- أوامر البداية ---
@bot.message_handler(commands=['start'])
def start_msg(message):
    uid = message.chat.id
    get_user(uid, message.from_user.first_name, message.from_user.username)
    bot.send_message(
        uid, 
        f"أهلاً بك يا <b>{message.from_user.first_name}</b> في متجر Hassany!\n\n"
        "🚀 نوفر لك أفضل خدمات الرشق والزيادات الاحترافية.\n👇 اختر من القائمة أدناه:",
        reply_markup=main_menu(uid)
    )

# --- معالجة الأزرار ---
@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    uid = call.message.chat.id
    data = call.data
    db = load_db()
    
    if data == "back_main":
        bot.edit_message_text("👇 القائمة الرئيسية:", uid, call.message.message_id, reply_markup=main_menu(uid))

    elif data == "my_account":
        user = db['users'].get(str(uid), {})
        text = (
            f"👤 <b>معلومات حسابك:</b>\n\n"
            f"📝 الاسم: {user.get('name', 'غير معروف')}\n"
            f"🆔 الايدي: <code>{uid}</code>\n"
            f"🪙 نقاطك الحالية: <b>{user.get('points', 0)}</b>"
        )
        bot.edit_message_text(text, uid, call.message.message_id, reply_markup=back_btn())

    elif data == "charge_points":
        user_steps[uid] = "wait_recharge_code"
        bot.edit_message_text("💳 <b>شحن الحساب:</b>\n\nقم بإرسال كود الشحن الخاص بك الآن:", uid, call.message.message_id, reply_markup=back_btn())

    # عرض الأقسام والخدمات
    elif data.startswith("cat_"):
        cat_type = data.split("_")[1]
        services = db['services'][cat_type]
        markup = types.InlineKeyboardMarkup(row_width=1)
        
        if not services:
            bot.edit_message_text("لا توجد خدمات في هذا القسم حالياً.", uid, call.message.message_id, reply_markup=back_btn())
            return
            
        for idx, srv in enumerate(services):
            markup.add(types.InlineKeyboardButton(f"{srv['name']} - {srv['price']}", callback_data=f"buy_{cat_type}_{idx}"))
        markup.add(types.InlineKeyboardButton("🔙 العودة", callback_data="back_main"))
        bot.edit_message_text("🛒 <b>اختر الخدمة التي تريدها:</b>", uid, call.message.message_id, reply_markup=markup)

    # شراء خدمة
    elif data.startswith("buy_"):
        _, cat_type, idx = data.split("_")
        idx = int(idx)
        srv = db['services'][cat_type][idx]
        user_points = db['users'][str(uid)]['points']
        price = int(srv['price'])
        
        if cat_type == "points" and user_points < price:
            bot.answer_callback_query(call.id, "❌ نقاطك غير كافية!", show_alert=True)
            return
            
        # خصم النقاط وإرسال الطلب
        if cat_type == "points":
            db['users'][str(uid)]['points'] -= price
            save_db(db)
            
        user = db['users'][str(uid)]
        bot.edit_message_text(f"✅ <b>حسنًا، لقد تم استلام طلبك وهو الآن قيد المراجعة.</b>\nالخدمة: {srv['name']}", uid, call.message.message_id, reply_markup=back_btn())
        
        # إرسال إشعار للمطور
        admin_text = (
            f"🔔 <b>طلب جديد!</b>\n\n"
            f"👤 الاسم: {user.get('name')}\n"
            f"🔗 اليوزر: @{user.get('username', 'لا يوجد')}\n"
            f"🆔 ID: <code>{uid}</code>\n"
            f"🛒 الخدمة: {srv['name']}\n"
            f"📝 الوصف المرفق: {srv['desc']}"
        )
        admin_kb = types.InlineKeyboardMarkup(row_width=2)
        admin_kb.add(
            types.InlineKeyboardButton("✅ موافقة", callback_data=f"ord_acc_{uid}"),
            types.InlineKeyboardButton("❌ رفض", callback_data=f"ord_rej_{uid}")
        )
        bot.send_message(ADMIN_ID, admin_text, reply_markup=admin_kb)

    # أزرار موافقة/رفض المطور
    elif data.startswith("ord_"):
        action, target_uid = data.split("_")[1], data.split("_")[2]
        
        if action == "acc":
            bot.send_message(target_uid, "✅ <b>تمت الموافقة على طلبك وهو الآن قيد التنفيذ!</b>")
            bot.edit_message_text(f"{call.message.html_text}\n\n<b>حالة الطلب:</b> 🟢 قيد التنفيذ", ADMIN_ID, call.message.message_id)
        elif action == "rej":
            bot.send_message(target_uid, "❌ <b>عذراً، تم رفض طلبك!</b> (تم إرجاع النقاط إذا كانت الخدمة بنقاط)")
            bot.edit_message_text(f"{call.message.html_text}\n\n<b>حالة الطلب:</b> 🔴 تم الرفض", ADMIN_ID, call.message.message_id)

    # --- لوحة المطور ---
    elif data == "admin_panel":
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("➕ إضافة خدمة جديدة", callback_data="add_service_start"),
            types.InlineKeyboardButton("🔗 إنشاء كود شحن (روابط)", callback_data="create_code_start"),
            types.InlineKeyboardButton("🔙 رجوع", callback_data="back_main")
        )
        bot.edit_message_text("⚙️ <b>لوحة تحكم Hassany Store:</b>", uid, call.message.message_id, reply_markup=markup)

    # إضافة خدمة جديدة
    elif data == "add_service_start":
        markup = types.InlineKeyboardMarkup(row_width=3)
        markup.add(
            types.InlineKeyboardButton("مجانية", callback_data="set_cat_free"),
            types.InlineKeyboardButton("نقاط", callback_data="set_cat_points"),
            types.InlineKeyboardButton("مدفوعة", callback_data="set_cat_paid")
        )
        bot.edit_message_text("حدد القسم الذي تريد إضافة الخدمة فيه:", uid, call.message.message_id, reply_markup=markup)

    elif data.startswith("set_cat_"):
        temp_service[uid] = {'cat': data.split("_")[2]}
        user_steps[uid] = "wait_service_name"
        bot.send_message(uid, "أرسل **اسم الخدمة** الآن:")

    # إنشاء كود شحن
    elif data == "create_code_start":
        user_steps[uid] = "wait_code_points"
        bot.send_message(uid, "أرسل عدد النقاط التي سيعطيها هذا الكود:")

# --- معالجة النصوص والردود ---
@bot.message_handler(func=lambda msg: True)
def handle_texts(message):
    uid = message.chat.id
    text = message.text
    db = load_db()

    # نظام الإكمال برد "تم" من المطور
    if message.reply_to_message and text == "تم" and uid == ADMIN_ID:
        match = re.search(r"ID:\s*(\d+)", message.reply_to_message.text)
        if match:
            target_uid = match.group(1)
            bot.send_message(target_uid, "🎉 <b>تم إكمال طلبك بنجاح وتم الرشق!</b>")
            bot.reply_to(message, "✅ تم إرسال إشعار الانتهاء للمستخدم بنجاح.")
        return

    # التفعيل السري
    if text == "BHGHV5H":
        user_steps[uid] = "wait_pass"
        bot.send_message(uid, "أرسل الرمز:")
        return
    if uid in user_steps and user_steps[uid] == "wait_pass":
        if text == "123":
            db['users'][str(uid)]['is_admin'] = True
            save_db(db)
            bot.send_message(uid, "✅ تم تفعيل المالك. أرسل /start")
        user_steps.pop(uid, None)
        return

    # شحن الرصيد
    if uid in user_steps and user_steps[uid] == "wait_recharge_code":
        if text in db['codes']:
            code_data = db['codes'][text]
            if code_data['uses'] > 0:
                db['users'][str(uid)]['points'] += code_data['points']
                db['codes'][text]['uses'] -= 1
                save_db(db)
                bot.send_message(uid, f"✅ <b>تم شحن حسابك بنجاح!</b>\nحصلت على {code_data['points']} نقطة.")
            else:
                bot.send_message(uid, "❌ هذا الكود منتهي الصلاحية أو استنفد عدد مرات الاستخدام.")
        else:
            bot.send_message(uid, "❌ كود الشحن غير صحيح.")
        user_steps.pop(uid, None)
        return

    # --- خطوات إضافة خدمة (للمطور) ---
    if uid in user_steps and user_steps[uid] == "wait_service_name":
        temp_service[uid]['name'] = text
        user_steps[uid] = "wait_service_desc"
        bot.send_message(uid, "أرسل **وصف الخدمة**:")
        return
    if uid in user_steps and user_steps[uid] == "wait_service_desc":
        temp_service[uid]['desc'] = text
        user_steps[uid] = "wait_service_price"
        bot.send_message(uid, "أرسل **السعر** (رقم فقط):")
        return
    if uid in user_steps and user_steps[uid] == "wait_service_price":
        temp_service[uid]['price'] = text
        cat = temp_service[uid]['cat']
        db['services'][cat].append(temp_service[uid])
        save_db(db)
        bot.send_message(uid, "✅ تم إضافة الخدمة بنجاح!")
        user_steps.pop(uid, None)
        return

    # --- خطوات إنشاء كود (للمطور) ---
    if uid in user_steps and user_steps[uid] == "wait_code_points":
        if text.isdigit():
            temp_code[uid] = {'points': int(text)}
            user_steps[uid] = "wait_code_uses"
            bot.send_message(uid, "كم شخص يستطيع استخدام هذا الكود؟ (رقم)")
        return
    if uid in user_steps and user_steps[uid] == "wait_code_uses":
        if text.isdigit():
            code_str = "HASSANY-" + ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
            db['codes'][code_str] = {'points': temp_code[uid]['points'], 'uses': int(text)}
            save_db(db)
            bot.send_message(uid, f"✅ <b>تم إنشاء الكود بنجاح!</b>\n\nالكود: <code>{code_str}</code>\nالنقاط: {temp_code[uid]['points']}\nالاستخدامات: {text}")
            user_steps.pop(uid, None)
        return
