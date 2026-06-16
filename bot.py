mport logging
import os
import asyncio
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
from telegram import Update, LabeledPrice
from telegram.ext import Application, CommandHandler, MessageHandler, PreCheckoutQueryHandler, filters, ContextTypes

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
names = []

def create_card(name, number, message=""):
    # Размер карточки
    W, H = 800, 500
    img = Image.new("RGB", (W, H), color="#0a0a0a")
    draw = ImageDraw.Draw(img)

    # Рамка
    draw.rectangle([20, 20, W-20, H-20], outline="#c8f135", width=2)
    draw.rectangle([28, 28, W-28, H-28], outline="#c8f135", width=1)

    # Заголовок
    draw.text((W//2, 80), "WALL OF MILLION NAMES", fill="#c8f135", anchor="mm")
    draw.line([(100, 110), (W-100, 110)], fill="#c8f135", width=1)

    # Имя
    draw.text((W//2, 200), name, fill="#ffffff", anchor="mm")

    # Номер
    draw.text((W//2, 270), f"#{number:,}", fill="#c8f135", anchor="mm")

    # Послание
    if message:
        draw.text((W//2, 340), f'"{message}"', fill="#aaaaaa", anchor="mm")

    # Дата и ссылка
    from datetime import datetime
    date_str = datetime.now().strftime("%d %B %Y")
    draw.text((W//2, 420), date_str, fill="#666666", anchor="mm")
    draw.text((W//2, 455), "wall1m.com", fill="#c8f135", anchor="mm")

    # Сохраняем в буфер
    buf = BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text(
        "👋 Welcome to Wall of a Million Names!\n\n"
        "🌍 One name. Forever.\n\n"
        "💫 Price: 150 Stars (~$2)\n"
        "🏆 Earn points, invite friends, win rewards!\n\n"
        "Just type your name 👇"
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    user_id = update.effective_user.id

    # Если ждём послание
    if context.user_data.get("waiting_message"):
        message = text if text.lower() != "skip" else ""
        name = context.user_data.get("name", "")
        context.user_data["message"] = message
        context.user_data["waiting_message"] = False

        await update.message.reply_invoice(
            title="Wall of a Million Names",
            description=f"Add '{name}' to the Wall forever",
            payload=f"name:{name}:msg:{message}:user:{user_id}",
            currency="XTR",
            prices=[LabeledPrice("One spot on the Wall", 150)],
            provider_token="",
        )
        return

    # Иначе это имя
    if len(text) < 2:
        await update.message.reply_text("Please enter a valid name (at least 2 characters)")
        return

    context.user_data["name"] = text
    context.user_data["waiting_message"] = True

    await update.message.reply_text(
        f"✅ Name: *{text}*\n\n"
        f"📝 Add a message to the Wall? (optional)\n"
        f"Write something or type *skip*",
        parse_mode="Markdown"
    )

async def precheckout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.pre_checkout_query.answer(ok=True)

async def successful_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    payload = update.message.successful_payment.invoice_payload
    parts = payload.split(":")

    name = parts[1] if len(parts) > 1 else "Unknown"
    message = parts[3] if len(parts) > 3 else ""
    user_id = update.effective_user.id

    names.append({"name": name, "message": message, "user_id": user_id})
    number = len(names)

    ref_link = f"https://t.me/wall1mnames_bot?start={user_id}"

    # Отправляем карточку
    try:
        card = create_card(name, number, message)
        await update.message.reply_photo(
            photo=card,
            caption=(
                f"🎉 *You are on the Wall!*\n\n"
                f"✅ Name: *{name}*\n"
                f"🔢 Number: *#{number:,}*\n\n"
                f"🏆 Share your link to earn points:\n{ref_link}"
            ),
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Card error: {e}")
        await update.message.reply_text(
            f"🎉 You are on the Wall!\n\n"
            f"✅ Name: {name}\n"
            f"🔢 Number: #{number:,}\n\n"
            f"🏆 Share your link:\n{ref_link}"
        )

async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"🏆 Leaderboard\n\nTotal names: {len(names)}\n\nInvite friends to earn points!"
    )

async def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("leaderboard", leaderboard))
    app.add_handler(PreCheckoutQueryHandler(precheckout))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    await app.initialize()
    await app.start()
    await app.updater.start_polling(drop_pending_updates=True)
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
