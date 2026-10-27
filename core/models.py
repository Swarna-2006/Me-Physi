from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.core.validators import MinValueValidator

class User(AbstractUser):
    class Role(models.TextChoices):
        ADMIN = "admin", "Administrator"
        DOCTOR = "doctor", "Doctor"
        PATIENT = "patient", "Patient"
    role = models.CharField(max_length=12, choices=Role.choices, default=Role.PATIENT)
    phone = models.CharField(max_length=25, blank=True)
    def save(self, *args, **kwargs):
        if self.is_superuser:
            self.role = self.Role.ADMIN
        super().save(*args, **kwargs)
    @property
    def display_name(self):
        return self.get_full_name().strip() or self.username

class DoctorProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="doctor_profile")
    specialty = models.CharField(max_length=120)
    qualification = models.CharField(max_length=160, blank=True)
    consultation_fee = models.DecimalField(max_digits=9, decimal_places=2, default=0, validators=[MinValueValidator(0)])
    bio = models.TextField(blank=True)
    available = models.BooleanField(default=True)
    def __str__(self): return f"Dr. {self.user.display_name} — {self.specialty}"

class PatientProfile(models.Model):
    class Sex(models.TextChoices):
        FEMALE = "female", "Female"
        MALE = "male", "Male"
        OTHER = "other", "Other"
        UNSPECIFIED = "unspecified", "Prefer not to say"
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="patient_profile")
    date_of_birth = models.DateField(null=True, blank=True)
    sex = models.CharField(max_length=12, choices=Sex.choices, default=Sex.UNSPECIFIED)
    blood_group = models.CharField(max_length=3, blank=True)
    address = models.TextField(blank=True)
    emergency_contact = models.CharField(max_length=120, blank=True)
    allergies = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    def __str__(self): return self.user.display_name

class Appointment(models.Model):
    class Status(models.TextChoices):
        REQUESTED = "requested", "Awaiting doctor response"
        CONFIRMED = "confirmed", "Confirmed"
        REJECTED = "rejected", "Declined by doctor"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"
    patient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="patient_appointments")
    doctor = models.ForeignKey(DoctorProfile, on_delete=models.PROTECT, related_name="appointments")
    scheduled_at = models.DateTimeField()
    reason = models.CharField(max_length=240)
    duration_minutes = models.PositiveSmallIntegerField(default=30)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.REQUESTED)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        ordering = ["-scheduled_at"]
        indexes = [models.Index(fields=["doctor", "scheduled_at"]), models.Index(fields=["patient", "scheduled_at"]), models.Index(fields=["status", "scheduled_at"])]
    def __str__(self): return f"{self.patient} with {self.doctor} on {self.scheduled_at:%d %b %Y %H:%M}"

class MedicalRecord(models.Model):
    patient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="medical_records")
    doctor = models.ForeignKey(DoctorProfile, on_delete=models.PROTECT, related_name="medical_records")
    appointment = models.OneToOneField(Appointment, on_delete=models.SET_NULL, null=True, blank=True, related_name="medical_record")
    diagnosis = models.CharField(max_length=240)
    symptoms = models.TextField(blank=True)
    clinical_notes = models.TextField()
    treatment_plan = models.TextField(blank=True)
    recorded_at = models.DateTimeField(auto_now_add=True)
    class Meta: ordering = ["-recorded_at"]
    def __str__(self): return f"Record for {self.patient} — {self.diagnosis}"

class Prescription(models.Model):
    record = models.ForeignKey(MedicalRecord, on_delete=models.CASCADE, related_name="prescriptions")
    medication = models.CharField(max_length=160)
    dosage = models.CharField(max_length=100)
    frequency = models.CharField(max_length=120)
    duration = models.CharField(max_length=100, blank=True)
    instructions = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    def __str__(self): return f"{self.medication} — {self.record.patient}"


class DoctorAvailability(models.Model):
    """A recurring weekly window during which a doctor accepts appointments."""
    WEEKDAYS = [(0, "Monday"), (1, "Tuesday"), (2, "Wednesday"), (3, "Thursday"), (4, "Friday"), (5, "Saturday"), (6, "Sunday")]
    doctor = models.ForeignKey(DoctorProfile, on_delete=models.CASCADE, related_name="availability_windows")
    weekday = models.PositiveSmallIntegerField(choices=WEEKDAYS)
    start_time = models.TimeField()
    end_time = models.TimeField()
    slot_minutes = models.PositiveSmallIntegerField(default=30)
    is_active = models.BooleanField(default=True)
    class Meta:
        ordering = ["weekday", "start_time"]
        constraints = [models.UniqueConstraint(fields=["doctor", "weekday", "start_time", "end_time"], name="unique_doctor_weekly_window")]
    def __str__(self): return f"{self.doctor} — {self.get_weekday_display()} {self.start_time:%H:%M}-{self.end_time:%H:%M}"


class Notification(models.Model):
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications")
    appointment = models.ForeignKey(Appointment, on_delete=models.CASCADE, null=True, blank=True, related_name="notifications")
    title = models.CharField(max_length=160)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)
    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["recipient", "read_at", "created_at"])]
    @property
    def is_read(self): return self.read_at is not None
    def __str__(self): return f"{self.title} — {self.recipient}"
