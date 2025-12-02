from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse
from datetime import datetime
from django.core.exceptions import PermissionDenied
from rest_framework.views import APIView
from django.contrib.auth.models import User
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
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
                user.roles.filter(role__name="ADMIN").exists() or
                user.roles.filter(role__name="ORGANIZER").exists()
            )
        )

def home_page(request):
    """Главная страница"""
    # Если пользователь уже авторизован, перенаправляем на страницу событий
    if request.user.is_authenticated:
        return redirect('events_page')
    # Если не авторизован, перенаправляем на страницу логина
    return redirect('login')

class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer

    def get_permissions(self):
        # Создание/изменение/удаление доступно только админам и модераторам
        if self.action in ["create", "update", "partial_update", "destroy"]:
            return [AdminOrOrganizer()]
        # Просмотр доступен всем
        return []

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
        # if self.action in ["create"]:
        #     return [IsOrganizer()]

        if self.action in ["create","update", "partial_update", "destroy"]:
            return [AdminOrOrganizer()]  # проверит has_object_permission

        return []  # просмотр — свободный

    def perform_update(self, serializer):
        event = self.get_object()

        # Проверка прав — организатор может менять только свои
        is_admin = self.request.user.roles.filter(role__name="ADMIN").exists()

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
        booking_user = instance.user  # Владелец бронирования

        is_admin = user.roles.filter(role__name="ADMIN").exists()
        is_moderator = user.roles.filter(role__name="MODERATOR").exists()

        # Проверка прав
        if instance.user != user and not (is_admin or is_moderator):
            raise PermissionDenied("Вы не можете удалить чужое бронирование")

        with transaction.atomic():
            # Освобождаем место
            seat.is_booked = False
            seat.save()

            # Возвращаем деньги владельцу бронирования
            refund_amount = instance.event.price

            # Получаем или создаем профиль пользователя
            profile, created = UserProfile.objects.get_or_create(user=booking_user)

            # Возвращаем деньги на баланс
            profile.balance += refund_amount
            profile.save()

            # Создаем запись о возврате в платежах
            Payment.objects.create(
                booking=instance,  # Привязываем к оригинальному бронированию
                amount=refund_amount,
                status="refunded",
                payment_type="refund"
            )

            # Логируем действие
            Log.objects.create(
                user=user,
                action=f"Отмена бронирования #{instance.id}. Возвращено {refund_amount} пользователю {booking_user.username}",
                ip_address=request.META.get("REMOTE_ADDR")
            )

            # Отправляем уведомление владельцу бронирования
            create_notifications(
                user=booking_user,
                message=f"Ваше бронирование места {seat.seat_number} на событие '{seat.event.title}' отменено. На ваш баланс возвращено {refund_amount} руб."
            )

            # Если отменяет не владелец, отправляем уведомление и отменяющему
            if user != booking_user:
                create_notifications(
                    user=user,
                    message=f"Вы отменили бронирование #{instance.id} пользователя {booking_user.username}"
                )

            # Удаляем бронирование (платеж с on_delete=CASCADE удалится автоматически)
            instance.delete()

        return Response(
            {
                'detail': f'Бронирование отменено.',
                'refund': f'{refund_amount} руб. возвращено на баланс пользователя {booking_user.username}.',
                'new_balance': f'{profile.balance} руб.'
            },
            status=status.HTTP_204_NO_CONTENT
        )

    def perform_create(self, serializer):
        booking = serializer.save(user=self.request.user)
        create_log(self.request.user, f'Создал бронирование #{booking.id}')

        create_notifications(
            user=self.request.user,
            message=f"Бронирование места {booking.seat.seat_number} на событие '{booking.event.title}' на сумму {booking.event.price} руб."
        )

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
    filter_backends = [DjangoFilterBackend]
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


class PaymentViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Payment.objects.all()
    serializer_class = PaymentSerializer
    permission_classes = [permissions.IsAuthenticated]
    def get_queryset(self):
        # Пользователь может читать только СВОИ уведомления
        return Payment.objects.filter(booking__user=self.request.user)
    @action(detail=False, methods=['post'])
    def top_up(self, request):
        """Пополнение баланса"""
        serializer = AddBalanceSerializer(data=request.data)
        if serializer.is_valid():
            amount = serializer.validated_data['amount']

            # Получаем или создаем профиль
            profile, created = UserProfile.objects.get_or_create(user=request.user)

            # Пополняем баланс
            profile.balance += amount
            profile.save()

            # Создаем запись о пополнении
            Payment.objects.create(
                booking=None,  # Теперь можно передавать None
                amount=amount,
                status="success",
                payment_type="topup"
            )

            return Response({
                "message": f"Баланс пополнен на {amount} руб.",
                "current_balance": f"{profile.balance} руб."
            })
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['get'])
    def my_balance(self, request):
        """Просмотр текущего баланса"""
        profile, created = UserProfile.objects.get_or_create(user=request.user)
        return Response({
            "username": request.user.username,
            "balance": float(profile.balance)  # Конвертируем в float для JSON
        })
class NotificationViewSet(viewsets.ReadOnlyModelViewSet):
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

class UserProfileViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = UserProfile.objects.all()
    serializer_class = UserProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # Обычный пользователь видит только свой профиль
        if self.request.user.is_staff:
            return UserProfile.objects.all()  # админ видит всех
        return UserProfile.objects.filter(user=self.request.user)

    def destroy(self, request, *args, **kwargs):
        # только админ может удалять профили
        if not request.user.is_staff:
            raise PermissionDenied("Вы не можете удалять профили")
        return super().destroy(request, *args, **kwargs)


def events_page(request):
    events = Event.objects.select_related("venue", "category")
    return render(request, "templates/pages/events.html", {"events": events})

def profile_page(request):
    if not request.user.is_authenticated:
        return redirect('/login/')  # если пользователь не залогинен
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    return render(request, 'templates/pages/profile.html', {'user': request.user, 'profile': profile})
class RegisterView(APIView):
    permission_classes = []  # регистрация доступна всем

    def get(self, request):
        # Отобразить форму регистрации
        return render(request, "templates/events/register.html")

    def post(self, request):
        # Если POST из формы — получить данные из request.POST
        data = request.data if request.content_type == "application/json" else request.POST
        serializer = RegisterSerializer(data=data, context={"request": request})

        if serializer.is_valid():
            user = serializer.save()
            login(request, user)
            return redirect("/events-list/")

        return render(request, "templates/events/register.html", {"errors": serializer.errors})
class LoginView(APIView):
    permission_classes = []  # вход доступен всем

    def get(self, request):
        return render(request, "templates/events/login.html")

    def post(self, request):
        data = request.POST

        username = data.get("username")
        password = data.get("password")

        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            return redirect("/events-list/")  # куда перенаправить после входа

        return render(
            request,
            "templates/events/login.html",
            {"error": "Неверный логин или пароль"}
        )
class LogoutView(APIView):
    def post(self, request):
        logout(request)
        return Response({"detail": "Вы вышли из системы"}, status=status.HTTP_200_OK)


@login_required
def my_bookings_page(request):
    """Простая страница с бронированиями"""
    # Получаем бронирования пользователя
    bookings = Booking.objects.filter(user=request.user).select_related('event', 'seat')

    # Обработка отмены бронирования
    if request.method == "POST" and "cancel_booking" in request.POST:
        booking_id = request.POST.get("booking_id")

        try:
            booking = Booking.objects.get(id=booking_id, user=request.user)

            # Проверяем, существует ли уже платеж для этого бронирования
            payment_exists = Payment.objects.filter(booking=booking).exists()

            if not payment_exists:
                # Создаем запись о возврате только если платежа не было
                Payment.objects.create(
                    booking=booking,
                    amount=booking.event.price,
                    status="refunded"
                )
            else:
                # Если платеж уже существует, можно его обновить или оставить как есть
                # Либо создать новый платеж с booking=None
                Payment.objects.create(
                    booking=None,  # Если разрешено NULL в модели
                    amount=booking.event.price,
                    status="refunded"
                )

            # Освобождаем место
            seat = booking.seat
            seat.is_booked = False
            seat.save()

            # Возвращаем деньги
            profile, _ = UserProfile.objects.get_or_create(user=request.user)
            profile.balance += booking.event.price
            profile.save()

            # Удаляем бронирование
            booking.delete()

            # Обновляем список
            bookings = Booking.objects.filter(user=request.user)

        except Booking.DoesNotExist:
            pass

    return render(request, "templates/pages/my_bookings.html", {
        "bookings": bookings
    })


@login_required
def event_detail_page(request, event_id):
    event = get_object_or_404(Event, id=event_id)
    free_seats = event.seats.filter(is_booked=False)
    user_review = Review.objects.filter(user=request.user, event=event).first()
    reviews = event.reviews.all()

    if request.method == "POST":
        if "seat_id" in request.POST:
            # Бронирование места
            seat_id = request.POST.get("seat_id")
            seat = get_object_or_404(Seat, id=seat_id, event=event, is_booked=False)

            # Проверяем баланс пользователя
            profile, created = UserProfile.objects.get_or_create(user=request.user)

            if profile.balance < event.price:
                # Если недостаточно средств
                return render(request, "templates/pages/event_detail.html", {
                    "event": event,
                    "free_seats": free_seats,
                    "reviews": reviews,
                    "user_review": user_review,
                    "error": f"Недостаточно средств на счету. Текущий баланс: {profile.balance} руб. Стоимость: {event.price} руб."
                })

            # Бронируем с использованием транзакции
            with transaction.atomic():
                # Блокируем место для предотвращения гонок
                seat = Seat.objects.select_for_update().get(pk=seat.id)
                if seat.is_booked:
                    return render(request, "templates/pages/event_detail.html", {
                        "event": event,
                        "free_seats": free_seats.filter(is_booked=False),
                        "reviews": reviews,
                        "user_review": user_review,
                        "error": "Место уже забронировано"
                    })

                # Бронируем место
                seat.is_booked = True
                seat.save()

                # Создаем бронирование
                booking = Booking.objects.create(
                    user=request.user,
                    event=event,
                    seat=seat
                )

                # Списываем деньги
                profile.balance -= event.price
                profile.save()

                # Создаем запись о платеже
                Payment.objects.create(
                    booking=booking,
                    amount=event.price,
                    status="success"
                )

                # Создаем уведомление
                create_notifications(
                    user=request.user,
                    message=f"Бронирование места {seat.seat_number} на событие '{event.title}' на сумму {event.price} руб."
                )

                # Логируем
                create_log(request.user, f'Создал бронирование #{booking.id}')

            # Перенаправляем на страницу успеха
            return redirect("event_detail_page", event_id=event.id)

        elif "review_text" in request.POST:
            # Добавление отзыва
            review_text = request.POST.get("review_text")
            rating = request.POST.get('rating', 5)
            if not user_review:  # можно оставить только один отзыв
                Review.objects.create(user=request.user, event=event, comment=review_text, rating=int(rating))
            return redirect("event_detail_page", event_id=event.id)

    return render(request, "templates/pages/event_detail.html", {
        "event": event,
        "free_seats": free_seats,
        "reviews": reviews,
        "user_review": user_review
    })


from decimal import Decimal


@login_required
def top_up_page(request):
    """Страница пополнения баланса"""
    if request.method == "POST":
        amount_str = request.POST.get("amount")
        try:
            # Конвертируем в Decimal вместо float
            amount = Decimal(amount_str)
            if amount <= Decimal('0'):
                return render(request, "templates/pages/topup.html", {
                    "error": "Сумма должна быть положительной"
                })

            # Пополняем баланс
            profile, created = UserProfile.objects.get_or_create(user=request.user)
            profile.balance += amount  # Теперь оба значения Decimal
            profile.save()

            # Создаем запись о платеже
            Payment.objects.create(
                booking=None,
                amount=amount,  # Передаем Decimal
                status="success",
                payment_type="topup"
            )

            # Перенаправляем обратно на страницу события или профиля
            redirect_to = request.GET.get('next', '/profile/')
            return redirect(redirect_to)

        except (ValueError, InvalidOperation) as e:
            return render(request, "templates/pages/topup.html", {
                "error": "Введите корректную сумму"
            })

    return render(request, "templates/pages/topup.html")


@login_required
def create_category_page(request):
    """HTML страница для создания категории"""
    # Проверка прав через ваш AdminOrOrganizer (с добавлением модератора)
    has_permission = request.user.is_authenticated and request.user.roles.filter(
        role__name__in=["ADMIN", "ORGANIZER", "MODERATOR"]
    ).exists()

    if not has_permission:
        raise PermissionDenied("У вас нет прав для создания категорий")

    if request.method == "POST":
        name = request.POST.get("name")
        description = request.POST.get("description", "")

        if not name:
            return render(request, "templates/pages/create_category.html", {
                "error": "Название категории обязательно"
            })

        # Создаем категорию
        category = Category.objects.create(
            name=name,
            description=description
        )

        # Логируем
        Log.objects.create(
            user=request.user,
            action=f"Создал категорию: {category.name}",
            ip_address=request.META.get("REMOTE_ADDR")
        )

        create_notifications(
            user=request.user,
            message=f"Вы создали категорию '{category.name}'"
        )

        return redirect("events_page")

    return render(request, "templates/pages/create_category.html")


@login_required
def create_venue_page(request):
    """HTML страница для создания места проведения"""
    # Проверка прав через ваш AdminOrOrganizer (с добавлением модератора)
    has_permission = request.user.is_authenticated and request.user.roles.filter(
        role__name__in=["ADMIN", "ORGANIZER", "MODERATOR"]
    ).exists()

    if not has_permission:
        raise PermissionDenied("У вас нет прав для создания мест проведения")

    if request.method == "POST":
        name = request.POST.get("name")
        address = request.POST.get("address")
        capacity_str = request.POST.get("capacity")

        if not name or not address or not capacity_str:
            return render(request, "templates/pages/create_venue.html", {
                "error": "Все поля обязательны"
            })

        try:
            capacity = int(capacity_str)
            if capacity <= 0:
                return render(request, "templates/pages/create_venue.html", {
                    "error": "Вместимость должна быть положительным числом"
                })
        except ValueError:
            return render(request, "templates/pages/create_venue.html", {
                "error": "Вместимость должна быть числом"
            })

        # Создаем место
        venue = Venue.objects.create(
            name=name,
            address=address,
            capacity=capacity
        )

        # Логируем
        Log.objects.create(
            user=request.user,
            action=f"Создал место проведения: {venue.name}",
            ip_address=request.META.get("REMOTE_ADDR")
        )

        create_notifications(
            user=request.user,
            message=f"Вы создали место проведения '{venue.name}'"
        )

        return redirect("events_page")

    return render(request, "templates/pages/create_venue.html")


@login_required
def create_event_page(request):
    """HTML страница для создания события"""
    # Проверка прав через ваш AdminOrOrganizer
    permission_checker = AdminOrOrganizer()
    if not permission_checker.has_permission(request, None):
        raise PermissionDenied("Только администраторы и организаторы могут создавать события")

    # Получаем доступные категории и места
    categories = Category.objects.all()
    venues = Venue.objects.all()

    if request.method == "POST":
        title = request.POST.get("title")
        description = request.POST.get("description")
        date_str = request.POST.get("date")
        venue_id = request.POST.get("venue")
        category_id = request.POST.get("category")
        price_str = request.POST.get("price", "0")

        # Проверка обязательных полей
        required_fields = [title, description, date_str, venue_id, category_id]
        if not all(required_fields):
            return render(request, "templates/pages/create_event.html", {
                "categories": categories,
                "venues": venues,
                "error": "Все поля обязательны"
            })

        try:
            # Парсим дату
            date = datetime.strptime(date_str, "%Y-%m-%dT%H:%M")
            price = Decimal(price_str)
            if price < 0:
                return render(request, "templates/pages/create_event.html", {
                    "categories": categories,
                    "venues": venues,
                    "error": "Цена не может быть отрицательной"
                })
        except ValueError as e:
            return render(request, "templates/pages/create_event.html", {
                "categories": categories,
                "venues": venues,
                "error": f"Ошибка в данных: {str(e)}"
            })

        try:
            venue = Venue.objects.get(id=venue_id)
            category = Category.objects.get(id=category_id)
        except (Venue.DoesNotExist, Category.DoesNotExist):
            return render(request, "templates/pages/create_event.html", {
                "categories": categories,
                "venues": venues,
                "error": "Выбранное место или категория не существуют"
            })

        # Создаем событие
        event = Event.objects.create(
            title=title,
            description=description,
            date=date,
            venue=venue,
            category=category,
            organizer=request.user,
            price=price
        )

        # Логируем
        Log.objects.create(
            user=request.user,
            action=f"Создал событие: {event.title}",
            ip_address=request.META.get("REMOTE_ADDR")
        )

        create_notifications(
            user=request.user,
            message=f"Вы создали событие '{event.title}'"
        )

        # Создаем автоматически места для события
        create_seats_for_event(event, venue.capacity)

        return redirect("event_detail_page", event_id=event.id)

    return render(request, "templates/pages/create_event.html", {
        "categories": categories,
        "venues": venues,
        "today": datetime.now().strftime("%Y-%m-%dT%H:%M")
    })


def create_seats_for_event(event, capacity):
    """Создает места для события"""
    seats = []
    for i in range(1, capacity + 1):
        seats.append(
            Seat(
                event=event,
                seat_number=str(i),
                is_booked=False
            )
        )
    Seat.objects.bulk_create(seats)


@login_required
def notifications_page(request):
    """Страница с уведомлениями пользователя"""
    # Получаем уведомления пользователя
    notifications = Notification.objects.filter(user=request.user).order_by('-created_at')

    # Помечаем все непрочитанные уведомления как прочитанные
    unread_notifications = notifications.filter(is_read=False)
    if unread_notifications.exists():
        unread_notifications.update(is_read=True)

    # Обработка удаления уведомлений
    if request.method == "POST" and "delete_notification" in request.POST:
        notification_id = request.POST.get("notification_id")
        try:
            notification = Notification.objects.get(id=notification_id, user=request.user)
            notification.delete()
            # Обновляем список
            notifications = Notification.objects.filter(user=request.user).order_by('-created_at')
        except Notification.DoesNotExist:
            pass

    # Обработка удаления всех уведомлений
    if request.method == "POST" and "delete_all" in request.POST:
        notifications.delete()
        notifications = Notification.objects.none()

    return render(request, "templates/pages/notifications.html", {
        "notifications": notifications,
        "unread_count": notifications.filter(is_read=False).count()  # для навбара
    })