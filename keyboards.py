from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def main_menu_keyboard():
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="💳 Добавить реквизиты карты", callback_data="add_card"
        )
    )
    builder.row(
        InlineKeyboardButton(text="📦 Создать сделку", callback_data="create_deal")
    )
    builder.row(InlineKeyboardButton(text="📋 Мои сделки", callback_data="my_deals"))
    builder.row(
        InlineKeyboardButton(
            text="🔗 Реферальная ссылка", callback_data="referral_link"
        )
    )
    builder.row(InlineKeyboardButton(text="📞 Поддержка", callback_data="support"))
    return builder.as_markup()


def deal_type_keyboard():
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="📱 Обычный товар", callback_data="deal_type_product"
        ),
        InlineKeyboardButton(text="🎁 Telegram Gift", callback_data="deal_type_gift"),
    )
    builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_menu"))
    return builder.as_markup()


def payment_method_keyboard():
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="⭐ Оплата звездами", callback_data="pay_stars"),
    )
    builder.row(
        InlineKeyboardButton(text="💵 Оплата валютой", callback_data="pay_currency"),
    )
    builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data="create_deal"))
    return builder.as_markup()


def currency_keyboard():
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="₽ RUB", callback_data="currency_rub"),
        InlineKeyboardButton(text="$ USD", callback_data="currency_usd"),
        InlineKeyboardButton(text="€ EUR", callback_data="currency_eur"),
    )
    builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data="pay_currency"))
    return builder.as_markup()


def join_deal_keyboard(deal_id: str):
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="✅ Присоединиться к сделке", callback_data=f"join_{deal_id}"
        )
    )
    return builder.as_markup()


def deal_actions_keyboard(deal_id: int, deal_type: str = "product"):
    builder = InlineKeyboardBuilder()

    if deal_type == "gift":
        builder.row(
            InlineKeyboardButton(
                text="🎁 Передать подарок боту",
                callback_data=f"transfer_gift_{deal_id}",
            )
        )

    builder.row(
        InlineKeyboardButton(
            text="✅ Подтвердить получение", callback_data=f"confirm_{deal_id}"
        ),
        InlineKeyboardButton(
            text="❌ Отменить сделку", callback_data=f"cancel_{deal_id}"
        ),
    )
    builder.row(
        InlineKeyboardButton(text="⚠️ Открыть спор", callback_data=f"dispute_{deal_id}")
    )
    return builder.as_markup()


def seller_delivery_keyboard(deal_id: int):
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="📦 Я передал товар", callback_data=f"seller_delivered_{deal_id}"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="❌ Отменить сделку", callback_data=f"cancel_{deal_id}"
        )
    )
    return builder.as_markup()


def buyer_confirm_keyboard(deal_id: int):
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="✅ Я получил товар", callback_data=f"confirm_{deal_id}"
        ),
    )
    builder.row(
        InlineKeyboardButton(
            text="⚠️ Товар не получен / спор", callback_data=f"dispute_{deal_id}"
        )
    )
    return builder.as_markup()


def gift_confirm_keyboard(deal_id: int):
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="✅ Это тот подарок", callback_data=f"confirm_gift_{deal_id}"
        ),
    )
    builder.row(
        InlineKeyboardButton(
            text="❌ Это не тот подарок", callback_data=f"reject_gift_{deal_id}"
        )
    )
    return builder.as_markup()


def buyer_payment_keyboard(deal_id: int):
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="💰 Я оплатил", callback_data=f"paid_{deal_id}")
    )
    builder.row(
        InlineKeyboardButton(
            text="❌ Отменить сделку", callback_data=f"cancel_{deal_id}"
        )
    )
    return builder.as_markup()


def admin_deals_keyboard(deal_id: int):
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="✅ Завершить (выплатить)", callback_data=f"admin_complete_{deal_id}"
        ),
        InlineKeyboardButton(
            text="❌ Отменить (вернуть)", callback_data=f"admin_cancel_{deal_id}"
        ),
    )
    builder.row(
        InlineKeyboardButton(
            text="📞 Связаться", callback_data=f"admin_contact_{deal_id}"
        )
    )
    return builder.as_markup()


def admin_user_keyboard(telegram_id: int):
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="🚫 Забанить", callback_data=f"admin_ban_{telegram_id}"
        ),
        InlineKeyboardButton(
            text="✅ Разбанить", callback_data=f"admin_unban_{telegram_id}"
        ),
    )
    return builder.as_markup()


def admin_menu_keyboard():
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📋 Все сделки", callback_data="admin_all_deals")
    )
    builder.row(
        InlineKeyboardButton(
            text="👤 Сделки пользователя", callback_data="admin_user_deals"
        )
    )
    builder.row(
        InlineKeyboardButton(text="🚫 Бан пользователя", callback_data="admin_ban_user")
    )
    builder.row(
        InlineKeyboardButton(text="🔙 В главное меню", callback_data="back_to_menu")
    )
    return builder.as_markup()


def cancel_keyboard():
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_action"))
    return builder.as_markup()


def referral_share_keyboard(referral_link: str):
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="📤 Поделиться ссылкой",
            url=f"https://t.me/share/url?url={referral_link}",
        )
    )
    builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_menu"))
    return builder.as_markup()


def back_to_menu_keyboard():
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🔙 В главное меню", callback_data="back_to_menu")
    )
    return builder.as_markup()
