from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import HttpResponseForbidden, HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from contest.services import get_current_edition
from voting.models import Ballot

from .forms import FriendGroupCreateForm, GroupSettingsForm, JoinByCodeForm
from .models import FriendGroup
from .services import (
    create_group,
    get_member_group_or_404,
    join_group,
    remove_member as remove_member_service,
    group_has_submitted_ballots,
    update_group_settings,
)


@login_required
def group_list(request):
    groups = (
        FriendGroup.objects.filter(memberships__user=request.user)
        .select_related("owner")
        .prefetch_related("memberships")
        .distinct()
    )
    return render(request, "groups/list.html", {"groups": groups})


@login_required
def group_create(request):
    if request.method == "POST":
        form = FriendGroupCreateForm(request.POST)
        if form.is_valid():
            group = create_group(
                owner=request.user,
                name=form.cleaned_data["name"],
                includes_ukraine=form.cleaned_data["includes_ukraine"],
            )
            messages.success(request, "Групу створено.")
            return redirect("groups:detail", group_id=group.id)
    else:
        form = FriendGroupCreateForm()
    return render(request, "groups/create.html", {"form": form})


@login_required
def group_detail(request, group_id):
    group = get_member_group_or_404(group_id=group_id, user=request.user)
    invite_url = request.build_absolute_uri(reverse("groups:join_by_invite", args=[group.invite_token]))
    memberships = list(group.memberships.select_related("user"))
    edition = get_current_edition()
    voted_user_ids = set()
    draft_user_ids = set()
    if edition:
        mode = Ballot.MODE_WITH_UKRAINE if group.includes_ukraine else Ballot.MODE_WITHOUT_UKRAINE
        member_user_ids = [membership.user_id for membership in memberships]
        voted_user_ids = set(
            Ballot.objects.filter(
                edition=edition,
                mode=mode,
                user_id__in=member_user_ids,
                immutable=True,
                submitted_at__isnull=False,
            ).values_list("user_id", flat=True),
        )
        draft_user_ids = set(
            Ballot.objects.filter(
                edition=edition,
                mode=mode,
                user_id__in=member_user_ids,
                immutable=False,
            ).values_list("user_id", flat=True),
        )
    for membership in memberships:
        membership.has_voted = membership.user_id in voted_user_ids
        membership.has_draft = membership.user_id in draft_user_ids

    settings_form = GroupSettingsForm(instance=group)
    can_edit_mode = not group_has_submitted_ballots(group)
    if not can_edit_mode:
        settings_form.fields["includes_ukraine"].disabled = True
    return render(
        request,
        "groups/detail.html",
        {
            "group": group,
            "memberships": memberships,
            "invite_url": invite_url,
            "settings_form": settings_form,
            "is_owner": group.owner_id == request.user.id,
            "can_edit_mode": can_edit_mode,
        },
    )


@login_required
def join_by_code(request):
    if request.method == "POST":
        form = JoinByCodeForm(request.POST)
        if form.is_valid():
            group = get_object_or_404(FriendGroup, join_code=form.cleaned_data["join_code"])
            join_group(group=group, user=request.user)
            return redirect("groups:detail", group_id=group.id)
    else:
        form = JoinByCodeForm()
    return render(request, "groups/join.html", {"form": form})


def join_by_invite(request, invite_token):
    group = get_object_or_404(FriendGroup, invite_token=invite_token)
    if not request.user.is_authenticated:
        request.session["pending_group_invite_token"] = invite_token
        login_url = reverse("accounts:login")
        return redirect(f"{login_url}?{urlencode({'next': request.get_full_path()})}")

    join_group(group=group, user=request.user)
    return redirect("groups:detail", group_id=group.id)


@login_required
def remove_member(request, group_id, user_id):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    group = get_member_group_or_404(group_id=group_id, user=request.user)
    try:
        remove_member_service(group=group, owner=request.user, user_id=user_id)
        messages.success(request, "Учасника видалено.")
    except PermissionDenied as exc:
        return HttpResponseForbidden(str(exc))
    except ValidationError as exc:
        messages.error(request, exc.message)
    return redirect("groups:detail", group_id=group.id)


@login_required
def rotate_invite(request, group_id):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    group = get_member_group_or_404(group_id=group_id, user=request.user)
    if group.owner_id != request.user.id:
        return HttpResponseForbidden("Only the group owner can refresh invite credentials.")
    group.rotate_invite_credentials()
    messages.success(request, "Код і лінк оновлено.")
    return redirect("groups:detail", group_id=group.id)


@login_required
def update_settings(request, group_id):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    group = get_member_group_or_404(group_id=group_id, user=request.user)
    form = GroupSettingsForm(request.POST, instance=group)
    if group_has_submitted_ballots(group):
        form.fields["includes_ukraine"].disabled = True
    if form.is_valid():
        try:
            update_group_settings(
                group=group,
                owner=request.user,
                name=form.cleaned_data["name"],
                includes_ukraine=form.cleaned_data["includes_ukraine"],
            )
            messages.success(request, "Налаштування групи оновлено.")
        except PermissionDenied as exc:
            return HttpResponseForbidden(str(exc))
        except ValidationError as exc:
            messages.error(request, exc.message)
    return redirect("groups:detail", group_id=group.id)


update_mode = update_settings
