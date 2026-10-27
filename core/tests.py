from datetime import datetime, time, timedelta
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from .models import User, DoctorProfile, DoctorAvailability, Appointment, Notification

class AppointmentWorkflowTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(username="admin1", password="Strong-test-pass-123", role=User.Role.ADMIN, is_staff=True)
        self.doctor_user = User.objects.create_user(username="doctor1", password="Strong-test-pass-123", first_name="Asha", role=User.Role.DOCTOR)
        self.doctor = DoctorProfile.objects.create(user=self.doctor_user, specialty="General Medicine")
        self.patient = User.objects.create_user(username="patient1", password="Strong-test-pass-123", first_name="Priya", role=User.Role.PATIENT)
        self.patient2 = User.objects.create_user(username="patient2", password="Strong-test-pass-123", first_name="Nila", role=User.Role.PATIENT)
        # Find the next Monday so a stable weekly window can be tested.
        today = timezone.localdate()
        days_until_monday = (0 - today.weekday()) % 7
        if days_until_monday == 0: days_until_monday = 7
        self.slot_date = today + timedelta(days=days_until_monday)
        DoctorAvailability.objects.create(doctor=self.doctor, weekday=0, start_time=time(9, 0), end_time=time(12, 0), slot_minutes=30)
        self.slot = timezone.make_aware(datetime.combine(self.slot_date, time(10, 0)), timezone.get_current_timezone())

    def post_booking(self, patient, slot=None):
        client=Client()
        client.force_login(patient)
        return client.post(reverse("book_appointment"), {"doctor": self.doctor.pk, "scheduled_at": (slot or self.slot).strftime("%Y-%m-%dT%H:%M"), "reason": "Routine consultation"})

    def test_patient_booking_creates_pending_request_and_notifications(self):
        response=self.post_booking(self.patient)
        self.assertRedirects(response, reverse("appointments"))
        appointment=Appointment.objects.get(patient=self.patient)
        self.assertEqual(appointment.status, Appointment.Status.REQUESTED)
        self.assertEqual(appointment.duration_minutes, 30)
        self.assertTrue(Notification.objects.filter(recipient=self.patient, appointment=appointment).exists())
        self.assertTrue(Notification.objects.filter(recipient=self.doctor_user, appointment=appointment).exists())

    def test_overlapping_request_is_rejected(self):
        self.post_booking(self.patient)
        response=self.post_booking(self.patient2)
        self.assertEqual(Appointment.objects.filter(doctor=self.doctor).count(), 1)
        self.assertContains(response, "already has an overlapping appointment")

    def test_doctor_accepts_request_and_patient_is_notified(self):
        self.post_booking(self.patient)
        appointment=Appointment.objects.get(patient=self.patient)
        client=Client(); client.force_login(self.doctor_user)
        response=client.post(reverse("update_appointment_status", args=[appointment.pk]), {"action":"accept"})
        self.assertRedirects(response, reverse("appointments"))
        appointment.refresh_from_db()
        self.assertEqual(appointment.status, Appointment.Status.CONFIRMED)
        self.assertTrue(Notification.objects.filter(recipient=self.patient, appointment=appointment, title="Appointment confirmed").exists())

    def test_patient_cannot_open_admin_add_doctor(self):
        client=Client(); client.force_login(self.patient)
        response=client.get(reverse("add_doctor"))
        self.assertEqual(response.status_code, 403)

    def test_time_outside_schedule_is_rejected(self):
        outside=timezone.make_aware(datetime.combine(self.slot_date, time(13, 0)), timezone.get_current_timezone())
        response=self.post_booking(self.patient, outside)
        self.assertFalse(Appointment.objects.filter(patient=self.patient).exists())
        self.assertContains(response, "outside the doctor&#x27;s published schedule")
