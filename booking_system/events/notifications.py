from .models import Notification
import asyncio
from asgiref.sync import sync_to_async
from django.db import models
def create_notifications(user, message):
    Notification.objects.create(user=user, message=message)
