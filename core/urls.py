from django.contrib.auth import views as auth_views
from django.urls import path
from . import views
urlpatterns = [
    path("register/", views.register, name="register"),
    path("login/", auth_views.LoginView.as_view(template_name="core/login.html", redirect_authenticated_user=True), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("profile/", views.profile, name="profile"),
    path("doctors/", views.doctors, name="doctors"),
    path("doctors/add/", views.add_doctor, name="add_doctor"),
    path("doctors/<int:pk>/schedule/", views.manage_doctor_schedule, name="manage_doctor_schedule"),
    path("schedule-windows/<int:pk>/toggle/", views.toggle_schedule_window, name="toggle_schedule_window"),
    path("notifications/", views.notifications, name="notifications"),
    path("patients/", views.patients, name="patients"),
    path("appointments/", views.appointments, name="appointments"),
    path("appointments/book/", views.book_appointment, name="book_appointment"),
    path("appointments/<int:pk>/status/", views.update_appointment_status, name="update_appointment_status"),
    path("appointments/<int:pk>/cancel/", views.cancel_patient_appointment, name="cancel_patient_appointment"),
    path("records/", views.records, name="records"),
    path("records/create/", views.create_record, name="create_record"),
    path("records/<int:pk>/", views.record_detail, name="record_detail"),
    path("records/<int:pk>/prescriptions/add/", views.add_prescription, name="add_prescription"),
]
