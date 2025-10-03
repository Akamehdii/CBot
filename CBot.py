import os
import json
from datetime import datetime
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from telegram import (
    Update,
    InlineKeyboardButton, InlineKeyboardMarkup,
    ReplyKeyboardMarkup, KeyboardButton,
)
from telegram.ext import (
    ApplicationBuilder, ContextTypes, CommandHandler,
    CallbackQueryHandler, MessageHandler, filters,
)

# =========================
#        SETTINGS
# =========================
# Env vars (Render → Environment)
BOT_TOKEN = os.environ.get("BOT_TOKEN")                 # required
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")             # required (e.g. https://your-app.onrender.com)
GROUP_CHAT_ID = int(os.environ.get("GROUP_CHAT_ID", "0"))   # admin group/channel id (negative for groups)

# Google Sheets (optional)
GSPREAD_CREDS_JSON = os.environ.get("GSPREAD_CREDS_JSON")   # JSON string
SHEET_NAME = os.environ.get("SHEET_NAME", "EnglishClubRegistrations")

# Optional public sheet link shown to users
SHEET_LINK = os.environ.get("SHEET_LINK", "")

# Events list (from ENV JSON or defaults)
DEFAULT_EVENTS = [
    {
        "id": "m1",
        "title": "Coffee & Conversation",
        "when": "2025-10-12 18:30",
        "place": "Café République",
        "maps": "https://maps.google.com/?q=Café+République",
        "price": "Free",
    }
]
try:
    EVENTS = json.loads(os.environ.get("EVENTS_JSON", ""))
    if not isinstance(EVENTS, list):
        EVENTS = DEFAULT_EVENTS
except Exception:
    EVENTS = DEFAULT_EVENTS

# Private meetup links per event id (optional)
try:
    MEETUP_LINKS = json.loads(os.environ.get("MEETUP_LINKS_JSON", "{}"))
except Exception:
    MEETUP_LINKS = {}

# =========================
#        TEXTS (FA)
# =========================
main_reply_keyboard = ReplyKeyboardMarkup(
    [["شروع مجدد 🔄", "لغو عملیات ❌"]], resize_keyboard=True
)

welcome_text = (
    "سلام! به ربات *English Club* خوش اومدی 🇬🇧☕\n"
    "با این ربات می‌تونی رویدادهای زبان انگلیسی در کافه‌های شهر رو ببینی و ثبت‌نام کنی."
)

faq_text = (
    "**سوالات متداول ❔**\n\n"
    "**کِی و کجا برگزار میشه؟** هر هفته چند میت‌آپ داریم؛ از ‘🎉 رویدادهای پیش‌رو’ ببین.\n\n"
    "**سطح زبان مهمه؟** نه؛ سطحت رو می‌پرسیم تا گروه‌بندی بهتر شه.\n\n"
    "**هزینه داره؟** بعضی رایگان، بعضی با هزینه کم (مثلاً شامل ۱ نوشیدنی).\n\n"
    "**نحوه قطعی شدن؟** بعد از ثبت، درخواستت برای ادمین میره؛ تایید بشه لینک میاد."
)

rules_text = (
    "⚠️ قوانین English Club:\n"
    "• احترام به بقیه شرکت‌کننده‌ها.\n"
    "• تا حد امکان انگلیسی صحبت کن.\n"
    "• اگر منصرف شدی زودتر خبر بده."
)

# =========================
#    INITIALIZE BOT
# =========================
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set")

application = ApplicationBuilder().token(BOT_TOKEN).build()

# -------------------------
# Inline Keyboards
# -------------------------
menu_buttons = [
    [InlineKeyboardButton("🎉 رویدادهای پیش‌رو", callback_data="list_events")],
    [InlineKeyboardButton("📝 ثبت‌نام در رویداد", callback_data="register")],
]
if SHEET_LINK:
    menu_buttons.append([InlineKeyboardButton("📋 برنامه‌ها و ظرفیت‌ها", url=SHEET_LINK)])
menu_buttons.extend([
    [InlineKeyboardButton("❔ سوالات متداول", callback_data="faq")],
    [InlineKeyboardButton("🆘 پشتیبانی", callback_data="support")],
])


def build_events_buttons():
    rows = []
    for e in EVENTS:
        label = f"{e['title']} | {e['place']} | {e['when']}"
        rows.append([InlineKeyboardButton(label, callback_data=f"event_{e['id']}")])
    if not rows:
        rows = [[InlineKeyboardButton("فعلاً رویدادی ثبت نشده", callback_data="noop")]]
    rows.append([InlineKeyboardButton("↩️ بازگشت", callback_data="back_home")])
    return rows

# =========================
#     HANDLERS
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(welcome_text, reply_markup=main_reply_keyboard, parse_mode="Markdown")
    await update.message.reply_text("یکی از گزینه‌ها رو انتخاب کن:", reply_markup=InlineKeyboardMarkup(menu_buttons))


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("عملیات لغو شد.", reply_markup=main_reply_keyboard)
    await update.message.reply_text("یکی از گزینه‌ها رو انتخاب کن:", reply_markup=InlineKeyboardMarkup(menu_buttons))


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    await query.answer()

    if data == "noop":
        return

    if data == "back_home":
        await query.edit_message_text("یکی از گزینه‌ها رو انتخاب کن:", reply_markup=InlineKeyboardMarkup(menu_buttons))
        return

    if data == "faq":
        await query.edit_message_text(
            faq_text, parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ بازگشت", callback_data="back_home")]])
        )
        return

    if data == "support":
        await query.edit_message_text(
            "برای پشتیبانی به آیدی زیر پیام بده:\n@englishclub_support",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ بازگشت", callback_data="back_home")]])
        )
        return

    if data == "list_events":
        await query.edit_message_text("رویدادهای پیش‌رو:", reply_markup=InlineKeyboardMarkup(build_events_buttons()))
        return

    if data.startswith("event_"):
        ev_id = data.split("_", 1)[1]
        ev = next((e for e in EVENTS if e["id"] == ev_id), None)
        if not ev:
            await query.answer("این رویداد یافت نشد.", show_alert=True)
            return
        txt = (
            f"**{ev['title']}**\n"
            f"📍 *{ev['place']}*\n"
            f"🕒 {ev['when']}\n"
            f"💶 {ev.get('price','Free')}\n\n"
            f"📍 نقشه: {ev.get('maps','—')}\n"
        )
        await query.edit_message_text(
            txt, parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📝 ثبت‌نام در همین رویداد", callback_data=f"register_{ev_id}")],
                [InlineKeyboardButton("↩️ بازگشت", callback_data="list_events")],
            ])
        )
        return

    if data == "register" or data.startswith("register_"):
        if data.startswith("register_"):
            context.user_data["selected_event_id"] = data.split("_", 1)[1]
        else:
            context.user_data["selected_event_id"] = None
        if not context.user_data["selected_event_id"]:
            await query.edit_message_text("یکی از رویدادها رو انتخاب کن:", reply_markup=InlineKeyboardMarkup(build_events_buttons()))
            context.user_data["step"] = "pick_event"
            return
        context.user_data["step"] = "name"
        await query.edit_message_text(
            rules_text,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✅ قبول دارم و ادامه", callback_data="accept_rules")]])
        )
        return

    if data == "accept_rules":
        context.user_data["step"] = "name"
        await query.edit_message_text("لطفاً *نام و نام خانوادگی* رو وارد کن:", parse_mode='Markdown')
        return

    # Admin approve/reject
    if data.startswith("approve_") or data.startswith("reject_"):
        try:
            action, user_chat_id, ev_id = data.split("_", 2)
            user_chat_id = int(user_chat_id)
            admin_name = query.from_user.first_name

            if action == "approve":
                link = MEETUP_LINKS.get(ev_id)
                if link:
                    msg = (
                        "🎉 ثبت‌نامت تایید شد!\n\n"
                        "اطلاعات رویداد و لینک گروه/هماهنگی:\n" + link
                    )
                    await context.bot.send_message(chat_id=user_chat_id, text=msg)
                    await query.edit_message_reply_markup(
                        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(f"✅ توسط {admin_name} تایید شد", callback_data="done")]])
                    )
                else:
                    await context.bot.send_message(chat_id=user_chat_id, text="🎉 ثبت‌نامت تایید شد! به‌زودی اطلاعات نهایی برات ارسال می‌شه.")
                    await query.edit_message_reply_markup(
                        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(f"✅ توسط {admin_name} تایید شد (بدون لینک)", callback_data="done")]])
                    )
            else:
                await context.bot.send_message(chat_id=user_chat_id, text="⚠️ متاسفانه ثبت‌نامت تایید نشد. برای رویدادهای بعدی اقدام کن یا با پشتیبانی در تماس باش.")
                await query.edit_message_reply_markup(
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(f"❌ توسط {admin_name} رد شد", callback_data="done")]])
                )
        except Exception as e:
            print(f"Error in admin callback: {e}")
            await query.answer("مشکلی پیش اومد.", show_alert=True)
        return


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_data = context.user_data
    step = user_data.get("step")
    text = (update.message.text or "").strip()

    if step == "pick_event" and text:
        # ignored; event selection is via inline buttons
        return

    if step == "name":
        if 2 <= len(text) <= 60:
            user_data["name"] = text
            user_data["step"] = "phone"
            contact_btn = ReplyKeyboardMarkup(
                [[KeyboardButton("ارسال شماره تماس 📱", request_contact=True)]],
                resize_keyboard=True, one_time_keyboard=True,
            )
            await update.message.reply_text("شماره تلفنت رو وارد کن یا دکمه زیر رو بزن:", reply_markup=contact_btn)
        else:
            await update.message.reply_text("لطفاً نام معتبر وارد کن (۲ تا ۶۰ کاراکتر).")
        return

    if step == "phone":
        user_data["phone"] = text
        user_data["step"] = "level"
        await update.message.reply_text(
            "سطح زبانت چیه؟ یکی رو انتخاب کن:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Beginner (A1–A2)", callback_data="lvl_A")],
                [InlineKeyboardButton("Intermediate (B1–B2)", callback_data="lvl_B")],
                [InlineKeyboardButton("Advanced (C1+)", callback_data="lvl_C")],
            ]),
        )
        return

    if step == "note":
        user_data["note"] = text
        await finalize_and_send(update, context)
        return
    # otherwise ignore


async def handle_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("step") == "phone":
        context.user_data["phone"] = update.message.contact.phone_number
        context.user_data["step"] = "level"
        await update.message.reply_text(
            "سطح زبانت چیه؟ یکی رو انتخاب کن:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Beginner (A1–A2)", callback_data="lvl_A")],
                [InlineKeyboardButton("Intermediate (B1–B2)", callback_data="lvl_B")],
                [InlineKeyboardButton("Advanced (C1+)", callback_data="lvl_C")],
            ]),
        )


async def handle_level(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    await query.answer()

    if not data.startswith("lvl_"):
        return

    lvl_map = {"lvl_A": "Beginner (A1–A2)", "lvl_B": "Intermediate (B1–B2)", "lvl_C": "Advanced (C1+)"}
    context.user_data["level"] = lvl_map.get(data, "Unknown")
    context.user_data["step"] = "note"
    await query.edit_message_text(
        "یادداشت/نیاز خاص داری؟ (اختیاری) اینجا بنویس و بفرست. اگر چیزی نداری، فقط یک خط تیره `-` بفرست.",
        parse_mode='Markdown'
    )


async def finalize_and_send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_info = context.user_data

    # ensure event selected; if not, pick first
    ev_id = user_info.get("selected_event_id")
    if not ev_id and EVENTS:
        ev_id = EVENTS[0]["id"]
        user_info["selected_event_id"] = ev_id
    ev = next((e for e in EVENTS if e["id"] == ev_id), None)

    # User confirmation
    summary = (
        "✅ درخواست ثبت‌نامت ثبت شد و برای ادمین ارسال میشه.\n\n"
        f"👤 نام: {user_info.get('name','—')}\n"
        f"📱 تماس: {user_info.get('phone','—')}\n"
        f"🗣️ سطح: {user_info.get('level','—')}\n"
        f"📝 توضیحات: {user_info.get('note','—')}\n"
    )
    if ev:
        summary += (
            f"\n📌 رویداد: {ev['title']}\n"
            f"📍 مکان: {ev['place']}\n"
            f"🕒 زمان: {ev['when']}\n"
        )
    await update.effective_chat.send_message(summary)

    # Send to admin group with Approve/Reject
    try:
        user_chat_id = update.effective_chat.id
        approve_cb = f"approve_{user_chat_id}_{ev_id or 'NA'}"
        reject_cb = f"reject_{user_chat_id}_{ev_id or 'NA'}"
        buttons = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ تایید", callback_data=approve_cb),
             InlineKeyboardButton("❌ رد", callback_data=reject_cb)]
        ])

        admin_txt = (
            "🔔 **ثبت‌نام جدید English Club**\n\n"
            f"👤 **نام:** {user_info.get('name','—')}\n"
            f"📱 **تماس:** {user_info.get('phone','—')}\n"
            f"🗣️ **سطح:** {user_info.get('level','—')}\n"
            f"📝 **توضیحات:** {user_info.get('note','—')}\n\n"
        )
        if ev:
            admin_txt += (
                f"📌 **رویداد:** {ev['title']}\n"
                f"📍 **مکان:** {ev['place']}\n"
                f"🕒 **زمان:** {ev['when']}\n"
                f"🗺️ **نقشه:** {ev.get('maps','—')}\n"
                f"💶 **هزینه:** {ev.get('price','Free')}\n"
            )

        if GROUP_CHAT_ID:
            await context.bot.send_message(chat_id=GROUP_CHAT_ID, text=admin_txt, parse_mode='Markdown', reply_markup=buttons)
    except Exception as e:
        print(f"Error sending to admin group: {e}")

    # Optional: write to Google Sheets
    await maybe_write_to_sheet(user_info, ev)

    # Clear user state
    context.user_data.clear()


# Google Sheets helper (optional)
async def maybe_write_to_sheet(user_info, ev):
    if not GSPREAD_CREDS_JSON:
        return
    try:
        import gspread
        from oauth2client.service_account import ServiceAccountCredentials
        scope = [
            'https://spreadsheets.google.com/feeds',
            'https://www.googleapis.com/auth/drive'
        ]
        creds_dict = json.loads(GSPREAD_CREDS_JSON)
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)

        try:
            sh = client.open(SHEET_NAME)
        except Exception:
            sh = client.create(SHEET_NAME)
        ws = sh.sheet1
        # ensure header
        if ws.row_count == 0:
            ws.update('A1:F1', [["Timestamp","Event","Name","Phone","Level","Note"]])
        now = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
        ws.append_row([
            now,
            ev['title'] if ev else '—',
            user_info.get('name','—'),
            user_info.get('phone','—'),
            user_info.get('level','—'),
            user_info.get('note','—'),
        ])
    except Exception as e:
        print("Sheets error:", e)


# Register Handlers
application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("cancel", cancel))
application.add_handler(MessageHandler(filters.TEXT & filters.Regex("^شروع مجدد 🔄$"), start))
application.add_handler(MessageHandler(filters.TEXT & filters.Regex("^لغو عملیات ❌$"), cancel))
application.add_handler(CallbackQueryHandler(handle_callback))
application.add_handler(CallbackQueryHandler(handle_level, pattern=r"^lvl_"))
application.add_handler(MessageHandler(filters.CONTACT, handle_contact))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex("^شروع مجدد 🔄$") & ~filters.Regex("^لغو عملیات ❌$"), handle_message))

# FastAPI lifecycle + webhook
@asynccontextmanager
async def lifespan(app: FastAPI):
    await application.initialize()
    if WEBHOOK_URL:
        await application.bot.set_webhook(url=WEBHOOK_URL)
    await application.start()
    yield
    await application.stop()
    await application.shutdown()

app = FastAPI(lifespan=lifespan)

@app.post("/")
async def handle_update(request: Request):
    body = await request.json()
    update = Update.de_json(body, application.bot)
    await application.process_update(update)
    return {"status": "ok"}

@app.get("/")
async def root():
    return {"status": "CBot is running."}
