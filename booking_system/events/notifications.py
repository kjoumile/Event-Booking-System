from .models import Notification

def create_notifications(user, message):
    Notification.objects.create(user=user, message=message)
