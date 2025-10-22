# -*- coding: utf-8 -*-
# 💸 Hisheb Bot Pro Lite — Core Features + Reset (English + Emoji)
# Developer: Monuwar Hussain

import os
import io
import csv
import time
import sqlite3
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

def today_range():
    now = datetime.now()
    start = datetime(now.year, now.month, now.day)
    end = start + timedelta(days=1)
    return int(start.timestamp()), int(end.timestamp())

def month_range():
    now = datetime.now()
    start = datetime(now.year, now.month, 1)
    end = datetime(now.year, now.month + 1, 1) if now.month < 12 else datetime(now.year + 1, 1, 1)
    return int(start.timestamp()), int(end.timestamp())

# ========== CORE COMMANDS ==========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 *Welcome to Hisheb Bot Pro Lite!*\n\n"
        "Track your daily and monthly expenses easily 💰\n"
        "Use */commands* to explore all features.",
        parse_mode="Markdown"
    )

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "ℹ️ *Quick start guide:*\n"
        "• `/add 150 food lunch`\n"
        "• `/daily`, `/monthly`, `/chart`\n"
        "• `/export` to download data\n"
        "• `/reset` to delete all data",
        parse_mode="Markdown"
    )

async def commands_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "📘 *Hisheb — Main Commands*\n\n"
        "➕ `/add <amount> <category> [note]` — Add expense\n"
        "📅 `/daily` — Today's summary\n"
        "🗓️ `/monthly` — Monthly summary\n"
        "📊 `/summary` — Total by category\n"
        "🥧 `/chart` — Pie chart by category\n"
        "📤 `/export` — Export monthly data (CSV)\n"
        "⚠️ `/reset` — Reset all data (with backup)\n"
        "ℹ️ `/help` — Help menu"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")

# ========== ADD EXPENSE ==========
async def add_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if len(args) < 2:
        await update.message.reply_text("❗ Usage: `/add <amount> <category> [note]`", parse_mode="Markdown")
        return

    try:
        amount = float(args[0])
    except ValueError:
        await update.message.reply_text("❌ Invalid amount. Please enter a number.")
        return

    category = args[1]
    note = " ".join(args[2:]) if len(args) > 2 else ""

    conn = db_conn()
    c = conn.cursor()
    c.execute("INSERT INTO expenses (user_id, amount, category, note, ts) VALUES (?, ?, ?, ?, ?)",
              (update.effective_user.id, amount, category, note, now_ts()))
    conn.commit()
    conn.close()

    await update.message.reply_text(
        f"✅ Added: *{amount:.2f}* 💵 in *{category}*\n📝 {note or 'No note'}",
        parse_mode="Markdown"
    )

# ========== SUMMARY ==========
async def summary_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = db_conn()
    c = conn.cursor()
    c.execute("SELECT category, SUM(amount) FROM expenses WHERE user_id=? GROUP BY category",
              (update.effective_user.id,))
    data = c.fetchall()
    conn.close()

    if not data:
        await update.message.reply_text("📭 No records yet.")
        return

    total = 0
    text = "📊 *Expense Summary:*\n\n"
    for cat, amt in data:
        total += amt
        text += f"• {cat}: {amt:.2f} 💵\n"
    text += f"\n💰 *Total:* {total:.2f}"
    await update.message.reply_text(text, parse_mode="Markdown")

# ========== DAILY ==========
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
        total += amt
        text += f"• {cat}: {amt:.2f} 💵\n"
    text += f"\n💰 *Total:* {total:.2f}"
    await update.message.reply_text(text, parse_mode="Markdown")

# ========== MONTHLY ==========
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
        total += amt
        text += f"• {cat}: {amt:.2f} 💵\n"
    text += f"\n💰 *Total:* {total:.2f}"
    await update.message.reply_text(text, parse_mode="Markdown")

# ========== CHART ==========
async def chart_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    start, end = month_range()
    conn = db_conn()
    c = conn.cursor()
    c.execute("SELECT category, SUM(amount) FROM expenses WHERE user_id=? AND ts BETWEEN ? AND ? GROUP BY category",
              (update.effective_user.id, start, end))
    data = c.fetchall()
    conn.close()

    if not data:
        await update.message.reply_text("📭 No data to show chart.")
        return

    labels = [r[0] for r in data]
    amounts = [r[1] for r in data]
    plt.figure(figsize=(5, 5))
    plt.pie(amounts, labels=labels, autopct="%1.1f%%", startangle=90)
    plt.title("💸 Monthly Expense Chart")
    plt.tight_layout()
    plt.savefig("chart.png")
    plt.close()

    with open("chart.png", "rb") as f:
        await update.message.reply_photo(f, caption="🥧 *Monthly Expense Breakdown*", parse_mode="Markdown")

# ========== EXPORT ==========
async def export_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    start, end = month_range()
    conn = db_conn()
    c = conn.cursor()
    c.execute("SELECT amount, category, note, ts FROM expenses WHERE user_id=? AND ts BETWEEN ? AND ?",
              (update.effective_user.id, start, end))
    rows = c.fetchall()
    conn.close()

    if not rows:
        await update.message.reply_text("📭 No data to export.")
        return

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Amount", "Category", "Note", "Date"])
    for r in rows:
        writer.writerow([r[0], r[1], r[2], datetime.fromtimestamp(r[3]).strftime("%Y-%m-%d")])
    output.seek(0)

    await context.bot.send_document(
        chat_id=update.effective_chat.id,
        document=io.BytesIO(output.getvalue().encode()),
        filename="Hisheb_Export.csv",
        caption="📤 Here’s your monthly expense export."
    )

# ========== RESET ==========
pending_reset = {}

async def reset_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    pending_reset[user_id] = True
    keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="cancel_reset")]]
    markup = InlineKeyboardMarkup(keyboard)
    msg = (
        "⚠️ *Warning: Data Reset*\n\n"
        "Are you sure you want to reset **all your data**?\n"
        "Before deletion, a CSV backup will be sent to you.\n\n"
        "✳️ Type *CONFIRM* to proceed.\n"
        "Or press Cancel to abort."
    )
    await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=markup)

async def handle_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in pending_reset:
        return
    text = update.message.text.strip().upper()
    if text != "CONFIRM":
        await update.message.reply_text("❗ Type only CONFIRM or press Cancel.")
        return

    processing = await update.message.reply_text("⚙️ Processing reset...")

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
            caption="📦 Backup before reset."
        )

    c.execute("DELETE FROM expenses WHERE user_id=?", (user_id,))
    conn.commit()
    conn.close()
    pending_reset.pop(user_id)
    await context.bot.edit_message_text(
        chat_id=update.effective_chat.id,
        message_id=processing.message_id,
        text="✅ *All data cleared successfully!*\n\n💡 Start again using `/add`.",
        parse_mode="Markdown"
    )

async def cancel_reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = query.from_user.id
    if uid in pending_reset:
        pending_reset.pop(uid)
        await query.edit_message_text("❎ Reset canceled.")
    else:
        await query.edit_message_text("ℹ️ No active reset request found.")

# ========== BUILD APP ==========
def build_app():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("commands", commands_cmd))
    app.add_handler(CommandHandler("add", add_cmd))
    app.add_handler(CommandHandler("summary", summary_cmd))
    app.add_handler(CommandHandler("daily", daily_cmd))
    app.add_handler(CommandHandler("monthly", monthly_cmd))
    app.add_handler(CommandHandler("chart", chart_cmd))
    app.add_handler(CommandHandler("export", export_cmd))
    app.add_handler(CommandHandler("reset", reset_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_confirmation))
    app.add_handler(CallbackQueryHandler(cancel_reset, pattern="cancel_reset"))
    return app

if __name__ == "__main__":
    print("🚀 Starting Hisheb Bot Pro Lite...")
    app = build_app()
    app.run_polling()
