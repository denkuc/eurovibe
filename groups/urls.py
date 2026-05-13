from django.urls import path

from . import views


app_name = "groups"

urlpatterns = [
    path("", views.group_list, name="list"),
    path("new/", views.group_create, name="create"),
    path("join/", views.join_by_code, name="join_by_code"),
    path("invite/<str:invite_token>/", views.join_by_invite, name="join_by_invite"),
    path("<int:group_id>/", views.group_detail, name="detail"),
    path("<int:group_id>/remove-member/<int:user_id>/", views.remove_member, name="remove_member"),
    path("<int:group_id>/rotate-invite/", views.rotate_invite, name="rotate_invite"),
    path("<int:group_id>/mode/", views.update_mode, name="update_mode"),
]
