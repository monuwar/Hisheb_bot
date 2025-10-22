# -*- coding: utf-8 -*-
# 💸 Hisheb Bot Pro — Full English + Emoji + Reset (Railway Version)
# Developer: Monuwar Hussain
# Compatible: Python-Telegram-Bot v20+, Railway-ready

import os
import io
import csv
import time
import sqlite3
import hashlib
from datetime import datetime, timedelta
import nest_asyncio
nest_asyncio.apply()
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from telegram import Update, InputFile, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, ContextTypes,
    MessageHandler, filters, CallbackQueryHandler
)
from dotenv import load_dotenv

# ========== ENV ==========
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise SystemExit("🚨 BOT_TOKEN missing in Railway → Variables.")

DB = "expenses.db"

# ========== DATABASE ==========
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
    conn.commit()
    conn.close()

init_db()

# ========== HELPERS ==========
def now_ts():
    return int(time.time())

def month_range():
    now = datetime.now()
    start = datetime(now.year, now.month, 1)
    if now.month == 12:
        end = datetime(now.year + 1, 1, 1)
    else:
        end = datetime(now.year, now.month + 1, 1)
    return int(start.timestamp()), int(end.timestamp()) - 1

def today_range():
    now = datetime.now()
    start = datetime(now.year, now.month, now.day)
    end = start + timedelta(days=1)
    return int(start.timestamp()), int(end.timestamp()) - 1

# ========== CORE COMMANDS ==========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 *Welcome to Hisheb Bot Pro!*\n\n"
        "Track your expenses easily 💰\n"
        "Use /commands to explore all available features.",
        parse_mode="Markdown"
    )

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "ℹ️ Use /commands to see all features.\n\n"
        "Quick Start:\n"
        "• `/add 150 food lunch`\n"
        "• `/daily`, `/monthly`, `/chart`\n"
        "• `/setlimit 10000` then `/status`",
        parse_mode="Markdown"
    )

async def commands_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "📘 *Hisheb — Full Command List*\n\n"
        "➕ `/add <amount> <category> [note]` — Add expense\n"
        "📊 `/summary` — All-time summary by category\n"
        "📅 `/daily` — Today's summary\n"
        "🗓️ `/monthly` — This month's summary\n"
        "💰 `/setlimit <amount>` — Set monthly limit\n"
        "📈 `/limit` — Show current limit\n"
        "🧾 `/status` — Month spent vs limit\n"
        "🥧 `/chart` — Pie chart by category\n"
        "📤 `/export` — Export this month's CSV\n"
        "🔐 `/lock <PIN>` — Lock bot\n"
        "🔓 `/unlock <PIN>` — Unlock bot\n"
        "⏰ `/setreminder <HH:MM>` — Daily reminder\n"
        "🛑 `/reminderoff` — Disable reminder\n"
        "⚠️ `/reset` — Reset all data (with backup)\n"
        "ℹ️ `/help` — Show help info"
    )
    await update.message.reply_text(text, parse_mode="Markdown")

# ========== ADD ==========
async def add_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    args = context.args
    if len(args) < 2:
        await update.message.reply_text("❗ Usage: `/add <amount> <category> [note]`", parse_mode="Markdown")
        return

    try:
        amount = float(args[0])
    except ValueError:
        await update.message.reply_text("❗ Amount must be a number.")
        return

    category = args[1]
    note = " ".join(args[2:]) if len(args) > 2 else ""
    conn = db_conn()
    c = conn.cursor()
    c.execute("INSERT INTO expenses (user_id, amount, category, note, ts) VALUES (?, ?, ?, ?, ?)",
              (user_id, amount, category, note, now_ts()))
    conn.commit()
    conn.close()
    await update.message.reply_text(f"✅ Added: {amount} 💵 in *{category}* ({note})", parse_mode="Markdown")

# ========== SUMMARY ==========
async def summary_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = db_conn()
    c = conn.cursor()
    c.execute("SELECT category, SUM(amount) FROM expenses WHERE user_id=? GROUP BY category",
              (update.effective_user.id,))
    data = c.fetchall()
    conn.close()

    if not data:
        await update.message.reply_text("📭 No records found.")
        return

    text = "📊 *Expense Summary:*\n\n"
    total = 0
    for cat, amt in data:
        text += f"• {cat}: {amt:.2f} 💵\n"
        total += amt
    text += f"\n💰 *Total:* {total:.2f}"
    await update.message.reply_text(text, parse_mode="Markdown")

# ========== DAILY / MONTHLY ==========
async def daily_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    start, end = today_range()
    conn = db_conn()
    c = conn.cursor()
    c.execute("SELECT category, SUM(amount) FROM expenses WHERE user_id=? AND ts BETWEEN ? AND ? GROUP BY category",
              (update.effective_user.id, start, end))
    data = c.fetchall()
    conn.close()

    if not data:
        await update.message.reply_text("📭 No records for today.")
        return

    text = "📅 *Today's Summary:*\n\n"
    total = 0
    for cat, amt in data:
        text += f"• {cat}: {amt:.2f} 💵\n"
        total += amt
    text += f"\n💰 *Total:* {total:.2f}"
    await update.message.reply_text(text, parse_mode="Markdown")

async def monthly_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    start, end = month_range()
    conn = db_conn()
    c = conn.cursor()
    c.execute("SELECT category, SUM(amount) FROM expenses WHERE user_id=? AND ts BETWEEN ? AND ? GROUP BY category",
              (update.effective_user.id, start, end))
    data = c.fetchall()
    conn.close()

    if not data:
        await update.message.reply_text("📭 No records for this month.")
        return

    text = "🗓️ *Monthly Summary:*\n\n"
    total = 0
    for cat, amt in data:
        text += f"• {cat}: {amt:.2f} 💵\n"
        total += amt
    text += f"\n💰 *Total:* {total:.2f}"
    await update.message.reply_text(text, parse_mode="Markdown")

# ========== RESET SYSTEM ==========
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

    conn = db_conn()
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

# ========== APP ==========
def build_app():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("commands", commands_cmd))
    app.add_handler(CommandHandler("add", add_cmd))
    app.add_handler(CommandHandler("summary", summary_cmd))
    app.add_handler(CommandHandler("daily", daily_cmd))
    app.add_handler(CommandHandler("monthly", monthly_cmd))
    app.add_handler(CommandHandler("reset", reset_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_confirmation))
    app.add_handler(CallbackQueryHandler(cancel_reset, pattern="cancel_reset"))
    return app

if __name__ == "__main__":
    print("🚀 Starting Hisheb Bot Pro (Railway Version)...")
    application = build_app()
    application.run_polling()
