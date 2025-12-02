from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

# Роутер для API
router = DefaultRouter()
router.register('categories', views.CategoryViewSet)
router.register('venues', views.VenueViewSet)
router.register('events', views.EventViewSet)
router.register('seats', views.SeatViewSet)
router.register('bookings', views.BookingViewSet)
router.register('roles', views.RoleViewSet)
router.register('user-roles', views.UserRoleViewSet)
router.register('reviews', views.ReviewViewSet)
router.register('payments', views.PaymentViewSet)
router.register('notifications', views.NotificationViewSet)
router.register('logs', views.LogViewSet)
router.register('profiles', views.UserProfileViewSet)

urlpatterns = [
    # REST API
    path('api/', include(router.urls)),

    # Главная страница
    path('', views.home_page, name='home'),

    # Аутентификация
    path('register/', views.RegisterView.as_view(), name='register'),
    path('login/', views.LoginView.as_view(), name='login'),
    path('logout/', views.LogoutView.as_view(), name='logout'),

    # Профиль и бронирования
    path('profile/', views.profile_page, name='profile-page'),
    path('my-bookings/', views.my_bookings_page, name='my_bookings'),

    # HTML страницы событий (измененные названия)
    path('events-list/', views.events_page, name='events_page'),  # Изменили events/ на events-list/
    path('event/<int:event_id>/', views.event_detail_page, name='event_detail_page'),  # Изменили events/ на event/

    # Создание контента
    path('create/category/', views.create_category_page, name='create_category'),
    path('create/venue/', views.create_venue_page, name='create_venue'),
    path('create/event/', views.create_event_page, name='create_event'),

    # Пополнение баланса
    path('topup/', views.top_up_page, name='payment-topup'),
]