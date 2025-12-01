from django.shortcuts import render
from django.http import HttpResponse
from rest_framework.views import APIView
from django.contrib.auth.models import User
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import *
from .serializers import *
from django_filters.rest_framework import DjangoFilterBackend
from .utils import create_log
from rest_framework.permissions import IsAuthenticated, BasePermission
from .permissions import IsAdmin, IsOrganizer, IsModerator
from .notifications import create_notifications
from rest_framework.exceptions import PermissionDenied

class AdminOrOrganizer(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        return (
            user.is_authenticated and (
                user.userrole_set.filter(role__name="ADMIN").exists() or
                user.userrole_set.filter(role__name="ORGANIZER").exists()
            )
        )
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

    def perform_create(self, serializer):
        serializer.save(organizer=self.request.user)

    def get_permissions(self):
        if self.action in ["create"]:
            return [IsOrganizer()]

        if self.action in ["update", "partial_update", "destroy"]:
            return [IsOrganizer()]  # проверит has_object_permission

        return []  # просмотр — свободный

    def perform_update(self, serializer):
        event = self.get_object()

        # Проверка прав — организатор может менять только свои
        is_admin = self.request.user.userrole_set.filter(role__name="ADMIN").exists()

        if event.organizer != self.request.user and not is_admin:
            raise PermissionDenied("Вы не можете редактировать событие, созданное не вами")

        # Сохраняем изменения
        updated_event = serializer.save()

        # Отправляем уведомления всем, у кого есть бронь
        for booking in updated_event.booking_set.all():
            create_notifications(
                user=booking.user,
                message=f"Событие «{updated_event.title}» было изменено"
            )

        # Записываем лог
        create_log(self.request.user, f"Обновил событие «{updated_event.title}»")

    # def perform_destroy(self, instance):
    #     users = [b.user for b in instance.booking_set.all()]
    #     event_name = instance.title
    #     # super().perform_destroy(instance)
    #
    #     for user in users:
    #         create_notifications(
    #             user=user,
    #             message=f"Событие '{event_name}' было отменено"
    #         )
    def perform_destroy(self, instance):
        bookings = list(instance.booking_set.select_related("user"))

        event_title = instance.title

        # Сначала создаем уведомления
        for booking in bookings:
            create_notifications(
                user=booking.user,
                message=f"Событие «{event_title}» было отменено. Ваше бронирование отменено."
            )

            # освободить место
            seat = booking.seat
            seat.is_booked = False
            seat.save()

            # удалить бронирование
            booking.delete()

        create_log(self.request.user, f"Удалил событие «{event_title}»")

        # теперь можно удалить событие
        super().perform_destroy(instance)

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
        create_notifications(
            user=user,
            message=f"Бронирование места {seat.seat_number} на событие '{seat.event.title}' отменено"
        )

        return Response({'detail':'Бронирование отменено'},status=status.HTTP_204_NO_CONTENT)

    def perform_create(self, serializer):
        booking = serializer.save(user=self.request.user)
        create_log(self.request.user, f'Создал бронирование #{booking.id}')

        create_notifications(
            user = self.request.user,
            message=f"Бронирование места {booking.seat.seat_number} на событие '{booking.event.title}'"
        )

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

    def get_permissions(self):
        if self.action in ["update", "partial_update", "destroy"]:
            return [IsModerator()]  # только модератор или админ
        return [permissions.IsAuthenticated()]  # создание — любой авторизованный

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


class RegisterView(APIView):
    permission_classes = []  # регистрация доступна всем

    def get(self, request):
        # Отобразить форму регистрации
        return render(request, "events/register.html")

    def post(self, request):
        # Если POST из формы — получить данные из request.POST
        data = request.data if request.content_type == "application/json" else request.POST
        serializer = RegisterSerializer(data=data, context={"request": request})

        if serializer.is_valid():
            user = serializer.save()
            message = f"Пользователь {user.username} создан!"
            return render(request, "events/register.html", {"message": message})

        return render(request, "events/register.html", {"errors": serializer.errors})