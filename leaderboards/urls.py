from django.urls import path

from . import views


app_name = "leaderboards"

urlpatterns = [
    path("countries/", views.global_country_leaderboard, name="global_countries"),
    path("groups/<int:group_id>/countries/", views.group_country_leaderboard, name="group_countries"),
]
