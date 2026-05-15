from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.http import HttpResponseForbidden
from django.shortcuts import redirect, render

from accounts.models import FeedbackMessage
from accounts.roles import is_superadmin
from contest.models import ContestEdition
from groups.models import FriendGroup, GroupMembership
from contest.services import (
    get_current_edition,
    parse_official_results_csv,
    save_official_results,
    seed_finalists,
)
from voting.models import Ballot, UserScore
from voting.services import calculate_user_scores, publish_user_scores

from .forms import EditionForm, OfficialResultsForm, create_edition
from .models import AdminAuditLog


@login_required
def dashboard(request):
    if not is_superadmin(request.user):
        return HttpResponseForbidden("Forbidden")

    edition = get_current_edition()
    official_preview = None

    if request.method == "POST":
        action = request.POST.get("action")
        try:
            if action == "create_edition":
                form = EditionForm(request.POST)
                if form.is_valid():
                    edition = create_edition(form.cleaned_data["year"])
                    finalists_count = seed_finalists(edition=edition)
                    _audit(
                        request,
                        "create_edition",
                        {"edition_id": edition.id, "year": edition.year, "finalists_count": finalists_count},
                    )
                    messages.success(request, f"Edition {edition.year} готовий. Фіналістів синхронізовано: {finalists_count}.")
                else:
                    _form_errors(request, form)
            elif action == "open_voting":
                edition = _require_edition(edition)
                edition.open_voting()
                edition.save(update_fields=["state", "voting_open_at", "updated_at"])
                _audit(request, "open_voting", {"edition_id": edition.id})
                messages.success(request, "Голосування відкрито.")
            elif action == "close_voting":
                edition = _require_edition(edition)
                edition.close_voting()
                edition.save(update_fields=["state", "voting_closed_at", "updated_at"])
                _audit(request, "close_voting", {"edition_id": edition.id})
                messages.success(request, "Голосування закрито.")
            elif action == "preview_official_results":
                edition = _require_edition(edition)
                rankings = parse_official_results_csv(edition=edition, text=request.POST.get("results_csv", ""))
                entries = {entry.id: entry for entry in edition.entries.all()}
                official_preview = [
                    {
                        "rank": result["final_rank"],
                        "entry": entries[result["entry_id"]],
                        "jury_points": result["jury_points"],
                        "televote_points": result["televote_points"],
                        "total_points": result["total_points"],
                    }
                    for result in sorted(rankings, key=lambda item: item["final_rank"])
                ]
                messages.success(request, "Офіційний порядок валідний. Перевір preview і збережи.")
            elif action == "save_official_results":
                edition = _require_edition(edition)
                rankings = parse_official_results_csv(edition=edition, text=request.POST.get("results_csv", ""))
                count = save_official_results(edition=edition, rankings=rankings)
                _audit(request, "save_official_results", {"edition_id": edition.id, "count": count})
                messages.success(request, f"Офіційний порядок збережено: {count} позицій.")
            elif action == "calculate_scores":
                edition = _require_edition(edition)
                count = calculate_user_scores(edition=edition)
                _audit(request, "calculate_scores", {"edition_id": edition.id, "count": count})
                messages.success(request, f"Перераховано score для бюлетенів: {count}.")
            elif action == "publish_scores":
                edition = _require_edition(edition)
                publish_user_scores(edition=edition)
                _audit(request, "publish_scores", {"edition_id": edition.id})
                messages.success(request, "Рейтинги користувачів опубліковано.")
            else:
                messages.error(request, "Невідома дія.")
        except ValidationError as exc:
            for error in _validation_messages(exc):
                messages.error(request, error)

        if action != "preview_official_results":
            return redirect("admin_panel:dashboard")

    edition = get_current_edition()
    submitted_ballots = Ballot.objects.filter(immutable=True, submitted_at__isnull=False)
    if edition:
        edition_submitted_ballots = submitted_ballots.filter(edition=edition)
    else:
        edition_submitted_ballots = submitted_ballots.none()
    feedback_page = Paginator(FeedbackMessage.objects.select_related("user"), 8).get_page(
        request.GET.get("feedback_page")
    )

    context = {
        "audit_logs": AdminAuditLog.objects.select_related("actor")[:12],
        "ballot_count": edition_submitted_ballots.count(),
        "edition": edition,
        "edition_form": EditionForm(),
        "entries": edition.entries.order_by("running_order") if edition else [],
        "feedback_page": feedback_page,
        "official_form": OfficialResultsForm(edition=edition),
        "official_preview": official_preview,
        "score_count": UserScore.objects.filter(edition=edition).count() if edition else 0,
        "stats": {
            "registered_users": get_user_model().objects.count(),
            "submitted_voters": submitted_ballots.values("user_id").distinct().count(),
            "edition_submitted_voters": edition_submitted_ballots.values("user_id").distinct().count(),
            "groups": FriendGroup.objects.count(),
            "memberships": GroupMembership.objects.count(),
            "feedback_messages": feedback_page.paginator.count,
        },
    }
    return render(request, "admin_panel/dashboard.html", context)


def _audit(request, action, metadata):
    AdminAuditLog.objects.create(actor=request.user, action=action, metadata=metadata)


def _form_errors(request, form):
    for field, errors in form.errors.items():
        for error in errors:
            messages.error(request, f"{field}: {error}")


def _require_edition(edition):
    if edition is None:
        raise ValidationError("Спочатку створи edition.")
    return edition


def _validation_messages(error):
    if hasattr(error, "messages"):
        return error.messages
    return [str(error)]
