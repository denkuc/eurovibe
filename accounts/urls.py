from django.urls import path

from . import views


app_name = "accounts"

urlpatterns = [
    path("register/", views.register, name="register"),
    path("login/", views.login_view, name="login"),
    path("feedback/", views.feedback, name="feedback"),
    path("logout/", views.logout_view, name="logout"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("superadmin/", views.superadmin_dashboard, name="superadmin_dashboard"),
]
