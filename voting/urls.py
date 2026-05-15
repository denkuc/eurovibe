from django.urls import path

from . import views

app_name = "voting"

urlpatterns = [
    path("", views.voting_home, name="index"),
    path("groups/<int:group_id>/members/<int:user_id>/ballot/", views.group_member_ballot, name="group_member_ballot"),
]
