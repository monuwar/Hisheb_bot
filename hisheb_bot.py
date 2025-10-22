# -*- coding: utf-8 -*-
# 🚀 Hisheb Bot Pro — Full Features (English + Emoji UI) — Railway-ready
# Features: /start /help /commands /add /summary /daily /monthly /setlimit /limit /status
#           /lock /unlock /export /chart /setreminder /reminderoff  (+ limit alerts)

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

from telegram import Update, InputFile
from telegram.ext import (
    ApplicationBuilder, CommandHandler, ContextTypes, JobQueue
)
from dotenv import load_dotenv

# ----- ENV -----
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise SystemExit("BOT_TOKEN is missing. Set it in Railway → Variables.")

DB = "expenses.db"

# ----------------------- DB -----------------------
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
            reminder_time TEXT   -- 'HH:MM' (24h), server local time
        )
    """)
    conn.commit(); conn.close()

def ensure_user(user_id: int):
    conn = db_conn(); c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO settings(user_id) VALUES(?)", (user_id,))
    conn.commit(); conn.close()

init_db()

# --------------------- Helpers ---------------------
def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

def now_ts() -> int:
    return int(time.time())

def today_range():
    now = datetime.now()
    start = datetime(now.year, now.month, now.day)
    end = start + timedelta(days=1)
    return int(start.timestamp()), int(end.timestamp()) - 1

def month_range():
    now = datetime.now()
    start = datetime(now.year, now.month, 1)
    if now.month == 12:
        end = datetime(now.year + 1, 1, 1)
    else:
        end = datetime(now.year, now.month + 1, 1)
    return int(start.timestamp()), int(end.timestamp()) - 1

async def is_locked(user_id: int) -> bool:
    conn = db_conn(); c = conn.cursor()
    c.execute("SELECT locked FROM settings WHERE user_id=?", (user_id,))
    row = c.fetchone()
    conn.close()
    return bool(row and row[0])

async def limit_value(user_id: int) -> float:
    conn = db_conn(); c = conn.cursor()
    c.execute("SELECT monthly_limit FROM settings WHERE user_id=?", (user_id,))
    row = c.fetchone(); conn.close()
    return float(row[0] or 0) if row else 0.0

async def month_spent(user_id: int) -> float:
    start, end = month_range()
    conn = db_conn(); c = conn.cursor()
    c.execute("SELECT SUM(amount) FROM expenses WHERE user_id=? AND ts BETWEEN ? AND ?",
              (user_id, start, end))
    s = c.fetchone()[0] or 0.0
    conn.close()
    return float(s)

# -------------- Core Command Handlers --------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ensure_user(update.effective_user.id)
    await update.message.reply_text(
        "👋 Welcome to *Hisheb Bot Pro!*\n\n"
        "Track your daily & monthly expenses easily 💰\n"
        "Type /commands to see everything at a glance.",
        parse_mode="Markdown"
    )

async def commands_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "📘 *Hisheb — Full Command List*\n\n"
        "➕ /add `<amount> <category> [note]` — Add expense\n"
        "📊 /summary — All-time summary by category\n"
        "🗓️ /daily — Today’s summary\n"
        "📅 /monthly — This month’s summary\n"
        "💰 /setlimit `<amount>` — Set monthly limit\n"
        "🚦 /limit — Show current limit\n"
        "📈 /status — Month spent vs limit\n"
        "🕰️ /setreminder `<HH:MM>` — Daily reminder\n"
        "🔕 /reminderoff — Disable reminder\n"
        "📉 /chart — Pie chart by category\n"
        "📤 /export — Export CSV (this month)\n"
        "🔒 /lock `<PIN>` — Lock bot\n"
        "🔓 /unlock `<PIN>` — Unlock bot\n"
        "ℹ️ /help — Show help"
    )
    await update.message.reply_text(text, parse_mode="Markdown")

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "ℹ️ Use /commands to see all features with examples.\n"
        "Quick start:\n"
        "• /add 150 food lunch\n"
        "• /daily, /monthly, /chart\n"
        "• /setlimit 10000, then /status",
        parse_mode="Markdown"
    )

# ----------------- Expense & Reports ----------------
async def add_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    ensure_user(uid)

    if await is_locked(uid):
        await update.message.reply_text("🔒 Locked. Use /unlock <PIN> to unlock.")
        return

    if len(context.args) < 2:
        await update.message.reply_text("⚠️ Usage: /add <amount> <category> [note]\nExample: /add 150 food lunch")
        return

    try:
        amount = float(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ Amount must be a number. Example: /add 150 food lunch")
        return

    category = context.args[1]
    note = " ".join(context.args[2:]) if len(context.args) > 2 else ""

    conn = db_conn(); c = conn.cursor()
    c.execute("INSERT INTO expenses(user_id,amount,category,note,ts) VALUES(?,?,?,?,?)",
              (uid, amount, category, note, now_ts()))
    conn.commit(); conn.close()

    await update.message.reply_text(
        f"✅ Added!\n💵 {amount} | 📂 {category}\n📝 {note or 'No note'}"
    )

    # Limit alerts
    lim = await limit_value(uid)
    if lim > 0:
        spent = await month_spent(uid)
        pct = spent / lim if lim else 0
        if pct >= 1.0:
            await update.message.reply_text(f"🚨 *Limit exceeded!* {spent:.0f} / {lim:.0f}", parse_mode="Markdown")
        elif pct >= 0.8:
            await update.message.reply_text(f"⚠️ *Reached 80% of limit:* {spent:.0f} / {lim:.0f}", parse_mode="Markdown")

async def summary_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if await is_locked(uid):
        await update.message.reply_text("🔒 Locked. Use /unlock <PIN>.")
        return

    conn = db_conn(); c = conn.cursor()
    c.execute("SELECT category, SUM(amount) FROM expenses WHERE user_id=? GROUP BY category", (uid,))
    rows = c.fetchall(); conn.close()

    if not rows:
        await update.message.reply_text("📭 No expenses yet.")
        return

    total = 0.0
    lines = ["📊 *Summary (All-time):*\n"]
    for cat, amt in rows:
        lines.append(f"• {cat}: 💵 {amt:.2f}")
        total += float(amt or 0)
    lines.append(f"\n🧾 *Total:* {total:.2f}")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

async def daily_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if await is_locked(uid):
        await update.message.reply_text("🔒 Locked.")
        return

    s, e = today_range()
    conn = db_conn(); c = conn.cursor()
    c.execute("""SELECT category, SUM(amount) FROM expenses
                 WHERE user_id=? AND ts BETWEEN ? AND ? GROUP BY category""", (uid, s, e))
    rows = c.fetchall(); conn.close()

    if not rows:
        await update.message.reply_text("📆 No expenses today.")
        return

    total = 0.0
    lines = ["🗓️ *Today’s Expenses:*\n"]
    for cat, amt in rows:
        lines.append(f"• {cat}: 💵 {amt:.2f}")
        total += float(amt or 0)
    lines.append(f"\n🧾 *Total Today:* {total:.2f}")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

async def monthly_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if await is_locked(uid):
        await update.message.reply_text("🔒 Locked.")
        return

    s, e = month_range()
    conn = db_conn(); c = conn.cursor()
    c.execute("""SELECT category, SUM(amount) FROM expenses
                 WHERE user_id=? AND ts BETWEEN ? AND ? GROUP BY category""", (uid, s, e))
    rows = c.fetchall(); conn.close()

    if not rows:
        await update.message.reply_text("📅 No expenses recorded this month.")
        return

    total = 0.0
    lines = ["📅 *Monthly Summary:*\n"]
    for cat, amt in rows:
        lines.append(f"• {cat}: 💵 {amt:.2f}")
        total += float(amt or 0)
    lines.append(f"\n🧾 *Total This Month:* {total:.2f}")
    lim = await limit_value(uid)
    if lim > 0:
        lines.append(f"💰 *Limit:* {lim:.2f}")
        if total >= lim:
            lines.append("🚨 *Limit exceeded!*")
        elif total >= lim * 0.8:
            lines.append("⚠️ *Reached 80% of limit.*")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

# ---------------- Limit / Status -------------------
async def setlimit_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id; ensure_user(uid)
    if len(context.args) != 1:
        await update.message.reply_text("⚙️ Usage: /setlimit <amount>")
        return
    try:
        lim = float(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ Invalid number.")
        return
    conn = db_conn(); c = conn.cursor()
    c.execute("UPDATE settings SET monthly_limit=? WHERE user_id=?", (lim, uid))
    conn.commit(); conn.close()
    await update.message.reply_text(f"💰 Monthly limit set: {lim:.2f}")

async def limit_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    lim = await limit_value(uid)
    await update.message.reply_text(f"💰 Current limit: {lim:.2f}")

async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    lim = await limit_value(uid)
    spent = await month_spent(uid)
    await update.message.reply_text(f"📈 This month: {spent:.2f} / {lim:.2f}")

# ---------------- Lock / Unlock --------------------
async def lock_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id; ensure_user(uid)
    if len(context.args) != 1:
        await update.message.reply_text("🔒 Usage: /lock <PIN>")
        return
    pin = context.args[0].strip()
    if len(pin) < 3:
        await update.message.reply_text("❌ PIN too short (min 3).")
        return
    conn = db_conn(); c = conn.cursor()
    c.execute("UPDATE settings SET locked=1, pin_hash=? WHERE user_id=?", (sha256(pin), uid))
    conn.commit(); conn.close()
    await update.message.reply_text("🔒 Bot locked. Use /unlock <PIN>.")

async def unlock_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if len(context.args) != 1:
        await update.message.reply_text("🔓 Usage: /unlock <PIN>")
        return
    pin = context.args[0].strip()
    conn = db_conn(); c = conn.cursor()
    c.execute("SELECT pin_hash FROM settings WHERE user_id=?", (uid,))
    row = c.fetchone()
    if not row or not row[0]:
        await update.message.reply_text("ℹ️ No PIN set. Use /lock <PIN> first.")
        conn.close(); return
    ok = sha256(pin) == row[0]
    if ok:
        c.execute("UPDATE settings SET locked=0 WHERE user_id=?", (uid,))
        conn.commit()
        await update.message.reply_text("✅ Unlocked!")
    else:
        await update.message.reply_text("❌ Incorrect PIN.")
    conn.close()

# ----------------- Export / Chart ------------------
async def export_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    s, e = month_range()
    conn = db_conn(); c = conn.cursor()
    c.execute("SELECT amount, category, note, ts FROM expenses WHERE user_id=? AND ts BETWEEN ? AND ?",
              (uid, s, e))
    rows = c.fetchall(); conn.close()
    if not rows:
        await update.message.reply_text("📭 No data to export this month.")
        return
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["amount", "category", "note", "datetime"])
    for a, cat, note, ts in rows:
        w.writerow([f"{a:.2f}", cat, note, datetime.fromtimestamp(ts).isoformat()])
    out.seek(0)
    await update.message.reply_document(
        document=InputFile(out, filename="hisheb_month.csv"),
        caption="📤 Exported this month’s expenses."
    )

async def chart_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    s, e = month_range()
    conn = db_conn(); c = conn.cursor()
    c.execute("SELECT category, SUM(amount) FROM expenses WHERE user_id=? AND ts BETWEEN ? AND ? GROUP BY category",
              (uid, s, e))
    rows = c.fetchall(); conn.close()
    if not rows:
        await update.message.reply_text("📊 No data to chart for this month.")
        return
    labels, amounts = zip(*rows)
    fig, ax = plt.subplots()
    ax.pie(amounts, labels=labels, autopct="%1.1f%%")
    ax.set_title("Hisheb — Expense Breakdown (This Month)")
    fig.savefig("chart.png")
    plt.close(fig)
    await update.message.reply_photo(photo=open("chart.png", "rb"), caption="📈 Expense Chart (This Month)")

# ---------------- Reminders (JobQueue) -------------
REMINDER_JOBS = {}  # user_id -> Job

async def send_daily_summary(context: ContextTypes.DEFAULT_TYPE):
    uid = context.job.chat_id
    s, e = today_range()
    conn = db_conn(); c = conn.cursor()
    c.execute("""SELECT category, SUM(amount) FROM expenses
                 WHERE user_id=? AND ts BETWEEN ? AND ? GROUP BY category""", (uid, s, e))
    rows = c.fetchall(); conn.close()
    if not rows:
        await context.bot.send_message(chat_id=uid, text="🕰️ Daily reminder: No expenses added today.")
        return
    total = sum(float(r[1] or 0) for r in rows)
    lines = ["🕰️ *Daily Reminder* — Today:\n"]
    for cat, amt in rows:
        lines.append(f"• {cat}: 💵 {float(amt):.2f}")
    lines.append(f"\n🧾 *Total:* {total:.2f}")
    await context.bot.send_message(chat_id=uid, text="\n".join(lines), parse_mode="Markdown")

def parse_hhmm(s: str):
    hh, mm = s.split(":")
    return int(hh), int(mm)

async def setreminder_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id; ensure_user(uid)
    if len(context.args) != 1:
        await update.message.reply_text("🕰️ Usage: /setreminder <HH:MM> (24h)")
        return
    t = context.args[0]
    try:
        hh, mm = parse_hhmm(t)
        assert 0 <= hh < 24 and 0 <= mm < 60
    except Exception:
        await update.message.reply_text("❌ Invalid time. Example: 21:30")
        return

    # save to DB
    conn = db_conn(); c = conn.cursor()
    c.execute("UPDATE settings SET reminder_time=? WHERE user_id=?", (t, uid))
    conn.commit(); conn.close()

    # (re)schedule
    if uid in REMINDER_JOBS:
        REMINDER_JOBS[uid].schedule_removal()
    jt = dtime(hour=hh, minute=mm)
    job = context.job_queue.run_daily(send_daily_summary, jt, chat_id=uid, name=f"rem_{uid}")
    REMINDER_JOBS[uid] = job

    await update.message.reply_text(f"✅ Daily reminder set at {t} (server time).")

async def reminderoff_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid in REMINDER_JOBS:
        REMINDER_JOBS[uid].schedule_removal()
        REMINDER_JOBS.pop(uid, None)
    conn = db_conn(); c = conn.cursor()
    c.execute("UPDATE settings SET reminder_time=NULL WHERE user_id=?", (uid,))
    conn.commit(); conn.close()
    await update.message.reply_text("🔕 Reminder disabled.")

async def restore_reminders(job_queue: JobQueue):
    """Re-schedule reminders for users who had saved times (called on startup)."""
    conn = db_conn(); c = conn.cursor()
    c.execute("SELECT user_id, reminder_time FROM settings WHERE reminder_time IS NOT NULL")
    rows = c.fetchall(); conn.close()
    for uid, t in rows:
        try:
            hh, mm = parse_hhmm(t)
            jt = dtime(hour=hh, minute=mm)
            job = job_queue.run_daily(send_daily_summary, jt, chat_id=uid, name=f"rem_{uid}")
            REMINDER_JOBS[uid] = job
        except Exception:
            continue
# --- Reset Command (Full Pro Version with Backup + Confirm + Cancel + Processing Animation) ---
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
import csv
import io
import time

pending_reset = {}

def reset_cmd(update, context):
    user_id = update.effective_user.id
    if user_id in pending_reset:
        update.message.reply_text("⚠️ You already have a pending reset request.\nPlease type CONFIRM or press Cancel below.")
        return

    pending_reset[user_id] = True
    keyboard = [
        [InlineKeyboardButton("❌ Cancel", callback_data="cancel_reset")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    update.message.reply_text(
        "⚠️ **Warning!**\n\n"
        "Are you sure you want to reset **all your data**?\n"
        "Before deletion, your data will be backed up and sent as a CSV file.\n\n"
        "Once confirmed, everything will be *permanently deleted* and cannot be recovered.\n\n"
        "👉 Type **CONFIRM** to proceed.\n"
        "❌ Or press the Cancel button below to abort this action.",
        parse_mode="Markdown",
        reply_markup=reply_markup
    )

def handle_confirmation(update, context):
    user_id = update.effective_user.id
    text = update.message.text.strip().upper()

    if user_id not in pending_reset:
        return

    if text == "CONFIRM":
        # Step 1: Show processing animation
        processing_msg = update.message.reply_text("🕒 Processing your reset request...")
        time.sleep(2.5)
        context.bot.edit_message_text(
            chat_id=update.effective_chat.id,
            message_id=processing_msg.message_id,
            text="📦 Preparing your backup..."
        )

        conn = sqlite3.connect(DB)
        c = conn.cursor()
        c.execute("SELECT amount, category, note, date FROM expenses WHERE user_id=?", (user_id,))
        rows = c.fetchall()

        # Step 2: Send CSV backup if data exists
        if rows:
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(["Amount", "Category", "Note", "Date"])
            writer.writerows(rows)
            output.seek(0)
            context.bot.send_document(
                chat_id=update.effective_chat.id,
                document=io.BytesIO(output.getvalue().encode()),
                filename="Hisheb_Backup.csv",
                caption="📦 Here’s a backup of your data before reset."
            )

        # Step 3: Delete all data
        c.execute("DELETE FROM expenses WHERE user_id=?", (user_id,))
        conn.commit()
        conn.close()
        pending_reset.pop(user_id)

        # Step 4: Success message
        context.bot.edit_message_text(
            chat_id=update.effective_chat.id,
            message_id=processing_msg.message_id,
            text="🧹 **Data Cleared Successfully!**\n\n"
                 "All your records have been deleted, and a backup CSV has been sent above.\n\n"
                 "✨ You can now start fresh and add new transactions anytime!\n\n"
                 "💡 *Tip:* Use /add to record your first new expense.",
            parse_mode="Markdown"
        )

    else:
        update.message.reply_text("❗ Please type only CONFIRM or press Cancel.")

def cancel_reset(update, context):
    query = update.callback_query
    user_id = query.from_user.id
    if user_id in pending_reset:
        pending_reset.pop(user_id)
        query.edit_message_text("❎ Reset action has been canceled. Your data is safe.")
    else:
        query.edit_message_text("ℹ️ No active reset request found.")

# --- Register Handlers ---
# -------------------- Main ------------------------
def build_app():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("commands", commands_cmd))

    app.add_handler(CommandHandler("add", add_cmd))
    app.add_handler(CommandHandler("summary", summary_cmd))
    app.add_handler(CommandHandler("daily", daily_cmd))
    app.add_handler(CommandHandler("monthly", monthly_cmd))

    app.add_handler(CommandHandler("setlimit", setlimit_cmd))
    app.add_handler(CommandHandler("limit", limit_cmd))
    app.add_handler(CommandHandler("status", status_cmd))

    app.add_handler(CommandHandler("lock", lock_cmd))
    app.add_handler(CommandHandler("unlock", unlock_cmd))

    app.add_handler(CommandHandler("export", export_cmd))
    app.add_handler(CommandHandler("chart", chart_cmd))

   
app.add_handler(CommandHandler("setreminder", setreminder_cmd))
    app.add_handler(CommandHandler("reminderoff", reminderoff_cmd))

    # ✅ Reset System Handlers
    app.add_handler(CommandHandler("reset", reset_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_confirmation))
    app.add_handler(CallbackQueryHandler(cancel_reset, pattern="cancel_reset"))

    return app

if __name__ == "__main__":
    print("🚀 Starting Hisheb Bot Pro…")
    application = build_app()
    # restore saved reminders on startup
    application.post_init = lambda app: restore_reminders(app.job_queue)
    application.run_polling()
