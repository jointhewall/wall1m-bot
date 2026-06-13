import logging
import os
from telegram import Update, LabeledPrice, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, PreCheckoutQueryHandler, filters, ContextTypes

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN", "ВСТАВЬ_СВОЙ_ТОКЕН_ЗДЕСЬ")
WALL_URL = "https://wall1m.com"  # Замени на свой домен

# Хранилище имён (потом заменим на базу данных)
names = []

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    ref = context.args[0] if context.args else None
    
    keyboard = [[InlineKeyboardButton("✨ Add my name — 150 Stars", callback_data="pay")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"👋 Welcome to *Wall of a Million Names*!\n\n"
        f"🌍 One name. Forever.\n"
        f"When the wall is full — it stays here forever.\n\n"
        f"💫 Price: 150 Stars (~$2)\n"
        f"🏆 Earn points, climb the leaderboard, win rewards!\n\n"
        f"Type your name and press the button below 👇",
        parse_mode="Markdown"
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
        description=f"Add '{name}' to the Wall forever 🌍",
        payload=f"name:{name}:user:{user_id}",
        currency="XTR",  # XTR = Telegram Stars
        prices=[LabeledPrice("One spot on the Wall", 150)],
        provider_token="",  # Пусто для Stars
    )

async def precheckout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.pre_checkout_query
    await query.answer(ok=True)

async def successful_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    payment = update.message.successful_payment
    payload = payment.invoice_payload
    
    # Извлекаем имя из payload
    parts = payload.split(":")
    name = parts[1] if len(parts) > 1 else "Unknown"
    user_id = update.effective_user.id
    
    # Добавляем в список
    names.append({"name": name, "user_id": user_id})
    number = len(names)
    
    # Личная ссылка
    ref_link = f"{WALL_URL}?ref={user_id}"
    
    await update.message.reply_text(
        f"🎉 *You are on the Wall!*\n\n"
        f"✅ Name: *{name}*\n"
        f"🔢 Your number: *#{number:,}*\n\n"
        f"🏆 *Earn points & climb the leaderboard:*\n"
        f"Share your personal link — get 50 points for every friend who joins!\n\n"
        f"🔗 Your link:\n`{ref_link}`\n\n"
        f"🌍 See your name on the Wall:\n{WALL_URL}",
        parse_mode="Markdown"
    )

async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"🏆 *Leaderboard*\n\n"
        f"Total names on the Wall: *{len(names)}*\n\n"
        f"🥇 Coming soon — invite friends to earn points!\n\n"
        f"🔗 Share your link to climb the rankings.",
        parse_mode="Markdown"
    )

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("leaderboard", leaderboard))
    app.add_handler(PreCheckoutQueryHandler(precheckout))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_name))
    
    logger.info("Bot started!")
    app.run_polling()

if __name__ == "__main__":
    main()
