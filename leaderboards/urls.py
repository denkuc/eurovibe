from django.urls import path

from . import views


app_name = "leaderboards"

urlpatterns = [
    path("countries/", views.global_country_leaderboard, name="global_countries"),
    path("countries/<str:mode>/", views.global_country_leaderboard, name="global_countries_by_mode"),
    path("users/", views.global_user_leaderboard, name="global_users"),
    path("users/<str:mode>/", views.global_user_leaderboard, name="global_users_by_mode"),
    path("groups/<int:group_id>/countries/", views.group_country_leaderboard, name="group_countries"),
    path("groups/<int:group_id>/users/", views.group_user_leaderboard, name="group_users"),
]
