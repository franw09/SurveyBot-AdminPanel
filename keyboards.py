"""
Клавиатуры для Telegram бота (ТОЛЬКО INLINE)
"""

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def get_main_menu():
    """
    Главное меню (INLINE кнопки)
    """
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📝 Пройти опрос", callback_data="start_survey")],
            [InlineKeyboardButton(text="📊 Мои результаты", callback_data="my_results")],
            [InlineKeyboardButton(text="ℹ️ О боте", callback_data="about")]
        ]
    )
    return keyboard


def get_admin_menu():
    """
    Меню администратора (INLINE)
    """
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats"),
                InlineKeyboardButton(text="👥 Пользователи", callback_data="admin_users")
            ],
            [
                InlineKeyboardButton(text="📥 Экспорт данных", callback_data="admin_export"),
                InlineKeyboardButton(text="📢 Рассылка", callback_data="admin_broadcast")
            ],
            [InlineKeyboardButton(text="🔙 Выход", callback_data="admin_exit")]
        ]
    )
    return keyboard


def get_survey_keyboard(answers: list, question_num: int):
    """
    INLINE клавиатура для опроса
    """
    buttons = []
    for i, answer in enumerate(answers):
        buttons.append([InlineKeyboardButton(
            text=answer,
            callback_data=f"ans_{question_num}_{i}"
        )])

    buttons.append([InlineKeyboardButton(text="❌ Отменить", callback_data="cancel_survey")])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_back_button(callback_data="back_menu"):
    """
    Кнопка возврата (INLINE)
    """
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад", callback_data=callback_data)]
        ]
    )
    return keyboard
