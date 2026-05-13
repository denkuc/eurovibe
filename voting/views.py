from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.shortcuts import redirect, render
from django.urls import reverse

from contest.services import get_current_edition

from .models import ALLOWED_POINTS, Ballot
from .services import get_available_voting_modes, submit_ballot


@login_required
def voting_home(request):
    edition = get_current_edition()
    modes = get_available_voting_modes(request.user, edition)
    selected_mode = _selected_mode(request, modes)
    existing_ballot = None
    ballot_items = []
    entries = []

    if edition:
        entries = list(edition.entries.all())

    if selected_mode and edition:
        existing_ballot = (
            Ballot.objects.filter(edition=edition, user=request.user, mode=selected_mode)
            .prefetch_related("items__contest_entry")
            .first()
        )
        if existing_ballot:
            ballot_items = list(existing_ballot.items.select_related("contest_entry"))

    if request.method == "POST":
        mode = request.POST.get("mode")
        if mode not in modes:
            messages.error(request, "Цей режим голосування тобі недоступний.")
            return redirect("voting:index")

        try:
            ballot = submit_ballot(
                user=request.user,
                edition=edition,
                mode=mode,
                assignments=_assignments_from_post(request.POST),
            )
        except ValidationError as exc:
            for error in _validation_messages(exc):
                messages.error(request, error)
            return redirect(f"{reverse('voting:index')}?mode={mode}")

        messages.success(request, "Голосування підтверджено. Бюлетень більше не можна змінити.")
        return redirect(f"{reverse('voting:index')}?mode={ballot.mode}")

    return render(
        request,
        "voting/voting_home.html",
        {
            "allowed_points": ALLOWED_POINTS,
            "ballot_items": ballot_items,
            "edition": edition,
            "entries": entries,
            "existing_ballot": existing_ballot,
            "modes": modes,
            "selected_mode": selected_mode,
        },
    )


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
