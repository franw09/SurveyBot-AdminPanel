"""
Обработчики команд (УЛУЧШЕННАЯ ВЕРСИЯ)
- Inline-кнопки (всё в одном сообщении)
- Зашифрованный пароль админа
- Опрос не захламляет чат
"""

import logging
import csv
import io
import hashlib
from os import getenv
from datetime import datetime

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, BufferedInputFile
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from keyboards import get_main_menu, get_admin_menu, get_survey_keyboard, get_back_button
from database import (
    add_user, update_user_activity, check_admin, set_admin,
    get_survey_state, set_survey_state, save_answer, get_user_responses,
    get_all_users, get_total_users, get_total_responses, get_completed_surveys,
    reset_user_survey, export_all_responses
)
from security import security

logger = logging.getLogger(__name__)
router = Router()

# ==================== ОПРОС ====================

SURVEY_QUESTIONS = [
    {
        'question': '1️⃣ Как вы узнали о нашем продукте?',
        'answers': ['Интернет', 'Реклама', 'От друзей', 'Другое']
    },
    {
        'question': '2️⃣ Как часто вы используете наш продукт?',
        'answers': ['Каждый день', 'Несколько раз в неделю', 'Раз в месяц', 'Редко']
    },
    {
        'question': '3️⃣ Оцените качество продукта от 1 до 5',
        'answers': ['⭐ 1', '⭐⭐ 2', '⭐⭐⭐ 3', '⭐⭐⭐⭐ 4', '⭐⭐⭐⭐⭐ 5']
    },
    {
        'question': '4️⃣ Порекомендуете ли вы нас друзьям?',
        'answers': ['Да, обязательно', 'Скорее да', 'Не уверен', 'Скорее нет', 'Нет']
    },
    {
        'question': '5️⃣ Что бы вы хотели улучшить?',
        'answers': ['Скорость работы', 'Интерфейс', 'Функционал', 'Поддержка', 'Всё устраивает']
    }
]

# ==================== СОСТОЯНИЯ ====================

class AdminStates(StatesGroup):
    waiting_password = State()
    waiting_broadcast = State()

class SurveyStates(StatesGroup):
    in_progress = State()


# ==================== ФУНКЦИИ ====================

def hash_password(password: str) -> str:
    """Хеширование пароля SHA256"""
    return hashlib.sha256(password.encode()).hexdigest()


def check_password(input_password: str, correct_password_hash: str) -> bool:
    """Проверка пароля"""
    return hash_password(input_password) == correct_password_hash


# Хешируем пароль из .env один раз при запуске
ADMIN_PASSWORD_HASH = hash_password(getenv("ADMIN_PASSWORD", "admin123"))


# ==================== КОМАНДЫ ====================

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    """Команда /start"""
    user = message.from_user

    # 🔒 ЗАЩИТА ОТ ФЛУДА
    if not security.check_flood(user.id):
        await message.answer("⚠️ Слишком много запросов! Подождите 10 секунд.")
        return

    await add_user(user.id, user.username, user.first_name, user.last_name)
    await update_user_activity(user.id)

    is_admin = await check_admin(user.id)

    if is_admin:
        await message.answer(
            f"👋 Привет, <b>{user.first_name}</b>!\n\n🔐 Вы администратор.",
            reply_markup=get_admin_menu()
        )
    else:
        await message.answer(
            f"👋 Привет, <b>{user.first_name}</b>!\n\nВыберите действие:",
            reply_markup=get_main_menu()
        )


# ==================== ОПРОС (INLINE) ====================

@router.callback_query(F.data == "start_survey")
async def callback_start_survey(callback: CallbackQuery, state: FSMContext):
    """Начало опроса"""
    user_id = callback.from_user.id

    # 🔒 ЗАЩИТА ОТ ФЛУДА
    if not security.check_flood(user_id):
        await callback.answer("⚠️ Слишком много запросов! Подождите.", show_alert=True)
        return

    await update_user_activity(user_id)

    current_question = await get_survey_state(user_id)

    if current_question == -1:
        await callback.message.edit_text(
            "✅ Вы уже прошли опрос!\n\nЧтобы пройти заново, обратитесь к администратору.",
            reply_markup=get_back_button()
        )
        await callback.answer()
        return

    if current_question > 0:
        await reset_user_survey(user_id)

    await set_survey_state(user_id, 0)
    await state.set_state(SurveyStates.in_progress)

    question = SURVEY_QUESTIONS[0]
    await callback.message.edit_text(
        f"📋 <b>Опрос</b>\n\n{question['question']}",
        reply_markup=get_survey_keyboard(question['answers'], 0)
    )
    await callback.answer()


@router.callback_query(F.data == "cancel_survey")
async def callback_cancel_survey(callback: CallbackQuery, state: FSMContext):
    """Отмена опроса"""
    await reset_user_survey(callback.from_user.id)
    await state.clear()

    await callback.message.edit_text(
        "❌ Опрос отменён.",
        reply_markup=get_main_menu()
    )
    await callback.answer()


@router.callback_query(F.data.startswith("ans_"))
async def callback_survey_answer(callback: CallbackQuery, state: FSMContext):
    """Обработка ответа на вопрос"""
    user_id = callback.from_user.id

    # 🔒 ЗАЩИТА ОТ ФЛУДА
    if not security.check_flood(user_id):
        await callback.answer("⚠️ Слишком быстро! Подождите.", show_alert=True)
        return

    await update_user_activity(user_id)

    # Парсим: ans_0_2 → вопрос 0, ответ 2
    parts = callback.data.split("_")
    question_num = int(parts[1])
    answer_index = int(parts[2])

    current_question = await get_survey_state(user_id)

    if current_question != question_num:
        await callback.answer("⚠️ Ошибка синхронизации", show_alert=True)
        return

    question = SURVEY_QUESTIONS[current_question]
    answer = question['answers'][answer_index]

    # Сохраняем ответ
    await save_answer(user_id, current_question, question['question'], answer)

    # Следующий вопрос
    next_question_num = current_question + 1

    if next_question_num >= len(SURVEY_QUESTIONS):
        # Опрос завершён
        await set_survey_state(user_id, -1)
        await state.clear()

        await callback.message.edit_text(
            "🎉 <b>Спасибо за участие!</b>\n\n✅ Ваши ответы сохранены.",
            reply_markup=get_main_menu()
        )
    else:
        # Следующий вопрос (РЕДАКТИРУЕМ то же сообщение!)
        await set_survey_state(user_id, next_question_num)
        next_question = SURVEY_QUESTIONS[next_question_num]

        await callback.message.edit_text(
            f"📋 <b>Опрос</b>\n\n{next_question['question']}",
            reply_markup=get_survey_keyboard(next_question['answers'], next_question_num)
        )

    await callback.answer()


@router.callback_query(F.data == "my_results")
async def callback_my_results(callback: CallbackQuery):
    """Показ результатов"""
    user_id = callback.from_user.id
    await update_user_activity(user_id)

    responses = await get_user_responses(user_id)

    if not responses:
        await callback.message.edit_text(
            "📋 Вы ещё не проходили опрос.",
            reply_markup=get_main_menu()
        )
        await callback.answer()
        return

    text = "📊 <b>Ваши ответы:</b>\n\n"
    for response in responses:
        text += f"<b>{response['question_text']}</b>\n➡️ {response['answer']}\n\n"

    await callback.message.edit_text(text, reply_markup=get_back_button())
    await callback.answer()


@router.callback_query(F.data == "about")
async def callback_about(callback: CallbackQuery):
    """О боте"""
    await update_user_activity(callback.from_user.id)

    await callback.message.edit_text(
        "ℹ️ <b>О боте</b>\n\n"
        "Этот бот для проведения опросов.\n\n"
        "🔹 Пройдите опрос\n"
        "🔹 Просмотрите результаты\n"
        "🔹 Ваши данные надёжно сохраняются",
        reply_markup=get_back_button()
    )
    await callback.answer()


@router.callback_query(F.data == "back_menu")
async def callback_back_menu(callback: CallbackQuery, state: FSMContext):
    """Возврат в меню"""
    await state.clear()
    is_admin = await check_admin(callback.from_user.id)

    await callback.message.edit_text(
        "📋 Главное меню:",
        reply_markup=get_admin_menu() if is_admin else get_main_menu()
    )
    await callback.answer()


# ==================== АДМИН-ПАНЕЛЬ ====================

@router.message(F.text.startswith("/admin"))
async def admin_login(message: Message, state: FSMContext):
    """Вход в админку"""
    user_id = message.from_user.id

    if await check_admin(user_id):
        await message.answer("🔐 Вы уже администратор.", reply_markup=get_admin_menu())
        return

    await state.set_state(AdminStates.waiting_password)

    # Удаляем команду /admin (чтобы не светить)
    try:
        await message.delete()
    except:
        pass

    await message.answer("🔐 Введите пароль администратора:\n\n<i>(сообщение с паролем автоматически удалится)</i>")


@router.message(AdminStates.waiting_password)
async def check_admin_password(message: Message, state: FSMContext):
    """Проверка пароля"""
    user_id = message.from_user.id
    password = message.text

    # Удаляем сообщение с паролем
    try:
        await message.delete()
    except:
        pass

    # Проверяем правильность пароля
    password_correct = check_password(password, ADMIN_PASSWORD_HASH)

    # 🔒 ЗАЩИТА ОТ ПЕРЕБОРА ПАРОЛЯ
    allowed, error_message = security.check_admin_attempt(user_id, password_correct)

    if not allowed:
        await message.answer(error_message)
        await state.clear()
        return

    if password_correct:
        await set_admin(user_id)
        await state.clear()
        await message.answer("✅ Доступ разрешён!", reply_markup=get_admin_menu())
    else:
        await message.answer(error_message)
        await state.clear()


@router.callback_query(F.data == "admin_exit")
async def callback_admin_exit(callback: CallbackQuery):
    """Выход из админки"""
    await callback.message.edit_text("👋 Выход из админ-панели.", reply_markup=get_main_menu())
    await callback.answer()


@router.callback_query(F.data == "admin_stats")
async def callback_admin_stats(callback: CallbackQuery):
    """Статистика"""
    if not await check_admin(callback.from_user.id):
        await callback.answer("❌ Доступ запрещён!", show_alert=True)
        return

    total_users = await get_total_users()
    total_responses = await get_total_responses()
    completed = await get_completed_surveys()

    completion_rate = (completed / total_users * 100) if total_users > 0 else 0

    text = (
        "📊 <b>Статистика:</b>\n\n"
        f"👥 Пользователей: <b>{total_users}</b>\n"
        f"✅ Завершённых опросов: <b>{completed}</b>\n"
        f"💬 Всего ответов: <b>{total_responses}</b>\n\n"
        f"📈 Завершаемость: <b>{completion_rate:.1f}%</b>"
    )

    await callback.message.edit_text(text, reply_markup=get_admin_menu())
    await callback.answer()


@router.callback_query(F.data == "admin_users")
async def callback_admin_users(callback: CallbackQuery):
    """Список пользователей"""
    if not await check_admin(callback.from_user.id):
        await callback.answer("❌ Доступ запрещён!", show_alert=True)
        return

    users = await get_all_users()

    if not users:
        await callback.answer("Пользователей нет.", show_alert=True)
        return

    text = "👥 <b>Пользователи:</b>\n\n"

    for user in users[:10]:
        name = user['first_name'] or "Без имени"
        username = f"@{user['username']}" if user['username'] else ""
        admin_badge = " 🔐" if user['is_admin'] else ""

        text += f"• <b>{name}</b> {username}{admin_badge}\n"
        text += f"  ID: <code>{user['user_id']}</code>\n\n"

    if len(users) > 10:
        text += f"\n...ещё {len(users) - 10}"

    await callback.message.edit_text(text, reply_markup=get_admin_menu())
    await callback.answer()


@router.callback_query(F.data == "admin_export")
async def callback_admin_export(callback: CallbackQuery):
    """Экспорт данных"""
    if not await check_admin(callback.from_user.id):
        await callback.answer("❌ Доступ запрещён!", show_alert=True)
        return

    responses = await export_all_responses()

    if not responses:
        await callback.answer("📋 Ответов нет.", show_alert=True)
        return

    # CSV
    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow(['User ID', 'Username', 'Имя', '№', 'Вопрос', 'Ответ', 'Дата'])

    for r in responses:
        writer.writerow([
            r['user_id'], r['username'], r['first_name'],
            r['question_number'], r['question_text'], r['answer'], r['answered_at']
        ])

    csv_bytes = output.getvalue().encode('utf-8-sig')
    output.close()

    filename = f"survey_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    file = BufferedInputFile(csv_bytes, filename=filename)

    await callback.message.answer_document(file, caption=f"📥 Экспорт: {len(responses)} записей")
    await callback.answer("✅ Файл отправлен")


@router.callback_query(F.data == "admin_broadcast")
async def callback_admin_broadcast(callback: CallbackQuery, state: FSMContext):
    """Рассылка"""
    if not await check_admin(callback.from_user.id):
        await callback.answer("❌ Доступ запрещён!", show_alert=True)
        return

    await state.set_state(AdminStates.waiting_broadcast)

    await callback.message.answer(
        "📢 <b>Рассылка</b>\n\n"
        "Отправьте сообщение которое получат все пользователи.\n\n"
        "Используйте HTML разметку."
    )
    await callback.answer()


@router.message(AdminStates.waiting_broadcast)
async def broadcast_send(message: Message, state: FSMContext):
    """Отправка рассылки"""
    if not await check_admin(message.from_user.id):
        return

    users = await get_all_users()
    broadcast_text = message.text

    await state.clear()

    status_msg = await message.answer(f"📢 Рассылка... (0/{len(users)})")

    success = 0
    failed = 0

    for i, user in enumerate(users, 1):
        try:
            await message.bot.send_message(user['user_id'], broadcast_text)
            success += 1
        except Exception as e:
            failed += 1
            logger.warning(f"Не отправлено {user['user_id']}: {e}")

        # Обновляем прогресс каждые 10 пользователей
        if i % 10 == 0:
            await status_msg.edit_text(f"📢 Рассылка... ({i}/{len(users)})")

    await status_msg.edit_text(
        f"✅ <b>Готово!</b>\n\n✅ Успешно: {success}\n❌ Ошибок: {failed}"
    )

    await message.answer("Готово!", reply_markup=get_admin_menu())


# ==================== НЕИЗВЕСТНЫЕ СООБЩЕНИЯ ====================

@router.message()
async def unknown_message(message: Message):
    """Обработка неизвестных сообщений"""
    await update_user_activity(message.from_user.id)
    is_admin = await check_admin(message.from_user.id)

    await message.answer(
        "❓ Выберите действие из меню:",
        reply_markup=get_admin_menu() if is_admin else get_main_menu()
    )
