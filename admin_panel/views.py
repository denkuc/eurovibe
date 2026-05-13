from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import HttpResponseForbidden
from django.shortcuts import redirect, render

from accounts.roles import is_superadmin
from contest.models import ContestEdition
from contest.services import (
    get_current_edition,
    parse_official_results_csv,
    replace_finalists_from_csv,
    save_official_results,
)
from voting.models import Ballot, UserScore
from voting.services import calculate_user_scores, publish_user_scores

from .forms import EditionForm, FinalistImportForm, OfficialResultsForm, create_edition
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
                    _audit(request, "create_edition", {"edition_id": edition.id, "year": edition.year})
                    messages.success(request, f"Edition {edition.year} готовий.")
                else:
                    _form_errors(request, form)
            elif action == "import_finalists":
                edition = _require_edition(edition)
                count = replace_finalists_from_csv(edition=edition, text=request.POST.get("finalists_csv", ""))
                _audit(request, "import_finalists", {"edition_id": edition.id, "count": count})
                messages.success(request, f"Імпортовано фіналістів: {count}.")
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
                official_preview = [(rank, entries[entry_id]) for rank, entry_id in sorted(rankings)]
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
    context = {
        "audit_logs": AdminAuditLog.objects.select_related("actor")[:12],
        "ballot_count": Ballot.objects.filter(edition=edition).count() if edition else 0,
        "edition": edition,
        "edition_form": EditionForm(),
        "entries": edition.entries.order_by("running_order") if edition else [],
        "finalist_form": FinalistImportForm(),
        "official_form": OfficialResultsForm(edition=edition),
        "official_preview": official_preview,
        "score_count": UserScore.objects.filter(edition=edition).count() if edition else 0,
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
