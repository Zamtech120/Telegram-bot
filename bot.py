import os
import logging
import requests
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler,
    ContextTypes, filters
)
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import uvicorn
import threading

# --- Load environment variables ---
load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN") or "your_telegram_bot_token"
API_KEY = os.getenv("API_KEY") or "my_secure_api_key_123"

# --- Logging ---
logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

user_check_state = {}

# --- FastAPI backend ---
backend_app = FastAPI()

@backend_app.get("/status")
def status():
    return {"status": "ok"}

@backend_app.post("/check_emails")
async def check_emails(request: Request):
    headers = request.headers
    if headers.get("x-api-key") != API_KEY:
        return JSONResponse(content={"error": "Unauthorized"}, status_code=401)
    
    data = await request.json()
    emails = data.get("emails", [])
    results = {}

    for email in emails:
        if "flag" in email:
            results[email] = "yes"
        elif "active" in email:
            results[email] = "no"
        else:
            results[email] = "error"
    return results

def run_backend():
    uvicorn.run(backend_app, host="127.0.0.1", port=8000)

# --- Telegram bot handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("✅ Start Email Check", callback_data="check")],
        [InlineKeyboardButton("ℹ️ Help", callback_data="help")],
        [InlineKeyboardButton("❌ Cancel", callback_data="cancel")],
        [InlineKeyboardButton("📡 Status", callback_data="status")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "🎉 Hello! I'm your PayPal email verification bot.\n\n"
        "Use the buttons below to get started 👇",
        reply_markup=reply_markup
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "check":
        await check_command(query, context)
    elif query.data == "help":
        await help_command(query, context)
    elif query.data == "cancel":
        await cancel_command(query, context)
    elif query.data == "status":
        await status_command(query, context)

async def check_command(update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.from_user.id if hasattr(update, "from_user") else update.effective_user.id
    user_check_state[user_id] = True
    text = "📨 Please send the email(s) you want to check."

    if hasattr(update, "edit_message_text"):
        await update.edit_message_text(text)
    elif hasattr(update, "message") and update.message:
        await update.message.reply_text(text)

async def help_command(update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "ℹ️ *How to use this bot:*\n\n"
        "1. Tap '✅ Start Email Check' to begin.\n"
        "2. Send a list of email addresses (comma or newline-separated).\n"
        "3. The bot will check if they're flagged or active.\n\n"
        "Tap '❌ Cancel' to cancel.\n"
        "Tap '📡 Status' to check backend health."
    )
    if hasattr(update, "edit_message_text"):
        await update.edit_message_text(help_text, parse_mode="Markdown")
    elif hasattr(update, "message") and update.message:
        await update.message.reply_text(help_text, parse_mode="Markdown")

async def cancel_command(update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.from_user.id if hasattr(update, "from_user") else update.effective_user.id
    user_check_state.pop(user_id, None)
    msg = "❌ Email check canceled."
    if hasattr(update, "edit_message_text"):
        await update.edit_message_text(msg)
    elif hasattr(update, "message") and update.message:
        await update.message.reply_text(msg)

async def status_command(update, context: ContextTypes.DEFAULT_TYPE):
    try:
        response = requests.get("http://127.0.0.1:8000/status")
        msg = "✅ Backend is up and running!" if response.status_code == 200 else "⚠ Backend returned an error."
    except Exception:
        msg = "❌ Could not reach backend."
    if hasattr(update, "edit_message_text"):
        await update.edit_message_text(msg)
    elif hasattr(update, "message") and update.message:
        await update.message.reply_text(msg)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not user_check_state.get(user_id):
        await update.message.reply_text("❗ Please press '✅ Start Email Check' first.")
        return

    emails = parse_emails(update.message.text)
    if not emails:
        await update.message.reply_text("⚠ Please send valid email addresses.")
        return

    await update.message.reply_text(f"🔍 Checking {len(emails)} emails...")

    try:
        response = requests.post(
            "http://127.0.0.1:8000/check_emails",
            json={"emails": emails},
            headers={"x-api-key": API_KEY}
        )
        response.raise_for_status()
        results = response.json()
        await update.message.reply_text(format_results(results))
    except Exception as e:
        logger.error(f"Backend error: {e}")
        await update.message.reply_text(f"⚠ Error: {str(e)}")
    finally:
        user_check_state[user_id] = False

# --- Helpers ---
def parse_emails(text: str):
    text = text.replace(",", "\n")
    return list({line.strip() for line in text.splitlines() if "@" in line and "." in line})

def format_results(results: dict):
    status_map = {
        "yes": "⚠️ Flagged",
        "no": "✅ Active",
        "captcha": "🛡 CAPTCHA blocked",
        "error": "❓ Unknown or Error"
    }
    return "\n".join(f"{status_map.get(status, '❓ Unknown')} – {email}" for email, status in results.items())

# --- Run both backend and bot ---
if __name__ == "__main__":
    # Start backend in separate thread
    threading.Thread(target=run_backend, daemon=True).start()

    if not TELEGRAM_BOT_TOKEN:
        print("❌ TELEGRAM_BOT_TOKEN is missing.")
        exit(1)

    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("🤖 Bot is running...")
    app.run_polling()
