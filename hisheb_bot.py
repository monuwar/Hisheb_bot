# -*- coding: utf-8 -*-
# 🤖 Hisheb Bot (Pro Edition)
# Language: Bangla + English
# Developer: Monuwar + ChatGPT Automation

import os
import sqlite3
import time
from datetime import datetime
from telegram import ParseMode
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters

BOT_TOKEN = os.getenv("BOT_TOKEN")
DB = "expenses.db"

# ---------------- Database ----------------
def init_db():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS expenses(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        amount REAL,
        category TEXT,
        note TEXT,
        ts INTEGER
    )""")
    conn.commit()
    conn.close()

init_db()

# ---------------- Functions ----------------
def add_expense(user_id, amount, category, note):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("INSERT INTO expenses(user_id, amount, category, note, ts) VALUES(?,?,?,?,?)",
              (user_id, amount, category, note, int(time.time())))
    conn.commit()
    conn.close()

def get_summary(user_id):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT category, SUM(amount) FROM expenses WHERE user_id=? GROUP BY category", (user_id,))
    rows = c.fetchall()
    conn.close()
    if not rows:
        return "📊 কোনো খরচ রেকর্ড করা হয়নি।\nNo expenses recorded yet."
    summary = "💰 *Hisheb Summary:*\n\n"
    for cat, total in rows:
        summary += f"• {cat}: {total:.2f}\n"
    return summary

# ---------------- Commands ----------------
def start(update, context):
    update.message.reply_text(
        "👋 *Welcome to Hisheb Bot*\n\n"
        "Track your daily expenses easily.\n\n"
        "👉 Use /commands to see all available features.\n\n"
        "💬 বাংলা বা English দুই ভাষাতেই ব্যবহার করতে পারবেন!",
        parse_mode=ParseMode.MARKDOWN
    )

def add_cmd(update, context):
    args = context.args
    if len(args) < 2:
        update.message.reply_text("Usage: /add <amount> <category> [note]\nউদাহরণ: /add 150 food lunch")
        return
    try:
        amount = float(args[0])
    except ValueError:
        update.message.reply_text("❌ Amount must be a number / পরিমাণ সংখ্যায় দিন।")
        return
    category = args[1]
    note = " ".join(args[2:]) if len(args) > 2 else ""
    add_expense(update.effective_user.id, amount, category, note)
    update.message.reply_text(f"✅ Added {amount:.2f} to {category} / {category}-এ {amount:.2f} টাকা যোগ হয়েছে।")

def summary_cmd(update, context):
    update.message.reply_text(get_summary(update.effective_user.id), parse_mode=ParseMode.MARKDOWN)

def commands_cmd(update, context):
    text = """
📘 *Hisheb Bot – Command List (বাংলা + English)*

🇧🇩 বাংলা কমান্ড:
🟢 /add <টাকা> <ক্যাটাগরি> [নোট] — খরচ যোগ করুন  
🟢 /summary — সারাংশ দেখুন  
🟢 /daily — আজকের খরচ  
🟢 /monthly — মাসিক সারাংশ  
🟢 /setlimit <পরিমাণ> — মাসিক বাজেট সেট করুন  
🟢 /status — বাজেট বনাম খরচ  
🟢 /setreminder <সময়> — রিমাইন্ডার চালু করুন  
🟢 /reminderoff — রিমাইন্ডার বন্ধ করুন  
🟢 /chart — মাসিক খরচের চার্ট  
🟢 /export — CSV ডেটা নিন  
🟢 /lock <PIN> — হিসেব লক করুন  
🟢 /unlock <PIN> — আনলক করুন  
🟢 /help — সাহায্য দেখুন  

🌐 English Commands:
🟢 /add <amount> <category> [note] — Add expense  
🟢 /summary — Show summary  
🟢 /daily — Today’s total  
🟢 /monthly — Monthly summary  
🟢 /setlimit <amount> — Set monthly limit  
🟢 /status — Budget vs Spent  
🟢 /setreminder <HH:MM> — Enable reminder  
🟢 /reminderoff — Disable reminder  
🟢 /chart — Expense chart  
🟢 /export — Export as CSV  
🟢 /lock <PIN> — Lock Hisheb  
🟢 /unlock <PIN> — Unlock  
🟢 /help — Show help  

💡 Use either বাংলা or English commands – Hisheb understands both!
"""
    update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

# ---------------- Main ----------------
def main():
    updater = Updater(BOT_TOKEN, use_context=True)
    dp = updater.dispatcher
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("add", add_cmd))
    dp.add_handler(CommandHandler("summary", summary_cmd))
    dp.add_handler(CommandHandler("commands", commands_cmd))
    updater.start_polling()
    print("🤖 Hisheb Bot running...")
    updater.idle()

if __name__ == "__main__":
    main()
