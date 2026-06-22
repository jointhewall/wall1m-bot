import logging
import os
import asyncio
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
from telegram import Update, LabeledPrice
from telegram.ext import Application, CommandHandler, MessageHandler, PreCheckoutQueryHandler, filters, ContextTypes

# Import our custom database module
import database

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")

def _load_font(size):
    """Loads a TrueType font that supports Cyrillic characters.
    Primary source: the DejaVuSans.ttf bundled inside the matplotlib package —
    this is guaranteed to exist after `pip install matplotlib`, regardless of
    the host OS or its system font configuration.
    Falls back to common Linux system font paths, then to PIL's default bitmap font."""
    candidate_paths = []

    try:
        import matplotlib
        mpl_font = os.path.join(
            os.path.dirname(matplotlib.__file__),
            "mpl-data", "fonts", "ttf", "DejaVuSans.ttf"
        )
        candidate_paths.append(mpl_font)
    except Exception:
        pass

    candidate_paths += [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/dejavu/DejaVuSans.ttf",
    ]

    for path in candidate_paths:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue

    logger.warning("No TrueType font with Cyrillic support found, falling back to default bitmap font")
    return ImageFont.load_default()

def create_card(name, number, message=""):
    """Generates a high-density digital artifact certificate without horizontal lines."""
    W, H = 800, 500
    img = Image.new("RGB", (W, H), color="#0a0a0a")
    draw = ImageDraw.Draw(img)

    font_title = _load_font(22)
    font_name = _load_font(38)
    font_number = _load_font(28)
    font_message = _load_font(20)
    font_footer = _load_font(16)

    # Frame blocks
    draw.rectangle([20, 20, W-20, H-20], outline="#c8f135", width=2)
    draw.rectangle([28, 28, W-28, H-28], outline="#c8f135", width=1)

    # Header title
    draw.text((W//2, 80), "WALL OF MILLION NAMES", fill="#c8f135", anchor="mm", font=font_title)

    # Name content text
    draw.text((W//2, 200), name, fill="#ffffff", anchor="mm", font=font_name)

    # Unique global registry sequence number
    draw.text((W//2, 270), f"#{number:,}", fill="#c8f135", anchor="mm", font=font_number)

    # User personalized message string
    if message:
        draw.text((W//2, 340), f'"{message}"', fill="#aaaaaa", anchor="mm", font=font_message)

    # Footer timestamp details
    from datetime import datetime
    date_str = datetime.now().strftime("%d %B %Y")
    draw.text((W//2, 420), date_str, fill="#666666", anchor="mm", font=font_footer)
    draw.text((W//2, 455), "wall1m.com", fill="#c8f135", anchor="mm", font=font_footer)

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

    if existing_user:
        # Daily check-in: +1 point, once per calendar day
        checked_in = await database.try_daily_checkin(user_id)
        checkin_line = "🎁 Daily check-in: +1 point!\n\n" if checked_in else ""

        await update.message.reply_text(
            f"👋 Welcome back, {existing_user['name']}!\n\n"
            f"{checkin_line}"
            f"📊 Your Stats:\n"
            f"🏆 Points: {existing_user['points']}\n"
            f"⭐ Avatar Level: {existing_user['level']}\n"
            f"👥 Friends invited: {existing_user['referral_count']}\n"
            f"👑 King Status: {'Active' if existing_user['is_vip'] else 'Inactive'}\n\n"
            f"🔄 Want to upgrade your profile?\n"
            f"/levelup — Upgrade Avatar Level (150 ⭐, +points)\n"
            f"/king — Claim 'King of the Hill' crown (150 ⭐, +50 points)\n"
            f"/leaderboard — See the Top 10"
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
        f"✅ Name saved: {text}\n\n"
        f"Step 2: Add a message to the Wall? (optional)\n"
        f"Write your message or type skip"
    )

async def levelup_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sends an invoice for a repeat 'Level Up' purchase (150 Stars)."""
    user_id = update.effective_user.id
    existing_user = await database.get_user_by_id(user_id)
    if not existing_user:
        await update.message.reply_text("You need to add your name to the Wall first! Type /start to begin.")
        return

    await update.message.reply_invoice(
        title="Level Up Your Avatar",
        description="Upgrade your avatar level and earn bonus points",
        payload=f"levelup:{user_id}",
        currency="XTR",
        prices=[LabeledPrice("Avatar Level Up", 1)],
        provider_token="",
    )


async def king_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sends an invoice for claiming the 'King of the Hill' crown (150 Stars)."""
    user_id = update.effective_user.id
    existing_user = await database.get_user_by_id(user_id)
    if not existing_user:
        await update.message.reply_text("You need to add your name to the Wall first! Type /start to begin.")
        return

    current_king = await database.get_current_king()
    king_note = f"\n\n👑 Current King: {current_king['name']}" if current_king else "\n\n👑 The throne is empty!"

    await update.message.reply_invoice(
        title="King of the Hill",
        description=f"Claim the crown and become the new King!{king_note}",
        payload=f"king:{user_id}",
        currency="XTR",
        prices=[LabeledPrice("King of the Hill Crown", 1)],
        provider_token="",
    )


async def precheckout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Validates and acknowledges the Telegram Stars pre-checkout query transaction."""
    await update.pre_checkout_query.answer(ok=True)

async def successful_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles verification processing upon successful transactions."""
    payload = update.message.successful_payment.invoice_payload
    parts = payload.split(":")
    user_id = update.effective_user.id

    # ── Level Up purchase: repeat buy, grows in value (LTV mechanic) ──────────
    if parts[0] == "levelup":
        result = await database.upgrade_user_level(telegram_user_id=user_id)
        await update.message.reply_text(
            f"⭐ Avatar Level Up!\n\n"
            f"📈 New Level: {result['level']}\n"
            f"🏆 Points earned: +{result['points_awarded']}\n\n"
            f"Next upgrade will be worth even more — keep climbing!"
        )
        return

    # ── King of the Hill purchase: dethrone + crown + VIP status ───────────────
    if parts[0] == "king":
        previous_king = await database.get_current_king()
        await database.crown_new_king(telegram_user_id=user_id, points_to_add=50)
        dethrone_note = f"\n\n👋 {previous_king['name']} has been dethroned." if previous_king else ""
        await update.message.reply_text(
            f"👑 You are the new King of the Hill!\n\n"
            f"🏆 Points earned: +50\n"
            f"✨ VIP status is now active on your profile.{dethrone_note}"
        )
        return

    # ── Standard slot purchase: register a new name on the Wall ────────────────
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

        ref_link = f"https://t.me/wall1mnames_bot?start={user_id}"

        # Apply rewards to the upstream system referrer user (+50 per referral,
        # plus a one-time +500 milestone bonus at 10 referrals)
        if invited_by:
            referral_result = await database.register_referral(
                telegram_user_id=invited_by,
                referral_points=50,
                milestone_bonus=500,
                milestone_count=10
            )
            if referral_result["milestone_hit"]:
                try:
                    await context.bot.send_message(
                        chat_id=invited_by,
                        text=(
                            f"🎉 Milestone reached!\n\n"
                            f"You've invited 10 friends to the Wall!\n"
                            f"🏆 Bonus: +500 points awarded!"
                        )
                    )
                except Exception as notify_err:
                    logger.warning(f"Could not notify referrer {invited_by} about milestone: {notify_err}")

        # ВАЖНО: никакого parse_mode и звёздочек вокруг текста с пользовательскими данными —
        # имя или сообщение пользователя может содержать символы *, _, [, ], которые ломают
        # Markdown-парсер Telegram и вызывают ошибку "can't find end of the entity"
        try:
            card = create_card(name, placement_id, message)
            await update.message.reply_photo(
                photo=card,
                caption=(
                    f"🎉 You are on the Wall!\n\n"
                    f"✅ Name: {name}\n"
                    f"🔢 Number: #{placement_id:,}\n\n"
                    f"🏆 Share your referral link to earn +50 points (and +500 at 10 friends!):\n{ref_link}"
                )
            )
        except Exception as e:
            logger.error(f"Card asset compilation failure scenario: {e}", exc_info=True)
            await update.message.reply_text(
                f"🎉 You are on the Wall!\n\n"
                f"✅ Name: {name}\n"
                f"🔢 Number: #{placement_id:,}\n\n"
                f"🏆 Share your referral link:\n{ref_link}"
            )

async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Displays the real Top-10 leaderboard and total stats from the database."""
    total_count = await database.get_total_participants_count()
    top10 = await database.get_top_leaderboard(limit=10)

    text = f"🏆 Leaderboard & Stats\n\n🌍 Total names on the wall: {total_count:,}\n\n"

    if top10:
        medals = ["👑", "🥈", "🥉"]
        for i, row in enumerate(top10):
            medal = medals[i] if i < 3 else f"{i + 1}."
            vip_tag = " 👑VIP" if row["is_vip"] else ""
            text += f"{medal} {row['name']} — {row['points']} pts (Lvl {row['level']}){vip_tag}\n"
    else:
        text += "No one on the wall yet — be the first!"

    text += "\n\nInvite friends using your link to climb the ranks!"
    await update.message.reply_text(text)

async def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("leaderboard", leaderboard))
    app.add_handler(CommandHandler("levelup", levelup_command))
    app.add_handler(CommandHandler("king", king_command))
    app.add_handler(PreCheckoutQueryHandler(precheckout))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    await app.initialize()
    await app.start()
    await app.updater.start_polling(drop_pending_updates=True)
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
