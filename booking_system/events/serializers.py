from rest_framework import serializers
from .models import Category, Venue, Event, Seat, Booking
from django.db import transaction

class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = '__all__'

class VenueSerializer(serializers.ModelSerializer):
    class Meta:
        model = Venue
        fields = '__all__'


class EventSerializer(serializers.ModelSerializer):
    # category = CategorySerializer(read_only=True)
    # venue = VenueSerializer(read_only=True)

    class Meta:
        model = Event
        fields = '__all__'

class SeatSerializer(serializers.ModelSerializer):
    # event = serializers.StringRelatedField()
    class Meta:
        model = Seat
        fields = '__all__'

class BookingSerializer(serializers.ModelSerializer):
    user_name = serializers.StringRelatedField(read_only=True, source='user')
    event_title = serializers.StringRelatedField(read_only=True, source='event')
    seat_number = serializers.StringRelatedField(read_only=True, source='seat')

    class Meta:
        model = Booking
        fields = '__all__'


    def validate(self, data):
        event = data['event']
        seat = data['seat']

        if seat.event !=event:
            raise serializers.ValidationError('Нет такого места')

        if seat.is_booked:
            raise serializers.ValidationError('Это место уже забронировано')

        return data
    def create(self, validated_data):
        seat = validated_data['seat']
        with transaction.atomic():
            seat = Seat.objects.select_for_update().get(pk=seat.pk)
            if seat.is_booked:
                raise serializers.ValidationError('Это место уже забронировано')
            seat.is_booked = True
            seat.save()
            user = self.context['request'].user
            return Booking.objects.create(**validated_data)