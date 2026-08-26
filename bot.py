# ═══════════════════════════════════════════════════════════════
# Добавить в bot.py
# ═══════════════════════════════════════════════════════════════

# ── 1. В функции start(), в блок разбора args, добавить ещё одну ветку ──
#    (рядом с уже существующими проверками args[0].isdigit() / "ga_" / "n-")
#
#    elif args and args[0].startswith("reg_"):
#        code = args[0][4:]
#        pending = await database.get_pending_registration(code)
#
#        if not pending:
#            text = (
#                "Эта ссылка уже использована или устарела. Введи имя заново 👇"
#                if is_ru else
#                "This link was already used or has expired. Type your name again 👇"
#            )
#            await update.message.reply_text(text)
#            return
#
#        msg_preview = f'\n💬 "{pending["message"]}"' if pending["message"] else ""
#        if is_ru:
#            text = f'Мы получили с сайта:\n\n✅ Имя: {pending["name"]}{msg_preview}\n\nВсё верно?'
#            btn_label = "✅ Подтвердить и попасть на стену"
#        else:
#            text = f'We got this from the site:\n\n✅ Name: {pending["name"]}{msg_preview}\n\nLooks good?'
#            btn_label = "✅ Confirm & join the Wall"
#
#        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton(btn_label, callback_data=f"confirm_reg:{code}")]])
#        await update.message.reply_text(text, reply_markup=keyboard)
#        return
#
# ── 2. Новый обработчик подтверждения — добавить как отдельную функцию ──

async def handle_confirm_registration(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает нажатие '✅ Confirm & join the Wall' — регистрирует человека
    без повторного ввода имени/послания, используя черновик с сайта."""
    query = update.callback_query
    await query.answer()

    code = query.data.split(":", 1)[1]
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    lang = (update.effective_user.language_code or 'en').lower()
    is_ru = lang.startswith('ru')

    pending = await database.get_pending_registration(code)
    if not pending:
        text = "Эта регистрация уже обработана или устарела." if is_ru else "This registration was already processed or expired."
        await context.bot.send_message(chat_id=chat_id, text=text)
        return

    name = pending["name"]
    message = pending["message"] or ""
    invited_by = context.user_data.get("invited_by")  # на случай, если пришла и реферальная метка

    # Забираем черновик сразу, чтобы двойной тап не создал две записи
    await database.delete_pending_registration(code)

    total_count = await database.get_total_participants_count()

    if total_count < 1000:
        placement_id = await database.create_new_participant(
            telegram_user_id=user_id,
            name=name,
            message=message,
            avatar_url=None,
            invited_by=invited_by
        )

        if invited_by:
            referral_result = await database.register_referral(
                telegram_user_id=invited_by,
                referral_points=50,
                milestone_bonus=500,
                milestone_count=10
            )
            if referral_result["milestone_hit"]:
                try:
                    milestone_text = (
                        "🎉 Milestone достигнут!\n\nТы пригласил 10 друзей на Стену!\n🏆 Бонус: +500 очков!"
                        if is_ru else
                        "🎉 Milestone reached!\n\nYou've invited 10 friends to the Wall!\n🏆 Bonus: +500 points awarded!"
                    )
                    await context.bot.send_message(chat_id=invited_by, text=milestone_text)
                except Exception as notify_err:
                    logger.warning(f"Could not notify referrer {invited_by} about milestone: {notify_err}")

        ref_link = f"https://t.me/wall1mnames_bot?start={user_id}"
        if is_ru:
            caption_text = (
                f"🎉 Ты на Стене!\n\n"
                f"✅ Имя: {name}\n"
                f"🔢 Номер: #{placement_id:,}\n"
                f"🆓 Бесплатное место (первые 1000)\n\n"
                f"🏆 Поделись реферальной ссылкой и получи +50 очков:\n{ref_link}"
            )
        else:
            caption_text = (
                f"🎉 You are on the Wall!\n\n"
                f"✅ Name: {name}\n"
                f"🔢 Number: #{placement_id:,}\n"
                f"🆓 Free spot (first 1000)\n\n"
                f"🏆 Share your referral link to earn +50 points:\n{ref_link}"
            )

        try:
            card = create_card(name, placement_id, message)
            await context.bot.send_photo(chat_id=chat_id, photo=card, caption=caption_text, reply_markup=_main_actions_keyboard())
        except Exception as e:
            logger.error(f"Card generation failed: {e}", exc_info=True)
            await context.bot.send_message(chat_id=chat_id, text=caption_text, reply_markup=_main_actions_keyboard())

    else:
        # Бесплатные места закончились — обычный флоу оплаты через Stars
        payload = f"buy_slot:{user_id}:name:{name}:msg:{message}"
        if invited_by:
            payload += f":ref:{invited_by}"

        await context.bot.send_invoice(
            chat_id=chat_id,
            title="Wall of a Million Names",
            description=f"Добавить '{name}' на Стену навсегда" if is_ru else f"Add '{name}' to the Wall forever",
            payload=payload,
            currency="XTR",
            prices=[LabeledPrice("One spot on the Wall", 150)],
            provider_token="",
        )


# ── 3. В функции main() зарегистрировать новый обработчик ──
#
#    app.add_handler(CallbackQueryHandler(handle_confirm_registration, pattern=r"^confirm_reg:"))
#
#    (добавить ДО общего button_callback, если у него нет своего pattern —
#     чтобы confirm_reg: не попал по ошибке в общий обработчик)
