from django.db import migrations


def backfill_status_history(apps, schema_editor):
    Appointment = apps.get_model("appointments", "Appointment")
    AppointmentStatusHistory = apps.get_model("appointments", "AppointmentStatusHistory")
    for appointment in Appointment.objects.all().iterator():
        if not AppointmentStatusHistory.objects.filter(appointment_id=appointment.id).exists():
            AppointmentStatusHistory.objects.create(
                appointment_id=appointment.id,
                actor_id=appointment.patient_id,
                from_status="",
                to_status=appointment.status,
                reason="Imported from pre-history appointment record",
                metadata={"migration": "appointments.0003"},
            )


class Migration(migrations.Migration):
    dependencies = [("appointments", "0002_appointmentstatushistory_and_more")]
    operations = [migrations.RunPython(backfill_status_history, migrations.RunPython.noop)]
