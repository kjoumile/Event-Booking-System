from django.shortcuts import render
from django.http import HttpResponse

from rest_framework import viewsets
from .models import Category, Venue, Event, Seat, Booking
from .serializers import CategorySerializer, VenueSerializer, EventSerializer, SeatSerializer, BookingSerializer


class CategoryViewSet(viewsets.ModelViewSet()):
    queryset = Category.objects.all()
    serializers_class = CategorySerializer

class VenueViewSet(viewsets.ModelViewSet):
    queryset = Venue.objects.all()
    serializer_class = VenueSerializer

class EventViewSet(viewsets.ModelViewSet):
    queryset = Event.objects.all()
    serializer_class = EventSerializer

class SeatViewSet(viewsets.ModelViewSet):
    queryset = Seat.objects.all()
    serializer_class = SeatSerializer

class BookingViewSet(viewsets.ModelViewSet):
    queryset = Booking.objects.all()
    serializer_class = BookingSerializer
# Create your views here.
