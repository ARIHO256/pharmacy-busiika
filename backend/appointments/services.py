"""Slot computation for doctor availability."""

import datetime

from django.utils import timezone

from .models import Appointment, Availability


def _parse_hhmm(value):
    """Parse 'HH:MM' (or 'HH:MM:SS') into a time object; None on failure."""
    if isinstance(value, datetime.time):
        return value
    try:
        parts = str(value).split(":")
        return datetime.time(int(parts[0]), int(parts[1]))
    except (ValueError, IndexError, TypeError):
        return None


def _overlaps(start_a, end_a, start_b, end_b):
    return start_a < end_b and end_a > start_b


def compute_free_slots(doctor, date):
    """Return free slots for `doctor` on `date`.

    Slots are generated from the doctor's active Availability rows matching the
    date's weekday. Holidays skip the whole row, break windows are cut out,
    past times are skipped when the date is today, and non-cancelled
    appointments are subtracted.

    Returns a list of {"start": "HH:MM", "end": "HH:MM"} dicts sorted by start.
    """
    if not isinstance(date, datetime.date):
        return []

    rows = Availability.objects.filter(
        doctor=doctor, weekday=date.weekday(), is_active=True
    )

    booked = list(
        Appointment.objects.filter(doctor=doctor, date=date).exclude(
            status=Appointment.Status.CANCELLED
        )
    )

    now = timezone.localtime()
    today = now.date()

    free = []
    for row in rows:
        holidays = row.holidays or []
        if date.isoformat() in {str(h) for h in holidays}:
            continue

        breaks = []
        for window in row.breaks or []:
            if not isinstance(window, dict):
                continue
            b_start = _parse_hhmm(window.get("start"))
            b_end = _parse_hhmm(window.get("end"))
            if b_start and b_end:
                breaks.append((b_start, b_end))

        step = datetime.timedelta(minutes=row.slot_minutes or 30)
        cursor = datetime.datetime.combine(date, row.start_time)
        day_end = datetime.datetime.combine(date, row.end_time)

        while cursor + step <= day_end:
            slot_start = cursor.time()
            slot_end = (cursor + step).time()

            in_break = any(
                _overlaps(slot_start, slot_end, b_start, b_end)
                for b_start, b_end in breaks
            )
            in_past = date == today and slot_start <= now.time()
            is_booked = any(
                _overlaps(slot_start, slot_end, appt.start_time, appt.end_time)
                for appt in booked
            )

            if not (in_break or in_past or is_booked):
                free.append(
                    {
                        "start": slot_start.strftime("%H:%M"),
                        "end": slot_end.strftime("%H:%M"),
                    }
                )
            cursor += step

    # Deduplicate (multiple rows may overlap) and sort.
    unique = {slot["start"]: slot for slot in free}
    return [unique[key] for key in sorted(unique)]


def find_slot(doctor, date, start_time):
    """Return the free slot dict matching `start_time`, or None."""
    wanted = start_time.strftime("%H:%M")
    for slot in compute_free_slots(doctor, date):
        if slot["start"] == wanted:
            return slot
    return None
