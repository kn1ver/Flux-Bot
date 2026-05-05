import re
import aiosqlite
import asyncio
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from config import ADMIN_IDS, REFERRAL_PERCENT
from database import db
from keyboards import (
    main_menu_keyboard,
    deal_type_keyboard,
    payment_method_keyboard,
    currency_keyboard,
    join_deal_keyboard,
    deal_actions_keyboard,
    buyer_payment_keyboard,
    admin_menu_keyboard,
    admin_deals_keyboard,
    admin_user_keyboard,
    cancel_keyboard,
    referral_share_keyboard,
    back_to_menu_keyboard,
    seller_delivery_keyboard,
    buyer_confirm_keyboard,
    gift_confirm_keyboard,
)
from states import (
    MenuStates,
    DealCreationStates,
    CardStates,
    AdminStates,
    GiftDisputeStates,
    ProductDisputeStates,
)

router = Router()


def is_admin(telegram_id: int) -> bool:
    return telegram_id in ADMIN_IDS


def get_user_display(user) -> str:
    if user and user.get("username"):
        return f"@{user['username']}"
    elif user and user.get("full_name"):
        return f"{user['full_name']} (ID: {user['telegram_id']})"
    return f"ID: {user['telegram_id']}" if user else "Неизвестно"


async def ensure_user(message: Message):
    user = await db.get_user(message.from_user.id)
    if not user:
        await db.create_user(
            message.from_user.id,
            message.from_user.username,
            message.from_user.full_name,
        )
        return await db.get_user(message.from_user.id)
    return user


async def check_banned(message: Message) -> bool:
    user = await db.get_user(message.from_user.id)
    return user and user.get("is_banned", 0) == 1


async def cleanup_old_deals():
    while True:
        try:
            old_deals = await db.get_old_incomplete_deals(24)
            for deal in old_deals:
                await db.delete_deal(deal["id"])
                try:
                    if deal["seller_id"]:
                        await router.bot.send_message(
                            deal["seller_id"],
                            f"❌ Сделка #{deal['deal_id']} удалена из-за неактивности.",
                        )
                except:
                    pass
        except:
            pass
        await asyncio.sleep(3600)


@router.message(MenuStates.idle)
async def main_menu(message: Message, state: FSMContext):
    if await check_banned(message):
        await message.answer("⛔ Вы заблокированы в боте.")
        return

    user_id = message.from_user.id

    async with aiosqlite.connect(db.db_path) as db_conn:
        db_conn.row_factory = aiosqlite.Row
        async with db_conn.execute(
            """SELECT * FROM deals WHERE seller_id = ? AND status = 'disputed' 
            AND deal_type IN ('gift', 'product')
            ORDER BY updated_at DESC LIMIT 1""",
            (user_id,),
        ) as cursor:
            disputed_deal = await cursor.fetchone()

    if disputed_deal:
        deal = dict(disputed_deal)
        seller = await db.get_user(deal["seller_id"])
        buyer = await db.get_user(deal["buyer_id"]) if deal["buyer_id"] else None

        seller_display = get_user_display(seller)
        buyer_display = get_user_display(buyer) if buyer else "—"

        price_str = (
            f"{deal['price_stars']}⭐"
            if deal["payment_method"] == "stars"
            else f"{deal['price_currency']} {deal['currency_type']}"
        )

        deal_type_str = "подарком" if deal["deal_type"] == "gift" else "товаром"

        response_text = (
            message.text or message.caption or "Доказательства (фото/скриншот)"
        )
        has_media = False
        media_file = None

        if message.photo:
            has_media = True
            media_file = message.photo[-1]
        elif message.document:
            has_media = True
            media_file = message.document

        await message.answer(
            "✅ <b>Ваш ответ получен!</b>\n\n"
            "Администратор рассмотрит ваши доказательства вместе с претензией покупателя.",
            parse_mode="HTML",
            reply_markup=back_to_menu_keyboard(),
        )

        for admin_id in ADMIN_IDS:
            try:
                admin_caption = (
                    f"📝 <b>Ответ продавца по спору</b>\n\n"
                    f"Сделка: #{deal['deal_id']}\n"
                    f"Продавец: {seller_display}\n"
                    f"Покупатель: {buyer_display}\n"
                    f"Товар: {deal['product_name']}\n"
                    f"Сумма: {price_str}\n\n"
                    f"📝 <b>Ответ продавца:</b>\n{response_text}\n\n"
                    f"<b>Действия:</b>\n• Вернуть {price_str} покупателю\n• Выплатить {price_str} продавцу"
                )

                if has_media and media_file:
                    if message.photo:
                        await message.bot.send_photo(
                            admin_id,
                            photo=media_file.file_id,
                            caption=admin_caption,
                            parse_mode="HTML",
                            reply_markup=admin_deals_keyboard(deal["id"]),
                        )
                    elif message.document:
                        await message.bot.send_document(
                            admin_id,
                            document=media_file.file_id,
                            caption=admin_caption,
                            parse_mode="HTML",
                            reply_markup=admin_deals_keyboard(deal["id"]),
                        )
                else:
                    await message.bot.send_message(
                        admin_id,
                        admin_caption,
                        parse_mode="HTML",
                        reply_markup=admin_deals_keyboard(deal["id"]),
                    )
            except:
                pass
        return

    await ensure_user(message)
    await message.answer(
        "🏠 <b>Главное меню</b>\n\nВыберите действие:",
        reply_markup=main_menu_keyboard(),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "back_to_menu")
async def back_to_menu_callback(callback: CallbackQuery, state: FSMContext):
    await state.set_state(MenuStates.idle)
    await callback.message.edit_text(
        "🏠 <b>Добро пожаловать в Flux Bot!</b>\n\n"
        "Я помогу вам безопасно провести сделки.\n"
        "Выберите действие из меню:",
        reply_markup=main_menu_keyboard(),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data == "add_card")
async def add_card_start(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "💳 <b>Добавить реквизиты карты</b>\n\n"
        "Введите реквизиты в формате:\n"
        "<code>Название банка - номер счета/телефона</code>\n\n"
        "Например: <code>Сбербанк - 89001234567</code>",
        parse_mode="HTML",
        reply_markup=cancel_keyboard(),
    )
    await state.set_state(CardStates.waiting_card_details)
    await callback.answer()


@router.message(CardStates.waiting_card_details)
async def process_card(message: Message, state: FSMContext):
    card_text = message.text.strip()

    if " - " not in card_text:
        await message.answer(
            "❌ Неверный формат. Используйте:\n"
            "<code>Название банка - номер счета/телефона</code>",
            parse_mode="HTML",
            reply_markup=cancel_keyboard(),
        )
        return

    parts = card_text.split(" - ", 1)
    bank_name = parts[0].strip()
    account_number = parts[1].strip()

    account_number_clean = re.sub(r"\D", "", account_number)

    if len(account_number_clean) < 5:
        await message.answer(
            "❌ Номер слишком короткий. Укажите корректный номер телефона (от 5 цифр) или номер карты/счета.",
            parse_mode="HTML",
            reply_markup=cancel_keyboard(),
        )
        return

    if len(account_number_clean) > 25:
        await message.answer(
            "❌ Номер слишком длинный. Укажите корректный номер.",
            parse_mode="HTML",
            reply_markup=cancel_keyboard(),
        )
        return

    await db.update_user_card(message.from_user.id, card_text)
    await message.answer(
        "✅ Реквизиты сохранены!", reply_markup=back_to_menu_keyboard()
    )
    await state.set_state(MenuStates.idle)


@router.callback_query(F.data == "create_deal")
async def create_deal_start(callback: CallbackQuery, state: FSMContext):
    user = await db.get_user(callback.from_user.id)
    if not user or not user.get("card_details"):
        await callback.message.edit_text(
            "⚠️ <b>Сначала добавьте реквизиты карты!</b>\n\n"
            "Это нужно для получения оплаты от покупателей.",
            parse_mode="HTML",
            reply_markup=main_menu_keyboard(),
        )
        await callback.answer()
        return

    await callback.message.edit_text(
        "📦 <b>Создание сделки</b>\n\nВыберите тип сделки:",
        reply_markup=deal_type_keyboard(),
        parse_mode="HTML",
    )
    await state.set_state(DealCreationStates.waiting_type)
    await callback.answer()


@router.callback_query(F.data == "deal_type_product")
async def deal_type_product(callback: CallbackQuery, state: FSMContext):
    await state.update_data(deal_type="product")
    await callback.message.edit_text(
        "📱 <b>Обычный товар</b>\n\nВведите название товара:",
        parse_mode="HTML",
        reply_markup=cancel_keyboard(),
    )
    await state.set_state(DealCreationStates.waiting_product_name)
    await callback.answer()


@router.callback_query(F.data == "deal_type_gift")
async def deal_type_gift(callback: CallbackQuery, state: FSMContext):
    await state.update_data(deal_type="gift")
    await callback.message.edit_text(
        "🎁 <b>Telegram Gift</b>\n\nВведите название подарка (например, Premium на 1 месяц):",
        parse_mode="HTML",
        reply_markup=cancel_keyboard(),
    )
    await state.set_state(DealCreationStates.waiting_product_name)
    await callback.answer()


@router.message(DealCreationStates.waiting_product_name)
async def process_product_name(message: Message, state: FSMContext):
    await state.update_data(product_name=message.text.strip())
    await message.answer(
        "💳 <b>Выберите способ оплаты:</b>",
        reply_markup=payment_method_keyboard(),
    )
    await state.set_state(DealCreationStates.waiting_payment_method)


@router.callback_query(F.data == "pay_stars")
async def pay_stars_selected(callback: CallbackQuery, state: FSMContext):
    await state.update_data(payment_method="stars")
    await callback.message.edit_text(
        "⭐ <b>Оплата звездами</b>\n\nВведите цену в звездах:",
        parse_mode="HTML",
        reply_markup=cancel_keyboard(),
    )
    await state.set_state(DealCreationStates.waiting_price)
    await callback.answer()


@router.callback_query(F.data == "pay_currency")
async def pay_currency_selected(callback: CallbackQuery, state: FSMContext):
    await state.update_data(payment_method="currency")
    await callback.message.edit_text(
        "💵 <b>Оплата валютой</b>\n\nВыберите валюту:",
        parse_mode="HTML",
        reply_markup=currency_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("currency_"))
async def currency_selected(callback: CallbackQuery, state: FSMContext):
    currency_map = {
        "currency_rub": "RUB",
        "currency_usd": "USD",
        "currency_eur": "EUR",
    }
    currency = currency_map.get(callback.data, "RUB")
    await state.update_data(currency_type=currency)

    currency_symbol = {"RUB": "₽", "USD": "$", "EUR": "€"}[currency]
    await callback.message.edit_text(
        f"💵 <b>Оплата в {currency}</b>\n\nВведите цену в {currency_symbol}:",
        parse_mode="HTML",
        reply_markup=cancel_keyboard(),
    )
    await state.set_state(DealCreationStates.waiting_price)
    await callback.answer()


@router.message(DealCreationStates.waiting_price)
async def process_price(message: Message, state: FSMContext):
    try:
        price = float(message.text.strip().replace(",", "."))
        if price <= 0:
            raise ValueError()
    except ValueError:
        await message.answer("❌ Введите положительное число.")
        return

    await state.update_data(price=price)
    await finish_deal_creation(message, state)


async def finish_deal_creation(message: Message, state: FSMContext):
    data = await state.get_data()

    payment_display = (
        "⭐ Звезды" if data["payment_method"] == "stars" else f"{data['currency_type']}"
    )

    deal = await db.create_deal(
        seller_id=message.from_user.id,
        deal_type=data["deal_type"],
        product_name=data["product_name"],
        price_stars=int(data["price"]) if data["payment_method"] == "stars" else 0,
        payment_method=data["payment_method"],
        price_currency=data.get("price")
        if data["payment_method"] == "currency"
        else None,
        currency_type=data.get("currency_type")
        if data["payment_method"] == "currency"
        else None,
    )

    bot_username = (await message.bot.me()).username
    deal_link = f"t.me/{bot_username}?start=deal_{deal['deal_id']}"

    deal_type_emoji = "🎁" if deal["deal_type"] == "gift" else "📱"

    await message.answer(
        f"✅ <b>Сделка создана!</b>\n\n"
        f"{deal_type_emoji} Тип: {'Telegram Gift' if deal['deal_type'] == 'gift' else 'Товар'}\n"
        f"📦 Товар: {deal['product_name']}\n"
        f"💰 Цена: {int(data['price']) if data['payment_method'] == 'stars' else f'{data['price']} {data.get('currency_type', '')}'}\n"
        f"💳 Оплата: {payment_display}\n\n"
        f"🔗 <b>Ссылка для покупателя:</b>\n"
        f"<code>{deal_link}</code>\n\n"
        f"Отправьте эту ссылку покупателю.",
        parse_mode="HTML",
        reply_markup=back_to_menu_keyboard(),
    )
    await state.set_state(MenuStates.idle)


@router.callback_query(F.data == "my_deals")
async def my_deals(callback: CallbackQuery, state: FSMContext):
    deals = await db.get_user_deals(callback.from_user.id)

    if not deals:
        await callback.message.edit_text(
            "📋 <b>Мои сделки</b>\n\nУ вас пока нет сделок.",
            parse_mode="HTML",
            reply_markup=back_to_menu_keyboard(),
        )
        await callback.answer()
        return

    text = "📋 <b>Мои сделки</b>\n\n"
    for deal in deals[:10]:
        status_emoji = {
            "pending": "⏳",
            "joined": "👤",
            "paid": "💰",
            "completed": "✅",
            "cancelled": "❌",
            "disputed": "⚠️",
        }.get(deal["status"], "❓")

        deal_type_emoji = "🎁" if deal["deal_type"] == "gift" else "📱"
        role = (
            "Продавец" if deal["seller_id"] == callback.from_user.id else "Покупатель"
        )

        price_str = (
            f"{deal['price_stars']}⭐"
            if deal["payment_method"] == "stars"
            else f"{deal['price_currency']} {deal['currency_type']}"
        )

        text += f"{status_emoji} #{deal['deal_id']} {deal_type_emoji}\n"
        text += f"   {deal['product_name']} - {price_str}\n"
        text += f"   Роль: {role} | Статус: {deal['status']}\n\n"

    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=back_to_menu_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "referral_link")
async def referral_link(callback: CallbackQuery, state: FSMContext):
    user = await db.get_user(callback.from_user.id)

    bot_username = (await callback.bot.me()).username
    referral_link = f"t.me/{bot_username}?start={callback.from_user.id}"

    stats = await db.get_referral_stats(callback.from_user.id)

    await callback.message.edit_text(
        f"🔗 <b>Ваша реферальная ссылка</b>\n\n"
        f"Ссылка: <code>{referral_link}</code>\n\n"
        f"📊 Статистика:\n"
        f"   Приглашено: {stats['count']} чел.\n"
        f"   Заработано: {stats['total'] or 0} ⭐\n\n"
        f"Вы получите 1% от каждой успешной сделки вашего реферала.",
        parse_mode="HTML",
        reply_markup=referral_share_keyboard(referral_link),
    )
    await callback.answer()


@router.callback_query(F.data == "support")
async def support(callback: CallbackQuery, state: FSMContext):
    admin_mention = f"@{await callback.bot.me()}"
    await callback.message.edit_text(
        f"📞 <b>Поддержка</b>\n\n"
        f"По всем вопросам обращайтесь к администратору: {admin_mention}",
        parse_mode="HTML",
        reply_markup=back_to_menu_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "cancel_action")
async def cancel_action(callback: CallbackQuery, state: FSMContext):
    await state.set_state(MenuStates.idle)
    await callback.message.edit_text(
        "❌ Действие отменено.",
        reply_markup=back_to_menu_keyboard(),
    )
    await callback.answer()


async def process_join_deal(message: Message, deal_id: str):
    deal = await db.get_deal_by_deal_id(deal_id)

    if not deal:
        await message.answer("❌ Сделка не найдена.")
        return

    if deal["status"] != "pending":
        await message.answer("❌ К этой сделке уже присоединились или она завершена.")
        return

    if deal["seller_id"] == message.from_user.id:
        await message.answer("❌ Вы не можете присоединиться к своей сделке.")
        return

    await db.join_deal(deal["id"], message.from_user.id)

    deal_type_emoji = "🎁" if deal["deal_type"] == "gift" else "📱"
    seller = await db.get_user(deal["seller_id"])
    seller_display = get_user_display(seller)

    price_str = (
        f"{deal['price_stars']}⭐"
        if deal["payment_method"] == "stars"
        else f"{deal['price_currency']} {deal['currency_type']}"
    )
    payment_method_str = (
        "звезды" if deal["payment_method"] == "stars" else deal["currency_type"]
    )

    await message.answer(
        f"👤 <b>Вы присоединились к сделке!</b>\n\n"
        f"📦 <b>Продавец:</b> {seller_display}\n\n"
        f"{deal_type_emoji} Товар: {deal['product_name']}\n"
        f"💰 Цена: {price_str} ({payment_method_str})\n\n"
        f"<b>Оплатите {payment_method_str} боту и нажмите кнопку ниже.</b>",
        parse_mode="HTML",
        reply_markup=buyer_payment_keyboard(deal["id"]),
    )

    for admin_id in ADMIN_IDS:
        try:
            buyer = await db.get_user(message.from_user.id)
            buyer_display = get_user_display(buyer)
            await message.bot.send_message(
                admin_id,
                f"👤 <b>Новая сделка!</b>\n\n"
                f"Сделка: #{deal['deal_id']}\n"
                f"Продавец: {seller_display}\n"
                f"Покупатель: {buyer_display}\n"
                f"Товар: {deal['product_name']}\n"
                f"Сумма: {price_str}",
                parse_mode="HTML",
            )
        except:
            pass

    try:
        buyer = await db.get_user(message.from_user.id)
        buyer_display = get_user_display(buyer)
        await message.bot.send_message(
            deal["seller_id"],
            f"👤 <b>Покупатель присоединился к сделке!</b>\n\n"
            f"Сделка: #{deal['deal_id']}\n"
            f"Покупатель: {buyer_display}\n"
            f"Товар: {deal['product_name']}\n"
            f"Сумма: {price_str}\n\n"
            f"⏳ Ожидайте оплаты от покупателя.",
            parse_mode="HTML",
        )
    except:
        pass


async def process_deal_callback(callback: CallbackQuery, deal_id: int, action: str):
    deal = await db.get_deal_by_id(deal_id)

    if not deal:
        await callback.answer("❌ Сделка не найдена")
        return

    seller = await db.get_user(deal["seller_id"])
    buyer = await db.get_user(deal["buyer_id"]) if deal["buyer_id"] else None

    seller_display = get_user_display(seller)
    buyer_display = get_user_display(buyer) if buyer else "—"

    price_str = (
        f"{deal['price_stars']}⭐"
        if deal["payment_method"] == "stars"
        else f"{deal['price_currency']} {deal['currency_type']}"
    )

    if action == "paid":
        if deal["buyer_paid"]:
            await callback.answer("❌ Вы уже подтвердили оплату")
            return

        await db.mark_buyer_paid(deal_id)

        if deal["deal_type"] == "gift":
            await callback.message.edit_text(
                f"💰 <b>Оплата подтверждена!</b>\n\n"
                f"⏳ Ожидайте передачи подарка от продавца.\n\n"
                f"Продавец: {seller_display}\n"
                f"Товар: {deal['product_name']}",
                parse_mode="HTML",
            )

            try:
                await callback.bot.send_message(
                    deal["seller_id"],
                    f"🎁 <b>Покупатель оплатил!</b>\n\n"
                    f"Сделка: #{deal['deal_id']}\n"
                    f"Товар: {deal['product_name']}\n"
                    f"Сумма: {price_str}\n\n"
                    f"👤 <b>Покупатель:</b> {buyer_display}\n\n"
                    f"<b>Отправьте подарок покупателю напрямую в Telegram.</b>\n\n"
                    f"После этого нажмите кнопку ниже:",
                    parse_mode="HTML",
                    reply_markup=InlineKeyboardMarkup(
                        inline_keyboard=[
                            [
                                InlineKeyboardButton(
                                    text="✅ Я передал подарок",
                                    callback_data=f"transfer_gift_{deal_id}",
                                )
                            ]
                        ]
                    ),
                )
            except:
                pass
        else:
            await callback.message.edit_text(
                f"💰 <b>Оплата подтверждена!</b>\n\n"
                f"⏳ Ожидайте передачи товара от продавца.\n\n"
                f"Продавец: {seller_display}",
                parse_mode="HTML",
                reply_markup=buyer_confirm_keyboard(deal_id),
            )

            try:
                await callback.bot.send_message(
                    deal["seller_id"],
                    f"📦 <b>Покупатель оплатил!</b>\n\n"
                    f"Сделка: #{deal['deal_id']}\n"
                    f"Товар: {deal['product_name']}\n"
                    f"Сумма: {price_str}\n\n"
                    f"<b>Передайте товар покупателю и нажмите кнопку ниже:</b>",
                    parse_mode="HTML",
                    reply_markup=seller_delivery_keyboard(deal_id),
                )
            except:
                pass

        await callback.answer()

    elif action == "seller_delivered":
        if deal["deal_type"] == "gift":
            await callback.answer("Для подарков используйте кнопку передачи подарка")
            return

        await callback.message.edit_text(
            "✅ <b>Вы подтвердили передачу товара!</b>\n\n"
            f"⏳ Ожидайте подтверждения от покупателя.",
            parse_mode="HTML",
        )

        if deal["buyer_id"]:
            try:
                await callback.bot.send_message(
                    deal["buyer_id"],
                    f"📦 <b>Продавец передал товар!</b>\n\n"
                    f"Сделка: #{deal['deal_id']}\n"
                    f"Товар: {deal['product_name']}\n\n"
                    f"<b>Пожалуйста, подтвердите получение товара или откройте спор.</b>",
                    parse_mode="HTML",
                    reply_markup=buyer_confirm_keyboard(deal_id),
                )
            except:
                pass

        await callback.answer()

    elif action == "transfer_gift":
        await db.update_deal_status(deal_id, "gift_sent")

        await callback.message.edit_text(
            "✅ <b>Вы подтвердили передачу подарка!</b>\n\n"
            "⏳ Ожидайте подтверждения от покупателя.\n\n"
            "Покупатель проверит подарок и подтвердит получение.",
            parse_mode="HTML",
            reply_markup=back_to_menu_keyboard(),
        )

        if deal["buyer_id"]:
            try:
                await callback.bot.send_message(
                    deal["buyer_id"],
                    f"🎁 <b>Продавец передал подарок!</b>\n\n"
                    f"Сделка: #{deal['deal_id']}\n"
                    f"Товар: {deal['product_name']}\n\n"
                    f"<b>Пожалуйста, подтвердите - это тот подарок, который вы ожидали, или откройте спор.</b>",
                    parse_mode="HTML",
                    reply_markup=gift_confirm_keyboard(deal_id),
                )
            except:
                pass

        for admin_id in ADMIN_IDS:
            try:
                await callback.bot.send_message(
                    admin_id,
                    f"📤 <b>Продавец передал подарок</b>\n\n"
                    f"Сделка: #{deal['deal_id']}\n"
                    f"Продавец: {seller_display}\n"
                    f"Покупатель: {buyer_display}\n"
                    f"Товар: {deal['product_name']}\n"
                    f"Сумма: {price_str}\n\n"
                    f"⏳ Ожидает подтверждения от покупателя.",
                    parse_mode="HTML",
                )
            except:
                pass

        await callback.answer()
        return

    elif action == "transfer_gift_manual":
        pass

    elif action == "gift_sent":
        if deal["seller_paid_gift"]:
            await callback.answer("❌ Подарок уже передан")
            return

        await db.mark_seller_gift_paid(deal_id)
        await db.update_deal_status(deal_id, "completed")

        await callback.message.edit_text(
            "✅ <b>Сделка завершена!</b>\n\n"
            "🎁 Подарок передан покупателю.\n"
            "💰 Деньги будут переведены продавцу администратором.",
            parse_mode="HTML",
            reply_markup=back_to_menu_keyboard(),
        )

        if deal["buyer_id"]:
            try:
                await callback.bot.send_message(
                    deal["buyer_id"],
                    f"🎁 <b>Подарок получен!</b>\n\n"
                    f"Сделка: #{deal['deal_id']}\n"
                    f"Товар: {deal['product_name']}\n\n"
                    f"✅ Сделка завершена!",
                    parse_mode="HTML",
                    reply_markup=back_to_menu_keyboard(),
                )
            except:
                pass

        for admin_id in ADMIN_IDS:
            try:
                admin_text = (
                    f"✅ <b>Сделка завершена</b>\n\n"
                    f"Сделка: #{deal['deal_id']}\n"
                    f"Продавец: {seller_display}\n"
                    f"Покупатель: {buyer_display}\n"
                    f"Товар: {deal['product_name']}\n"
                    f"Сумма: {price_str}\n\n"
                )

                if (
                    deal["payment_method"] == "currency"
                    and seller
                    and seller.get("card_details")
                ):
                    admin_text += f"💳 <b>Реквизиты продавца:</b>\n<code>{seller['card_details']}</code>\n\n"

                admin_text += f"<b>Переведите {price_str} продавцу.</b>"

                await callback.bot.send_message(
                    admin_id,
                    admin_text,
                    parse_mode="HTML",
                    reply_markup=admin_deals_keyboard(deal_id),
                )
            except:
                pass

        await process_referral_commission(callback.bot, deal)
        await callback.answer()

    elif action == "confirm":
        if deal["deal_type"] == "gift":
            await callback.answer("Для подарков используйте кнопку 'Подарок передан'")
            return

        await db.update_deal_status(deal_id, "completed")

        await callback.message.edit_text(
            "✅ <b>Сделка завершена!</b>\n\n"
            "💰 Деньги будут переведены продавцу администратором.",
            parse_mode="HTML",
            reply_markup=back_to_menu_keyboard(),
        )

        try:
            await callback.bot.send_message(
                deal["seller_id"],
                f"✅ <b>Сделка завершена!</b>\n\n"
                f"Сделка: #{deal['deal_id']}\n"
                f"Товар: {deal['product_name']}\n"
                f"Сумма: {price_str}\n\n"
                f"💰 Деньги будут переведены вам администратором.",
                parse_mode="HTML",
            )
        except:
            pass

        for admin_id in ADMIN_IDS:
            try:
                admin_text = (
                    f"✅ <b>Сделка завершена</b>\n\n"
                    f"Сделка: #{deal['deal_id']}\n"
                    f"Продавец: {seller_display}\n"
                    f"Покупатель: {buyer_display}\n"
                    f"Товар: {deal['product_name']}\n"
                    f"Сумма: {price_str}\n\n"
                )

                if (
                    deal["payment_method"] == "currency"
                    and seller
                    and seller.get("card_details")
                ):
                    admin_text += f"💳 <b>Реквизиты продавца:</b>\n<code>{seller['card_details']}</code>\n\n"

                admin_text += f"<b>Переведите {price_str} продавцу.</b>"

                await callback.bot.send_message(
                    admin_id,
                    admin_text,
                    parse_mode="HTML",
                )
            except:
                pass

        await process_referral_commission(callback.bot, deal)
        await callback.answer()

    elif action == "cancel":
        if (
            deal["status"] in ["gift_received", "gift_sent"]
            and deal["deal_type"] == "gift"
            and deal["buyer_id"] == callback.from_user.id
        ):
            await db.update_deal_status(deal_id, "gift_sent")
            await callback.message.edit_text(
                "✅ <b>Отменено</b>\n\n"
                "Пожалуйста, подтвердите - это тот подарок, который вы ожидали.",
                parse_mode="HTML",
                reply_markup=gift_confirm_keyboard(deal_id),
            )

            try:
                await callback.bot.send_message(
                    deal["seller_id"],
                    f"ℹ️ <b>Покупатель отменил спор</b>\n\n"
                    f"Сделка: #{deal['deal_id']}\n"
                    f"Ожидается подтверждение от покупателя.",
                    parse_mode="HTML",
                )
            except:
                pass
        else:
            await db.update_deal_status(deal_id, "cancelled")
            await callback.message.edit_text(
                "❌ Сделка отменена.", reply_markup=back_to_menu_keyboard()
            )

            for user_id in [deal["seller_id"], deal["buyer_id"]]:
                if user_id:
                    try:
                        await callback.bot.send_message(
                            user_id,
                            f"❌ <b>Сделка отменена</b>\n\nСделка: #{deal['deal_id']}",
                            parse_mode="HTML",
                        )
                    except:
                        pass

        await callback.answer()

    elif action == "dispute":
        if (
            deal["deal_type"] == "product"
            and deal["status"] == "paid"
            and deal["buyer_id"] == callback.from_user.id
        ):
            await state.update_data(dispute_deal_id=deal_id)

            await callback.message.edit_text(
                "⚠️ <b>Открыт спор по товару</b>\n\n"
                "Пожалуйста, опишите проблему и приложите доказательства:\n"
                "- Скриншот/фото товара\n"
                "- Описание проблемы\n\n"
                "📝 <b>Отправьте текст и/или фото доказательств</b>",
                parse_mode="HTML",
                reply_markup=cancel_keyboard(),
            )
            await state.set_state(ProductDisputeStates.waiting_dispute_proof)
            await callback.answer()
            return

        await db.update_deal_status(deal_id, "disputed")
        await callback.message.edit_text(
            "⚠️ <b>Спор открыт</b>\n\nАдминистратор свяжется с вами.",
            parse_mode="HTML",
            reply_markup=back_to_menu_keyboard(),
        )

        for admin_id in ADMIN_IDS:
            try:
                await callback.bot.send_message(
                    admin_id,
                    f"⚠️ <b>Открыт спор по сделке</b>\n\n"
                    f"Сделка: #{deal['deal_id']}\n"
                    f"Продавец: {seller_display}\n"
                    f"Покупатель: {buyer_display}\n"
                    f"Товар: {deal['product_name']}\n"
                    f"Сумма: {price_str}",
                    parse_mode="HTML",
                    reply_markup=admin_deals_keyboard(deal_id),
                )
            except:
                pass

        await callback.answer()


async def process_referral_commission(bot, deal):
    referred_by = await db.is_user_referred(deal["buyer_id"])

    if referred_by:
        commission = int(deal["price_stars"] * REFERRAL_PERCENT / 100)
        if commission > 0:
            await db.add_referral(referred_by, deal["buyer_id"], deal["id"], commission)

            try:
                await bot.send_message(
                    referred_by,
                    f"💰 <b>Вы получили реферальную комиссию!</b>\n\n"
                    f"Сделка: #{deal['deal_id']}\n"
                    f"Комиссия: {commission} ⭐",
                    parse_mode="HTML",
                )
            except:
                pass


@router.callback_query(F.data.startswith("join_"))
async def join_deal_callback(callback: CallbackQuery, state: FSMContext):
    deal_id = callback.data.replace("join_", "")
    await process_join_deal(callback.message, deal_id)
    await callback.answer()


@router.callback_query(F.data.startswith("paid_"))
async def paid_callback(callback: CallbackQuery):
    deal_id = int(callback.data.replace("paid_", ""))
    await process_deal_callback(callback, deal_id, "paid")


@router.callback_query(F.data.startswith("transfer_gift_"))
async def transfer_gift_callback(callback: CallbackQuery):
    deal_id = int(callback.data.replace("transfer_gift_", ""))
    await process_deal_callback(callback, deal_id, "transfer_gift")


@router.callback_query(F.data.startswith("gift_sent_"))
async def gift_sent_callback(callback: CallbackQuery):
    deal_id = int(callback.data.replace("gift_sent_", ""))
    await process_deal_callback(callback, deal_id, "gift_sent")


@router.callback_query(F.data.startswith("seller_delivered_"))
async def seller_delivered_callback(callback: CallbackQuery):
    deal_id = int(callback.data.replace("seller_delivered_", ""))
    await process_deal_callback(callback, deal_id, "seller_delivered")


@router.callback_query(F.data.startswith("confirm_gift_"))
async def confirm_gift_callback(callback: CallbackQuery):
    deal_id = int(callback.data.replace("confirm_gift_", ""))
    deal = await db.get_deal_by_id(deal_id)

    if not deal or deal["status"] not in ["gift_received", "gift_sent"]:
        await callback.answer("Сделка не найдена или уже завершена")
        return

    await db.update_deal_status(deal_id, "completed")

    seller = await db.get_user(deal["seller_id"])
    buyer = await db.get_user(deal["buyer_id"]) if deal["buyer_id"] else None

    price_str = f"{deal['price_stars']}⭐"
    seller_display = get_user_display(seller)
    buyer_display = get_user_display(buyer) if buyer else "—"

    await callback.message.edit_text(
        "✅ <b>Вы подтвердили подарок!</b>\n\n"
        "Сделка завершена. Деньги будут переведены продавцу администратором.",
        parse_mode="HTML",
        reply_markup=back_to_menu_keyboard(),
    )

    if deal["seller_id"]:
        try:
            await callback.bot.send_message(
                deal["seller_id"],
                f"✅ <b>Покупатель подтвердил получение подарка!</b>\n\n"
                f"Сделка: #{deal['deal_id']}\n"
                f"Товар: {deal['product_name']}\n"
                f"Сумма: {price_str}\n\n"
                f"💰 Деньги будут переведены вам администратором.",
                parse_mode="HTML",
            )
        except:
            pass

    for admin_id in ADMIN_IDS:
        try:
            admin_text = (
                f"✅ <b>Сделка завершена (подарок подтвержден)</b>\n\n"
                f"Сделка: #{deal['deal_id']}\n"
                f"Продавец: {seller_display}\n"
                f"Покупатель: {buyer_display}\n"
                f"Товар: {deal['product_name']}\n"
                f"Сумма: {price_str}\n\n"
            )

            if (
                deal["payment_method"] == "currency"
                and seller
                and seller.get("card_details")
            ):
                admin_text += f"💳 <b>Реквизиты продавца:</b>\n<code>{seller['card_details']}</code>\n\n"

            admin_text += f"<b>Переведите {price_str} продавцу.</b>"

            await callback.bot.send_message(
                admin_id,
                admin_text,
                parse_mode="HTML",
                reply_markup=admin_deals_keyboard(deal_id),
            )
        except:
            pass

    await process_referral_commission(callback.bot, deal)
    await callback.answer()


@router.callback_query(F.data.startswith("confirm_"))
async def confirm_callback(callback: CallbackQuery):
    deal_id = int(callback.data.replace("confirm_", ""))
    await process_deal_callback(callback, deal_id, "confirm")


@router.callback_query(F.data.startswith("cancel_"))
async def cancel_deal_callback(callback: CallbackQuery):
    deal_id = int(callback.data.replace("cancel_", ""))
    await process_deal_callback(callback, deal_id, "cancel")


@router.callback_query(F.data.startswith("reject_gift_"))
async def reject_gift_callback(callback: CallbackQuery, state: FSMContext):
    deal_id = int(callback.data.replace("reject_gift_", ""))
    deal = await db.get_deal_by_id(deal_id)

    if not deal or deal["status"] not in ["gift_received", "gift_sent"]:
        await callback.answer("Сделка не найдена или уже завершена")
        return

    await state.update_data(dispute_deal_id=deal_id)

    await callback.message.edit_text(
        "⚠️ <b>Открыт спор по подарку</b>\n\n"
        "Пожалуйста, опишите проблему и приложите доказательства:\n"
        "- Скриншот полученного подарка\n"
        "- Ссылку на подарок\n"
        "- Описание того, что не так с подарком\n\n"
        "📝 <b>Отправьте текст и/или фото доказательств</b>",
        parse_mode="HTML",
        reply_markup=cancel_keyboard(),
    )
    await state.set_state(GiftDisputeStates.waiting_dispute_proof)
    await callback.answer()


@router.message(GiftDisputeStates.waiting_dispute_proof)
async def process_dispute_proof(message: Message, state: FSMContext):
    data = await state.get_data()
    deal_id = data.get("dispute_deal_id")

    if not deal_id:
        await message.answer("❌ Что-то пошло не так. Начните заново.")
        await state.set_state(MenuStates.idle)
        return

    deal = await db.get_deal_by_id(deal_id)

    if not deal or deal["status"] not in ["gift_received", "gift_sent"]:
        await message.answer("❌ Сделка не найдена или уже завершена.")
        await state.set_state(MenuStates.idle)
        return

    await db.update_deal_status(deal_id, "disputed")

    dispute_proof = (
        message.text or message.caption or "Доказательства приложены (фото/скриншот)"
    )
    has_media = False
    media_file = None

    if message.photo:
        has_media = True
        media_file = message.photo[-1]
    elif message.document:
        has_media = True
        media_file = message.document

    seller = await db.get_user(deal["seller_id"])
    buyer = await db.get_user(deal["buyer_id"]) if deal["buyer_id"] else None

    price_str = f"{deal['price_stars']}⭐"
    seller_display = get_user_display(seller)
    buyer_display = get_user_display(buyer) if buyer else "—"

    await message.answer(
        "⚠️ <b>Спор открыт</b>\n\n"
        "Администратор рассмотрит вашу претензию и свяжется с обеими сторонами.",
        parse_mode="HTML",
        reply_markup=back_to_menu_keyboard(),
    )
    await state.set_state(MenuStates.idle)

    if deal["seller_id"]:
        try:
            await message.bot.send_message(
                deal["seller_id"],
                f"⚠️ <b>Покупатель открыл спор по подарку</b>\n\n"
                f"Сделка: #{deal['deal_id']}\n"
                f"Товар: {deal['product_name']}\n\n"
                f"📝 <b>Претензия покупателя:</b>\n{dispute_proof}\n\n"
                f"Пожалуйста, предоставьте доказательства того, что подарок соответствует заказу.",
                parse_mode="HTML",
            )
        except:
            pass

    for admin_id in ADMIN_IDS:
        try:
            admin_caption = (
                f"⚠️ <b>Открыт спор по сделке с подарком</b>\n\n"
                f"Сделка: #{deal['deal_id']}\n"
                f"Продавец: {seller_display}\n"
                f"Покупатель: {buyer_display}\n"
                f"Товар: {deal['product_name']}\n"
                f"Сумма: {price_str}\n\n"
                f"📝 <b>Претензия покупателя:</b>\n{dispute_proof}\n\n"
            )

            if deal.get("gift_message"):
                admin_caption += (
                    f"💬 <b>Сообщение подарка:</b>\n{deal['gift_message']}\n\n"
                )

            admin_caption += f"<b>Действия:</b>\n• Вернуть {price_str} покупателю\n• Выплатить {price_str} продавцу"

            if has_media and media_file:
                if message.photo:
                    await message.bot.send_photo(
                        admin_id,
                        photo=media_file.file_id,
                        caption=admin_caption,
                        parse_mode="HTML",
                        reply_markup=admin_deals_keyboard(deal_id),
                    )
                elif message.document:
                    await message.bot.send_document(
                        admin_id,
                        document=media_file.file_id,
                        caption=admin_caption,
                        parse_mode="HTML",
                        reply_markup=admin_deals_keyboard(deal_id),
                    )
            else:
                await message.bot.send_message(
                    admin_id,
                    admin_caption,
                    parse_mode="HTML",
                    reply_markup=admin_deals_keyboard(deal_id),
                )
        except:
            pass


@router.message(ProductDisputeStates.waiting_dispute_proof)
async def process_product_dispute_proof(message: Message, state: FSMContext):
    data = await state.get_data()
    deal_id = data.get("dispute_deal_id")

    if not deal_id:
        await message.answer("❌ Что-то пошло не так. Начните заново.")
        await state.set_state(MenuStates.idle)
        return

    deal = await db.get_deal_by_id(deal_id)

    if not deal or deal["status"] != "paid" or deal["deal_type"] != "product":
        await message.answer("❌ Сделка не найдена или уже завершена.")
        await state.set_state(MenuStates.idle)
        return

    await db.update_deal_status(deal_id, "disputed")

    dispute_proof = (
        message.text or message.caption or "Доказательства приложены (фото/скриншот)"
    )
    has_media = False
    media_file = None

    if message.photo:
        has_media = True
        media_file = message.photo[-1]
    elif message.document:
        has_media = True
        media_file = message.document

    seller = await db.get_user(deal["seller_id"])
    buyer = await db.get_user(deal["buyer_id"]) if deal["buyer_id"] else None

    price_str = f"{deal['price_stars']}⭐"
    seller_display = get_user_display(seller)
    buyer_display = get_user_display(buyer) if buyer else "—"

    await message.answer(
        "⚠️ <b>Спор открыт</b>\n\n"
        "Администратор рассмотрит вашу претензию и свяжется с обеими сторонами.",
        parse_mode="HTML",
        reply_markup=back_to_menu_keyboard(),
    )
    await state.set_state(MenuStates.idle)

    if deal["seller_id"]:
        try:
            await message.bot.send_message(
                deal["seller_id"],
                f"⚠️ <b>Покупатель открыл спор по товару</b>\n\n"
                f"Сделка: #{deal['deal_id']}\n"
                f"Товар: {deal['product_name']}\n\n"
                f"📝 <b>Претензия покупателя:</b>\n{dispute_proof}\n\n"
                f"Пожалуйста, предоставьте доказательства того, что товар соответствует заказу.",
                parse_mode="HTML",
            )
        except:
            pass

    for admin_id in ADMIN_IDS:
        try:
            admin_caption = (
                f"⚠️ <b>Открыт спор по сделке с товаром</b>\n\n"
                f"Сделка: #{deal['deal_id']}\n"
                f"Продавец: {seller_display}\n"
                f"Покупатель: {buyer_display}\n"
                f"Товар: {deal['product_name']}\n"
                f"Сумма: {price_str}\n\n"
                f"📝 <b>Претензия покупателя:</b>\n{dispute_proof}\n\n"
                f"<b>Действия:</b>\n• Вернуть {price_str} покупателю\n• Выплатить {price_str} продавцу"
            )

            if has_media and media_file:
                if message.photo:
                    await message.bot.send_photo(
                        admin_id,
                        photo=media_file.file_id,
                        caption=admin_caption,
                        parse_mode="HTML",
                        reply_markup=admin_deals_keyboard(deal_id),
                    )
                elif message.document:
                    await message.bot.send_document(
                        admin_id,
                        document=media_file.file_id,
                        caption=admin_caption,
                        parse_mode="HTML",
                        reply_markup=admin_deals_keyboard(deal_id),
                    )
            else:
                await message.bot.send_message(
                    admin_id,
                    admin_caption,
                    parse_mode="HTML",
                    reply_markup=admin_deals_keyboard(deal_id),
                )
        except:
            pass


@router.callback_query(F.data.startswith("dispute_"))
async def dispute_callback(callback: CallbackQuery):
    deal_id = int(callback.data.replace("dispute_", ""))
    await process_deal_callback(callback, deal_id, "dispute")


from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


@router.message(lambda m: m.text and m.text.startswith("/admin"))
async def admin_menu(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ У вас нет доступа к админ-панели.")
        return

    await message.answer(
        "⚙️ <b>Админ-панель</b>\n\nВыберите действие:",
        reply_markup=admin_menu_keyboard(),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "admin_all_deals")
async def admin_all_deals(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа")
        return

    deals = await db.get_all_deals(20)

    if not deals:
        await callback.message.edit_text(
            "📋 <b>Все сделки</b>\n\nСделок пока нет.",
            parse_mode="HTML",
            reply_markup=admin_menu_keyboard(),
        )
        await callback.answer()
        return

    text = "📋 <b>Все сделки (последние 20)</b>\n\n"
    for deal in deals:
        status_emoji = {
            "pending": "⏳",
            "joined": "👤",
            "paid": "💰",
            "completed": "✅",
            "cancelled": "❌",
            "disputed": "⚠️",
        }.get(deal["status"], "❓")

        seller = await db.get_user(deal["seller_id"])
        buyer = await db.get_user(deal["buyer_id"]) if deal["buyer_id"] else None

        price_str = (
            f"{deal['price_stars']}⭐"
            if deal["payment_method"] == "stars"
            else f"{deal['price_currency']} {deal['currency_type']}"
        )

        text += f"{status_emoji} #{deal['deal_id']}\n"
        text += f"   Продавец: {get_user_display(seller)}\n"
        text += f"   Покупатель: {get_user_display(buyer) if buyer else '—'}\n"
        text += f"   Товар: {deal['product_name']} | {price_str}\n"
        text += f"   Статус: {deal['status']}\n\n"

    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=admin_menu_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "admin_user_deals")
async def admin_user_deals(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа")
        return

    await callback.message.edit_text(
        "👤 <b>Сделки пользователя</b>\n\nВведите Telegram ID пользователя:",
        parse_mode="HTML",
        reply_markup=cancel_keyboard(),
    )
    await state.set_state(AdminStates.waiting_user_id)
    await callback.answer()


@router.message(AdminStates.waiting_user_id)
async def process_admin_user_deals(message: Message, state: FSMContext):
    try:
        telegram_id = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Введите корректный Telegram ID")
        return

    deals = await db.get_user_deals_by_telegram_id(telegram_id, 20)

    if not deals:
        await message.answer(
            f"📋 <b>Сделки пользователя {telegram_id}</b>\n\nСделок не найдено.",
            parse_mode="HTML",
            reply_markup=admin_menu_keyboard(),
        )
    else:
        text = f"📋 <b>Сделки пользователя {telegram_id}</b>\n\n"
        for deal in deals:
            status_emoji = {
                "pending": "⏳",
                "joined": "👤",
                "paid": "💰",
                "completed": "✅",
                "cancelled": "❌",
                "disputed": "⚠️",
            }.get(deal["status"], "❓")

            role = "Продавец" if deal["seller_id"] == telegram_id else "Покупатель"

            price_str = (
                f"{deal['price_stars']}⭐"
                if deal["payment_method"] == "stars"
                else f"{deal['price_currency']} {deal['currency_type']}"
            )

            text += f"{status_emoji} #{deal['deal_id']} ({role})\n"
            text += f"   Товар: {deal['product_name']} | {price_str}\n"
            text += f"   Статус: {deal['status']}\n\n"

        await message.answer(
            text,
            parse_mode="HTML",
            reply_markup=admin_user_keyboard(telegram_id),
        )

    await state.set_state(MenuStates.idle)


@router.callback_query(F.data == "admin_ban_user")
async def admin_ban_user_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа")
        return

    await callback.message.edit_text(
        "🚫 <b>Бан пользователя</b>\n\nВведите Telegram ID пользователя:",
        parse_mode="HTML",
        reply_markup=cancel_keyboard(),
    )
    await state.set_state(AdminStates.waiting_user_id)
    await callback.answer()


@router.callback_query(F.data.startswith("admin_ban_"))
async def admin_ban_callback(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа")
        return

    telegram_id = int(callback.data.replace("admin_ban_", ""))
    await db.ban_user(telegram_id, True)

    await callback.message.edit_text(
        f"✅ Пользователь {telegram_id} заблокирован.",
        reply_markup=admin_menu_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin_unban_"))
async def admin_unban_callback(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа")
        return

    telegram_id = int(callback.data.replace("admin_unban_", ""))
    await db.ban_user(telegram_id, False)

    await callback.message.edit_text(
        f"✅ Пользователь {telegram_id} разблокирован.",
        reply_markup=admin_menu_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin_complete_"))
async def admin_complete_deal(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа")
        return

    deal_id = int(callback.data.replace("admin_complete_", ""))
    deal = await db.get_deal_by_id(deal_id)

    if deal:
        await db.update_deal_status(deal_id, "completed")

        seller = await db.get_user(deal["seller_id"])
        buyer = await db.get_user(deal["buyer_id"]) if deal["buyer_id"] else None

        price_str = (
            f"{deal['price_stars']}⭐"
            if deal["payment_method"] == "stars"
            else f"{deal['price_currency']} {deal['currency_type']}"
        )

        seller_display = get_user_display(seller)
        seller_card = seller.get("card_details") if seller else None

        admin_msg = f"✅ <b>Сделка #{deal['deal_id']} завершена вручную.</b>\n\n"

        if deal["payment_method"] == "currency" and seller_card:
            admin_msg += f"💳 <b>Реквизиты продавца для перевода:</b>\n<code>{seller_card}</code>\n\n"

        admin_msg += f"💰 <b>Сумма к переводу:</b> {price_str}\n👤 <b>Получатель:</b> {seller_display}"

        await callback.answer("✅ Сделка завершена", show_alert=True)

        try:
            await callback.bot.edit_message_caption(
                chat_id=callback.message.chat.id,
                message_id=callback.message.message_id,
                caption=admin_msg,
                parse_mode="HTML",
                reply_markup=admin_menu_keyboard(),
            )
        except:
            try:
                await callback.bot.edit_message_text(
                    chat_id=callback.message.chat.id,
                    message_id=callback.message.message_id,
                    text=admin_msg,
                    parse_mode="HTML",
                    reply_markup=admin_menu_keyboard(),
                )
            except:
                pass

        try:
            await callback.bot.send_message(
                deal["seller_id"],
                f"✅ <b>Сделка завершена администратором</b>\n\n"
                f"Сделка: #{deal['deal_id']}\n"
                f"Товар: {deal['product_name']}\n"
                f"Сумма: {price_str}\n\n"
                f"💰 Деньги переведены вам.",
                parse_mode="HTML",
            )
        except:
            pass

    await callback.answer()


@router.callback_query(F.data.startswith("admin_cancel_"))
async def admin_cancel_deal(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа")
        return

    deal_id = int(callback.data.replace("admin_cancel_", ""))
    deal = await db.get_deal_by_id(deal_id)

    if deal:
        await db.update_deal_status(deal_id, "cancelled")

        buyer = await db.get_user(deal["buyer_id"]) if deal["buyer_id"] else None

        price_str = (
            f"{deal['price_stars']}⭐"
            if deal["payment_method"] == "stars"
            else f"{deal['price_currency']} {deal['currency_type']}"
        )

        buyer_display = get_user_display(buyer) if buyer else "—"
        buyer_card = buyer.get("card_details") if buyer else None

        admin_msg = f"❌ <b>Сделка #{deal['deal_id']} отменена.</b>\n\n"

        if deal["payment_method"] == "currency" and buyer_card:
            admin_msg += f"💳 <b>Реквизиты покупателя для возврата:</b>\n<code>{buyer_card}</code>\n\n"

        admin_msg += f"💰 <b>Сумма к возврату:</b> {price_str}\n👤 <b>Получатель:</b> {buyer_display}"

        await callback.answer("❌ Сделка отменена", show_alert=True)

        try:
            await callback.bot.edit_message_caption(
                chat_id=callback.message.chat.id,
                message_id=callback.message.message_id,
                caption=admin_msg,
                parse_mode="HTML",
                reply_markup=admin_menu_keyboard(),
            )
        except:
            try:
                await callback.bot.edit_message_text(
                    chat_id=callback.message.chat.id,
                    message_id=callback.message.message_id,
                    text=admin_msg,
                    parse_mode="HTML",
                    reply_markup=admin_menu_keyboard(),
                )
            except:
                pass

        for user_id in [deal["seller_id"], deal["buyer_id"]]:
            if user_id:
                try:
                    await callback.bot.send_message(
                        user_id,
                        f"❌ <b>Сделка отменена администратором</b>\n\n"
                        f"Сделка: #{deal['deal_id']}\n"
                        f"Товар: {deal['product_name']}",
                        parse_mode="HTML",
                    )
                except:
                    pass

    await callback.answer()


async def handle_start_command(message: Message, state: FSMContext):
    await ensure_user(message)

    if await check_banned(message):
        await message.answer("⛔ Вы заблокированы в боте.")
        return

    args = message.text.split()
    if len(args) > 1:
        param = args[1]

        if param.startswith("deal_"):
            deal_id = param.replace("deal_", "")
            await process_join_deal(message, deal_id)
            return

        if param.isdigit():
            referrer_id = int(param)
            if referrer_id != message.from_user.id:
                user = await db.get_user(message.from_user.id)
                if user and not user.get("referred_by"):
                    async with aiosqlite.connect(db.db_path) as db_conn:
                        await db_conn.execute(
                            "UPDATE users SET referred_by = ? WHERE telegram_id = ?",
                            (referrer_id, message.from_user.id),
                        )
                        await db_conn.commit()

    await message.answer(
        "🏠 <b>Добро пожаловать в Flux Bot!</b>\n\n"
        "Я помогу вам безопасно провести сделки.\n"
        "Выберите действие из меню:",
        reply_markup=main_menu_keyboard(),
        parse_mode="HTML",
    )
    await state.set_state(MenuStates.idle)
