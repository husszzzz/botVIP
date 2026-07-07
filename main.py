import os
import sqlite3
import threading
from flask import Flask
import telebot
from telebot import types

# --- CONFIGURATION ---
TOKEN = os.environ.get('BOT_TOKEN', 'YOUR_BOT_TOKEN_HERE')
ADMIN_ID = int(os.environ.get('ADMIN_ID', '0'))  # Put your Telegram User ID here

bot = telebot.TeleBot(TOKEN)
app = Flask('')

# --- FLASK SERVER FOR RENDER KEEP-ALIVE ---
@app.route('/')
def home():
    return "<h1>Hassany Store Bot is Alive!</h1>"

def run_flask():
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

# --- DATABASE SETUP ---
DB_NAME = 'bot_database.db'

def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    # Users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            balance REAL DEFAULT 0.0,
            points INTEGER DEFAULT 0,
            referred_by INTEGER
        )
    ''')
    # Orders table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            order_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            service_type TEXT,
            service_name TEXT,
            target_link TEXT,
            cost REAL,
            cost_type TEXT,
            status TEXT DEFAULT 'قيد الانتظار'
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# --- TEMPORARY USER STATES ---
USER_STATES = {}  # {user_id: {'action': 'waiting_for_link', 'service': '...', 'type': '...', 'cost': 0}}
ADMIN_STATES = {}

# --- KEYBOARDS (USER INTERFACE) ---
def get_main_keyboard(user_id):
    markup = types.InlineKeyboardMarkup(row_width=2)
    btn_free = types.InlineKeyboardButton("🎁 خدمات مجانية", callback_data="menu_free")
    btn_points = types.InlineKeyboardButton("🪙 رشق بالنقاط", callback_data="menu_points")
    btn_paid = types.InlineKeyboardButton("💎 خدمات مدفوعة V.I.P", callback_data="menu_paid")
    btn_account = types.InlineKeyboardButton("👤 حسابي", callback_data="menu_account")
    btn_orders = types.InlineKeyboardButton("🛍️ طلباتي", callback_data="menu_orders")
    
    markup.add(btn_free)
    markup.add(btn_points, btn_paid)
    markup.add(btn_account, btn_orders)
    
    if user_id == ADMIN_ID:
        btn_admin = types.InlineKeyboardButton("⚙️ لوحة التحكم للمطور", callback_data="menu_admin")
        markup.add(btn_admin)
        
    return markup

def get_back_button(target="main_menu"):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔙 العودة للقائمة الرئيسية", callback_data=target))
    return markup

# --- HOME COMMAND ---
@bot.message_handler(commands=['start'])
def start_command(message):
    user_id = message.from_user.id
    username = message.from_user.username or "بدون يوزر"
    
    # Handle Referral System
    args = message.text.split()
    referred_by = None
    if len(args) > 1 and args[1].isdigit():
        referred_by = int(args[1])
        if referred_by == user_id:
            referred_by = None

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()
    
    if not user:
        cursor.execute("INSERT INTO users (user_id, username, referred_by) VALUES (?, ?, ?)", 
                       (user_id, username, referred_by))
        conn.commit()
        
        # Reward the referrer
        if referred_by:
            cursor.execute("UPDATE users SET points = points + 5 WHERE user_id = ?", (referred_by,))
            conn.commit()
            try:
                bot.send_message(referred_by, f"🎁 دخل شخص جديد من رابطك! تم إضافه +5 نقاط إلى حسابك.")
            except:
                pass
    
    conn.close()
    
    welcome_text = (
        f"🙋‍♂️ أهلاً بك يا {message.from_user.first_name} في بوت الخدمات الحصري الخاص بنا!

"
        "🚀 نوفر لك أفضل خدمات الرشق والزيادات للمطويرين والمستخدمين:
"
        "🔹 خدمات مجانية تماماً
"
        "🔹 خدمات مقابل تجميع النقاط
"
        "🔹 خدمات مدفوعة بجودة وسرعة خارقة

"
        "👇 اختر القسم الذي تريده من الأزرار الشفافة أدناه:"
    )
    bot.send_message(user_id, welcome_text, reply_markup=get_main_keyboard(user_id))

# --- CALLBACK QUERY HANDLER ---
@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    user_id = call.from_user.id
    data = call.data
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()
    
    if not user:
        bot.answer_callback_query(call.id, "الرجاء إرسال /start أولاً لتسجيل حسابك.")
        conn.close()
        return

    # 1. Main Menu Back
    if data == "main_menu":
        USER_STATES.pop(user_id, None)
        bot.edit_message_text(
            chat_id=user_id,
            message_id=call.message.message_id,
            text="👇 اختر القسم المناسب لك من القائمة الرئيسية:",
            reply_markup=get_main_keyboard(user_id)
        )

    # 2. Free Services Menu
    elif data == "menu_free":
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("🎁 50 متابع انستقرام (مجاني)", callback_data="order_free_ig_50"),
            types.InlineKeyboardButton("🎁 100 مشاهدة تليجرام (مجاني)", callback_data="order_free_tg_100"),
            types.InlineKeyboardButton("🔙 عودة", callback_data="main_menu")
        )
        bot.edit_message_text("👇 اختر الخدمة المجانية المتاحة حالياً:", user_id, call.message.message_id, reply_markup=markup)

    # 3. Points Services Menu
    elif data == "menu_points":
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("🪙 200 متابع تليجرام [السعر: 50 نقطة]", callback_data="order_pts_tg_200"),
            types.InlineKeyboardButton("🪙 500 لايك انستقرام [السعر: 30 نقطة]", callback_data="order_pts_ig_500"),
            types.InlineKeyboardButton("🔙 عودة", callback_data="main_menu")
        )
        bot.edit_message_text(f"🪙 رصيد نقاطك الحالي: {user['points']} نقطة.
👇 اختر الخدمة المطلوبة:", user_id, call.message.message_id, reply_markup=markup)

    # 4. Paid Services Menu
    elif data == "menu_paid":
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("💎 1000 متابع انستقرام ثبات عالي [السعر: $1.50]", callback_data="order_paid_ig_1k"),
            types.InlineKeyboardButton("💎 1000 عضو قناة تليجرام حقيقيين [السعر: $2.00]", callback_data="order_paid_tg_1k"),
            types.InlineKeyboardButton("🔙 عودة", callback_data="main_menu")
        )
        bot.edit_message_text(f"💎 رصيدك النقدي الحالي: ${user['balance']:.2f}
👇 اختر باقة الـ VIP المطلوبة:", user_id, call.message.message_id, reply_markup=markup)

    # 5. Account Info
    elif data == "menu_account":
        bot_info = bot.get_me()
        ref_link = f"https://t.me/{bot_info.username}?start={user_id}"
        account_text = (
            f"👤 **معلومات حسابك الخاص:**

"
            f"🆔 معرف الحساب (ID): `{user_id}`
"
            f"🪙 نقاطك الحالية: {user['points']} نقطة
"
            f"💎 رصيدك المدفوع: ${user['balance']:.2f}

"
            f"🔗 **رابط الدعوة الخاص بك لربح النقاط:**
{ref_link}

"
            f"📢 *انشر الرابط، وكل شخص يدخل عن طريقك ستحصل على +5 نقاط مجانية لتطلب رشق مجاني!*"
        )
        bot.edit_message_text(account_text, user_id, call.message.message_id, parse_mode="Markdown", reply_markup=get_back_button())

    # 6. User Orders Status
    elif data == "menu_orders":
        cursor.execute("SELECT * FROM orders WHERE user_id = ? ORDER BY order_id DESC LIMIT 10", (user_id,))
        orders = cursor.fetchall()
        if not orders:
            orders_text = "🛍️ ليس لديك أي طلبات سابقة حالياً."
        else:
            orders_text = "🛍️ **آخر 10 طلبات لك وحالتها:**

"
            for o in orders:
                orders_text += f"🔢 طلب رقم: #{o['order_id']} | {o['service_name']}
🔗 الرابط: {o['target_link']}
📌 الحالة: **{o['status']}**
──────────────────
"
        bot.edit_message_text(orders_text, user_id, call.message.message_id, parse_mode="Markdown", reply_markup=get_back_button())

    # --- ORDER SELECTION PROCESSING ---
    elif data.startswith("order_"):
        parts = data.split("_")
        service_type = parts[1] # free, pts, paid
        
        # Define mock dynamic pricing/cost metadata
        service_meta = {
            "free_ig_50": {"name": "50 متابع انستقرام مجاني", "cost": 0, "cost_type": "free"},
            "free_tg_100": {"name": "100 مشاهدة تليجرام مجاني", "cost": 0, "cost_type": "free"},
            "pts_tg_200": {"name": "200 متابع تليجرام بالنقاط", "cost": 50, "cost_type": "points"},
            "pts_ig_500": {"name": "500 لايك انستقرام بالنقاط", "cost": 30, "cost_type": "points"},
            "paid_ig_1k": {"name": "1k متابع انستقرام ثبات V.I.P", "cost": 1.50, "cost_type": "balance"},
            "paid_tg_1k": {"name": "1k عضو تليجرام حقيقي V.I.P", "cost": 2.00, "cost_type": "balance"}
        }
        
        srv_key = "_".join(parts[2:])
        full_key = f"{service_type}_{srv_key}"
        
        if full_key in service_meta:
            meta = service_meta[full_key]
            
            # Check capabilities/balance
            if meta['cost_type'] == "points" and user['points'] < meta['cost']:
                bot.answer_callback_query(call.id, "❌ نقاطك غير كافية لإتمام هذا الطلب!", show_alert=True)
                conn.close()
                return
            elif meta['cost_type'] == "balance" and user['balance'] < meta['cost']:
                bot.answer_callback_query(call.id, "❌ رصيدك المالي غير كافٍ! يرجى التواصل مع المالك للشحن.", show_alert=True)
                conn.close()
                return
                
            # Set state to wait for link
            USER_STATES[user_id] = {
                'action': 'waiting_for_link',
                'service_type': service_type,
                'name': meta['name'],
                'cost': meta['cost'],
                'cost_type': meta['cost_type']
            }
            
            bot.edit_message_text(
                f"📥 لقد اخترت خدمة: **{meta['name']}**
"
                f"💰 التكلفة: {meta['cost']} ({meta['cost_type']})

"
                f"✍️ يرجى إرسال رابط الحساب أو القناة المراد رشقها الآن:",
                user_id, call.message.message_id, parse_mode="Markdown"
            )
            
    # --- ADMIN CALLBACKS ---
    elif data == "menu_admin" and user_id == ADMIN_ID:
        show_admin_panel(user_id, call.message.message_id)
        
    elif data == "admin_pending" and user_id == ADMIN_ID:
        cursor.execute("SELECT * FROM orders WHERE status = 'قيد الانتظار' ORDER BY order_id ASC LIMIT 5")
        pending_orders = cursor.fetchall()
        if not pending_orders:
            bot.edit_message_text("✅ لا توجد طلبات معلقة حالياً.", user_id, call.message.message_id, reply_markup=get_back_button("menu_admin"))
        else:
            bot.delete_message(user_id, call.message.message_id)
            for o in pending_orders:
                txt = (
                    f"⚙️ **طلب رشق جديد معلق**

"
                    f"🔢 رقم الطلب: #{o['order_id']}
"
                    f"👤 المستخدم (ID): `{o['user_id']}`
"
                    f"📦 الخدمة: {o['service_name']}
"
                    f"🔗 الرابط: `{o['target_link']}`"
                )
                m = types.InlineKeyboardMarkup()
                m.add(
                    types.InlineKeyboardButton("✅ تم التنفيذ والإكمال", callback_data=f"adm_approve_{o['order_id']}"),
                    types.InlineKeyboardButton("❌ رفض وإرجاع الرصيد", callback_data=f"adm_reject_{o['order_id']}")
                )
                bot.send_message(user_id, txt, parse_mode="Markdown", reply_markup=m)
            # Add a back button at the end
            bot.send_message(user_id, "تم عرض الطلبات المعلقة.", reply_markup=get_back_button("menu_admin"))
            
    elif data.startswith("adm_") and user_id == ADMIN_ID:
        # Action inside approval/rejection
        _, action, o_id = data.split("_")
        cursor.execute("SELECT * FROM orders WHERE order_id = ?", (o_id,))
        order = cursor.fetchone()
        
        if order:
            if action == "approve":
                cursor.execute("UPDATE orders SET status = 'مكتمل' WHERE order_id = ?", (o_id,))
                conn.commit()
                bot.edit_message_text(f"✅ تم تأشير الطلب #{o_id} كمكتمل.", user_id, call.message.message_id)
                try:
                    bot.send_message(order['user_id'], f"🎉 خبر سعيد! طلبك رقم #{o_id} الخاص بـ ({order['service_name']}) تم تنفيذه وإكماله بنجاح مبروك!")
                except: pass
            elif action == "reject":
                cursor.execute("UPDATE orders SET status = 'مرفوض ومسترجع' WHERE order_id = ?", (o_id,))
                # Refund balance/points
                if order['cost_type'] == 'points':
                    cursor.execute("UPDATE users SET points = points + ? WHERE user_id = ?", (order['cost'], order['user_id']))
                elif order['cost_type'] == 'balance':
                    cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (order['cost'], order['user_id']))
                conn.commit()
                bot.edit_message_text(f"❌ تم رفض الطلب #{o_id} وإرجاع التكلفة للمستخدم.", user_id, call.message.message_id)
                try:
                    bot.send_message(order['user_id'], f"⚠️ تم رفض طلبك رقم #{o_id} الخاص بـ ({order['service_name']}) من قبل الإدارة وتم إعادة الرصيد/النقاط إلى حسابك تلقائياً.")
                except: pass
                
    elif data == "admin_gift" and user_id == ADMIN_ID:
        ADMIN_STATES[user_id] = 'waiting_for_gift_data'
        bot.edit_message_text("✍️ أرسل الايدي الخاص بالمستخدم ومقدار الهدية بالشكل التالي:
`ID:Amount`
مثال لشحن رصيد مدفوع بقيمة 10 دولار:
`12345678:10`", user_id, call.message.message_id, parse_mode="Markdown")

    elif data == "admin_broadcast" and user_id == ADMIN_ID:
        ADMIN_STATES[user_id] = 'waiting_for_broadcast_text'
        bot.edit_message_text("✍️ أرسل نص الرسالة التي تريد إذاعتها لجميع مستخدمين البوت الآن:", user_id, call.message.message_id)

    conn.close()

def show_admin_panel(admin_id, msg_id=None):
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("📥 عرض الطلبات المعلقة", callback_data="admin_pending"),
        types.InlineKeyboardButton("🎁 شحن رصيد / إهداء نقاط", callback_data="admin_gift"),
        types.InlineKeyboardButton("📢 إرسال إذاعة جماعية", callback_data="admin_broadcast"),
        types.InlineKeyboardButton("🔙 العودة للرئيسية", callback_data="main_menu")
    )
    text = "⚙️ **أهلاً بك مطورنا في لوحة التحكم الإدارية:**

تستطيع من هنا التحكم بكامل طلبات الرشق والعمليات داخل البوت بسلاسة."
    if msg_id:
        bot.edit_message_text(text, admin_id, msg_id, parse_mode="Markdown", reply_markup=markup)
    else:
        bot.send_message(admin_id, text, parse_mode="Markdown", reply_markup=markup)

# --- USER TEXT RESPONSES / MULTI-STEP LOGIC ---
@bot.message_handler(func=lambda msg: True, content_types=['text'])
def handle_text_messages(message):
    user_id = message.from_user.id
    text = message.text
    
    # Check Admin Input State
    if user_id == ADMIN_ID and user_id in ADMIN_STATES:
        state = ADMIN_STATES[user_id]
        conn = get_db_connection()
        cursor = conn.cursor()
        
        if state == 'waiting_for_gift_data':
            ADMIN_STATES.pop(user_id, None)
            try:
                target_id, amount = text.split(":")
                target_id = int(target_id.strip())
                amount = float(amount.strip())
                
                cursor.execute("SELECT * FROM users WHERE user_id = ?", (target_id,))
                target_user = cursor.fetchone()
                if target_user:
                    # In this setup, let's treat floats as Balance and whole ints as points or just add to Balance
                    cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, target_id))
                    conn.commit()
                    bot.send_message(user_id, f"✅ تم بنجاح إضافة ${amount:.2f} إلى رصيد الحساب رقم `{target_id}`.")
                    try:
                        bot.send_message(target_id, f"💰 تم شحن حسابك بمبلغ قدره ${amount:.2f} من قبل الإدارة، جاهز للاستخدام الآن!")
                    except: pass
                else:
                    bot.send_message(user_id, "❌ لم يتم العثور على مستخدم بهذا الايدي في قاعدة البيانات.")
            except Exception as e:
                bot.send_message(user_id, f"❌ حدث خطأ في الصيغة يرجى المحاولة مجدداً. الخطأ: {e}")
                
        elif state == 'waiting_for_broadcast_text':
            ADMIN_STATES.pop(user_id, None)
            cursor.execute("SELECT user_id FROM users")
            all_users = cursor.fetchall()
            bot.send_message(user_id, f"📢 بدأت عملية الإذاعة إلى {len(all_users)} مستخدم...")
            count = 0
            for u in all_users:
                try:
                    bot.send_message(u['user_id'], text)
                    count += 1
                except: pass
            bot.send_message(user_id, f"✅ اكتملت الإذاعة بنجاح ووصلت الرسالة إلى {count} مستخدم بنجاح.")
            
        conn.close()
        show_admin_panel(user_id)
        return

    # Check User Input State (Link Submission)
    if user_id in USER_STATES and USER_STATES[user_id]['action'] == 'waiting_for_link':
        state_data = USER_STATES.pop(user_id)
        
        # Open database connection
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Deduct cost from the user
        if state_data['cost_type'] == 'points':
            cursor.execute("UPDATE users SET points = points - ? WHERE user_id = ?", (state_data['cost'], user_id))
        elif state_data['cost_type'] == 'balance':
            cursor.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (state_data['cost'], user_id))
            
        # Log the order
        cursor.execute(
            "INSERT INTO orders (user_id, service_type, service_name, target_link, cost, cost_type) VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, state_data['service_type'], state_data['name'], text, state_data['cost'], state_data['cost_type'])
        )
        conn.commit()
        order_id = cursor.lastrowid
        conn.close()
        
        # User Confirmation
        bot.send_message(
            user_id, 
            f"✅ **تم الشراء بنجاح!**

"
            f"🔢 رقم الطلب الخاص بك: `#{order_id}`
"
            f"📦 الخدمة: {state_data['name']}
"
            f"🔗 الرابط المرسل: `{text}`

"
            f"⏳ يرجى انتظار مدة التفعيل، ستصلك رسالة إشعار تلقائية فور اكتمال الرشق من قبل المطور.",
            parse_mode="Markdown",
            reply_markup=get_back_button()
        )
        
        # Notify Admin
        try:
            admin_alert = (
                f"🚨 **إشعار طلب رشق جديد!**

"
                f"🔢 رقم الطلب: #{order_id}
"
                f"👤 مرسل الطلب ID: `{user_id}`
"
                f"📦 الخدمة المطلوبة: {state_data['name']}
"
                f"🔗 الرابط المستهدف: `{text}`

"
                f"📥 ادخل على لوحة التحكم للمطور لإكمال التنفيذ أو الرفض."
            )
            bot.send_message(ADMIN_ID, admin_alert, parse_mode="Markdown")
        except:
            pass

# --- MAIN LOOP RUNNER ---
if __name__ == '__main__':
    print("Starting Flask web server...")
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    
    print("Bot loop started successfully...")
    bot.infinity_polling()
