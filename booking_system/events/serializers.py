from rest_framework import serializers
from .models import Category, Venue, Event, Seat, Booking

class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = '__all__'

class VenueSerializer(serializers.ModelSerializer):
    class Meta:
        model = Venue
        fields = '__all__'


class EventSerializer(serializers.ModelSerializer):
    category = CategorySerializer(read_only=True)
    venue = VenueSerializer(read_only=True)

    class Meta:
        model = Event
        fields = '__all__'

class SeatSerializer(serializers.ModelSerializer):
    event = serializers.StringRelatedField()
    class Meta:
        model = Seat
        fields = '__all__'

class BookingSerializer(serializers.ModelSerializer):
    event = serializers.StringRelatedField()
    seat = serializers.StringRelatedField()

    class Meta:
        model = Booking
        fields = '__all__'