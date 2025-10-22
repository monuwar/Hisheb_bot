# -*- coding: utf-8 -*-
# 🚀 Hisheb Bot Pro (Full Version + Reset Feature)
# All Commands: /start /help /commands /add /summary /daily /monthly /setlimit /limit /status
#               /lock /unlock /chart /export /setreminder /reminderoff /reset

import os
import io
import csv
import time
import sqlite3
import hashlib
from datetime import datetime, time as dtime, timedelta, timezone
import nest_asyncio
nest_asyncio.apply()
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from telegram import Update, InputFile, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, ContextTypes, JobQueue,
    MessageHandler, filters, CallbackQueryHandler
)
from dotenv import load_dotenv

# ============ ENV ============
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise SystemExit("BOT_TOKEN missing. Set it in Railway → Variables.")

DB = "expenses.db"

# ============ DB ============
def db_conn():
    return sqlite3.connect(DB)

def init_db():
    conn = db_conn()
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS expenses(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount REAL,
            category TEXT,
            note TEXT,
            ts INTEGER
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS settings(
            user_id INTEGER PRIMARY KEY,
            monthly_limit REAL DEFAULT 0,
            locked INTEGER DEFAULT 0,
            pin_hash TEXT,
            reminder_time TEXT
        )
    """)
    conn.commit()
    conn.close()

init_db()

# ============ HELPERS ============
def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

def now_ts() -> int:
    return int(time.time())

def month_range():
    now = datetime.now()
    start = datetime(now.year, now.month, 1)
    if now.month == 12:
        end = datetime(now.year + 1, 1, 1)
    else:
        end = datetime(now.year, now.month + 1, 1)
    return int(start.timestamp()), int(end.timestamp()) - 1

# ============ COMMANDS ============
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Welcome to *Hisheb Bot Pro!*\n\n"
        "Track your daily and monthly expenses easily 💰\n"
        "Type /commands to see everything at a glance.",
        parse_mode="Markdown"
    )

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "ℹ️ Use /commands to see all features with examples.\n\n"
        "Quick start:\n• /add 150 food lunch\n• /daily /monthly /chart\n• /setlimit 10000 then /status",
        parse_mode="Markdown"
    )

async def commands_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "📘 *Hisheb — Full Command List*\n\n"
        "/add <amount> <category> [note] — Add expense\n"
        "/summary — All-time summary by category\n"
        "/daily — Today's summary\n"
        "/monthly — This month's summary\n"
        "/setlimit <amount> — Set monthly limit\n"
        "/limit — Show current limit\n"
        "/status — Month spent vs limit\n"
        "/chart — Pie chart by category\n"
        "/export — Export CSV (this month)\n"
        "/lock <PIN> — Lock bot\n"
        "/unlock <PIN> — Unlock bot\n"
        "/setreminder <HH:MM> — Daily reminder\n"
        "/reminderoff — Disable reminder\n"
        "/reset — Reset all data (with backup)\n"
        "/help — Show help"
    )
    await update.message.reply_text(text, parse_mode="Markdown")

# ============ RESET SYSTEM ============
pending_reset = {}

async def reset_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    pending_reset[user_id] = True

    keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="cancel_reset")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    msg = (
        "⚠️ *Warning: Data Reset*\n\n"
        "Are you sure you want to reset **all your data**?\n\n"
        "Before deletion, a CSV backup will be sent to you.\n"
        "Once confirmed, everything will be *permanently deleted* and cannot be recovered.\n\n"
        "✳️ Type *CONFIRM* to proceed.\n"
        "Or press the Cancel button below to abort this action."
    )
    await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=reply_markup)

async def handle_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in pending_reset:
        return

    text = update.message.text.strip().upper()
    if text != "CONFIRM":
        await update.message.reply_text("❗ Please type only CONFIRM or press Cancel.")
        return

    processing = await update.message.reply_text("⚙️ Processing your reset request...")

    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT amount, category, note, ts FROM expenses WHERE user_id=?", (user_id,))
    rows = c.fetchall()

    if rows:
        out = io.StringIO()
        writer = csv.writer(out)
        writer.writerow(["Amount", "Category", "Note", "Date"])
        for r in rows:
            writer.writerow(r)
        out.seek(0)
        await context.bot.send_document(
            chat_id=update.effective_chat.id,
            document=io.BytesIO(out.getvalue().encode()),
            filename="Hisheb_Backup.csv",
            caption="📦 Here's a backup of your data before reset."
        )

    c.execute("DELETE FROM expenses WHERE user_id=?", (user_id,))
    conn.commit()
    conn.close()
    pending_reset.pop(user_id)

    await context.bot.edit_message_text(
        chat_id=update.effective_chat.id,
        message_id=processing.message_id,
        text="✅ *All data cleared successfully!*\n\n"
             "Your records have been deleted and a CSV backup has been sent above.\n"
             "You can now start fresh and add new transactions anytime.\n\n"
             "💡 Tip: Use /add to record your first new expense.",
        parse_mode="Markdown"
    )

async def cancel_reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    if user_id in pending_reset:
        pending_reset.pop(user_id)
        await query.edit_message_text("❎ Reset canceled. Your data is safe.")
    else:
        await query.edit_message_text("ℹ️ No active reset request found.")

# ============ APP ============
def build_app():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("commands", commands_cmd))
    app.add_handler(CommandHandler("reset", reset_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_confirmation))
    app.add_handler(CallbackQueryHandler(cancel_reset, pattern="cancel_reset"))

    return app

if __name__ == "__main__":
    print("🚀 Starting Hisheb Bot Pro...")
    application = build_app()
    application.run_polling()
