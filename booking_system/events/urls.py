from django.urls import  path, include
from rest_framework.routers import DefaultRouter
from . import views


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



urlpatterns = [
    path('', include(router.urls)),
    path('register/', views.RegisterView.as_view(), name='register'),
    path('login/', views.LoginView.as_view(), name='login'),
    path('logout/', views.LogoutView.as_view(), name='logout')
]
