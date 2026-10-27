from datetime import timedelta, datetime
from django.contrib import messages
from django.contrib.auth import login
from django.db import transaction
from django.db.models import Q
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from .decorators import roles_required
from .forms import PatientRegistrationForm, PatientProfileForm, AppointmentForm, DoctorCreateForm, DoctorScheduleForm, MedicalRecordForm, PrescriptionForm
from .models import User, DoctorProfile, DoctorAvailability, PatientProfile, Appointment, MedicalRecord, Notification

def notify_user(recipient, title, message, appointment=None):
    if recipient:
        Notification.objects.create(recipient=recipient, title=title, message=message, appointment=appointment)

def notify_appointment_parties(appointment, title, message):
    notify_user(appointment.patient, title, message, appointment)
    notify_user(appointment.doctor.user, title, message, appointment)
    for admin_user in User.objects.filter(Q(is_superuser=True) | Q(role=User.Role.ADMIN), is_active=True).exclude(pk__in=[appointment.patient_id, appointment.doctor.user_id]):
        notify_user(admin_user, title, message, appointment)

def active_appointments():
    return Appointment.objects.filter(status__in=[Appointment.Status.REQUESTED, Appointment.Status.CONFIRMED])

def appointment_conflict(doctor, patient, start, duration_minutes, exclude_pk=None):
    end = start + timedelta(minutes=duration_minutes)
    qs = active_appointments().filter(scheduled_at__lt=end, scheduled_at__gt=start - timedelta(days=1))
    if exclude_pk: qs = qs.exclude(pk=exclude_pk)
    doctor_conflict = qs.filter(doctor=doctor).filter(scheduled_at__lt=end).filter(scheduled_at__gte=start - timedelta(minutes=24*60))
    for existing in doctor_conflict:
        existing_end = existing.scheduled_at + timedelta(minutes=existing.duration_minutes)
        if existing.scheduled_at < end and existing_end > start:
            return "This doctor already has an overlapping appointment. Please choose another slot."
    patient_conflict = qs.filter(patient=patient)
    for existing in patient_conflict:
        existing_end = existing.scheduled_at + timedelta(minutes=existing.duration_minutes)
        if existing.scheduled_at < end and existing_end > start:
            return "You already have an overlapping appointment. Please choose another time."
    return None

def validate_doctor_slot(doctor, start):
    local_start = timezone.localtime(start)
    chosen = local_start.replace(tzinfo=None)
    windows = DoctorAvailability.objects.filter(doctor=doctor, weekday=local_start.weekday(), is_active=True)
    for window in windows:
        slot_start = datetime.combine(local_start.date(), window.start_time)
        slot_end = datetime.combine(local_start.date(), window.end_time)
        duration = window.slot_minutes
        end = chosen + timedelta(minutes=duration)
        if chosen >= slot_start and end <= slot_end:
            elapsed = int((chosen - slot_start).total_seconds() // 60)
            if elapsed % duration == 0:
                return duration
    return "That time is outside the doctor's published schedule or is not aligned to an available slot. Choose a published slot."


def home(request):
    if request.user.is_authenticated: return redirect("dashboard")
    return render(request, "core/home.html")

def register(request):
    if request.user.is_authenticated: return redirect("dashboard")
    form = PatientRegistrationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save(); login(request, user); messages.success(request, "Your patient account has been created."); return redirect("dashboard")
    return render(request, "core/form_page.html", {"form":form,"title":"Create patient account","subtitle":"Join ME-PHYSI to manage appointments and view your records.","button_label":"Create account"})

@login_required
def dashboard(request):
    user=request.user
    if user.is_superuser or user.role == User.Role.ADMIN:
        context={"patient_count":User.objects.filter(role="patient").count(),"doctor_count":DoctorProfile.objects.count(),"appointment_count":Appointment.objects.count(),"upcoming":Appointment.objects.filter(scheduled_at__gte=timezone.now()).exclude(status="cancelled").select_related("patient","doctor__user")[:8],"dashboard_role":"Administrator"}
    elif user.role == User.Role.DOCTOR:
        profile=DoctorProfile.objects.filter(user=user).first()
        appointments=Appointment.objects.filter(doctor=profile).select_related("patient").exclude(status="cancelled") if profile else Appointment.objects.none()
        context={"appointment_count":appointments.count(),"upcoming":appointments.filter(scheduled_at__gte=timezone.now())[:8],"dashboard_role":"Doctor","doctor_profile":profile}
    else:
        appointments=Appointment.objects.filter(patient=user).select_related("doctor__user").exclude(status="cancelled")
        context={"appointment_count":appointments.count(),"upcoming":appointments.filter(scheduled_at__gte=timezone.now())[:8],"record_count":MedicalRecord.objects.filter(patient=user).count(),"dashboard_role":"Patient"}
    return render(request,"core/dashboard.html",context)

@login_required
def profile(request):
    if request.user.role == User.Role.DOCTOR:
        messages.info(request,"Contact an administrator to update your professional profile.")
        return redirect("dashboard")
    patient, _ = PatientProfile.objects.get_or_create(user=request.user)
    form=PatientProfileForm(request.POST or None, instance=patient)
    if request.method=="POST" and form.is_valid(): form.save(); messages.success(request,"Profile updated."); return redirect("profile")
    return render(request,"core/form_page.html",{"form":form,"title":"My patient profile","subtitle":"Keep your information up to date.","button_label":"Save profile"})

@login_required
def doctors(request):
    query=request.GET.get("q","").strip()
    items=DoctorProfile.objects.select_related("user").filter(available=True)
    if query: items=items.filter(Q(user__first_name__icontains=query)|Q(user__last_name__icontains=query)|Q(specialty__icontains=query))
    return render(request,"core/doctors.html",{"doctors":items,"query":query})

@roles_required("admin")
def add_doctor(request):
    form = DoctorCreateForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            data = form.cleaned_data
            user = User.objects.create_user(username=data["username"], password=data["password"], first_name=data["first_name"], last_name=data.get("last_name", ""), email=data["email"], phone=data.get("phone", ""), role=User.Role.DOCTOR)
            profile = DoctorProfile.objects.create(user=user, specialty=data["specialty"], qualification=data.get("qualification", ""), consultation_fee=data["consultation_fee"], bio=data.get("bio", ""), available=True)
            for weekday in data["weekdays"]:
                DoctorAvailability.objects.create(doctor=profile, weekday=int(weekday), start_time=data["start_time"], end_time=data["end_time"], slot_minutes=int(data["slot_minutes"]))
            notify_user(user, "ME-PHYSI doctor account created", "Your doctor account has been created. Sign in with the username and password provided by the administrator.")
        messages.success(request, f"Doctor account and schedule created for Dr. {user.display_name}.")
        return redirect("doctors")
    return render(request, "core/form_page.html", {"form": form, "title": "Add a doctor", "subtitle": "Create a doctor login and publish their weekly appointment hours.", "button_label": "Create doctor and schedule"})

@roles_required("admin")
def manage_doctor_schedule(request, pk):
    doctor = get_object_or_404(DoctorProfile.objects.select_related("user"), pk=pk)
    form = DoctorScheduleForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        data=form.cleaned_data
        overlap_days=[]
        for weekday in data["weekdays"]:
            for existing in doctor.availability_windows.filter(weekday=int(weekday), is_active=True):
                if existing.start_time < data["end_time"] and existing.end_time > data["start_time"]:
                    overlap_days.append(existing.get_weekday_display())
                    break
        if overlap_days:
            form.add_error(None, "This window overlaps existing active hours on: " + ", ".join(sorted(set(overlap_days))) + ". Pause or adjust the existing window first.")
        else:
            with transaction.atomic():
                for weekday in data["weekdays"]:
                    DoctorAvailability.objects.get_or_create(doctor=doctor, weekday=int(weekday), start_time=data["start_time"], end_time=data["end_time"], defaults={"slot_minutes": int(data["slot_minutes"]), "is_active": True})
            messages.success(request, "Weekly schedule window added.")
            return redirect("manage_doctor_schedule", pk=doctor.pk)
    return render(request, "core/schedule.html", {"doctor":doctor, "form":form, "windows":doctor.availability_windows.all()})

@roles_required("admin")
def toggle_schedule_window(request, pk):
    if request.method != "POST": return redirect("doctors")
    window=get_object_or_404(DoctorAvailability.objects.select_related("doctor"), pk=pk)
    if not window.is_active:
        overlap=DoctorAvailability.objects.filter(doctor=window.doctor, weekday=window.weekday, is_active=True).exclude(pk=window.pk).filter(start_time__lt=window.end_time, end_time__gt=window.start_time).exists()
        if overlap:
            messages.error(request, "This window overlaps another active window. Resolve the overlap before activating it.")
            return redirect("manage_doctor_schedule", pk=window.doctor_id)
    window.is_active=not window.is_active
    window.save(update_fields=["is_active"])
    messages.success(request, "Schedule window updated. Existing appointments are not automatically changed; contact affected patients if hours need to change.")
    return redirect("manage_doctor_schedule", pk=window.doctor_id)

@login_required
def notifications(request):
    items=request.user.notifications.select_related("appointment")
    if request.method == "POST":
        ids=list(items.filter(read_at__isnull=True).values_list("id", flat=True))
        Notification.objects.filter(id__in=ids).update(read_at=timezone.now())
        messages.success(request, "Notifications marked as read.")
        return redirect("notifications")
    return render(request, "core/notifications.html", {"notifications":items, "unread_count":items.filter(read_at__isnull=True).count()})

@login_required
def patients(request):
    if not (request.user.is_superuser or request.user.role in [User.Role.ADMIN,User.Role.DOCTOR]): return HttpResponseForbidden("Only authorized staff can view the patient directory.")
    query=request.GET.get("q","").strip()
    items=User.objects.filter(role=User.Role.PATIENT).select_related("patient_profile")
    if query: items=items.filter(Q(first_name__icontains=query)|Q(last_name__icontains=query)|Q(username__icontains=query)|Q(email__icontains=query))
    return render(request,"core/patients.html",{"patients":items,"query":query})

@login_required
def book_appointment(request):
    if request.user.role != User.Role.PATIENT:
        return HttpResponseForbidden("Only patient accounts can request appointments.")
    form=AppointmentForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        appointment=form.save(commit=False)
        appointment.patient=request.user
        with transaction.atomic():
            doctor=DoctorProfile.objects.select_for_update().select_related("user").filter(pk=appointment.doctor_id, available=True, user__is_active=True).first()
            # Serialize bookings for this patient too, including bookings with different doctors.
            User.objects.select_for_update().get(pk=request.user.pk)
            if not doctor:
                form.add_error("doctor", "This doctor is no longer accepting appointments.")
            else:
                slot_result=validate_doctor_slot(doctor, appointment.scheduled_at)
                if isinstance(slot_result, str):
                    form.add_error("scheduled_at", slot_result)
                else:
                    appointment.duration_minutes=slot_result
                    conflict=appointment_conflict(doctor, request.user, appointment.scheduled_at, appointment.duration_minutes)
                    if conflict:
                        form.add_error("scheduled_at", conflict)
                    else:
                        appointment.doctor=doctor
                        appointment.save()
                        notify_user(doctor.user, "New appointment request", f"{request.user.display_name} requested an appointment for {timezone.localtime(appointment.scheduled_at):%d %b %Y at %H:%M}. Please accept or decline it.", appointment)
                        for admin_user in User.objects.filter(Q(is_superuser=True) | Q(role=User.Role.ADMIN), is_active=True):
                            notify_user(admin_user, "Appointment request received", f"A new appointment request was submitted for Dr. {doctor.user.display_name}.", appointment)
                        notify_user(request.user, "Appointment request submitted", f"Your request for {timezone.localtime(appointment.scheduled_at):%d %b %Y at %H:%M} has been sent to Dr. {doctor.user.display_name}. It is not confirmed until the doctor accepts it.", appointment)
                        messages.success(request, "Request submitted. You will receive a notification when the doctor responds.")
                        return redirect("appointments")
    schedule_doctors=DoctorProfile.objects.filter(available=True, user__is_active=True).prefetch_related("availability_windows", "user")
    return render(request,"core/form_page.html",{"form":form,"title":"Request an appointment","subtitle":"Choose a published doctor slot. Your appointment remains pending until the doctor accepts it.","button_label":"Send appointment request", "schedule_doctors":schedule_doctors})

@login_required
def appointments(request):
    user=request.user
    if user.is_superuser or user.role==User.Role.ADMIN: items=Appointment.objects.all()
    elif user.role==User.Role.DOCTOR:
        doctor=DoctorProfile.objects.filter(user=user).first(); items=Appointment.objects.filter(doctor=doctor) if doctor else Appointment.objects.none()
    else: items=Appointment.objects.filter(patient=user)
    items=items.select_related("patient","doctor__user")
    return render(request,"core/appointments.html",{"appointments":items})

@login_required
def update_appointment_status(request, pk):
    if request.method != "POST": return redirect("appointments")
    with transaction.atomic():
        appt=get_object_or_404(Appointment.objects.select_for_update().select_related("doctor__user", "patient"), pk=pk)
        is_admin=request.user.is_superuser or request.user.role == User.Role.ADMIN
        is_own_doctor=request.user.role == User.Role.DOCTOR and appt.doctor.user_id == request.user.id
        if not (is_admin or is_own_doctor): return HttpResponseForbidden("Only the assigned doctor or an administrator can process this appointment.")
        action=request.POST.get("action", "")
        transitions={
            "accept": (Appointment.Status.REQUESTED, Appointment.Status.CONFIRMED),
            "reject": (Appointment.Status.REQUESTED, Appointment.Status.REJECTED),
            "complete": (Appointment.Status.CONFIRMED, Appointment.Status.COMPLETED),
            "cancel": ((Appointment.Status.REQUESTED, Appointment.Status.CONFIRMED), Appointment.Status.CANCELLED),
        }
        if action not in transitions:
            messages.error(request, "Unknown appointment action.")
        else:
            expected, new_status=transitions[action]
            allowed_current=expected if isinstance(expected, tuple) else (expected,)
            if appt.status not in allowed_current:
                messages.error(request, f"This appointment cannot be {action}ed from its current status ({appt.get_status_display()}).")
            elif action == "accept" and appt.scheduled_at <= timezone.now():
                messages.error(request, "A past appointment cannot be confirmed. Contact the clinic if this request is still valid.")
            elif action == "complete" and appt.scheduled_at > timezone.now():
                messages.error(request, "An appointment cannot be marked completed before its scheduled time.")
            elif action == "accept":
                conflict=appointment_conflict(appt.doctor, appt.patient, appt.scheduled_at, appt.duration_minutes, exclude_pk=appt.pk)
                if conflict:
                    appt.status=Appointment.Status.REJECTED
                    appt.save(update_fields=["status", "updated_at"])
                    notify_appointment_parties(appt, "Appointment could not be confirmed", "The requested slot conflicts with another booking and could not be confirmed. Please request a different time.")
                    messages.error(request, "This slot conflicts with another booking, so it could not be confirmed.")
                else:
                    appt.status=new_status; appt.save(update_fields=["status", "updated_at"])
                    notify_appointment_parties(appt, "Appointment confirmed", f"Dr. {appt.doctor.user.display_name} accepted the appointment for {timezone.localtime(appt.scheduled_at):%d %b %Y at %H:%M}.")
                    messages.success(request, "Appointment confirmed and both parties notified.")
            else:
                appt.status=new_status; appt.save(update_fields=["status", "updated_at"])
                titles={"reject":"Appointment declined", "complete":"Appointment completed", "cancel":"Appointment cancelled"}
                descriptions={"reject":f"Dr. {appt.doctor.user.display_name} declined the appointment. Please request another slot if needed.", "complete":"The appointment has been marked as completed.", "cancel":"The appointment has been cancelled."}
                notify_appointment_parties(appt, titles[action], descriptions[action])
                action_labels={"reject":"declined", "complete":"marked completed", "cancel":"cancelled"}
                messages.success(request, f"Appointment {action_labels[action]} and notifications sent.")
    return redirect("appointments")

@login_required
def cancel_patient_appointment(request, pk):
    if request.method != "POST": return redirect("appointments")
    with transaction.atomic():
        appt=get_object_or_404(Appointment.objects.select_for_update().select_related("doctor__user", "patient"), pk=pk, patient=request.user)
        if request.user.role != User.Role.PATIENT: return HttpResponseForbidden("Only the patient who requested the appointment can cancel it here.")
        if appt.status not in (Appointment.Status.REQUESTED, Appointment.Status.CONFIRMED):
            messages.error(request, "Only pending or confirmed appointments can be cancelled.")
        elif appt.scheduled_at <= timezone.now():
            messages.error(request, "Past appointments cannot be cancelled through the portal. Contact the clinic if this is an error.")
        else:
            appt.status=Appointment.Status.CANCELLED; appt.save(update_fields=["status", "updated_at"])
            notify_appointment_parties(appt, "Appointment cancelled by patient", f"{appt.patient.display_name} cancelled the appointment scheduled for {timezone.localtime(appt.scheduled_at):%d %b %Y at %H:%M}.")
            messages.success(request, "Appointment cancelled. The doctor and clinic have been notified.")
    return redirect("appointments")

@roles_required("doctor","admin")
def records(request):
    if request.user.role=="doctor" and not request.user.is_superuser:
        doctor=DoctorProfile.objects.filter(user=request.user).first(); items=MedicalRecord.objects.filter(doctor=doctor) if doctor else MedicalRecord.objects.none()
    else: items=MedicalRecord.objects.all()
    return render(request,"core/records.html",{"records":items.select_related("patient","doctor__user")})

@roles_required("doctor","admin")
def create_record(request):
    doctor=DoctorProfile.objects.filter(user=request.user).first() if request.user.role=="doctor" else None
    form=MedicalRecordForm(request.POST or None,doctor=doctor)
    if request.method=="POST" and form.is_valid():
        record=form.save(commit=False)
        if doctor: record.doctor=doctor
        else:
            selected=record.appointment.doctor if record.appointment else None
            if selected is None: form.add_error("appointment","For an administrator-created record, select an appointment so the treating doctor can be assigned.")
            else: record.doctor=selected
        if record.doctor: record.save(); messages.success(request,"Medical record created."); return redirect("records")
    return render(request,"core/form_page.html",{"form":form,"title":"Create medical record","subtitle":"Enter accurate clinical information. Only record information obtained through appropriate clinical care.","button_label":"Save medical record"})

@login_required
def record_detail(request, pk):
    record=get_object_or_404(MedicalRecord.objects.select_related("patient","doctor__user").prefetch_related("prescriptions"),pk=pk)
    allowed=request.user.is_superuser or request.user.role=="admin" or record.patient_id==request.user.id or (request.user.role=="doctor" and record.doctor.user_id==request.user.id)
    if not allowed: return HttpResponseForbidden("You do not have permission to view this medical record.")
    return render(request,"core/record_detail.html",{"record":record,"prescription_form":PrescriptionForm() if request.user.role=="doctor" and record.doctor.user_id==request.user.id else None})

@login_required
def add_prescription(request, pk):
    if request.method!="POST": return redirect("record_detail",pk=pk)
    record=get_object_or_404(MedicalRecord.objects.select_related("doctor__user"),pk=pk)
    if request.user.role!="doctor" or record.doctor.user_id!=request.user.id: return HttpResponseForbidden("Only the treating doctor can add a prescription.")
    form=PrescriptionForm(request.POST)
    if form.is_valid(): item=form.save(commit=False); item.record=record; item.save(); messages.success(request,"Prescription added.")
    else: messages.error(request,"Please check the prescription details and try again.")
    return redirect("record_detail",pk=pk)
