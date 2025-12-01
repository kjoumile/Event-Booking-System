from .models import Log

def create_log(user, action):
    Log.objects.create(
        user=user,
        action=action
    )