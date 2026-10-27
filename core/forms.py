from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.utils import timezone
from .models import User, PatientProfile, DoctorProfile, DoctorAvailability, Appointment, MedicalRecord, Prescription

class PatientRegistrationForm(UserCreationForm):
    first_name = forms.CharField(max_length=150)
    last_name = forms.CharField(max_length=150, required=False)
    email = forms.EmailField()
    class Meta:
        model = User
        fields = ("username", "first_name", "last_name", "email", "phone")
    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = User.Role.PATIENT
        user.first_name = self.cleaned_data["first_name"]
        user.last_name = self.cleaned_data["last_name"]
        user.email = self.cleaned_data["email"]
        user.phone = self.cleaned_data.get("phone", "")
        if commit: user.save(); PatientProfile.objects.get_or_create(user=user)
        return user

class PatientProfileForm(forms.ModelForm):
    class Meta:
        model = PatientProfile
        fields = ["date_of_birth", "sex", "blood_group", "address", "emergency_contact", "allergies"]
        widgets = {"date_of_birth": forms.DateInput(attrs={"type":"date"}), "address": forms.Textarea(attrs={"rows":3}), "allergies": forms.Textarea(attrs={"rows":3})}

class AppointmentForm(forms.ModelForm):
    scheduled_at = forms.DateTimeField(input_formats=["%Y-%m-%dT%H:%M"], widget=forms.DateTimeInput(attrs={"type":"datetime-local", "step": "900"}, format="%Y-%m-%dT%H:%M"))
    class Meta:
        model = Appointment
        fields = ["doctor", "scheduled_at", "reason"]
        widgets = {"reason": forms.TextInput(attrs={"placeholder":"Brief reason for appointment", "maxlength":"240"})}
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["doctor"].queryset = DoctorProfile.objects.filter(available=True, user__is_active=True).select_related("user")
        self.fields["doctor"].label_from_instance = lambda d: f"Dr. {d.user.display_name} — {d.specialty}"
    def clean_scheduled_at(self):
        value = self.cleaned_data["scheduled_at"]
        if timezone.is_naive(value): value = timezone.make_aware(value, timezone.get_current_timezone())
        if value <= timezone.now(): raise forms.ValidationError("Choose a future date and time.")
        if value.second or value.microsecond:
            raise forms.ValidationError("Choose a time without seconds.")
        return value

class DoctorCreateForm(forms.Form):
    username = forms.CharField(max_length=150)
    first_name = forms.CharField(max_length=150)
    last_name = forms.CharField(max_length=150, required=False)
    email = forms.EmailField()
    phone = forms.CharField(max_length=25, required=False)
    password = forms.CharField(widget=forms.PasswordInput, min_length=8, help_text="At least 8 characters.")
    specialty = forms.CharField(max_length=120)
    qualification = forms.CharField(max_length=160, required=False)
    consultation_fee = forms.DecimalField(max_digits=9, decimal_places=2, min_value=0, initial=0)
    bio = forms.CharField(widget=forms.Textarea(attrs={"rows":3}), required=False)
    weekdays = forms.MultipleChoiceField(choices=DoctorAvailability.WEEKDAYS, widget=forms.CheckboxSelectMultiple, help_text="Select the days this doctor accepts appointments.")
    start_time = forms.TimeField(widget=forms.TimeInput(attrs={"type":"time"}, format="%H:%M"), input_formats=["%H:%M"])
    end_time = forms.TimeField(widget=forms.TimeInput(attrs={"type":"time"}, format="%H:%M"), input_formats=["%H:%M"])
    slot_minutes = forms.ChoiceField(choices=[("15","15 minutes"),("30","30 minutes"),("45","45 minutes"),("60","60 minutes")], initial="30")
    def clean_username(self):
        value=self.cleaned_data["username"]
        if User.objects.filter(username__iexact=value).exists(): raise forms.ValidationError("That username is already taken.")
        return value
    def clean_email(self):
        value=self.cleaned_data["email"]
        if User.objects.filter(email__iexact=value).exists(): raise forms.ValidationError("An account with this email already exists.")
        return value
    def clean(self):
        data=super().clean()
        if data.get("start_time") and data.get("end_time") and data["end_time"] <= data["start_time"]:
            self.add_error("end_time", "End time must be later than start time.")
        if data.get("weekdays") and not data["weekdays"]: self.add_error("weekdays", "Choose at least one working day.")
        return data

class DoctorScheduleForm(forms.Form):
    weekdays = forms.MultipleChoiceField(choices=DoctorAvailability.WEEKDAYS, widget=forms.CheckboxSelectMultiple)
    start_time = forms.TimeField(widget=forms.TimeInput(attrs={"type":"time"}, format="%H:%M"), input_formats=["%H:%M"])
    end_time = forms.TimeField(widget=forms.TimeInput(attrs={"type":"time"}, format="%H:%M"), input_formats=["%H:%M"])
    slot_minutes = forms.ChoiceField(choices=[("15","15 minutes"),("30","30 minutes"),("45","45 minutes"),("60","60 minutes")], initial="30")
    def clean(self):
        data=super().clean()
        if data.get("start_time") and data.get("end_time") and data["end_time"] <= data["start_time"]: self.add_error("end_time", "End time must be later than start time.")
        return data

class MedicalRecordForm(forms.ModelForm):
    class Meta:
        model = MedicalRecord
        fields = ["patient", "appointment", "diagnosis", "symptoms", "clinical_notes", "treatment_plan"]
        widgets = {"symptoms":forms.Textarea(attrs={"rows":2}), "clinical_notes":forms.Textarea(attrs={"rows":4}), "treatment_plan":forms.Textarea(attrs={"rows":3})}
    def __init__(self, *args, doctor=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["patient"].queryset = User.objects.filter(role=User.Role.PATIENT)
        self.fields["appointment"].required = False
        self.fields["appointment"].queryset = Appointment.objects.select_related("patient", "doctor").filter(status__in=[Appointment.Status.CONFIRMED, Appointment.Status.COMPLETED])
        if doctor:
            self.fields["appointment"].queryset = self.fields["appointment"].queryset.filter(doctor=doctor)

class PrescriptionForm(forms.ModelForm):
    class Meta:
        model = Prescription
        fields = ["medication", "dosage", "frequency", "duration", "instructions"]
        widgets = {"instructions":forms.Textarea(attrs={"rows":2})}
