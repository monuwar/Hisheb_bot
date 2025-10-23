# -*- coding: utf-8 -*-
# ✅ Minimal Railway-Safe Hisheb Bot (Core Check Version)

import os, asyncio
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from dotenv import load_dotenv

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    raise SystemExit("🚨 BOT_TOKEN missing! Set it in Railway → Variables.")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ Bot is alive! Hello from Hisheb Bot 👋")

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("ℹ️ Use /commands to see full list later.")

async def commands_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📘 Commands:\n/start – start bot\n/help – show help\n/commands – this list"
    )

def build_app():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("commands", commands_cmd))
    return app

if __name__ == "__main__":
    print("🚀 Starting Hisheb Bot (Minimal Railway Check)…")

    async def main():
        app = build_app()
        await app.initialize()
        await app.start()
        print("🤖 Bot is running…")
        await app.updater.start_polling()
        await asyncio.Event().wait()

    asyncio.run(main())
