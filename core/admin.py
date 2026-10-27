from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, DoctorProfile, DoctorAvailability, PatientProfile, Appointment, MedicalRecord, Prescription, Notification

@admin.register(User)
class CustomUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (("ME-PHYSI", {"fields": ("role", "phone")}),)
    add_fieldsets = UserAdmin.add_fieldsets + (("ME-PHYSI", {"fields": ("role", "phone", "first_name", "last_name", "email")}),)
    list_display = ("username", "email", "first_name", "last_name", "role", "is_staff")
    list_filter = ("role", "is_staff", "is_active")

@admin.register(DoctorProfile)
class DoctorProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "specialty", "consultation_fee", "available")
    search_fields = ("user__first_name", "user__last_name", "specialty")

@admin.register(PatientProfile)
class PatientProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "date_of_birth", "sex", "blood_group")
    search_fields = ("user__username", "user__first_name", "user__last_name")

@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ("patient", "doctor", "scheduled_at", "status")
    list_filter = ("status", "scheduled_at")
    search_fields = ("patient__username", "doctor__user__username")

class PrescriptionInline(admin.TabularInline): model=Prescription; extra=0
@admin.register(MedicalRecord)
class MedicalRecordAdmin(admin.ModelAdmin):
    list_display = ("patient", "doctor", "diagnosis", "recorded_at")
    search_fields = ("patient__username", "diagnosis")
    inlines = [PrescriptionInline]
admin.site.register(Prescription)

@admin.register(DoctorAvailability)
class DoctorAvailabilityAdmin(admin.ModelAdmin):
    list_display = ("doctor", "weekday", "start_time", "end_time", "slot_minutes", "is_active")
    list_filter = ("weekday", "is_active", "slot_minutes")

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("recipient", "title", "created_at", "read_at")
    list_filter = ("created_at", "read_at")
    search_fields = ("recipient__username", "title", "message")
    readonly_fields = ("created_at",)
