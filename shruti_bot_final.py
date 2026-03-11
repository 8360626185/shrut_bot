#!/usr/bin/env python3
"""
Shruti Online Sarvice - FULL INTEGRATED Telegram Bot
- Website session login (auto)
- Wallet system (UPI QR via Pay0.shop)
- Service request → wallet deduct → result Telegram par
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
#   ⚙️  CONFIGURATION — APNI DETAILS YAHAN HAIN (already filled)
# ════════════════════════════════════════════════════════════════
BOT_TOKEN        = "8789030708:AAE6Xv0ImgKHCcaw8eSqbvLj3P-QnaA2KOQ"   # @BotFather se lo
ADMIN_IDS        = [8789030708]                  # Apna Telegram ID

WEBSITE_URL      = "https://cscvleservice.beer"
ADMIN_PHONE      = "1234567890"
ADMIN_PASSWORD   = "03122010"

PAY0_MERCHANT_ID = "svVFRo76286320206024"
PAY0_API_KEY     = "238620578b32a062bb75f0ebcaeda57b"
PAY0_API_URL     = "https://pay0.shop/api"

DB_FILE          = "bot_database.json"
# ════════════════════════════════════════════════════════════════

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# Conversation states
(AWAIT_RECHARGE_AMT, AWAIT_SERVICE_INPUT, AWAIT_ADMIN_PRICE,
 AWAIT_NEW_SVC, AWAIT_BROADCAST) = range(5)

# ─── ALL SERVICES ────────────────────────────────────────────────────────────
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
            "rc_server1":       {"name": "RC Pdf Server 1",               "price": 20,  "url": "/admin/rc_pdf_server1",   "field": "vehicle_number", "label": "Vehicle Number (e.g. DL01AB1234)"},
            "rc_server2":       {"name": "RC Pdf Server 2",               "price": 20,  "url": "/admin/rc_pdf_server2",   "field": "vehicle_number", "label": "Vehicle Number"},
            "challan":          {"name": "Challan Instant",               "price": 15,  "url": "/admin/challan_instant",  "field": "vehicle_number", "label": "Vehicle Number"},
            "dl_server1":       {"name": "DL Pdf Server 1",               "price": 20,  "url": "/admin/dl_pdf_server1",   "field": "dl_number",      "label": "DL Number"},
            "dl_server2":       {"name": "DL Pdf Blue Server 2",          "price": 20,  "url": "/admin/dl_pdf_server2",   "field": "dl_number",      "label": "DL Number"},
            "ll_pdf":           {"name": "LL Pdf Request",                "price": 15,  "url": "/admin/ll_pdf",           "field": "ll_number",      "label": "LL Number"},
        }
    },
    "voter": {
        "name": "🗳️ Voter Services", "emoji": "🗳️",
        "services": {
            "voter_original":   {"name": "Voter Instant Original PDF",    "price": 20,  "url": "/admin/vot_org_instant",  "field": "epic_number",    "label": "EPIC/Voter ID Number"},
            "voter_advance":    {"name": "Voter Advance Instant",         "price": 25,  "url": "/admin/voter_advance",    "field": "epic_number",    "label": "EPIC Number"},
            "voter_manual":     {"name": "Voter Manual Instant",          "price": 30,  "url": "/admin/voter_manual",     "field": "epic_number",    "label": "EPIC Number"},
        }
    },
    "aadhaar": {
        "name": "🪪 Aadhaar Services", "emoji": "🪪",
        "services": {
            "aadhaar_download": {"name": "Aadhaar Download",              "price": 10,  "url": "/admin/aadhaar_download", "field": "aadhaar_number", "label": "Aadhaar Number"},
            "aadhaar_pvc":      {"name": "Aadhaar PVC Card",              "price": 50,  "url": "/admin/aadhaar_pvc",      "field": "aadhaar_number", "label": "Aadhaar Number"},
        }
    },
    "ration": {
        "name": "🍚 Ration Services", "emoji": "🍚",
        "services": {
            "ration_find":      {"name": "Ration Card Find",              "price": 10,  "url": "/admin/ration_find",      "field": "ration_number",  "label": "Ration Card Number"},
        }
    },
    "electricity": {
        "name": "⚡ Electricity Bill", "emoji": "⚡",
        "services": {
            "elec_bill":        {"name": "Electricity Bill Check",        "price": 5,   "url": "/admin/elec_bill",        "field": "consumer_number","label": "Consumer Number"},
        }
    },
}

# ════════════════════════════════════════════════════════════════
#   DATABASE (JSON file based)
# ════════════════════════════════════════════════════════════════
def load_db():
    if os.path.exists(DB_FILE):
        with open(DB_FILE) as f:
            return json.load(f)
    return {"users": {}, "orders": [], "prices": {}, "pending_payments": {}}

def save_db(db):
    with open(DB_FILE, "w") as f:
        json.dump(db, f, indent=2, ensure_ascii=False)

def get_user(uid):
    db = load_db()
    uid = str(uid)
    if uid not in db["users"]:
        db["users"][uid] = {"wallet": 0.0, "name": "", "joined": datetime.now().strftime("%d-%m-%Y")}
        save_db(db)
    return db["users"][uid]

def update_wallet(uid, amount):
    """amount positive = credit, negative = debit"""
    db = load_db()
    uid = str(uid)
    if uid not in db["users"]:
        db["users"][uid] = {"wallet": 0.0, "name": "", "joined": datetime.now().strftime("%d-%m-%Y")}
    db["users"][uid]["wallet"] = round(db["users"][uid]["wallet"] + amount, 2)
    save_db(db)
    return db["users"][uid]["wallet"]

def get_wallet(uid):
    return get_user(uid)["wallet"]

def get_price(svc_key):
    db = load_db()
    if svc_key in db.get("prices", {}):
        return db["prices"][svc_key]
    for cat in ALL_SERVICES.values():
        if svc_key in cat["services"]:
            return cat["services"][svc_key]["price"]
    return 0

def get_svc_info(svc_key):
    for cat in ALL_SERVICES.values():
        if svc_key in cat["services"]:
            return cat["services"][svc_key]
    return None

def save_order(order):
    db = load_db()
    db["orders"].append(order)
    save_db(db)

def is_admin(uid): return uid in ADMIN_IDS

# ════════════════════════════════════════════════════════════════
#   WEBSITE SESSION (Auto login)
# ════════════════════════════════════════════════════════════════
_website_session = None
_session_cookies = {}

async def get_website_session():
    """Login to website and get session cookies"""
    global _session_cookies
    try:
        async with aiohttp.ClientSession() as s:
            # Get CSRF token
            async with s.get(f"{WEBSITE_URL}/auth") as r:
                html = await r.text()
                soup = BeautifulSoup(html, 'html.parser')
                csrf = ""
                t = soup.find('input', {'name': '_token'})
                if t: csrf = t.get('value', '')
                m = soup.find('meta', {'name': 'csrf-token'})
                if m: csrf = m.get('content', '')
                cookies = dict(r.cookies)

            # Login
            login_data = {
                '_token': csrf,
                'phone': ADMIN_PHONE,
                'password': ADMIN_PASSWORD,
            }
            async with s.post(f"{WEBSITE_URL}/auth/login",
                              data=login_data,
                              cookies=cookies,
                              allow_redirects=True) as r:
                _session_cookies = {k: v.value for k, v in s.cookie_jar._cookies.get('cscvleservice.beer', {}).items()}
                logger.info(f"Login status: {r.status}, cookies: {list(_session_cookies.keys())}")
                return _session_cookies
    except Exception as e:
        logger.error(f"Login error: {e}")
        return {}

async def call_service_api(svc_key, user_input):
    """Call website service and get result"""
    svc = get_svc_info(svc_key)
    if not svc:
        return None, "Service nahi mili"

    cookies = await get_website_session()
    if not cookies:
        return None, "Website login fail"

    try:
        async with aiohttp.ClientSession(cookies=cookies) as s:
            url = f"{WEBSITE_URL}{svc['url']}"

            # GET page for CSRF
            async with s.get(url) as r:
                html = await r.text()
                soup = BeautifulSoup(html, 'html.parser')
                csrf = ""
                t = soup.find('input', {'name': '_token'})
                if t: csrf = t.get('value', '')

            # POST service request
            post_data = {
                '_token': csrf,
                svc['field']: user_input.strip(),
            }
            async with s.post(url, data=post_data) as r:
                result_html = await r.text()
                return result_html, None

    except Exception as e:
        logger.error(f"Service API error: {e}")
        return None, str(e)

def parse_service_result(svc_key, html):
    """Parse result from HTML response"""
    soup = BeautifulSoup(html, 'html.parser')

    # Check for success modal / alert
    result_text = ""
    result_data = {}

    # Modal content
    modal = soup.find('div', {'class': 'modal-body'}) or soup.find('div', {'id': 'resultModal'})
    if modal:
        result_text = modal.get_text(strip=True)

    # Alert success
    alert = soup.find('div', {'class': lambda x: x and 'alert' in x})
    if alert:
        result_text = alert.get_text(strip=True)

    # Table data (like RC, DL details)
    table = soup.find('table')
    if table:
        rows = table.find_all('tr')
        for row in rows:
            cols = row.find_all(['td', 'th'])
            if len(cols) >= 2:
                key = cols[0].get_text(strip=True)
                val = cols[1].get_text(strip=True)
                if key and val:
                    result_data[key] = val

    # PDF link
    pdf_link = None
    for a in soup.find_all('a', href=True):
        if '.pdf' in a['href'].lower() or 'download' in a['href'].lower():
            pdf_link = a['href']
            if not pdf_link.startswith('http'):
                pdf_link = WEBSITE_URL + pdf_link

    # Success check
    success_keywords = ['success', 'found', 'CENPK', 'INSTANT', 'PAN No', 'RC', 'DL']
    is_success = any(kw.lower() in html.lower() for kw in success_keywords)

    return {
        "success": is_success,
        "text": result_text,
        "data": result_data,
        "pdf_link": pdf_link,
        "raw_html": html[:500]
    }

# ════════════════════════════════════════════════════════════════
#   PAY0.SHOP PAYMENT INTEGRATION
# ════════════════════════════════════════════════════════════════
async def create_payment_order(uid, amount, purpose="Wallet Recharge"):
    """Create UPI payment order via Pay0.shop"""
    try:
        order_id = f"WALLET_{uid}_{int(datetime.now().timestamp())}"
        async with aiohttp.ClientSession() as s:
            payload = {
                "merchant_id": PAY0_MERCHANT_ID,
                "api_key": PAY0_API_KEY,
                "amount": str(amount),
                "order_id": order_id,
                "customer_name": str(uid),
                "customer_email": f"{uid}@telegram.bot",
                "customer_mobile": "9999999999",
                "purpose": purpose,
                "redirect_url": f"https://t.me/YourBotUsername",
                "webhook_url": "",  # optional
            }
            # Try Pay0.shop API
            async with s.post(f"{PAY0_API_URL}/create_order",
                              json=payload,
                              headers={"Content-Type": "application/json"},
                              timeout=aiohttp.ClientTimeout(total=10)) as r:
                data = await r.json()
                logger.info(f"Pay0 response: {data}")
                if data.get("status") == "success" or data.get("payment_url"):
                    return {
                        "order_id": order_id,
                        "payment_url": data.get("payment_url") or data.get("url"),
                        "upi_id": data.get("upi_id", ""),
                        "qr_url": data.get("qr_url") or data.get("qr_code"),
                    }
    except Exception as e:
        logger.error(f"Pay0 error: {e}")

    # Fallback: direct UPI link
    upi_string = f"upi://pay?pa=8360626185@upi&pn=ShrutiOnline&am={amount}&tn=WalletRecharge_{uid}&cu=INR"
    return {
        "order_id": f"WALLET_{uid}_{int(datetime.now().timestamp())}",
        "payment_url": None,
        "upi_id": "8360626185@upi",
        "upi_string": upi_string,
        "qr_url": f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data={upi_string}",
    }

async def verify_payment(order_id):
    """Check payment status from Pay0.shop"""
    try:
        async with aiohttp.ClientSession() as s:
            async with s.post(f"{PAY0_API_URL}/check_order",
                              json={"merchant_id": PAY0_MERCHANT_ID,
                                    "api_key": PAY0_API_KEY,
                                    "order_id": order_id},
                              timeout=aiohttp.ClientTimeout(total=10)) as r:
                data = await r.json()
                return data.get("status") == "success" or data.get("payment_status") == "paid"
    except Exception as e:
        logger.error(f"Payment verify error: {e}")
        return False

# ════════════════════════════════════════════════════════════════
#   KEYBOARDS
# ════════════════════════════════════════════════════════════════
def main_kb(uid=None):
    wallet = get_wallet(uid) if uid else 0
    btns = [
        [InlineKeyboardButton(f"💰 Wallet: ₹{wallet}  |  ➕ Recharge", callback_data="wallet_menu")],
        [InlineKeyboardButton("💳 PAN Card",    callback_data="cat_pan"),
         InlineKeyboardButton("🏍️ Vehicle",     callback_data="cat_vehicle")],
        [InlineKeyboardButton("🗳️ Voter",        callback_data="cat_voter"),
         InlineKeyboardButton("🪪 Aadhaar",      callback_data="cat_aadhaar")],
        [InlineKeyboardButton("🍚 Ration",       callback_data="cat_ration"),
         InlineKeyboardButton("⚡ Electricity",  callback_data="cat_electricity")],
        [InlineKeyboardButton("📋 Price List",   callback_data="price_list"),
         InlineKeyboardButton("📦 My Orders",    callback_data="my_orders")],
    ]
    if uid and is_admin(uid):
        btns.append([InlineKeyboardButton("⚙️ ADMIN PANEL 🔧", callback_data="admin_panel")])
    return InlineKeyboardMarkup(btns)

# ════════════════════════════════════════════════════════════════
#   /start
# ════════════════════════════════════════════════════════════════
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    # Register user
    db = load_db()
    uid = str(u.id)
    if uid not in db["users"]:
        db["users"][uid] = {"wallet": 0.0, "name": u.first_name, "joined": datetime.now().strftime("%d-%m-%Y")}
        save_db(db)

    wallet = get_wallet(u.id)
    await update.message.reply_text(
        f"🙏 *Namaste {u.first_name} ji!*\n\n"
        f"Welcome to *Shruti Online Sarvice* 🇮🇳\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"💰 Aapka Wallet Balance: *₹{wallet}*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"Service use karne ke liye pehle wallet recharge karein\n"
        f"Phir koi bhi service choose karein 👇",
        parse_mode="Markdown",
        reply_markup=main_kb(u.id)
    )

# ════════════════════════════════════════════════════════════════
#   WALLET SYSTEM
# ════════════════════════════════════════════════════════════════
async def wallet_menu(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    uid = q.from_user.id
    wallet = get_wallet(uid)
    btns = [
        [InlineKeyboardButton("➕ ₹50 Recharge",  callback_data="recharge_50"),
         InlineKeyboardButton("➕ ₹100 Recharge", callback_data="recharge_100")],
        [InlineKeyboardButton("➕ ₹200 Recharge", callback_data="recharge_200"),
         InlineKeyboardButton("➕ Custom Amount",  callback_data="recharge_custom")],
        [InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")],
    ]
    await q.edit_message_text(
        f"💰 *Wallet Menu*\n\n"
        f"Current Balance: *₹{wallet}*\n\n"
        f"Kitna recharge karna hai? 👇",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(btns)
    )

async def recharge_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    data = q.data
    uid = q.from_user.id

    if data == "recharge_custom":
        await q.edit_message_text(
            "💰 *Custom Recharge*\n\nKitne rupye recharge karne hain?\n_(Sirf number likho, jaise: 150)_",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="wallet_menu")]]))
        ctx.user_data["awaiting"] = "recharge_amount"
        return AWAIT_RECHARGE_AMT

    amount = int(data.replace("recharge_", ""))
    await process_recharge(q.edit_message_text, uid, amount, ctx)

async def recharge_amount_recv(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    text = update.message.text.strip()
    if not text.isdigit() or int(text) < 10:
        await update.message.reply_text("❌ Valid amount daalo (minimum ₹10)")
        return AWAIT_RECHARGE_AMT
    await process_recharge(update.message.reply_text, uid, int(text), ctx)
    return ConversationHandler.END

async def process_recharge(reply_func, uid, amount, ctx):
    """Generate UPI QR and payment link"""
    payment = await create_payment_order(uid, amount)
    order_id = payment["order_id"]

    # Save pending payment
    db = load_db()
    db["pending_payments"][order_id] = {"uid": str(uid), "amount": amount, "time": datetime.now().strftime("%d-%m-%Y %H:%M")}
    save_db(db)
    ctx.user_data["pending_order_id"] = order_id
    ctx.user_data["pending_amount"] = amount

    qr_url = payment.get("qr_url", "")
    upi_id = payment.get("upi_id", "")
    pay_url = payment.get("payment_url", "")

    text = (
        f"💳 *UPI Payment — ₹{amount}*\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"📋 Order ID: `{order_id}`\n\n"
        f"1️⃣ Neeche QR scan karein *OR*\n"
        f"2️⃣ UPI ID par pay karein:\n`{upi_id}`\n\n"
        f"💰 Amount: *₹{amount}*\n\n"
        f"⚠️ Payment ke baad *'✅ Maine Pay Kar Diya'* button dabayein"
    )
    btns = [[InlineKeyboardButton("✅ Maine Pay Kar Diya", callback_data=f"verify_{order_id}")]]
    if pay_url:
        btns.insert(0, [InlineKeyboardButton("💳 Payment Link Kholo", url=pay_url)])
    btns.append([InlineKeyboardButton("❌ Cancel", callback_data="wallet_menu")])

    # Send QR image
    try:
        import requests as req_sync
        qr_img = req_sync.get(qr_url, timeout=5)
        await reply_func(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(btns))
    except:
        await reply_func(
            text + f"\n\n🔗 QR: {qr_url}",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(btns)
        )

async def verify_payment_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer("⏳ Checking...")
    uid = q.from_user.id
    order_id = q.data.replace("verify_", "")

    db = load_db()
    pending = db["pending_payments"].get(order_id)
    if not pending:
        await q.edit_message_text("❌ Order nahi mila. /start se dobara try karein.")
        return

    # Verify with Pay0.shop
    paid = await verify_payment(order_id)

    if paid:
        amount = pending["amount"]
        new_balance = update_wallet(uid, amount)
        # Remove pending
        del db["pending_payments"][order_id]
        save_db(db)
        await q.edit_message_text(
            f"✅ *Payment Confirmed!*\n\n"
            f"💰 ₹{amount} wallet mein add ho gaye!\n"
            f"🏦 New Balance: *₹{new_balance}*\n\n"
            f"Ab koi bhi service use karein 👇",
            parse_mode="Markdown",
            reply_markup=main_kb(uid)
        )
    else:
        # Admin manual verify option
        btns = [
            [InlineKeyboardButton("🔄 Phir Check Karein", callback_data=f"verify_{order_id}")],
            [InlineKeyboardButton("📸 Screenshot Bhejo Admin ko", callback_data="contact_admin")],
            [InlineKeyboardButton("❌ Cancel", callback_data="wallet_menu")],
        ]
        await q.edit_message_text(
            f"⏳ *Payment abhi confirm nahi hua*\n\n"
            f"Order ID: `{order_id}`\n"
            f"Amount: ₹{pending['amount']}\n\n"
            f"Agar payment ho gayi hai toh 2-3 minute wait karke phir check karein.\n"
            f"Ya admin ko screenshot bhejein.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(btns)
        )

# Admin manual wallet add
async def admin_add_wallet_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Admin manually adds wallet balance"""
    q = update.callback_query; await q.answer()
    if not is_admin(q.from_user.id): return
    # Format: admin_addwallet_UID_AMOUNT
    parts = q.data.split("_")
    target_uid = parts[2]; amount = int(parts[3])
    new_bal = update_wallet(int(target_uid), amount)
    await q.edit_message_text(f"✅ ₹{amount} added to user {target_uid}. New balance: ₹{new_bal}")
    try:
        await ctx.bot.send_message(int(target_uid),
            f"✅ *Wallet Recharge Successful!*\n💰 ₹{amount} add ho gaye!\nNew Balance: *₹{new_bal}*",
            parse_mode="Markdown")
    except: pass

# ════════════════════════════════════════════════════════════════
#   SERVICE FLOW
# ════════════════════════════════════════════════════════════════
async def show_cat(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    cat_key = q.data.replace("cat_", "")
    cat = ALL_SERVICES.get(cat_key)
    if not cat: return
    uid = q.from_user.id
    wallet = get_wallet(uid)
    text = f"{cat['name']}\n━━━━━━━━━━━━━━━━\n💰 Aapka Balance: *₹{wallet}*\n\n"
    btns = []
    for sk, sv in cat["services"].items():
        p = get_price(sk)
        affordable = "✅" if wallet >= p else "❌"
        text += f"{affordable} {sv['name']} — *₹{p}*\n"
        btns.append([InlineKeyboardButton(f"{affordable} {sv['name']}  ₹{p}", callback_data=f"svc_{sk}")])
    text += "\n✅=Balance enough | ❌=Recharge needed"
    btns.append([InlineKeyboardButton("➕ Wallet Recharge", callback_data="wallet_menu")])
    btns.append([InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")])
    await q.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(btns))

async def service_select(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    uid = q.from_user.id
    sk = q.data.replace("svc_", "")
    svc = get_svc_info(sk)
    if not svc:
        await q.edit_message_text("❌ Service nahi mili"); return
    price = get_price(sk)
    wallet = get_wallet(uid)

    if wallet < price:
        await q.edit_message_text(
            f"❌ *Insufficient Balance*\n\n"
            f"Service: {svc['name']}\n"
            f"Required: *₹{price}*\n"
            f"Your Balance: *₹{wallet}*\n\n"
            f"Please wallet recharge karein 👇",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("➕ Wallet Recharge Karein", callback_data="wallet_menu")],
                [InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")],
            ])
        )
        return

    ctx.user_data["selected_svc"] = sk
    await q.edit_message_text(
        f"📝 *{svc['name']}*\n"
        f"💰 Charge: *₹{price}*\n"
        f"🏦 Balance: *₹{wallet}*\n\n"
        f"👇 *{svc['label']} daalo:*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="main_menu")]])
    )
    return AWAIT_SERVICE_INPUT

async def service_input_recv(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user_input = update.message.text.strip()
    sk = ctx.user_data.get("selected_svc")
    svc = get_svc_info(sk)
    price = get_price(sk)
    wallet = get_wallet(uid)

    if not sk or not svc:
        await update.message.reply_text("❌ Service timeout. /start se dobara try karein.")
        return ConversationHandler.END

    if wallet < price:
        await update.message.reply_text("❌ Balance kam hai. Wallet recharge karein.", reply_markup=main_kb(uid))
        return ConversationHandler.END

    # Deduct wallet
    new_balance = update_wallet(uid, -price)
    oid = f"ORD{int(datetime.now().timestamp())}"

    await update.message.reply_text(
        f"⏳ *Processing...*\n\n"
        f"📌 Service: {svc['name']}\n"
        f"🔍 Input: `{user_input}`\n"
        f"💰 ₹{price} deducted | Balance: ₹{new_balance}",
        parse_mode="Markdown"
    )

    # Call website API
    html_result, error = await call_service_api(sk, user_input)

    if error or not html_result:
        # Refund on failure
        update_wallet(uid, price)
        await update.message.reply_text(
            f"❌ *Service Error*\n\n{error or 'Unknown error'}\n\n"
            f"💰 ₹{price} refund ho gaye. Balance: ₹{get_wallet(uid)}",
            parse_mode="Markdown", reply_markup=main_kb(uid)
        )
        return ConversationHandler.END

    result = parse_service_result(sk, html_result)

    # Save order
    save_order({
        "order_id": oid, "uid": str(uid), "service": svc['name'],
        "input": user_input, "price": price,
        "status": "success" if result["success"] else "failed",
        "time": datetime.now().strftime("%d-%m-%Y %H:%M")
    })

    if result["success"]:
        # Format result nicely
        result_text = f"✅ *{svc['name']} — Result*\n━━━━━━━━━━━━━━━━\n\n"
        if result["text"]:
            result_text += f"{result['text']}\n\n"
        if result["data"]:
            for k, v in result["data"].items():
                result_text += f"📌 *{k}:* {v}\n"
        result_text += f"\n🆔 Order: `{oid}`\n💰 Balance: ₹{new_balance}"

        btns = [[InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]]
        if result["pdf_link"]:
            btns.insert(0, [InlineKeyboardButton("📄 PDF Download Karein", url=result["pdf_link"])])

        await update.message.reply_text(result_text, parse_mode="Markdown",
                                        reply_markup=InlineKeyboardMarkup(btns))
    else:
        # Refund
        update_wallet(uid, price)
        await update.message.reply_text(
            f"❌ *Result nahi mila*\n\n"
            f"Input check karein aur dobara try karein.\n"
            f"💰 ₹{price} refund ho gaye. Balance: ₹{get_wallet(uid)}",
            parse_mode="Markdown", reply_markup=main_kb(uid)
        )

    return ConversationHandler.END

# ════════════════════════════════════════════════════════════════
#   MY ORDERS
# ════════════════════════════════════════════════════════════════
async def my_orders(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    uid = str(q.from_user.id)
    db = load_db()
    my = [o for o in db["orders"] if o.get("uid") == uid][-5:][::-1]
    if not my:
        text = "📦 *Aapke koi orders nahi hain*\n\nKoi service use karein!"
    else:
        text = "📦 *Aapke Recent Orders*\n━━━━━━━━━━━━━━━━\n\n"
        for o in my:
            icon = "✅" if o["status"] == "success" else "❌"
            text += f"{icon} {o['service']}\n🔍 `{o['input']}` | 💰 ₹{o['price']}\n🕐 {o['time']}\n\n"
    await q.edit_message_text(text, parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]]))

# ════════════════════════════════════════════════════════════════
#   PRICE LIST
# ════════════════════════════════════════════════════════════════
async def price_list(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    text = "📋 *Sabhi Services — Price List*\n━━━━━━━━━━━━━━━━\n\n"
    for cat in ALL_SERVICES.values():
        text += f"{cat['name']}\n"
        for sk, sv in cat["services"].items():
            text += f"  • {sv['name']} — *₹{get_price(sk)}*\n"
        text += "\n"
    await q.edit_message_text(text, parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]]))

# ════════════════════════════════════════════════════════════════
#   ADMIN PANEL
# ════════════════════════════════════════════════════════════════
async def admin_panel_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    if not is_admin(q.from_user.id):
        await q.answer("❌ Access Denied!", show_alert=True); return
    db = load_db()
    total_users = len(db["users"])
    total_orders = len(db["orders"])
    total_revenue = sum(o["price"] for o in db["orders"] if o.get("status") == "success")
    pending_pay = len(db["pending_payments"])

    await q.edit_message_text(
        f"⚙️ *Admin Panel*\n━━━━━━━━━━━━━━━━\n"
        f"👥 Total Users: {total_users}\n"
        f"📦 Total Orders: {total_orders}\n"
        f"💰 Total Revenue: ₹{total_revenue}\n"
        f"⏳ Pending Payments: {pending_pay}\n",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("💰 Price Manage",        callback_data="admin_prices")],
            [InlineKeyboardButton("📦 All Orders",          callback_data="admin_orders")],
            [InlineKeyboardButton("👥 All Users",           callback_data="admin_users")],
            [InlineKeyboardButton("⏳ Pending Payments",    callback_data="admin_pending")],
            [InlineKeyboardButton("📢 Broadcast Message",   callback_data="admin_broadcast")],
            [InlineKeyboardButton("🏠 Main Menu",           callback_data="main_menu")],
        ])
    )

async def admin_prices_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    if not is_admin(q.from_user.id): return
    btns = [[InlineKeyboardButton(cat["name"], callback_data=f"admincat_{ck}")] for ck, cat in ALL_SERVICES.items()]
    btns.append([InlineKeyboardButton("🔙 Admin Panel", callback_data="admin_panel")])
    await q.edit_message_text("💰 *Kaun si category?*", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(btns))

async def admin_price_cat(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    if not is_admin(q.from_user.id): return
    ck = q.data.replace("admincat_",""); cat = ALL_SERVICES.get(ck)
    btns = [[InlineKeyboardButton(f"✏️ {sv['name']}  ₹{get_price(sk)}", callback_data=f"setprice_{sk}")]
            for sk, sv in cat["services"].items()]
    btns.append([InlineKeyboardButton("🔙 Back", callback_data="admin_prices")])
    await q.edit_message_text(f"{cat['name']}\nKis service ki price?", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(btns))

async def set_price_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    if not is_admin(q.from_user.id): return
    sk = q.data.replace("setprice_","")
    svc = get_svc_info(sk); cur = get_price(sk)
    ctx.user_data.update({"psk": sk})
    await q.edit_message_text(
        f"✏️ *{svc['name']}*\nCurrent: *₹{cur}*\n\nNaya price daalo:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="admin_prices")]]))
    return AWAIT_ADMIN_PRICE

async def set_price_save(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return ConversationHandler.END
    t = update.message.text.strip()
    if not t.isdigit():
        await update.message.reply_text("❌ Sirf number!"); return AWAIT_ADMIN_PRICE
    sk = ctx.user_data["psk"]; svc = get_svc_info(sk)
    db = load_db()
    if "prices" not in db: db["prices"] = {}
    db["prices"][sk] = int(t); save_db(db)
    await update.message.reply_text(
        f"✅ *Price Updated!*\n📌 {svc['name']}\n💰 New: *₹{t}*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⚙️ Admin Panel", callback_data="admin_panel")]]))
    return ConversationHandler.END

async def admin_orders_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    if not is_admin(q.from_user.id): return
    db = load_db()
    recent = db["orders"][-10:][::-1]
    text = f"📦 *Recent Orders ({len(recent)})*\n━━━━━━━━━━━━━━━━\n\n"
    for o in recent:
        icon = "✅" if o.get("status") == "success" else "❌"
        text += f"{icon} `{o['order_id']}`\n👤 {o.get('uid','')} | {o['service']}\n💰 ₹{o['price']} | 🕐 {o['time']}\n\n"
    await q.edit_message_text(text, parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Admin Panel", callback_data="admin_panel")]]))

async def admin_users_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    if not is_admin(q.from_user.id): return
    db = load_db()
    text = f"👥 *All Users ({len(db['users'])})*\n━━━━━━━━━━━━━━━━\n\n"
    for uid, u in list(db["users"].items())[-20:]:
        text += f"👤 ID: `{uid}` | 💰 ₹{u['wallet']} | Joined: {u.get('joined','?')}\n"
    await q.edit_message_text(text[:4000], parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Admin Panel", callback_data="admin_panel")]]))

async def admin_pending_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    if not is_admin(q.from_user.id): return
    db = load_db()
    pending = db.get("pending_payments", {})
    if not pending:
        text = "✅ Koi pending payment nahi!"
        btns = [[InlineKeyboardButton("🔙 Admin Panel", callback_data="admin_panel")]]
    else:
        text = f"⏳ *Pending Payments ({len(pending)})*\n━━━━━━━━━━━━━━━━\n\n"
        btns = []
        for oid, p in pending.items():
            text += f"🆔 `{oid}`\n👤 UID: {p['uid']} | 💰 ₹{p['amount']} | 🕐 {p['time']}\n\n"
            btns.append([InlineKeyboardButton(
                f"✅ Manually Approve ₹{p['amount']} for {p['uid']}",
                callback_data=f"admin_addwallet_{p['uid']}_{p['amount']}_{oid}"
            )])
        btns.append([InlineKeyboardButton("🔙 Admin Panel", callback_data="admin_panel")])
    await q.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(btns))

async def admin_manual_approve(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    if not is_admin(q.from_user.id): return
    parts = q.data.split("_")
    # admin_addwallet_UID_AMOUNT_ORDERID
    target_uid = parts[3]; amount = int(parts[4]); oid = parts[5]
    new_bal = update_wallet(int(target_uid), amount)
    db = load_db()
    if oid in db.get("pending_payments", {}):
        del db["pending_payments"][oid]; save_db(db)
    await q.edit_message_text(f"✅ ₹{amount} added to {target_uid}. Balance: ₹{new_bal}")
    try:
        await ctx.bot.send_message(int(target_uid),
            f"✅ *Wallet Recharge Approved!*\n💰 ₹{amount} add ho gaye!\nNew Balance: *₹{new_bal}*\n\nAb service use karein 👇",
            parse_mode="Markdown", reply_markup=main_kb(int(target_uid)))
    except: pass

async def admin_broadcast_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    if not is_admin(q.from_user.id): return
    await q.edit_message_text(
        "📢 *Broadcast Message*\n\nSabhi users ko kya message bhejna hai?\n_(Text likhein)_",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="admin_panel")]]))
    return AWAIT_BROADCAST

async def admin_broadcast_send(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return ConversationHandler.END
    msg = update.message.text
    db = load_db()
    sent = 0; failed = 0
    for uid in db["users"]:
        try:
            await ctx.bot.send_message(int(uid), f"📢 *Shruti Online Sarvice*\n\n{msg}", parse_mode="Markdown")
            sent += 1
            await asyncio.sleep(0.05)
        except: failed += 1
    await update.message.reply_text(
        f"✅ Broadcast complete!\n✅ Sent: {sent}\n❌ Failed: {failed}",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⚙️ Admin Panel", callback_data="admin_panel")]]))
    return ConversationHandler.END

# ════════════════════════════════════════════════════════════════
#   MISC CALLBACKS
# ════════════════════════════════════════════════════════════════
async def main_menu_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    uid = q.from_user.id; wallet = get_wallet(uid)
    await q.edit_message_text(
        f"🏠 *Main Menu*\n💰 Balance: *₹{wallet}*\n\nService choose karein 👇",
        parse_mode="Markdown", reply_markup=main_kb(uid))

async def contact_admin_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    await q.edit_message_text(
        "📞 *Admin se Contact Karein*\n\nApna payment screenshot admin ko bhejein.\nWoh manually balance add kar denge.",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]]))

async def unknown(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🤔 /start likhein", reply_markup=main_kb(update.effective_user.id))

# ════════════════════════════════════════════════════════════════
#   MAIN
# ════════════════════════════════════════════════════════════════
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    # Service input conversation
    svc_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(service_select, pattern="^svc_")],
        states={AWAIT_SERVICE_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, service_input_recv)]},
        fallbacks=[], per_user=True)

    # Recharge conversation
    recharge_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(recharge_handler, pattern="^recharge_custom$")],
        states={AWAIT_RECHARGE_AMT: [MessageHandler(filters.TEXT & ~filters.COMMAND, recharge_amount_recv)]},
        fallbacks=[], per_user=True)

    # Price set
    price_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(set_price_start, pattern="^setprice_")],
        states={AWAIT_ADMIN_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_price_save)]},
        fallbacks=[], per_user=True)

    # Broadcast
    broadcast_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_broadcast_start, pattern="^admin_broadcast$")],
        states={AWAIT_BROADCAST: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_broadcast_send)]},
        fallbacks=[], per_user=True)

    app.add_handler(CommandHandler("start", start))
    app.add_handler(svc_conv)
    app.add_handler(recharge_conv)
    app.add_handler(price_conv)
    app.add_handler(broadcast_conv)

    app.add_handler(CallbackQueryHandler(main_menu_cb,          pattern="^main_menu$"))
    app.add_handler(CallbackQueryHandler(wallet_menu,            pattern="^wallet_menu$"))
    app.add_handler(CallbackQueryHandler(recharge_handler,       pattern="^recharge_"))
    app.add_handler(CallbackQueryHandler(verify_payment_cb,      pattern="^verify_"))
    app.add_handler(CallbackQueryHandler(admin_manual_approve,   pattern="^admin_addwallet_"))
    app.add_handler(CallbackQueryHandler(show_cat,               pattern="^cat_"))
    app.add_handler(CallbackQueryHandler(price_list,             pattern="^price_list$"))
    app.add_handler(CallbackQueryHandler(my_orders,              pattern="^my_orders$"))
    app.add_handler(CallbackQueryHandler(admin_panel_cb,         pattern="^admin_panel$"))
    app.add_handler(CallbackQueryHandler(admin_prices_cb,        pattern="^admin_prices$"))
    app.add_handler(CallbackQueryHandler(admin_price_cat,        pattern="^admincat_"))
    app.add_handler(CallbackQueryHandler(admin_orders_cb,        pattern="^admin_orders$"))
    app.add_handler(CallbackQueryHandler(admin_users_cb,         pattern="^admin_users$"))
    app.add_handler(CallbackQueryHandler(admin_pending_cb,       pattern="^admin_pending$"))
    app.add_handler(CallbackQueryHandler(contact_admin_cb,       pattern="^contact_admin$"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, unknown))

    print("✅ Shruti Online Sarvice Bot chal raha hai...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
