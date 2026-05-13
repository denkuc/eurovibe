from django.contrib import admin
from django.http import HttpResponse
from django.shortcuts import render
from django.urls import include, path


def home(request):
    return render(request, "home.html")


def healthz(request):
    return HttpResponse("ok\n", content_type="text/plain")


urlpatterns = [
    path("", home, name="home"),
    path("accounts/", include("accounts.urls")),
    path("superadmin/", include("admin_panel.urls")),
    path("contest/", include("contest.urls")),
    path("groups/", include("groups.urls")),
    path("voting/", include("voting.urls")),
    path("healthz/", healthz, name="healthz"),
    path("admin/", admin.site.urls),
]
