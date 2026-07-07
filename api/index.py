import os
import json
import telebot
from telebot import types
from flask import Flask, request
import gspread

# --- الإعدادات الخاصة بك ---
TOKEN = '8774379921:AAGs5CJSRYuQq4hexglNndaUmiONy7aWf3Q'
ADMIN_ID = 6799794121
SHEET_ID = '133iZiMipX2NbiBWI7jaFEFRIQnTKfBsUN5MlGJWB2GI'

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

# --- الاتصال بجوجل شيت ---
def get_sheet():
    creds_json = os.environ.get('GOOGLE_CREDENTIALS')
    if not creds_json:
        return None
    try:
        creds_dict = json.loads(creds_json)
        gc = gspread.service_account_from_dict(creds_dict)
        sheet = gc.open_by_key(SHEET_ID).sheet1
        
        # التأكد من وجود العناوين في السطر الأول
        if not sheet.row_values(1):
            sheet.append_row(['user_id', 'username', 'points', 'balance'])
            
        return sheet
    except Exception as e:
        print("خطأ في الاتصال:", e)
        return None

def get_or_create_user(user_id, username):
    sheet = get_sheet()
    if not sheet: return None
    
    records = sheet.get_all_records()
    for row in records:
        if str(row.get('user_id', '')) == str(user_id):
            return row # المستخدم موجود مسبقاً
            
    # إذا المستخدم جديد، نسجله بالشيت
    sheet.append_row([str(user_id), username, 0, 0.0])
    return {'user_id': str(user_id), 'username': username, 'points': 0, 'balance': 0.0}

# --- دوال الأزرار ---
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

# --- مسارات Vercel (Webhook) ---
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
    return f"✅ تم تشغيل البوت وربطه بنجاح! الرابط: {webhook_url}", 200

# --- أوامر البوت ---
@bot.message_handler(commands=['start'])
def start_command(message):
    user_id = message.from_user.id
    username = message.from_user.username or "بدون_يوزر"
    
    # رسالة ترحيبية وتأكيد التسجيل بجوجل شيت
    bot.send_message(user_id, "⏳ جاري التحقق من حسابك...")
    user = get_or_create_user(user_id, username)
    
    if user:
        welcome = (
            f"🙋‍♂️ أهلاً بك يا {message.from_user.first_name} في بوت Hassany Store!\n\n"
            "🚀 نوفر لك أفضل خدمات الرشق (مجانية، بالنقاط، ومدفوعة):\n"
            "👇 اختر القسم الذي تريده:"
        )
        bot.send_message(user_id, welcome, reply_markup=get_main_keyboard(user_id))
    else:
        bot.send_message(user_id, "❌ حدث خطأ في الاتصال بقاعدة البيانات. يرجى المحاولة لاحقاً.")

@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    user_id = call.from_user.id
    data = call.data
    username = call.from_user.username or "بدون_يوزر"

    if data == "main_menu":
        bot.edit_message_text("👇 القائمة الرئيسية:", user_id, call.message.message_id, reply_markup=get_main_keyboard(user_id))

    elif data == "menu_account":
        bot.edit_message_text("⏳ جاري سحب رصيدك من قاعدة البيانات...", user_id, call.message.message_id)
        user = get_or_create_user(user_id, username)
        
        if user:
            account_text = (
                f"👤 **معلومات حسابك الخاص:**\n\n"
                f"🆔 الايدي: `{user_id}`\n"
                f"🪙 نقاطك: {user['points']} نقطة\n"
                f"💎 رصيدك: ${user['balance']:.2f}\n\n"
                f"✅ *بياناتك محفوظة بأمان في سيرفراتنا.*"
            )
            bot.edit_message_text(account_text, user_id, call.message.message_id, parse_mode="Markdown", reply_markup=get_back_button())
        else:
            bot.edit_message_text("❌ لم نتمكن من جلب بياناتك.", user_id, call.message.message_id, reply_markup=get_back_button())

    elif data == "menu_free":
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(types.InlineKeyboardButton("🎁 50 متابع انستا", callback_data="fake_order"), get_back_button().keyboard[0][0])
        bot.edit_message_text("الخدمات المجانية المتاحة:", user_id, call.message.message_id, reply_markup=markup)

    elif data == "menu_admin" and user_id == ADMIN_ID:
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(types.InlineKeyboardButton("💡 طريقة الشحن للأعضاء", callback_data="admin_how_to"), get_back_button().keyboard[0][0])
        bot.edit_message_text("⚙️ **لوحة المطور:**\nبما أن البوت مربوط بـ Google Sheets، تستطيع إدارة المتجر من هناك.", user_id, call.message.message_id, reply_markup=markup)

    elif data == "admin_how_to":
        bot.answer_callback_query(call.id, "لشحن رصيد شخص: افتح ملف الجوجل شيت من موبايلك، غير رقمه بحقل الرصيد (balance) والبوت راح يقراه مباشرة!", show_alert=True)

    elif data == "fake_order":
        bot.answer_callback_query(call.id, "✅ تم استلام الطلب بنجاح!", show_alert=True)
