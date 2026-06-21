import logging
import os
import asyncio
from io import BytesIO
from PIL import Image, ImageDraw
from telegram import Update, LabeledPrice
from telegram.ext import Application, CommandHandler, MessageHandler, PreCheckoutQueryHandler, filters, ContextTypes

# Import our custom database module
import database

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")

def create_card(name, number, message=""):
    """Generates a high-density digital artifact certificate without horizontal lines."""
    W, H = 800, 500
    img = Image.new("RGB", (W, H), color="#0a0a0a")
    draw = ImageDraw.Draw(img)

    # Frame blocks
    draw.rectangle([20, 20, W-20, H-20], outline="#c8f135", width=2)
    draw.rectangle([28, 28, W-28, H-28], outline="#c8f135", width=1)

    # Header title
    draw.text((W//2, 80), "WALL OF MILLION NAMES", fill="#c8f135", anchor="mm")

    # Name content text
    draw.text((W//2, 200), name, fill="#ffffff", anchor="mm")

    # Unique global registry sequence number
    draw.text((W//2, 270), f"#{number:,}", fill="#c8f135", anchor="mm")

    # User personalized message string
    if message:
        draw.text((W//2, 340), f'"{message}"', fill="#aaaaaa", anchor="mm")

    # Footer timestamp details
    from datetime import datetime
    date_str = datetime.now().strftime("%d %B %Y")
    draw.text((W//2, 420), date_str, fill="#666666", anchor="mm")
    draw.text((W//2, 455), "wall1m.com", fill="#c8f135", anchor="mm")

    buf = BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the user registration process sequentially and processes referral codes."""
    context.user_data.clear()
    user_id = update.effective_user.id
    logger.info(f"--- START COMMAND TRIGGERED BY USER {user_id} ---")
    
    # Extract referral payload from command arguments
    args = context.args
    if args and args[0].isdigit():
        referrer_id = int(args[0])
        if referrer_id != user_id:
            context.user_data["invited_by"] = referrer_id
            logger.info(f"Referrer detected: {referrer_id}")

    try:
        logger.info("Attempting to connect to Supabase database via database.py...")
        existing_user = await database.get_user_by_id(user_id)
        logger.info(f"Database response for user check: {existing_user}")
    except Exception as db_err:
        logger.error(f"CRITICAL DATABASE CONNECTION ERROR: {db_err}", exc_info=True)
        await update.message.reply_text("⚠️ Database connection failed. Please check host environment variables.")
        return
    
    if False:  # ВРЕМЕННЫЙ КОСТЫЛЬ ДЛЯ ТЕСТА РЕГИСТРАЦИИ
        await update.message.reply_text(
            f"👋 Welcome back, *{existing_user['name']}*!\n\n"
            f"📊 Your Stats:\n"
            f"🏆 Points: *{existing_user['points']}*\n"
            f"⭐ Avatar Level: *{existing_user['level']}*\n"
            f"👑 King Status: *{'Active' if existing_user['is_vip'] else 'Inactive'}*\n\n"
            f"🔄 Want to upgrade your digital asset profile? Choose your option:\n"
            f"1️⃣ Upgrade Avatar Level (+30 points)\n"
            f"2️⃣ Claim 'King of the Hill' crown (+50 points)\n\n"
            f"📥 Select your action below.",
            parse_mode="Markdown"
        )
        return

    await update.message.reply_text(
        "👋 Welcome to Wall of a Million Names!\n\n"
        "🌍 One name. Forever.\n\n"
        "💫 Price: 150 Stars (~$2)\n"
        "🏆 Earn points, invite friends, win rewards!\n\n"
        "Step 1: Just type your name below 👇"
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Processes sequential message steps one-by-one."""
    text = update.message.text.strip()
    user_id = update.effective_user.id

    # Step 2: Waiting for the optional message input
    if context.user_data.get("waiting_message"):
        message = text if text.lower() != "skip" else ""
        name = context.user_data.get("name", "")
        invited_by = context.user_data.get("invited_by")
        
        context.user_data["message"] = message
        context.user_data["waiting_message"] = False

        # Build dynamic billing system structure payload for standard slot purchase
        payload = f"buy_slot:{user_id}:name:{name}:msg:{message}"
        if invited_by:
            payload += f":ref:{invited_by}"

        await update.message.reply_invoice(
            title="Wall of a Million Names",
            description=f"Add '{name}' to the Wall forever",
            payload=payload,
            currency="XTR",
            prices=[LabeledPrice("One spot on the Wall", 1)],
            provider_token="",
        )
        return

    # Step 1: Validating and capturing the name
    if len(text) < 2:
        await update.message.reply_text("Please enter a valid name (at least 2 characters)")
        return

    context.user_data["name"] = text
    context.user_data["waiting_message"] = True

    await update.message.reply_text(
        f"✅ Name saved: *{text}*\n\n"
        f"Step 2: Add a message to the Wall? (optional)\n"
        f"Write your message or type *skip*",
        parse_mode="Markdown"
    )

async def precheckout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Validates and acknowledges the Telegram Stars pre-checkout query transaction."""
    await update.pre_checkout_query.answer(ok=True)

async def successful_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles verification processing upon successful transactions."""
    payload = update.message.successful_payment.invoice_payload
    parts = payload.split(":")
    user_id = update.effective_user.id
    
    # Process base profile registration placement action execution sequence
    if parts[0] == "buy_slot":
        name = parts[3]
        message = parts[5]
        invited_by = int(parts[7]) if len(parts) > 6 else None
        
        avatar_url = f"https://api.dicebear.com/7.x/bottts/png?seed={user_id}"
        
        # Insert entry into database registry reference
        placement_id = await database.create_new_participant(
            telegram_user_id=user_id,
            name=name,
            message=message,
            avatar_url=avatar_url,
            invited_by=invited_by
        )
        
        # Apply rewards to the upstream system referrer user
        if invited_by:
            await database.add_points_to_user(telegram_user_id=invited_by, points_to_add=50)
            
        ref_link = f"https://t.me/wall1mnames_bot?start={user_id}"
        
      try:
    card = create_card(name, placement_id, message)
    await update.message.reply_photo(
        photo=card,
        caption=(
            f"🎉 You are on the Wall!\n\n"
            f"✅ Name: {name}\n"
            f"🔢 Number: #{placement_id:,}\n\n"
            f"🏆 Share your referral link to earn +50 points:\n{ref_link}"
        )
    )
except Exception as e:
            logger.error(f"Card asset compilation failure scenario: {e}")
            await update.message.reply_text(
                f"🎉 You are on the Wall!\n\n"
                f"✅ Name: {name}\n"
                f"🔢 Number: #{placement_id:,}\n\n"
                f"🏆 Share your referral link:\n{ref_link}"
            )

async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Displays total stats from the database."""
    total_count = await database.get_total_participants_count()
    await update.message.reply_text(
        f"🏆 *Leaderboard & Stats*\n\n"
        f"🌍 Total active names on the wall: *{total_count:,}*\n\n"
        f"Invite friends using your link to accumulate points and reach the top 10 positions!",
        parse_mode="Markdown"
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
