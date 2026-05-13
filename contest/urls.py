from django.urls import path

from . import views

app_name = "contest"

urlpatterns = [
    path("finalists/", views.finalist_list, name="finalist_list"),
]

