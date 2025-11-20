from django.urls import  path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register('categories', views.CategoryViewSet)
router.register('venues', views.VenueViewSet)
router.register('events', views.EventViewSet)
router.register('seats', views.SeatViewSet)
router.register('bookings', views.BookingViewSet)

urlpatterns = [
    path('', include(router.urls))
]
