#!/usr/bin/env python3
"""
Shruti Online Sarvice - FULL INTEGRATED Telegram Bot
Fixed: QR code generation, UPI payment, Admin panel
"""

import logging, json, os, asyncio, aiohttp, aiofiles
from datetime import datetime
from bs4 import BeautifulSoup
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputFile
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, ConversationHandler, filters, ContextTypes
)

# ════════════════════════════════════════════════════════════════
BOT_TOKEN        = "8789030708:AAE6Xv0ImgKHCcaw8eSqbvLj3P-QnaA2KOQ"
ADMIN_IDS        = [5482954908]
WEBSITE_URL      = "https://cscvleservice.beer"
ADMIN_PHONE      = "1234567890"
ADMIN_PASSWORD   = "03122010"
PAY0_MERCHANT_ID = "svVFRo76286320206024"
PAY0_API_KEY     = "238620578b32a062bb75f0ebcaeda57b"
PAY0_API_URL     = "https://pay0.shop/api"
UPI_ID           = "rtosarvice@ptyes"
UPI_NAME         = "Shruti Online Sarvice"
DB_FILE          = "bot_database.json"
# ════════════════════════════════════════════════════════════════

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

(AWAIT_RECHARGE_AMT, AWAIT_SERVICE_INPUT, AWAIT_ADMIN_PRICE,
 AWAIT_NEW_SVC, AWAIT_BROADCAST) = range(5)

ALL_SERVICES = {
    "pan": {
        "name": "💳 PAN Card Services", "emoji": "💳",
        "services": {
            "instant_pan":      {"name": "Pan Number Find (Aadhaar se)",  "price": 30,  "url": "/admin/instant_pan",      "field": "aadhaar_number", "label": "12-digit Aadhaar Number"},
            "pan_to_aadhaar":   {"name": "Pan To Aadhaar Number",         "price": 30,  "url": "/admin/pan_to_aadhaar",   "field": "pan_number",     "label": "PAN Number (e.g. ABCDE1234F)"},
            "pan_details_find": {"name": "Pan Details Find",              "price": 30,  "url": "/admin/pan_details",      "field": "pan_number",     "label": "PAN Number"},
            "pan_advance":      {"name": "Pan Advance",                   "price": 40,  "url": "/admin/pan_advance",      "field": "aadhaar_number", "label": "Aadhaar Number"},
            "pan_manual":       {"name": "Pan Manual",                    "price": 50,  "url": "/admin/pan_manual",       "field": "aadhaar_number", "label": "Aadhaar Number"},
            "gst_details":      {"name": "GST Details Find",              "price": 25,  "url": "/admin/gst_details",      "field": "gstin",          "label": "GSTIN Number"},
        }
    },
    "vehicle": {
        "name": "🏍️ Vehicle Services", "emoji": "🏍️",
        "services": {
            "rc_server1":  {"name": "RC Pdf Server 1",       "price": 20, "url": "/admin/rc_pdf_server1",  "field": "vehicle_number", "label": "Vehicle Number (e.g. DL01AB1234)"},
            "rc_server2":  {"name": "RC Pdf Server 2",       "price": 20, "url": "/admin/rc_pdf_server2",  "field": "vehicle_number", "label": "Vehicle Number"},
            "challan":     {"name": "Challan Instant",       "price": 15, "url": "/admin/challan_instant", "field": "vehicle_number", "label": "Vehicle Number"},
            "dl_server1":  {"name": "DL Pdf Server 1",       "price": 20, "url": "/admin/dl_pdf_server1",  "field": "dl_number",      "label": "DL Number"},
            "dl_server2":  {"name": "DL Pdf Blue Server 2",  "price": 20, "url": "/admin/dl_pdf_server2",  "field": "dl_number",      "label": "DL Number"},
            "ll_pdf":      {"name": "LL Pdf Request",        "price": 15, "url": "/admin/ll_pdf",          "field": "ll_number",      "label": "LL Number"},
        }
    },
    "voter": {
        "name": "🗳️ Voter Services", "emoji": "🗳️",
        "services": {
            "voter_original": {"name": "Voter Instant Original PDF", "price": 20, "url": "/admin/vot_org_instant", "field": "epic_number", "label": "EPIC/Voter ID Number"},
            "voter_advance":  {"name": "Voter Advance Instant",      "price": 25, "url": "/admin/voter_advance",   "field": "epic_number", "label": "EPIC Number"},
            "voter_manual":   {"name": "Voter Manual Instant",       "price": 30, "url": "/admin/voter_manual",    "field": "epic_number", "label": "EPIC Number"},
        }
    },
    "aadhaar": {
        "name": "🪪 Aadhaar Services", "emoji": "🪪",
        "services": {
            "aadhaar_download": {"name": "Aadhaar Download",   "price": 10, "url": "/admin/aadhaar_download", "field": "aadhaar_number", "label": "Aadhaar Number"},
            "aadhaar_pvc":      {"name": "Aadhaar PVC Card",   "price": 50, "url": "/admin/aadhaar_pvc",      "field": "aadhaar_number", "label": "Aadhaar Number"},
        }
    },
    "ration": {
        "name": "🍚 Ration Services", "emoji": "🍚",
        "services": {
            "ration_find": {"name": "Ration Card Find", "price": 10, "url": "/admin/ration_find", "field": "ration_number", "label": "Ration Card Number"},
        }
    },
    "electricity": {
        "name": "⚡ Electricity Bill", "emoji": "⚡",
        "services": {
            "elec_bill": {"name": "Electricity Bill Check", "price": 5, "url": "/admin/elec_bill", "field": "consumer_number", "label": "Consumer Number"},
        }
    },
}

# ── DB ────────────────────────────────────────────────────────
def load_db():
    if os.path.exists(DB_FILE):
        with open(DB_FILE) as f: return json.load(f)
    return {"users": {}, "orders": [], "prices": {}, "pending_payments": {}}

def save_db(db):
    with open(DB_FILE, "w") as f: json.dump(db, f, indent=2, ensure_ascii=False)

def get_user(uid):
    db = load_db(); uid = str(uid)
    if uid not in db["users"]:
        db["users"][uid] = {"wallet": 0.0, "name": "", "joined": datetime.now().strftime("%d-%m-%Y")}
        save_db(db)
    return db["users"][uid]

def update_wallet(uid, amount):
    db = load_db(); uid = str(uid)
    if uid not in db["users"]:
        db["users"][uid] = {"wallet": 0.0, "name": "", "joined": datetime.now().strftime("%d-%m-%Y")}
    db["users"][uid]["wallet"] = round(db["users"][uid]["wallet"] + amount, 2)
    save_db(db)
    return db["users"][uid]["wallet"]

def get_wallet(uid): return get_user(uid)["wallet"]

def get_price(svc_key):
    db = load_db()
    if svc_key in db.get("prices", {}): return db["prices"][svc_key]
    for cat in ALL_SERVICES.values():
        if svc_key in cat["services"]: return cat["services"][svc_key]["price"]
    return 0

def get_svc_info(svc_key):
    for cat in ALL_SERVICES.values():
        if svc_key in cat["services"]: return cat["services"][svc_key]
    return None

def save_order(order):
    db = load_db(); db["orders"].append(order); save_db(db)

def is_admin(uid): return uid in ADMIN_IDS

# ── Website Session ───────────────────────────────────────────
async def get_website_session():
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(f"{WEBSITE_URL}/auth") as r:
                html = await r.text()
                soup = BeautifulSoup(html, 'html.parser')
                csrf = ""
                t = soup.find('input', {'name': '_token'})
                if t: csrf = t.get('value', '')
                m = soup.find('meta', {'name': 'csrf-token'})
                if m: csrf = m.get('content', '')
            login_data = {'_token': csrf, 'phone': ADMIN_PHONE, 'password': ADMIN_PASSWORD}
            async with s.post(f"{WEBSITE_URL}/auth/login", data=login_data, allow_redirects=True) as r:
                cookies = {k: v.value for k, v in s.cookie_jar._cookies.get('cscvleservice.beer', {}).items()}
                return cookies
    except Exception as e:
        logger.error(f"Login error: {e}"); return {}

async def call_service_api(svc_key, user_input):
    svc = get_svc_info(svc_key)
    if not svc: return None, "Service nahi mili"
    cookies = await get_website_session()
    if not cookies: return None, "Website login fail"
    try:
        async with aiohttp.ClientSession(cookies=cookies) as s:
            url = f"{WEBSITE_URL}{svc['url']}"
            async with s.get(url) as r:
                html = await r.text()
                soup = BeautifulSoup(html, 'html.parser')
                csrf = ""
                t = soup.find('input', {'name': '_token'})
                if t: csrf = t.get('value', '')
            post_data = {'_token': csrf, svc['field']: user_input.strip()}
            async with s.post(url, data=post_data) as r:
                return await r.text(), None
    except Exception as e:
        logger.error(f"Service error: {e}"); return None, str(e)

def parse_service_result(svc_key, html):
    soup = BeautifulSoup(html, 'html.parser')
    result_text = ""; result_data = {}
    modal = soup.find('div', {'class': 'modal-body'}) or soup.find('div', {'id': 'resultModal'})
    if modal: result_text = modal.get_text(strip=True)
    alert = soup.find('div', {'class': lambda x: x and 'alert' in x})
    if alert: result_text = alert.get_text(strip=True)
    table = soup.find('table')
    if table:
        for row in table.find_all('tr'):
            cols = row.find_all(['td', 'th'])
            if len(cols) >= 2:
                k = cols[0].get_text(strip=True); v = cols[1].get_text(strip=True)
                if k and v: result_data[k] = v
    pdf_link = None
    for a in soup.find_all('a', href=True):
        if '.pdf' in a['href'].lower() or 'download' in a['href'].lower():
            pdf_link = a['href']
            if not pdf_link.startswith('http'): pdf_link = WEBSITE_URL + pdf_link
    is_success = any(kw.lower() in html.lower() for kw in ['success','found','CENPK','INSTANT','PAN No','RC','DL'])
    return {"success": is_success, "text": result_text, "data": result_data, "pdf_link": pdf_link}

# ── UPI Payment ───────────────────────────────────────────────
async def create_payment_order(uid, amount):
    order_id = f"WALLET_{uid}_{int(datetime.now().timestamp())}"
    
    # Try Pay0.shop API first
    try:
        async with aiohttp.ClientSession() as s:
            payload = {
                "merchant_id": PAY0_MERCHANT_ID,
                "api_key": PAY0_API_KEY,
                "amount": str(amount),
                "order_id": order_id,
                "customer_name": str(uid),
                "customer_email": f"{uid}@telegram.bot",
                "customer_mobile": "9999999999",
                "purpose": "Wallet Recharge",
                "redirect_url": "https://t.me/ShrutiSarviceBot",
            }
            async with s.post(f"{PAY0_API_URL}/create_order",
                              json=payload,
                              headers={"Content-Type": "application/json"},
                              timeout=aiohttp.ClientTimeout(total=8)) as r:
                data = await r.json()
                if data.get("status") == "success" or data.get("payment_url"):
                    pay_url = data.get("payment_url") or data.get("url", "")
                    return {
                        "order_id": order_id,
                        "payment_url": pay_url,
                        "upi_id": UPI_ID,
                        "qr_url": f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data=upi://pay?pa={UPI_ID}%26pn={UPI_NAME}%26am={amount}%26tn=Order_{order_id}%26cu=INR",
                    }
    except Exception as e:
        logger.error(f"Pay0 error: {e}")

    # Fallback: Direct UPI QR (always works!)
    upi_data = f"upi://pay?pa={UPI_ID}&pn={UPI_NAME}&am={amount}&tn=Wallet_{uid}&cu=INR"
    import urllib.parse
    qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data={urllib.parse.quote(upi_data)}"
    return {
        "order_id": order_id,
        "payment_url": None,
        "upi_id": UPI_ID,
        "qr_url": qr_url,
    }

async def verify_payment(order_id):
    try:
        async with aiohttp.ClientSession() as s:
            async with s.post(f"{PAY0_API_URL}/check_order",
                              json={"merchant_id": PAY0_MERCHANT_ID, "api_key": PAY0_API_KEY, "order_id": order_id},
                              timeout=aiohttp.ClientTimeout(total=8)) as r:
                data = await r.json()
                return data.get("status") == "success" or data.get("payment_status") == "paid"
    except: return False

# ── Keyboards ─────────────────────────────────────────────────
def main_kb(uid=None):
    wallet = get_wallet(uid) if uid else 0
    btns = [
        [InlineKeyboardButton(f"💰 Wallet: ₹{wallet}  |  ➕ Recharge", callback_data="wallet_menu")],
        [InlineKeyboardButton("💳 PAN Card",   callback_data="cat_pan"),
         InlineKeyboardButton("🏍️ Vehicle",    callback_data="cat_vehicle")],
        [InlineKeyboardButton("🗳️ Voter",       callback_data="cat_voter"),
         InlineKeyboardButton("🪪 Aadhaar",     callback_data="cat_aadhaar")],
        [InlineKeyboardButton("🍚 Ration",      callback_data="cat_ration"),
         InlineKeyboardButton("⚡ Electricity", callback_data="cat_electricity")],
        [InlineKeyboardButton("📋 Price List",  callback_data="price_list"),
         InlineKeyboardButton("📦 My Orders",   callback_data="my_orders")],
    ]
    if uid and is_admin(uid):
        btns.append([InlineKeyboardButton("⚙️ ADMIN PANEL 🔧", callback_data="admin_panel")])
    return InlineKeyboardMarkup(btns)

# ── /start ────────────────────────────────────────────────────
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    db = load_db(); uid = str(u.id)
    if uid not in db["users"]:
        db["users"][uid] = {"wallet": 0.0, "name": u.first_name, "joined": datetime.now().strftime("%d-%m-%Y")}
        save_db(db)
    wallet = get_wallet(u.id)
    await update.message.reply_text(
        f"🙏 *Namaste {u.first_name} ji!*\n\n"
        f"Welcome to *Shruti Online Sarvice* 🇮🇳\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"💰 Wallet Balance: *₹{wallet}*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"Pehle wallet recharge karein, phir service use karein 👇",
        parse_mode="Markdown", reply_markup=main_kb(u.id))

# ── Wallet ────────────────────────────────────────────────────
async def wallet_menu(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    wallet = get_wallet(q.from_user.id)
    await q.edit_message_text(
        f"💰 *Wallet Recharge*\n\nCurrent Balance: *₹{wallet}*\n\nKitna recharge karna hai?",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ ₹50",  callback_data="recharge_50"),
             InlineKeyboardButton("➕ ₹100", callback_data="recharge_100")],
            [InlineKeyboardButton("➕ ₹200", callback_data="recharge_200"),
             InlineKeyboardButton("➕ ₹500", callback_data="recharge_500")],
            [InlineKeyboardButton("➕ Custom Amount", callback_data="recharge_custom")],
            [InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")],
        ]))

async def recharge_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    if q.data == "recharge_custom":
        await q.edit_message_text(
            "💰 Kitne rupye recharge karne hain?\n_(Minimum ₹10, sirf number likho)_",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="wallet_menu")]]))
        return AWAIT_RECHARGE_AMT
    amount = int(q.data.replace("recharge_", ""))
    await process_recharge(q, amount, ctx)

async def recharge_amount_recv(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    t = update.message.text.strip()
    if not t.isdigit() or int(t) < 10:
        await update.message.reply_text("❌ Valid amount daalo (minimum ₹10)")
        return AWAIT_RECHARGE_AMT
    # Create fake query-like object
    class FakeQ:
        from_user = update.effective_user
        async def edit_message_text(self, *a, **kw): pass
    await process_recharge_msg(update.message.reply_text, update.effective_user.id, int(t), ctx)
    return ConversationHandler.END

async def process_recharge(q, amount, ctx):
    uid = q.from_user.id
    payment = await create_payment_order(uid, amount)
    order_id = payment["order_id"]
    db = load_db()
    db["pending_payments"][order_id] = {"uid": str(uid), "amount": amount, "time": datetime.now().strftime("%d-%m-%Y %H:%M")}
    save_db(db)

    qr_url = payment.get("qr_url", "")
    upi_id = payment.get("upi_id", UPI_ID)
    pay_url = payment.get("payment_url")

    text = (
        f"💳 *UPI Payment — ₹{amount}*\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"📋 Order ID: `{order_id}`\n\n"
        f"🔷 UPI ID par pay karein:\n`{upi_id}`\n\n"
        f"💰 Amount: *₹{amount}*\n\n"
        f"👇 *QR Code scan karein ya UPI ID use karein*\n\n"
        f"⚠️ Payment ke baad *'✅ Maine Pay Kar Diya'* dabayein"
    )
    btns = []
    if pay_url:
        btns.append([InlineKeyboardButton("💳 Payment Link", url=pay_url)])
    btns.append([InlineKeyboardButton("✅ Maine Pay Kar Diya", callback_data=f"verify_{order_id}")])
    btns.append([InlineKeyboardButton("❌ Cancel", callback_data="wallet_menu")])

    # Send QR as photo
    try:
        await q.message.reply_photo(
            photo=qr_url,
            caption=text,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(btns)
        )
        await q.edit_message_text("👆 QR Code upar bheja gaya hai!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]]))
    except Exception as e:
        logger.error(f"QR send error: {e}")
        await q.edit_message_text(
            text + f"\n\n🔗 [QR Code Yahan Dekho]({qr_url})",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(btns),
            disable_web_page_preview=False
        )

async def process_recharge_msg(reply_func, uid, amount, ctx):
    payment = await create_payment_order(uid, amount)
    order_id = payment["order_id"]
    db = load_db()
    db["pending_payments"][order_id] = {"uid": str(uid), "amount": amount, "time": datetime.now().strftime("%d-%m-%Y %H:%M")}
    save_db(db)
    qr_url = payment.get("qr_url", "")
    upi_id = payment.get("upi_id", UPI_ID)
    text = (f"💳 *UPI Payment — ₹{amount}*\n📋 Order: `{order_id}`\n\n"
            f"UPI ID: `{upi_id}`\n💰 Amount: *₹{amount}*\n\n"
            f"⚠️ Pay karke '✅ Maine Pay Kar Diya' dabayein\n\n🔗 QR: {qr_url}")
    btns = [[InlineKeyboardButton("✅ Maine Pay Kar Diya", callback_data=f"verify_{order_id}")],
            [InlineKeyboardButton("❌ Cancel", callback_data="wallet_menu")]]
    await reply_func(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(btns))

async def verify_payment_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer("⏳ Checking...")
    uid = q.from_user.id
    order_id = q.data.replace("verify_", "")
    db = load_db()
    pending = db["pending_payments"].get(order_id)
    if not pending:
        await q.edit_message_text("❌ Order nahi mila."); return
    paid = await verify_payment(order_id)
    if paid:
        amount = pending["amount"]
        new_bal = update_wallet(uid, amount)
        del db["pending_payments"][order_id]; save_db(db)
        await q.edit_message_text(
            f"✅ *Payment Confirmed!*\n💰 ₹{amount} add ho gaye!\nBalance: *₹{new_bal}*",
            parse_mode="Markdown", reply_markup=main_kb(uid))
    else:
        await q.edit_message_text(
            f"⏳ *Payment confirm nahi hua*\n\nOrder: `{order_id}`\nAmount: ₹{pending['amount']}\n\n"
            f"2-3 min wait karke phir check karein.\nYa admin ko screenshot bhejein.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 Phir Check Karein", callback_data=f"verify_{order_id}")],
                [InlineKeyboardButton("📸 Admin ko Batao", callback_data="contact_admin")],
                [InlineKeyboardButton("❌ Cancel", callback_data="wallet_menu")],
            ]))

# ── Services ──────────────────────────────────────────────────
async def show_cat(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    cat_key = q.data.replace("cat_", ""); cat = ALL_SERVICES.get(cat_key)
    if not cat: return
    uid = q.from_user.id; wallet = get_wallet(uid)
    text = f"{cat['name']}\n━━━━━━━━━━━━━━━━\n💰 Balance: *₹{wallet}*\n\n"
    btns = []
    for sk, sv in cat["services"].items():
        p = get_price(sk); icon = "✅" if wallet >= p else "❌"
        text += f"{icon} {sv['name']} — *₹{p}*\n"
        btns.append([InlineKeyboardButton(f"{icon} {sv['name']}  ₹{p}", callback_data=f"svc_{sk}")])
    text += "\n✅=Balance enough | ❌=Recharge needed"
    btns.append([InlineKeyboardButton("➕ Recharge", callback_data="wallet_menu")])
    btns.append([InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")])
    await q.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(btns))

async def service_select(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    uid = q.from_user.id; sk = q.data.replace("svc_", "")
    svc = get_svc_info(sk)
    if not svc: await q.edit_message_text("❌ Service nahi mili"); return
    price = get_price(sk); wallet = get_wallet(uid)
    if wallet < price:
        await q.edit_message_text(
            f"❌ *Balance Kam Hai*\nRequired: *₹{price}* | Balance: *₹{wallet}*",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("➕ Recharge Karein", callback_data="wallet_menu")],
                [InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")],
            ])); return
    ctx.user_data["selected_svc"] = sk
    await q.edit_message_text(
        f"📝 *{svc['name']}*\n💰 Charge: *₹{price}* | Balance: *₹{wallet}*\n\n👇 *{svc['label']} daalo:*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="main_menu")]]))
    return AWAIT_SERVICE_INPUT

async def service_input_recv(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id; user_input = update.message.text.strip()
    sk = ctx.user_data.get("selected_svc"); svc = get_svc_info(sk)
    price = get_price(sk); wallet = get_wallet(uid)
    if not sk or not svc:
        await update.message.reply_text("❌ Timeout. /start se dobara try karein.")
        return ConversationHandler.END
    if wallet < price:
        await update.message.reply_text("❌ Balance kam hai.", reply_markup=main_kb(uid))
        return ConversationHandler.END
    new_balance = update_wallet(uid, -price)
    oid = f"ORD{int(datetime.now().timestamp())}"
    await update.message.reply_text(
        f"⏳ *Processing...*\n📌 {svc['name']}\n🔍 `{user_input}`\n💰 ₹{price} deducted",
        parse_mode="Markdown")
    html_result, error = await call_service_api(sk, user_input)
    if error or not html_result:
        update_wallet(uid, price)
        await update.message.reply_text(
            f"❌ *Error*\n{error}\n💰 ₹{price} refund ho gaye.",
            parse_mode="Markdown", reply_markup=main_kb(uid))
        return ConversationHandler.END
    result = parse_service_result(sk, html_result)
    save_order({"order_id": oid, "uid": str(uid), "service": svc['name'],
                "input": user_input, "price": price,
                "status": "success" if result["success"] else "failed",
                "time": datetime.now().strftime("%d-%m-%Y %H:%M")})
    if result["success"]:
        rt = f"✅ *{svc['name']} — Result*\n━━━━━━━━━━━━━━━━\n\n"
        if result["text"]: rt += f"{result['text']}\n\n"
        if result["data"]:
            for k, v in result["data"].items(): rt += f"📌 *{k}:* {v}\n"
        rt += f"\n🆔 Order: `{oid}`\n💰 Balance: ₹{new_balance}"
        btns = [[InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]]
        if result["pdf_link"]: btns.insert(0, [InlineKeyboardButton("📄 PDF Download", url=result["pdf_link"])])
        await update.message.reply_text(rt, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(btns))
    else:
        update_wallet(uid, price)
        await update.message.reply_text(
            f"❌ *Result nahi mila*\nInput check karein.\n💰 ₹{price} refund ho gaye.",
            parse_mode="Markdown", reply_markup=main_kb(uid))
    return ConversationHandler.END

# ── My Orders ─────────────────────────────────────────────────
async def my_orders(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    uid = str(q.from_user.id); db = load_db()
    my = [o for o in db["orders"] if o.get("uid") == uid][-5:][::-1]
    text = "📦 *Aapke Recent Orders*\n━━━━━━━━━━━━━━━━\n\n" if my else "📦 Koi orders nahi."
    for o in my:
        icon = "✅" if o["status"] == "success" else "❌"
        text += f"{icon} {o['service']}\n🔍 `{o['input']}` | 💰 ₹{o['price']}\n🕐 {o['time']}\n\n"
    await q.edit_message_text(text, parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]]))

# ── Price List ────────────────────────────────────────────────
async def price_list(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    text = "📋 *Price List*\n━━━━━━━━━━━━━━━━\n\n"
    for cat in ALL_SERVICES.values():
        text += f"{cat['name']}\n"
        for sk, sv in cat["services"].items(): text += f"  • {sv['name']} — *₹{get_price(sk)}*\n"
        text += "\n"
    await q.edit_message_text(text, parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]]))

# ── Admin Panel ───────────────────────────────────────────────
async def admin_panel_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    if not is_admin(q.from_user.id): await q.answer("❌ Access Denied!", show_alert=True); return
    db = load_db()
    await q.edit_message_text(
        f"⚙️ *Admin Panel*\n━━━━━━━━━━━━━━━━\n"
        f"👥 Users: {len(db['users'])}\n"
        f"📦 Orders: {len(db['orders'])}\n"
        f"💰 Revenue: ₹{sum(o['price'] for o in db['orders'] if o.get('status')=='success')}\n"
        f"⏳ Pending: {len(db['pending_payments'])}",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("💰 Price Manage",      callback_data="admin_prices")],
            [InlineKeyboardButton("📦 All Orders",        callback_data="admin_orders")],
            [InlineKeyboardButton("👥 All Users",         callback_data="admin_users")],
            [InlineKeyboardButton("⏳ Pending Payments",  callback_data="admin_pending")],
            [InlineKeyboardButton("📢 Broadcast",         callback_data="admin_broadcast")],
            [InlineKeyboardButton("🏠 Main Menu",         callback_data="main_menu")],
        ]))

async def admin_prices_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    if not is_admin(q.from_user.id): return
    btns = [[InlineKeyboardButton(cat["name"], callback_data=f"admincat_{ck}")] for ck, cat in ALL_SERVICES.items()]
    btns.append([InlineKeyboardButton("🔙 Back", callback_data="admin_panel")])
    await q.edit_message_text("💰 Category choose karein:", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(btns))

async def admin_price_cat(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    if not is_admin(q.from_user.id): return
    ck = q.data.replace("admincat_",""); cat = ALL_SERVICES.get(ck)
    btns = [[InlineKeyboardButton(f"✏️ {sv['name']}  ₹{get_price(sk)}", callback_data=f"setprice_{sk}")]
            for sk, sv in cat["services"].items()]
    btns.append([InlineKeyboardButton("🔙 Back", callback_data="admin_prices")])
    await q.edit_message_text(f"{cat['name']}", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(btns))

async def set_price_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    if not is_admin(q.from_user.id): return
    sk = q.data.replace("setprice_",""); svc = get_svc_info(sk)
    ctx.user_data["psk"] = sk
    await q.edit_message_text(
        f"✏️ *{svc['name']}*\nCurrent: *₹{get_price(sk)}*\n\nNaya price daalo:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="admin_prices")]]))
    return AWAIT_ADMIN_PRICE

async def set_price_save(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return ConversationHandler.END
    t = update.message.text.strip()
    if not t.isdigit(): await update.message.reply_text("❌ Sirf number!"); return AWAIT_ADMIN_PRICE
    sk = ctx.user_data["psk"]; svc = get_svc_info(sk)
    db = load_db()
    if "prices" not in db: db["prices"] = {}
    db["prices"][sk] = int(t); save_db(db)
    await update.message.reply_text(
        f"✅ *Price Updated!*\n{svc['name']}\n💰 New: *₹{t}*", parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⚙️ Admin Panel", callback_data="admin_panel")]]))
    return ConversationHandler.END

async def admin_orders_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    if not is_admin(q.from_user.id): return
    db = load_db(); recent = db["orders"][-10:][::-1]
    text = f"📦 *Orders ({len(recent)})*\n━━━━━━━━━━━━━━━━\n\n"
    for o in recent:
        icon = "✅" if o.get("status")=="success" else "❌"
        text += f"{icon} {o['service']}\n👤 {o.get('uid','')} | 💰 ₹{o['price']} | 🕐 {o['time']}\n\n"
    await q.edit_message_text(text[:4000], parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Admin Panel", callback_data="admin_panel")]]))

async def admin_users_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    if not is_admin(q.from_user.id): return
    db = load_db()
    text = f"👥 *Users ({len(db['users'])})*\n━━━━━━━━━━━━━━━━\n\n"
    for uid, u in list(db["users"].items())[-20:]:
        text += f"👤 `{uid}` | 💰 ₹{u['wallet']} | {u.get('joined','?')}\n"
    await q.edit_message_text(text[:4000], parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Admin Panel", callback_data="admin_panel")]]))

async def admin_pending_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    if not is_admin(q.from_user.id): return
    db = load_db(); pending = db.get("pending_payments", {})
    if not pending:
        text = "✅ Koi pending payment nahi!"
        btns = [[InlineKeyboardButton("🔙 Admin Panel", callback_data="admin_panel")]]
    else:
        text = f"⏳ *Pending ({len(pending)})*\n━━━━━━━━━━━━━━━━\n\n"
        btns = []
        for oid, p in pending.items():
            text += f"👤 {p['uid']} | 💰 ₹{p['amount']} | 🕐 {p['time']}\n"
            btns.append([InlineKeyboardButton(
                f"✅ Approve ₹{p['amount']} — User {p['uid']}",
                callback_data=f"approve_{p['uid']}_{p['amount']}_{oid}")])
        btns.append([InlineKeyboardButton("🔙 Admin Panel", callback_data="admin_panel")])
    await q.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(btns))

async def admin_manual_approve(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    if not is_admin(q.from_user.id): return
    parts = q.data.split("_")
    target_uid = parts[1]; amount = int(parts[2]); oid = parts[3]
    new_bal = update_wallet(int(target_uid), amount)
    db = load_db()
    if oid in db.get("pending_payments", {}): del db["pending_payments"][oid]; save_db(db)
    await q.edit_message_text(f"✅ ₹{amount} added! Balance: ₹{new_bal}")
    try:
        await ctx.bot.send_message(int(target_uid),
            f"✅ *Wallet Recharge!*\n💰 ₹{amount} add ho gaye!\nBalance: *₹{new_bal}*",
            parse_mode="Markdown", reply_markup=main_kb(int(target_uid)))
    except: pass

async def admin_broadcast_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    if not is_admin(q.from_user.id): return
    await q.edit_message_text("📢 *Broadcast*\n\nSabhi users ko message likhein:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="admin_panel")]]))
    return AWAIT_BROADCAST

async def admin_broadcast_send(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return ConversationHandler.END
    msg = update.message.text; db = load_db(); sent = 0; failed = 0
    for uid in db["users"]:
        try:
            await ctx.bot.send_message(int(uid), f"📢 *Shruti Online Sarvice*\n\n{msg}", parse_mode="Markdown")
            sent += 1; await asyncio.sleep(0.05)
        except: failed += 1
    await update.message.reply_text(f"✅ Sent: {sent} | ❌ Failed: {failed}",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⚙️ Admin Panel", callback_data="admin_panel")]]))
    return ConversationHandler.END

async def main_menu_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    uid = q.from_user.id
    await q.edit_message_text(
        f"🏠 *Main Menu*\n💰 Balance: *₹{get_wallet(uid)}*\n\nService choose karein 👇",
        parse_mode="Markdown", reply_markup=main_kb(uid))

async def contact_admin_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    await q.edit_message_text(
        "📞 *Admin Contact*\n\nPayment screenshot admin ko bhejein — woh manually add kar denge.",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]]))

async def unknown(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🤔 /start likhein", reply_markup=main_kb(update.effective_user.id))

# ── MAIN ──────────────────────────────────────────────────────
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(service_select, pattern="^svc_")],
        states={AWAIT_SERVICE_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, service_input_recv)]},
        fallbacks=[], per_user=True))
    app.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(recharge_handler, pattern="^recharge_custom$")],
        states={AWAIT_RECHARGE_AMT: [MessageHandler(filters.TEXT & ~filters.COMMAND, recharge_amount_recv)]},
        fallbacks=[], per_user=True))
    app.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(set_price_start, pattern="^setprice_")],
        states={AWAIT_ADMIN_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_price_save)]},
        fallbacks=[], per_user=True))
    app.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_broadcast_start, pattern="^admin_broadcast$")],
        states={AWAIT_BROADCAST: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_broadcast_send)]},
        fallbacks=[], per_user=True))

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(main_menu_cb,       pattern="^main_menu$"))
    app.add_handler(CallbackQueryHandler(wallet_menu,         pattern="^wallet_menu$"))
    app.add_handler(CallbackQueryHandler(recharge_handler,    pattern="^recharge_"))
    app.add_handler(CallbackQueryHandler(verify_payment_cb,   pattern="^verify_"))
    app.add_handler(CallbackQueryHandler(admin_manual_approve,pattern="^approve_"))
    app.add_handler(CallbackQueryHandler(show_cat,            pattern="^cat_"))
    app.add_handler(CallbackQueryHandler(price_list,          pattern="^price_list$"))
    app.add_handler(CallbackQueryHandler(my_orders,           pattern="^my_orders$"))
    app.add_handler(CallbackQueryHandler(admin_panel_cb,      pattern="^admin_panel$"))
    app.add_handler(CallbackQueryHandler(admin_prices_cb,     pattern="^admin_prices$"))
    app.add_handler(CallbackQueryHandler(admin_price_cat,     pattern="^admincat_"))
    app.add_handler(CallbackQueryHandler(admin_orders_cb,     pattern="^admin_orders$"))
    app.add_handler(CallbackQueryHandler(admin_users_cb,      pattern="^admin_users$"))
    app.add_handler(CallbackQueryHandler(admin_pending_cb,    pattern="^admin_pending$"))
    app.add_handler(CallbackQueryHandler(contact_admin_cb,    pattern="^contact_admin$"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, unknown))

    print("✅ Shruti Online Sarvice Bot chal raha hai...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
