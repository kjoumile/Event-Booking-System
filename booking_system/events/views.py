from django.shortcuts import render
from django.http import HttpResponse

from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import Category, Venue, Event, Seat, Booking, Role, UserRole, Review, Payment, Notification, Log
from .serializers import (CategorySerializer, VenueSerializer, EventSerializer, SeatSerializer, BookingSerializer,
                          RoleSerializer, UserRoleSerializer, ReviewSerializer, PaymentSerializer, NotificationSerializer,
                          LogSerializer)
from django_filters.rest_framework import DjangoFilterBackend
from .utils import create_log

class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer

class VenueViewSet(viewsets.ModelViewSet):
    queryset = Venue.objects.all()
    serializer_class = VenueSerializer

class EventViewSet(viewsets.ModelViewSet):
    queryset = Event.objects.all()
    serializer_class = EventSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['date', 'category', 'venue']
    #
    @action(detail=True, methods=['get'], url_path='free-seats')
    def free_seats(self, request, pk=None):
        event = self.get_object()
        free_seats = event.seats.filter(is_booked=False)

        data = [
            {
                "id":seat.id,
                'seat_number': seat.seat_number,
                "is_booked": seat.is_booked
            }
            for seat in free_seats
        ]
        return Response(data)
class SeatViewSet(viewsets.ModelViewSet):
    queryset = Seat.objects.all()
    serializer_class = SeatSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['event','is_booked']
    def get_queryset(self):
        queryset = Seat.objects.all()
        event_id = self.request.query_params.get('event')

        if event_id:
            queryset = queryset.filter(event_id=event_id)

        return queryset


class BookingViewSet(viewsets.ModelViewSet):
    queryset = Booking.objects.all()
    serializer_class = BookingSerializer
    permission_classes = [permissions.IsAuthenticated]

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        seat = instance.seat
        user = request.user
        seat.is_booked = False
        seat.save()
        Log.objects.create(
            user = user,
            action=f"Отмена бронирования места {seat.id} на событие {seat.event.id}",
            ip_address = request._request.META.get("REMOTE_ADDR")
        )
        instance.delete()

        return Response({'detail':'Бронирование отменено'},status=status.HTTP_204_NO_CONTENT)

    def perform_create(self, serializer):
        booking = serializer.save(user=self.request.user)
        create_log(self.request.user, f'Создал бронирование #{booking.id}')

    def perform_destroy(self, instance):
        create_log(self.request.user, f'Отменил бронирование #{instance.id}')
        super().perform_destroy(instance)

# Create your views here.
class RoleViewSet(viewsets.ModelViewSet):
    queryset = Role.objects.all()
    serializer_class = RoleSerializer
    permission_classes = [permissions.IsAdminUser]

class UserRoleViewSet(viewsets.ModelViewSet):
    queryset = UserRole.objects.all()
    serializer_class = UserRoleSerializer
    permission_classes = [permissions.IsAdminUser]

class ReviewViewSet(viewsets.ModelViewSet):
    queryset = Review.objects.all()
    serializer_class = ReviewSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        review = serializer.save(user=self.request.user)
        create_log(self.request.user, f"Оставил отзыв #{review.id}")

    def perform_update(self, serializer):
        review = serializer.save()
        create_log(self.request.user, f"Изменил отзыв #{review.id}")

    def perform_destroy(self, instance):
        create_log(self.request.user, f"Удалил отзыв #{instance.id}")
        super().perform_destroy(instance)

class PaymentViewSet(viewsets.ModelViewSet):
    queryset = Payment.objects.all()
    serializer_class = PaymentSerializer
    permission_classes = [permissions.IsAuthenticated]

class NotificationViewSet(viewsets.ModelViewSet):
    queryset = Notification.objects.all()
    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # Пользователь может читать только СВОИ уведомления
        return Notification.objects.filter(user=self.request.user)

class LogViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Log.objects.all()
    serializer_class = LogSerializer
    permission_classes = [permissions.IsAdminUser]
