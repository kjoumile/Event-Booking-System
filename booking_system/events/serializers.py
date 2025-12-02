from rest_framework import serializers
from .models import *
from django.db import transaction
from django.contrib.auth.models import User

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
    organizer = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = Event
        fields = '__all__'

class SeatSerializer(serializers.ModelSerializer):
    event_name = serializers.CharField(source='event.title', read_only=True)
    class Meta:
        model = Seat
        fields = ['id', 'seat_number', 'is_booked', 'event_name']


class BookingSerializer(serializers.ModelSerializer):
    user_name = serializers.StringRelatedField(read_only=True, source='user')
    event_title = serializers.StringRelatedField(read_only=True, source='event')
    seat_number = serializers.StringRelatedField(read_only=True, source='seat')

    class Meta:
        model = Booking
        fields = ['id', 'event', 'seat', 'booking_time', 'user_name', 'event_title', 'seat_number']

    def validate(self, data):
        event = data['event']
        seat = data['seat']

        if seat.event != event:
            raise serializers.ValidationError('Нет такого места')

        if seat.is_booked:
            raise serializers.ValidationError('Это место уже забронировано')

        return data

    def create(self, validated_data):
        user = self.context['request'].user
        event = validated_data['event']

        # Получаем или создаем профиль
        profile, created = UserProfile.objects.get_or_create(user=user)

        seat = validated_data['seat']

        if profile.balance < event.price:
            raise serializers.ValidationError("Недостаточно средств на счету")

        with transaction.atomic():
            seat = Seat.objects.select_for_update().get(pk=seat.pk)
            if seat.is_booked:
                raise serializers.ValidationError('Это место уже забронировано')

            seat.is_booked = True
            seat.save()

            # Списание средств
            profile.balance -= event.price
            profile.save()

            booking = Booking.objects.create(**validated_data)

            Payment.objects.create(
                booking=booking,
                amount=event.price,
                status="success"
            )

            return booking


class RoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Role
        fields = '__all__'

class UserRoleSerializer(serializers.ModelSerializer):
    user = serializers.StringRelatedField()
    role = serializers.StringRelatedField()

    class Meta:
        model = UserRole
        fields = '__all__'

class ReviewSerializer(serializers.ModelSerializer):
    user = serializers.StringRelatedField(read_only=True)
    event_name = serializers.CharField(source='event.title', read_only=True)

    class Meta:
        model = Review
        fields = '__all__'

    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)

    def validate(self, data):
        user = self.context['request'].user
        event = data['event']

        if Review.objects.filter(user=user, event=event).exists():
            raise serializers.ValidationError('Вы уже оставили отзыв')
        return data


class PaymentSerializer(serializers.ModelSerializer):
    booking_id = serializers.IntegerField(source='booking.id', read_only=True, allow_null=True)
    user = serializers.SerializerMethodField()
    payment_type_display = serializers.CharField(source='get_payment_type_display', read_only=True)

    class Meta:
        model = Payment
        fields = [
            'id', 'booking_id', 'amount', 'status',
            'created_at', 'user', 'payment_type',
            'payment_type_display'
        ]

    def get_user(self, obj):
        if obj.booking:
            return obj.booking.user.username

        # Для платежей без бронирования получаем пользователя из контекста запроса
        request = self.context.get('request')
        if request and request.user:
            return request.user.username

        return "Система"
class AddBalanceSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=10, decimal_places=2)

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("Сумма должна быть положительной")
        return value
class NotificationSerializer(serializers.ModelSerializer):
    user = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = Notification
        fields = '__all__'

    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)
class LogSerializer(serializers.ModelSerializer):
    user = serializers.StringRelatedField()

    class Meta:
        model = Log
        fields = '__all__'

class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ("username", "password")

    def create(self, validated_data):
        user = User.objects.create_user(
            username=validated_data["username"],
            password=validated_data["password"]
        )
        role, created = Role.objects.get_or_create(name="USER")
        UserRole.objects.create(user=user, role=role)

        return user
class UserProfileSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)

    class Meta:
        model = UserProfile
        fields = ["id", "username", "balance"]
