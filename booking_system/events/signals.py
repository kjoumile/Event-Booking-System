from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db import transaction
from django.contrib.auth.models import User
from .models import *

@receiver(post_save, sender=Event)
def create_seats_for_events(sender, instance,created, **kwargs):
    if not created:
        return
    venue_capacity = instance.venue.capacity
    with transaction.atomic():
        seats = [
            Seat(event = instance, seat_number=i+1, is_booked=False)
            for i in range(venue_capacity)
        ]
        Seat.objects.bulk_create(seats)

from .models import UserProfile

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)