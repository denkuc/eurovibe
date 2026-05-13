from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme

from groups.models import FriendGroup
from groups.services import join_group

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


def _redirect_after_auth(request, fallback):
    invite_token = request.session.pop("pending_group_invite_token", "")
    if invite_token:
        try:
            group = FriendGroup.objects.get(invite_token=invite_token)
        except FriendGroup.DoesNotExist:
            pass
        else:
            join_group(group=group, user=request.user)
            return redirect("groups:detail", group_id=group.id)
    return redirect(_safe_next_url(request, fallback))


def register(request):
    if request.user.is_authenticated:
        return redirect("groups:list")

    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return _redirect_after_auth(request, reverse("groups:list"))
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
        return redirect(_safe_next_url(request, reverse("groups:list")))

    if request.method == "POST":
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            login(request, form.get_user())
            return _redirect_after_auth(request, reverse("groups:list"))
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
    return redirect("admin_panel:dashboard")
