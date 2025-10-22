# -*- coding: utf-8 -*-
# 💸 Hisheb Bot Pro — Final Async Safe Railway Version
# ✅ All Commands + Reset Backup + Markdown Fixed + Emoji UI
# Developer: Monuwar Hussain

import os, io, csv, time, sqlite3, asyncio
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
from telegram.helpers import escape_markdown
from dotenv import load_dotenv

# ========== ENV ==========
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise SystemExit("🚨 BOT_TOKEN missing! Set it in Railway → Variables.")

DB = "/tmp/expenses.db"  # Railway safe path

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
def now_ts(): return int(time.time())

def today_range():
    now = datetime.now()
    start = datetime(now.year, now.month, now.day)
    end = start + timedelta(days=1)
    return int(start.timestamp()), int(end.timestamp())

def month_range():
    now = datetime.now()
    start = datetime(now.year, now.month, 1)
    next_m = datetime(now.year + (now.month // 12), (now.month % 12) + 1, 1)
    return int(start.timestamp()), int(next_m.timestamp())

# ========== CORE ==========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "👋 *Welcome to Hisheb Bot Pro\\!*\\n\\n"
        "Track your daily & monthly expenses effortlessly 💰\\n"
        "Use /commands to explore all features\\."
    )
    await update.message.reply_text(msg, parse_mode="MarkdownV2")

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "ℹ️ *Quick start:*\n"
        "• `/add 150 food lunch`\n"
        "• `/daily`, `/monthly`, `/chart`\n"
        "• `/export` — download CSV\n"
        "• `/reset` — delete all data"
    )
    await update.message.reply_text(msg, parse_mode="MarkdownV2")

async def commands_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "📘 *Hisheb — Full Command List*\n\n"
        "➕ `/add <amount> <category> [note]` — Add expense\n"
        "📅 `/daily` — Today's summary\n"
        "🗓️ `/monthly` — This month's summary\n"
        "📊 `/summary` — All-time summary\n"
        "🥧 `/chart` — Pie chart by category\n"
        "📤 `/export` — Export CSV (this month)\n"
        "⚠️ `/reset` — Reset all data (with backup)\n"
        "ℹ️ `/help` — Show help info"
    )
    await update.message.reply_text(msg, parse_mode="MarkdownV2")

# ========== ADD ==========
async def add_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if len(args) < 2:
        await update.message.reply_text("❗ Usage: `/add <amount> <category> [note]`", parse_mode="MarkdownV2")
        return
    try:
        amt = float(args[0])
    except ValueError:
        await update.message.reply_text("❌ Amount must be a number.")
        return
    cat = args[1]
    note = " ".join(args[2:]) if len(args) > 2 else ""
    conn = db_conn()
    c = conn.cursor()
    c.execute("INSERT INTO expenses(user_id,amount,category,note,ts)VALUES(?,?,?,?,?)",
              (update.effective_user.id, amt, cat, note, now_ts()))
    conn.commit(); conn.close()
    await update.message.reply_text(
        f"✅ Added *{amt:.2f}* 💵 in *{escape_markdown(cat,2)}*\n📝 {escape_markdown(note or 'No note',2)}",
        parse_mode="MarkdownV2")

# ========== SUMMARY ==========
async def summary_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = db_conn()
    c = conn.cursor()
    c.execute("SELECT category,SUM(amount)FROM expenses WHERE user_id=? GROUP BY category",
              (update.effective_user.id,))
    rows = c.fetchall(); conn.close()
    if not rows:
        await update.message.reply_text("📭 No records found."); return
    total = sum(r[1] for r in rows)
    msg = "📊 *Expense Summary:*\n\n" + "\n".join([f"• {r[0]}: {r[1]:.2f} 💵" for r in rows])
    msg += f"\n\n💰 *Total:* {total:.2f}"
    await update.message.reply_text(msg, parse_mode="MarkdownV2")

# ========== DAILY ==========
async def daily_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    s, e = today_range()
    conn = db_conn(); c = conn.cursor()
    c.execute("SELECT category,SUM(amount)FROM expenses WHERE user_id=? AND ts BETWEEN ? AND ? GROUP BY category",
              (update.effective_user.id, s, e))
    rows = c.fetchall(); conn.close()
    if not rows:
        await update.message.reply_text("📭 No data for today."); return
    total = sum(r[1] for r in rows)
    msg = "📅 *Today's Summary:*\n\n" + "\n".join([f"• {r[0]}: {r[1]:.2f} 💵" for r in rows])
    msg += f"\n\n💰 *Total:* {total:.2f}"
    await update.message.reply_text(msg, parse_mode="MarkdownV2")

# ========== MONTHLY ==========
async def monthly_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    s, e = month_range()
    conn = db_conn(); c = conn.cursor()
    c.execute("SELECT category,SUM(amount)FROM expenses WHERE user_id=? AND ts BETWEEN ? AND ? GROUP BY category",
              (update.effective_user.id, s, e))
    rows = c.fetchall(); conn.close()
    if not rows:
        await update.message.reply_text("📭 No records for this month."); return
    total = sum(r[1] for r in rows)
    msg = "🗓️ *Monthly Summary:*\n\n" + "\n".join([f"• {r[0]}: {r[1]:.2f} 💵" for r in rows])
    msg += f"\n\n💰 *Total:* {total:.2f}"
    await update.message.reply_text(msg, parse_mode="MarkdownV2")

# ========== CHART ==========
async def chart_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    s, e = month_range()
    conn = db_conn(); c = conn.cursor()
    c.execute("SELECT category,SUM(amount)FROM expenses WHERE user_id=? AND ts BETWEEN ? AND ? GROUP BY category",
              (update.effective_user.id, s, e))
    rows = c.fetchall(); conn.close()
    if not rows:
        await update.message.reply_text("📭 No data to display chart."); return
    labels, values = zip(*rows)
    plt.figure(figsize=(5,5))
    plt.pie(values, labels=labels, autopct="%1.1f%%", startangle=90)
    plt.title("💸 Monthly Expense Chart")
    plt.savefig("/tmp/chart.png"); plt.close()
    with open("/tmp/chart.png","rb") as f:
        await update.message.reply_photo(f, caption="🥧 *Monthly Expense Chart*", parse_mode="MarkdownV2")

# ========== EXPORT ==========
async def export_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    s, e = month_range()
    conn = db_conn(); c = conn.cursor()
    c.execute("SELECT amount,category,note,ts FROM expenses WHERE user_id=? AND ts BETWEEN ? AND ?",
              (update.effective_user.id, s, e))
    rows = c.fetchall(); conn.close()
    if not rows:
        await update.message.reply_text("📭 No data to export."); return
    out = io.StringIO(); w = csv.writer(out)
    w.writerow(["Amount","Category","Note","Date"])
    for r in rows:
        w.writerow([r[0],r[1],r[2],datetime.fromtimestamp(r[3]).strftime("%Y-%m-%d")])
    out.seek(0)
    await context.bot.send_document(update.effective_chat.id,
        document=io.BytesIO(out.getvalue().encode()),
        filename="Hisheb_Export.csv",
        caption="📤 Your monthly data export")

# ========== RESET ==========
pending_reset = {}

async def reset_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    pending_reset[uid] = True
    kb = [[InlineKeyboardButton("❌ Cancel", callback_data="cancel_reset")]]
    markup = InlineKeyboardMarkup(kb)
    msg = (
        "⚠️ *Warning: Data Reset*\n\n"
        "Are you sure you want to reset all your data?\n"
        "A CSV backup will be sent before deletion.\n\n"
        "Type *CONFIRM* to proceed or press Cancel."
    )
    await update.message.reply_text(msg, parse_mode="MarkdownV2", reply_markup=markup)

async def handle_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid not in pending_reset: return
    if update.message.text.strip().upper() != "CONFIRM":
        await update.message.reply_text("❗ Type CONFIRM or press Cancel."); return
    proc = await update.message.reply_text("⚙️ Processing reset...")
    conn = db_conn(); c = conn.cursor()
    c.execute("SELECT amount,category,note,ts FROM expenses WHERE user_id=?", (uid,))
    rows = c.fetchall()
    if rows:
        out = io.StringIO(); w = csv.writer(out)
        w.writerow(["Amount","Category","Note","Date"])
        for r in rows:
            w.writerow([r[0],r[1],r[2],datetime.fromtimestamp(r[3]).strftime("%Y-%m-%d")])
        out.seek(0)
        await context.bot.send_document(uid, io.BytesIO(out.getvalue().encode()),
            filename="Hisheb_Backup.csv", caption="📦 Backup before reset")
    c.execute("DELETE FROM expenses WHERE user_id=?", (uid,))
    conn.commit(); conn.close(); pending_reset.pop(uid)
    await context.bot.edit_message_text(chat_id=update.effective_chat.id,
        message_id=proc.message_id,
        text="✅ *All data cleared successfully!*\\n\\n💡 Use /add to start again.",
        parse_mode="MarkdownV2")

async def cancel_reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; uid = q.from_user.id
    if uid in pending_reset:
        pending_reset.pop(uid); await q.edit_message_text("❎ Reset canceled. Your data is safe.")
    else:
        await q.edit_message_text("ℹ️ No active reset found.")

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

# ========== RAILWAY SAFE MAIN ==========
if __name__ == "__main__":
    print("🚀 Starting Hisheb Bot Pro (Async Safe Railway Build)…")

    async def main():
        app = build_app()
        await app.initialize()
        await app.start()
        print("🤖 Bot is now running...")
        await app.updater.start_polling()
        await asyncio.Event().wait()  # Keeps running forever

    asyncio.run(main())
