# events/async_service.py - ПРАВИЛЬНАЯ ВЕРСИЯ
import asyncio
from asgiref.sync import sync_to_async
from django.db import transaction
from .models import Notification, Log


class AsyncNotificationService:
    """Правильная асинхронная отправка уведомлений и логирование"""

    @staticmethod
    async def send_notification_async(user_id, message):
        """Асинхронная отправка уведомления"""
        try:
            await sync_to_async(Notification.objects.create)(
                user_id=user_id,
                message=message,
                is_read=False
            )
            print(f"✅ Асинхронное уведомление отправлено пользователю {user_id}")
        except Exception as e:
            print(f"❌ Ошибка уведомления: {e}")

    @staticmethod
    async def create_log_async(user_id, action, ip_address=None):
        """Асинхронное логирование"""
        try:
            await sync_to_async(Log.objects.create)(
                user_id=user_id,
                action=action,
                ip_address=ip_address
            )
            print(f"📝 Асинхронный лог создан для пользователя {user_id}")
        except Exception as e:
            print(f"❌ Ошибка логирования: {e}")

    @staticmethod
    def fire_and_forget_async(coroutine):
        """Запуск асинхронной задачи без ожидания"""
        try:
            # Пытаемся запустить в существующем event loop
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Если loop уже запущен, создаем задачу
                asyncio.create_task(coroutine)
            else:
                # Иначе запускаем новый loop
                loop.run_until_complete(coroutine)
        except RuntimeError:
            # Если нет event loop, создаем новый в отдельном потоке
            import threading

            def run_in_thread():
                new_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(new_loop)
                new_loop.run_until_complete(coroutine)
                new_loop.close()

            thread = threading.Thread(target=run_in_thread, daemon=True)
            thread.start()

    @staticmethod
    async def send_bulk_notifications_async(user_ids, message_template, **kwargs):
        """Асинхронная массовая отправка уведомлений"""
        tasks = []
        for user_id in user_ids:
            message = message_template.format(user_id=user_id, **kwargs)
            task = AsyncNotificationService.send_notification_async(user_id, message)
            tasks.append(task)

        # Запускаем все задачи параллельно
        await asyncio.gather(*tasks, return_exceptions=True)