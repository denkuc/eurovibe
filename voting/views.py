from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from contest.services import get_current_edition
from groups.services import get_member_group_or_404

from .models import ALLOWED_POINTS, Ballot
from .services import get_available_voting_modes, save_ballot_draft, submit_ballot


@login_required
def voting_home(request):
    edition = get_current_edition()
    modes = get_available_voting_modes(request.user, edition)
    selected_mode = _selected_mode(request, modes)
    existing_ballot = None
    draft_ballot = None
    ballot_items = []
    entries = []

    if edition:
        entries = list(edition.entries.all())

    if selected_mode and edition:
        current_ballot = (
            Ballot.objects.filter(edition=edition, user=request.user, mode=selected_mode)
            .prefetch_related("items__contest_entry")
            .first()
        )
        if current_ballot:
            if current_ballot.is_submitted:
                existing_ballot = current_ballot
            else:
                draft_ballot = current_ballot
            ballot_items = list(current_ballot.items.select_related("contest_entry"))

    if request.method == "POST":
        mode = request.POST.get("mode")
        action = request.POST.get("action", "submit")
        if mode not in modes:
            messages.error(request, "Цей режим голосування тобі недоступний.")
            return redirect("voting:index")

        try:
            service = save_ballot_draft if action == "save_draft" else submit_ballot
            ballot = service(
                user=request.user,
                edition=edition,
                mode=mode,
                assignments=_assignments_from_post(request.POST),
            )
        except ValidationError as exc:
            for error in _validation_messages(exc):
                messages.error(request, error)
            return redirect(f"{reverse('voting:index')}?mode={mode}")

        if action == "save_draft":
            messages.success(request, "Чернетку збережено.")
        else:
            messages.success(request, "Голосування підтверджено. Бюлетень більше не можна змінити.")
        return redirect(f"{reverse('voting:index')}?mode={ballot.mode}")

    return render(
        request,
        "voting/voting_home.html",
        {
            "allowed_points": ALLOWED_POINTS,
            "ballot_items": ballot_items,
            "edition": edition,
            "entries": _ordered_entries(entries, selected_mode),
            "draft_ballot": draft_ballot,
            "existing_ballot": existing_ballot,
            "modes": modes,
            "selected_mode": selected_mode,
        },
    )


@login_required
def group_member_ballot(request, group_id, user_id):
    group = get_member_group_or_404(group_id=group_id, user=request.user)
    edition = get_current_edition()
    mode = Ballot.MODE_WITH_UKRAINE if group.includes_ukraine else Ballot.MODE_WITHOUT_UKRAINE
    member = get_object_or_404(group.memberships.select_related("user"), user_id=user_id)
    ballot = get_object_or_404(
        Ballot.objects.select_related("user", "edition").prefetch_related("items__contest_entry"),
        edition=edition,
        user=member.user,
        mode=mode,
        immutable=True,
        submitted_at__isnull=False,
    )
    return render(
        request,
        "voting/group_member_ballot.html",
        {
            "ballot": ballot,
            "ballot_items": list(ballot.items.select_related("contest_entry")),
            "group": group,
            "mode": mode,
        },
    )


def _ordered_entries(entries, selected_mode):
    if selected_mode == Ballot.MODE_WITHOUT_UKRAINE:
        return sorted(entries, key=lambda entry: (not entry.is_ukraine, entry.running_order))
    return entries


def _selected_mode(request, modes):
    requested_mode = request.POST.get("mode") or request.GET.get("mode")
    if requested_mode in modes:
        return requested_mode
    return modes[0] if modes else None


def _assignments_from_post(post_data):
    assignments = []
    for points in ALLOWED_POINTS:
        entry_id = next((value for value in reversed(post_data.getlist(f"points_{points}")) if value), "")
        if entry_id:
            assignments.append((points, entry_id))
    return assignments


def _validation_messages(error):
    if hasattr(error, "messages"):
        return error.messages
    return [str(error)]
