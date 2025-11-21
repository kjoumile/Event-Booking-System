from django.shortcuts import render
from django.http import HttpResponse

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import Category, Venue, Event, Seat, Booking
from .serializers import CategorySerializer, VenueSerializer, EventSerializer, SeatSerializer, BookingSerializer


class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer

class VenueViewSet(viewsets.ModelViewSet):
    queryset = Venue.objects.all()
    serializer_class = VenueSerializer

class EventViewSet(viewsets.ModelViewSet):
    queryset = Event.objects.all()
    serializer_class = EventSerializer
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
    def get_queryset(self):
        queryset = Seat.objects.all()
        event_id = self.request.query_params.get('event')

        if event_id:
            queryset = queryset.filter(event_id=event_id)

        return queryset


class BookingViewSet(viewsets.ModelViewSet):
    queryset = Booking.objects.all()
    serializer_class = BookingSerializer

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        seat = instance.seat

        seat.is_booked = False
        seat.save()
        instance.delete()

        return Response(status=status.HTTP_204_NO_CONTENT)
# Create your views here.
