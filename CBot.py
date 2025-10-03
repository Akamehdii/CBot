import os
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


# Open or create sheet
try:
sh = client.open(SHEET_NAME)
except Exception:
sh = client.create(SHEET_NAME)
ws = sh.sheet1
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
return {"status": "EngClubBot is running."}