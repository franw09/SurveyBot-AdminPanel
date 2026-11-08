"""
Модуль работы с базой данных SQLite
Хранит пользователей, их ответы на опросы и статистику
"""

import aiosqlite
import logging
from datetime import datetime
from typing import Optional, List, Dict

logger = logging.getLogger(__name__)

DB_NAME = "survey_bot.db"


async def init_db():
    """
    Инициализирует базу данных, создаёт таблицы если их нет
    """
    async with aiosqlite.connect(DB_NAME) as db:
        # Таблица пользователей
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                is_admin INTEGER DEFAULT 0,
                registered_at TEXT,
                last_activity TEXT
            )
        """)

        # Таблица ответов на опросы
        await db.execute("""
            CREATE TABLE IF NOT EXISTS survey_responses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                question_number INTEGER,
                question_text TEXT,
                answer TEXT,
                answered_at TEXT,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        """)

        # Таблица для хранения состояния опроса пользователя
        await db.execute("""
            CREATE TABLE IF NOT EXISTS user_survey_state (
                user_id INTEGER PRIMARY KEY,
                current_question INTEGER DEFAULT 0,
                started_at TEXT,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        """)

        await db.commit()
        logger.info("✅ Таблицы базы данных созданы/проверены")


async def add_user(user_id: int, username: str = None, first_name: str = None, last_name: str = None):
    """
    Добавляет нового пользователя в базу данных
    """
    async with aiosqlite.connect(DB_NAME) as db:
        now = datetime.now().isoformat()
        await db.execute("""
            INSERT OR IGNORE INTO users (user_id, username, first_name, last_name, registered_at, last_activity)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (user_id, username, first_name, last_name, now, now))
        await db.commit()


async def update_user_activity(user_id: int):
    """
    Обновляет время последней активности пользователя
    """
    async with aiosqlite.connect(DB_NAME) as db:
        now = datetime.now().isoformat()
        await db.execute("""
            UPDATE users SET last_activity = ? WHERE user_id = ?
        """, (now, user_id))
        await db.commit()


async def check_admin(user_id: int) -> bool:
    """
    Проверяет является ли пользователь администратором
    """
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("""
            SELECT is_admin FROM users WHERE user_id = ?
        """, (user_id,))
        result = await cursor.fetchone()
        return result and result[0] == 1


async def set_admin(user_id: int):
    """
    Делает пользователя администратором
    """
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            UPDATE users SET is_admin = 1 WHERE user_id = ?
        """, (user_id,))
        await db.commit()


async def get_survey_state(user_id: int) -> int:
    """
    Получает текущий вопрос пользователя в опросе
    """
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("""
            SELECT current_question FROM user_survey_state WHERE user_id = ?
        """, (user_id,))
        result = await cursor.fetchone()
        return result[0] if result else 0


async def set_survey_state(user_id: int, question_number: int):
    """
    Устанавливает текущий вопрос пользователя в опросе
    """
    async with aiosqlite.connect(DB_NAME) as db:
        now = datetime.now().isoformat()
        await db.execute("""
            INSERT OR REPLACE INTO user_survey_state (user_id, current_question, started_at)
            VALUES (?, ?, ?)
        """, (user_id, question_number, now))
        await db.commit()


async def save_answer(user_id: int, question_number: int, question_text: str, answer: str):
    """
    Сохраняет ответ пользователя на вопрос
    """
    async with aiosqlite.connect(DB_NAME) as db:
        now = datetime.now().isoformat()
        await db.execute("""
            INSERT INTO survey_responses (user_id, question_number, question_text, answer, answered_at)
            VALUES (?, ?, ?, ?, ?)
        """, (user_id, question_number, question_text, answer, now))
        await db.commit()


async def get_user_responses(user_id: int) -> List[Dict]:
    """
    Получает все ответы конкретного пользователя
    """
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("""
            SELECT question_number, question_text, answer, answered_at
            FROM survey_responses
            WHERE user_id = ?
            ORDER BY question_number
        """, (user_id,))
        rows = await cursor.fetchall()
        return [
            {
                'question_number': row[0],
                'question_text': row[1],
                'answer': row[2],
                'answered_at': row[3]
            }
            for row in rows
        ]


async def get_all_users() -> List[Dict]:
    """
    Получает список всех пользователей
    """
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("""
            SELECT user_id, username, first_name, last_name, is_admin, registered_at, last_activity
            FROM users
            ORDER BY registered_at DESC
        """)
        rows = await cursor.fetchall()
        return [
            {
                'user_id': row[0],
                'username': row[1],
                'first_name': row[2],
                'last_name': row[3],
                'is_admin': row[4],
                'registered_at': row[5],
                'last_activity': row[6]
            }
            for row in rows
        ]


async def get_total_users() -> int:
    """
    Получает общее количество пользователей
    """
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT COUNT(*) FROM users")
        result = await cursor.fetchone()
        return result[0] if result else 0


async def get_total_responses() -> int:
    """
    Получает общее количество ответов
    """
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT COUNT(*) FROM survey_responses")
        result = await cursor.fetchone()
        return result[0] if result else 0


async def get_completed_surveys() -> int:
    """
    Получает количество завершённых опросов
    """
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("""
            SELECT COUNT(DISTINCT user_id) FROM user_survey_state WHERE current_question = -1
        """)
        result = await cursor.fetchone()
        return result[0] if result else 0


async def reset_user_survey(user_id: int):
    """
    Сбрасывает прогресс опроса пользователя
    """
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("DELETE FROM user_survey_state WHERE user_id = ?", (user_id,))
        await db.execute("DELETE FROM survey_responses WHERE user_id = ?", (user_id,))
        await db.commit()


async def export_all_responses() -> List[Dict]:
    """
    Экспортирует все ответы для CSV/Excel
    """
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("""
            SELECT
                u.user_id,
                u.username,
                u.first_name,
                u.last_name,
                sr.question_number,
                sr.question_text,
                sr.answer,
                sr.answered_at
            FROM survey_responses sr
            JOIN users u ON sr.user_id = u.user_id
            ORDER BY sr.answered_at DESC
        """)
        rows = await cursor.fetchall()
        return [
            {
                'user_id': row[0],
                'username': row[1] or 'Нет username',
                'first_name': row[2] or '',
                'last_name': row[3] or '',
                'question_number': row[4],
                'question_text': row[5],
                'answer': row[6],
                'answered_at': row[7]
            }
            for row in rows
        ]
