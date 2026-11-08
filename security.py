"""
Модуль безопасности бота
- Защита от DDoS/DoS атак
- Антифлуд (rate limiting)
- Защита от перебора пароля
"""

import time
import logging
from collections import defaultdict
from typing import Dict, Tuple

logger = logging.getLogger(__name__)


class SecurityManager:
    """Менеджер безопасности"""

    def __init__(self):
        # Хранилище: user_id -> (количество запросов, время первого запроса)
        self._user_requests: Dict[int, list] = defaultdict(list)

        # Хранилище попыток входа в админку: user_id -> (количество попыток, время блокировки)
        self._admin_attempts: Dict[int, Tuple[int, float]] = {}

        # Настройки антифлуда
        self.FLOOD_LIMIT = 10  # Максимум запросов
        self.FLOOD_WINDOW = 10  # За 10 секунд

        # Настройки защиты админки
        self.MAX_ADMIN_ATTEMPTS = 3  # Максимум попыток входа
        self.ADMIN_BAN_TIME = 300  # Бан на 5 минут (300 сек)

    def check_flood(self, user_id: int) -> bool:
        """
        Проверяет не спамит ли пользователь
        Возвращает True если всё ОК, False если флуд
        """
        now = time.time()

        # Получаем список временных меток запросов пользователя
        requests = self._user_requests[user_id]

        # Удаляем старые запросы (старше FLOOD_WINDOW секунд)
        requests = [req_time for req_time in requests if now - req_time < self.FLOOD_WINDOW]

        # Обновляем список
        self._user_requests[user_id] = requests

        # Если превышен лимит — флуд!
        if len(requests) >= self.FLOOD_LIMIT:
            logger.warning(f"🚨 Флуд от пользователя {user_id}")
            return False

        # Добавляем текущий запрос
        requests.append(now)
        return True

    def check_admin_attempt(self, user_id: int, password_correct: bool) -> Tuple[bool, str]:
        """
        Проверяет попытку входа в админку
        Возвращает (разрешено ли, сообщение)
        """
        now = time.time()

        # Проверяем есть ли активная блокировка
        if user_id in self._admin_attempts:
            attempts, ban_time = self._admin_attempts[user_id]

            # Если забанен и бан ещё активен
            if attempts >= self.MAX_ADMIN_ATTEMPTS and (now - ban_time) < self.ADMIN_BAN_TIME:
                remaining = int(self.ADMIN_BAN_TIME - (now - ban_time))
                logger.warning(f"🚫 Попытка входа забаненного пользователя {user_id}")
                return False, f"⛔ Слишком много попыток!\n\nПопробуйте через {remaining} секунд."

            # Если бан истёк — сбрасываем
            if (now - ban_time) >= self.ADMIN_BAN_TIME:
                del self._admin_attempts[user_id]

        # Если пароль правильный — сбрасываем попытки
        if password_correct:
            if user_id in self._admin_attempts:
                del self._admin_attempts[user_id]
            return True, ""

        # Неверный пароль — увеличиваем счётчик
        if user_id in self._admin_attempts:
            attempts, _ = self._admin_attempts[user_id]
            attempts += 1
        else:
            attempts = 1

        self._admin_attempts[user_id] = (attempts, now)

        # Если превышен лимит попыток
        if attempts >= self.MAX_ADMIN_ATTEMPTS:
            logger.warning(f"🚨 Пользователь {user_id} заблокирован за перебор пароля")
            return False, f"⛔ Слишком много попыток!\n\nПопробуйте через {self.ADMIN_BAN_TIME} секунд."

        remaining_attempts = self.MAX_ADMIN_ATTEMPTS - attempts
        return True, f"❌ Неверный пароль!\n\nОсталось попыток: {remaining_attempts}"

    def reset_flood(self, user_id: int):
        """Сбрасывает счётчик флуда для пользователя"""
        if user_id in self._user_requests:
            del self._user_requests[user_id]

    def get_stats(self) -> Dict:
        """Возвращает статистику безопасности"""
        now = time.time()

        active_bans = sum(
            1 for user_id, (attempts, ban_time) in self._admin_attempts.items()
            if attempts >= self.MAX_ADMIN_ATTEMPTS and (now - ban_time) < self.ADMIN_BAN_TIME
        )

        return {
            'monitored_users': len(self._user_requests),
            'failed_login_attempts': len(self._admin_attempts),
            'active_bans': active_bans
        }


# Глобальный экземпляр менеджера безопасности
security = SecurityManager()
