from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme

from .forms import LoginForm, RegisterForm
from .roles import is_superadmin


def _safe_next_url(request, fallback):
    next_url = request.POST.get("next") or request.GET.get("next")
    if next_url and url_has_allowed_host_and_scheme(
        next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return next_url
    return fallback


def register(request):
    if request.user.is_authenticated:
        return redirect("accounts:dashboard")

    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect(_safe_next_url(request, reverse("accounts:dashboard")))
    else:
        form = RegisterForm()

    return render(
        request,
        "accounts/register.html",
        {
            "form": form,
            "next": request.POST.get("next") or request.GET.get("next", ""),
        },
    )


def login_view(request):
    if request.user.is_authenticated:
        return redirect(_safe_next_url(request, reverse("accounts:dashboard")))

    if request.method == "POST":
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            login(request, form.get_user())
            return redirect(_safe_next_url(request, reverse("accounts:dashboard")))
    else:
        form = LoginForm(request)

    return render(
        request,
        "accounts/login.html",
        {
            "form": form,
            "next": request.POST.get("next") or request.GET.get("next", ""),
        },
    )


@login_required
def logout_view(request):
    if request.method == "POST":
        logout(request)
        return redirect("home")
    return redirect("accounts:dashboard")


@login_required
def dashboard(request):
    return render(
        request,
        "accounts/dashboard.html",
        {
            "is_superadmin": is_superadmin(request.user),
        },
    )


@login_required
def superadmin_dashboard(request):
    if not is_superadmin(request.user):
        return HttpResponseForbidden("Forbidden")
    return render(request, "accounts/superadmin_dashboard.html")
