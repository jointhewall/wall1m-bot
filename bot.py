import logging
import os
import asyncio
from telegram import Update, LabeledPrice, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, PreCheckoutQueryHandler, filters, ContextTypes

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
WALL_URL = "https://t.me/wall1mnames_bot"

names = []

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Welcome to Wall of a Million Names!\n\n"
        "🌍 One name. Forever.\n"
        "When the wall is full — it stays here forever.\n\n"
        "💫 Price: 150 Stars (~$2)\n"
        "🏆 Earn points, invite friends, win rewards!\n\n"
        "Just type your name 👇"
    )

async def handle_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    if len(name) < 2:
        await update.message.reply_text("Please enter a valid name (at least 2 characters)")
        return
    
    context.user_data["name"] = name
    user_id = update.effective_user.id
    
    await update.message.reply_invoice(
        title="Wall of a Million Names",
        description=f"Add '{name}' to the Wall forever",
        payload=f"name:{name}:user:{user_id}",
        currency="XTR",
        prices=[LabeledPrice("One spot on the Wall", 150)],
        provider_token="",
    )

async def precheckout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.pre_checkout_query.answer(ok=True)

async def successful_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    payload = update.message.successful_payment.invoice_payload
    parts = payload.split(":")
    name = parts[1] if len(parts) > 1 else "Unknown"
    user_id = update.effective_user.id
    
    names.append({"name": name, "user_id": user_id})
    number = len(names)
    
    ref_link = f"https://t.me/wall1mnames_bot?start={user_id}"
    
    await update.message.reply_text(
        f"🎉 You are on the Wall!\n\n"
        f"✅ Name: {name}\n"
        f"🔢 Your number: #{number:,}\n\n"
        f"🏆 Earn points — share your link:\n"
        f"{ref_link}\n\n"
        f"Every friend who joins = +50 points for you!"
    )

async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"🏆 Leaderboard\n\n"
        f"Total names: {len(names)}\n\n"
        f"Invite friends to earn points and climb the rankings!"
    )

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("leaderboard", leaderboard))
    app.add_handler(PreCheckoutQueryHandler(precheckout))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_name))
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
