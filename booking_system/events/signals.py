from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db import transaction
from .models import Event, Seat

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