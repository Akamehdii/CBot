# CBot.py  — English Club Registration Bot (Polling version)
# Requires: python-telegram-bot==20.3

import os
import json
from datetime import datetime

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
BOT_TOKEN = os.environ.get("BOT_TOKEN")                         # REQUIRED
GROUP_CHAT_ID = int(os.environ.get("GROUP_CHAT_ID", "0"))       # admin group/channel id (negative for groups)
SHEET_LINK = os.environ.get("SHEET_LINK", "")                   # optional

# Google Sheets (optional)
GSPREAD_CREDS_JSON = os.environ.get("GSPREAD_CREDS_JSON")       # JSON string
SHEET_NAME = os.environ.get("SHEET_NAME", "EnglishClubRegistrations")

# EVENTS & PRIVATE LINKS
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
    EVENTS = json.loads(os.environ.get("EVENTS_JSON", "")) or DEFAULT_EVENTS
    if not isinstance(EVENTS, list):
        EVENTS = DEFAULT_EVENTS
except Exception:
    EVENTS = DEFAULT_EVENTS

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
    "• **کِی و کجا؟** هر هفته چند میت‌آپ داریم؛ از «🎉 رویدادهای پیش‌رو» ببین.\n"
    "• **سطح زبان؟** فرقی نمی‌کنه؛ سطحت رو می‌پرسیم تا گروه‌بندی بهتر شه.\n"
    "• **هزینه؟** بعضی رایگان، بعضی با هزینه‌ی کم (مثلاً شامل ۱ نوشیدنی).\n"
    "• **نهایی شدن؟** ثبت‌نامت برای ادمین میره؛ با تایید، لینک هماهنگی برات میاد."
)

rules_text = (
    "⚠️ قوانین English Club:\n"
    "• احترام به همه شرکت‌کننده‌ها.\n"
    "• تا حد امکان انگلیسی صحبت کن.\n"
    "• اگر منصرف شدی زودتر خبر بده.\n"
)

# =========================
#       MENUS/KEYS
# =========================
def build_main_menu():
    buttons = [
        [InlineKeyboardButton("🎉 رویدادهای پیش‌رو", callback_data="list_events")],
        [InlineKeyboardButton("📝 ثبت‌نام در رویداد", callback_data="register")],
    ]
    if SHEET_LINK:
        buttons.append([InlineKeyboardButton("📋 برنامه‌ها و ظرفیت‌ها", url=SHEET_LINK)])
    buttons.extend([
        [InlineKeyboardButton("❔ سوالات متداول", callback_data="faq")],
        [InlineKeyboardButton("🆘 پشتیبانی", callback_data="support")],
    ])
    return InlineKeyboardMarkup(buttons)


def build_events_buttons():
    rows = []
    for e in EVENTS:
        label = f"{e['title']} | {e['place']} | {e['when']}"
        rows.append([InlineKeyboardButton(label, callback_data=f"event_{e['id']}")])
    if not rows:
        rows = [[InlineKeyboardButton("فعلاً رویدادی ثبت نشده", callback_data="noop")]]
    rows.append([InlineKeyboardButton("↩️ بازگشت", callback_data="back_home")])
    return InlineKeyboardMarkup(rows)

# =========================
#        HANDLERS
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message:
        await update.message.reply_text(
            welcome_text, reply_markup=main_reply_keyboard, parse_mode="Markdown"
        )
        await update.message.reply_text("یکی از گزینه‌ها رو انتخاب کن:", reply_markup=build_main_menu())


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("عملیات لغو شد.", reply_markup=main_reply_keyboard)
    await update.message.reply_text("یکی از گزینه‌ها رو انتخاب کن:", reply_markup=build_main_menu())


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data

    # گارد برای دکمه سطح
    if data.startswith("lvl_"):
        return await handle_level(update, context)

    await query.answer()

    if data == "noop":
        return

    if data == "back_home":
        await query.edit_message_text("یکی از گزینه‌ها رو انتخاب کن:", reply_markup=build_main_menu())
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
        await query.edit_message_text("رویدادهای پیش‌رو:", reply_markup=build_events_buttons())
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
            await query.edit_message_text("یکی از رویدادها رو انتخاب کن:", reply_markup=build_events_buttons())
            context.user_data["step"] = "pick_event"
            return
        context.user_data["step"] = "name"
        await query.edit_message_text(
            rules_text,
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("✅ قبول دارم و ادامه", callback_data="accept_rules")]]
            )
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
                else:
                    await context.bot.send_message(chat_id=user_chat_id, text="🎉 ثبت‌نامت تایید شد! به‌زودی اطلاعات نهایی برات ارسال می‌شه.")
            else:
                await context.bot.send_message(chat_id=user_chat_id, text="⚠️ متاسفانه ثبت‌نامت تایید نشد.")
        except Exception as e:
            print(f"Error in admin callback: {e}")
        return


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_data = context.user_data
    step = user_data.get("step")
    text = (update.message.text or "").strip()

    if step == "pick_event" and text:
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

    lvl_map = {"lvl_A": "Beginner (A1–A2)", "lvl_B": "Intermediate (B1–B2)", "lvl_C": "Advanced (C1+)"}
    context.user_data["level"] = lvl_map.get(data, "Unknown")
    context.user_data["step"] = "note"
    await query.edit_message_text(
        "یادداشت/نیاز خاص داری؟ (اختیاری) اینجا بنویس و بفرست. اگر چیزی نداری، فقط یک خط تیره `-` بفرست.",
        parse_mode='Markdown'
    )


async def finalize_and_send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_info = context.user_data
    ev_id = user_info.get("selected_event_id") or (EVENTS[0]["id"] if EVENTS else None)
    ev = next((e for e in EVENTS if e["id"] == ev_id), None)

    summary = (
        "✅ درخواست ثبت‌نامت ثبت شد و برای ادمین ارسال میشه.\n\n"
        f"👤 نام: {user_info.get('name','—')}\n"
        f"📱 تماس: {user_info.get('phone','—')}\n"
        f"🗣️ سطح: {user_info.get('level','—')}\n"
        f"📝 توضیحات: {user_info.get('note','—')}\n"
    )
    if ev:
        summary += f"\n📌 رویداد: {ev['title']}\n📍 مکان: {ev['place']}\n🕒 زمان: {ev['when']}\n"
    await update.effective_chat.send_message(summary)

    # Send to admin group
    if GROUP_CHAT_ID:
        user_chat_id = update.effective_chat.id
        approve_cb = f"approve_{user_chat_id}_{ev_id or 'NA'}"
        reject_cb = f"reject_{user_chat_id}_{ev_id or 'NA'}"
        buttons = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ تایید", callback_data=approve_cb),
             InlineKeyboardButton("❌ رد", callback_data=reject_cb)]
        ])
        admin_txt = (
            f"🔔 **ثبت‌نام جدید English Club**\n\n👤 {user_info.get('name','—')}\n"
            f"📱 {user_info.get('phone','—')}\n🗣️ {user_info.get('level','—')}\n📝 {user_info.get('note','—')}\n"
        )
        if ev:
            admin_txt += f"\n📌 {ev['title']} | {ev['place']} | {ev['when']}"
        await context.bot.send_message(chat_id=GROUP_CHAT_ID, text=admin_txt, parse_mode='Markdown', reply_markup=buttons)

    context.user_data.clear()


def main():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN is not set")

    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("cancel", cancel))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex("^شروع مجدد 🔄$"), start))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex("^لغو عملیات ❌$"), cancel))
    # ترتیب مهمه
    app.add_handler(CallbackQueryHandler(handle_level, pattern=r"^lvl_"))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.CONTACT, handle_contact))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("CBot is running with polling...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
