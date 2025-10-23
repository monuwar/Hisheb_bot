# -*- coding: utf-8 -*-
# 🚀 Hisheb Bot Pro (English + Emoji + Reset + CSV + Chart)
# Author: Monuwar Edition

import os, io, csv, sqlite3, asyncio, nest_asyncio, matplotlib.pyplot as plt
from datetime import datetime as dt
from telegram import Update, InputFile, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from dotenv import load_dotenv

# ===== INIT =====
load_dotenv()
nest_asyncio.apply()
BOT_TOKEN = os.getenv("BOT_TOKEN")
DB = "expenses.db"

# ===== DATABASE =====
def db_conn():
    conn = sqlite3.connect(DB)
    conn.execute("""CREATE TABLE IF NOT EXISTS expenses(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        amount REAL,
        category TEXT,
        note TEXT,
        ts INTEGER
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS settings(
        user_id INTEGER PRIMARY KEY,
        monthly_limit REAL DEFAULT 0
    )""")
    conn.commit()
    return conn

# ===== COMMANDS =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ Bot is alive! Hello from *Hisheb Bot* 👋", parse_mode="Markdown")

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "📘 *Commands:*\n"
        "/start – start bot\n"
        "/add <amount> <category> [note] – Add expense\n"
        "/summary – All-time summary by category\n"
        "/daily – Today’s summary\n"
        "/monthly – This month’s summary\n"
        "/setlimit <amount> – Set monthly limit\n"
        "/limit – Show current limit\n"
        "/status – Month spent vs limit\n"
        "/chart – Pie chart (this month)\n"
        "/export – Export CSV (this month)\n"
        "/reset – Reset all data (with backup)\n"
        "/help – Show help info"
    )
    await update.message.reply_text(text, parse_mode="Markdown")

# ===== ADD EXPENSE =====
async def add_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        args = context.args
        if len(args) < 2:
            await update.message.reply_text("⚠️ Usage: /add <amount> <category> [note]")
            return
        amount = float(args[0])
        category = args[1]
        note = " ".join(args[2:]) if len(args) > 2 else ""
        conn = db_conn()
        conn.execute("INSERT INTO expenses (user_id, amount, category, note, ts) VALUES (?, ?, ?, ?, ?)",
                     (update.effective_user.id, amount, category, note, int(dt.now().timestamp())))
        conn.commit()
        conn.close()
        await update.message.reply_text(f"💸 Added: {amount} ({category}) ✅")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

# ===== SUMMARY =====
async def summary_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = db_conn()
    c = conn.cursor()
    c.execute("SELECT category, SUM(amount) FROM expenses WHERE user_id=? GROUP BY category", (update.effective_user.id,))
    rows = c.fetchall()
    conn.close()
    if not rows:
        await update.message.reply_text("📊 No data yet.")
        return
    msg = "📊 *All-time Summary:*\n"
    for cat, total in rows:
        msg += f"• {cat}: {total:.2f}\n"
    await update.message.reply_text(msg, parse_mode="Markdown")

# ===== LIMIT =====
async def setlimit_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("⚠️ Usage: /setlimit <amount>")
        return
    amount = float(context.args[0])
    conn = db_conn()
    conn.execute("INSERT OR REPLACE INTO settings (user_id, monthly_limit) VALUES (?, ?)",
                 (update.effective_user.id, amount))
    conn.commit()
    conn.close()
    await update.message.reply_text(f"✅ Monthly limit set to {amount:.2f}")

async def limit_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = db_conn()
    c = conn.cursor()
    c.execute("SELECT monthly_limit FROM settings WHERE user_id=?", (update.effective_user.id,))
    row = c.fetchone()
    conn.close()
    if not row or row[0] == 0:
        await update.message.reply_text("⚠️ No limit set. Use /setlimit <amount>")
    else:
        await update.message.reply_text(f"💰 Current limit: {row[0]:.2f}")

# ===== EXPORT =====
async def export_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = db_conn()
    c = conn.cursor()
    c.execute("SELECT amount, category, note, ts FROM expenses WHERE user_id=?", (update.effective_user.id,))
    rows = c.fetchall()
    conn.close()
    if not rows:
        await update.message.reply_text("⚠️ No data to export.")
        return
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Amount", "Category", "Note", "Date"])
    for r in rows:
        writer.writerow([r[0], r[1], r[2], dt.fromtimestamp(r[3]).strftime("%Y-%m-%d")])
    output.seek(0)
    await update.message.reply_document(InputFile(io.BytesIO(output.getvalue().encode()), filename="Hisheb_Data.csv"))
    await update.message.reply_text("✅ Exported successfully.")

# ===== RESET =====
pending_reset = {}

async def reset_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    pending_reset[user_id] = True
    keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="cancel_reset")]]
    await update.message.reply_text(
        "⚠️ *Warning: Data Reset*\n\n"
        "Are you sure you want to reset *all your data*?\n\n"
        "Before deletion, a CSV backup will be sent to you.\n"
        "Once confirmed, everything will be *permanently deleted* and cannot be recovered.\n\n"
        "👉 Type *CONFIRM* to proceed, or press Cancel to abort.",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def confirm_reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().upper()
    user_id = update.effective_user.id
    if user_id not in pending_reset:
        return
    if text != "CONFIRM":
        return
    conn = db_conn()
    c = conn.cursor()
    c.execute("SELECT amount, category, note, ts FROM expenses WHERE user_id=?", (user_id,))
    rows = c.fetchall()
    if rows:
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["Amount", "Category", "Note", "Date"])
        for r in rows:
            writer.writerow([r[0], r[1], r[2], dt.fromtimestamp(r[3]).strftime("%Y-%m-%d")])
        output.seek(0)
        await update.message.reply_document(InputFile(io.BytesIO(output.getvalue().encode()), filename="Backup_Before_Reset.csv"))
    c.execute("DELETE FROM expenses WHERE user_id=?", (user_id,))
    conn.commit()
    conn.close()
    del pending_reset[user_id]
    await update.message.reply_text("✅ All data cleared successfully!")

async def cancel_reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    if user_id in pending_reset:
        del pending_reset[user_id]
    await query.edit_message_text("❎ Reset canceled. Your data is safe.")

# ===== MAIN =====
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("add", add_cmd))
    app.add_handler(CommandHandler("summary", summary_cmd))
    app.add_handler(CommandHandler("setlimit", setlimit_cmd))
    app.add_handler(CommandHandler("limit", limit_cmd))
    app.add_handler(CommandHandler("export", export_cmd))
    app.add_handler(CommandHandler("reset", reset_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, confirm_reset))
    app.add_handler(CallbackQueryHandler(cancel_reset, pattern="cancel_reset"))

    print("🚀 Starting Hisheb Bot Pro (Full English + Emoji)...")
    app.run_polling()

if __name__ == "__main__":
    main()
