from django.contrib import admin

from .models import Appointment, Availability


@admin.register(Availability)
class AvailabilityAdmin(admin.ModelAdmin):
    list_display = ("doctor", "weekday", "start_time", "end_time", "slot_minutes", "is_active")
    list_filter = ("weekday", "is_active")


@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ("patient", "doctor", "date", "start_time", "type", "status")
    list_filter = ("status", "type", "date")
