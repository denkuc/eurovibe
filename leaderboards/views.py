from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import render

from contest.models import ContestEdition
from contest.services import get_current_edition
from groups.models import FriendGroup
from groups.services import get_member_group_or_404
from voting.models import Ballot

from .services import (
    get_global_country_leaderboard,
    get_global_user_leaderboard,
    get_group_country_leaderboard,
    get_group_user_leaderboard,
)


def global_country_leaderboard(request, mode=Ballot.MODE_WITH_UKRAINE):
    if mode not in {Ballot.MODE_WITH_UKRAINE, Ballot.MODE_WITHOUT_UKRAINE}:
        raise Http404("Unknown leaderboard mode.")

    edition = get_current_edition()
    rows = get_global_country_leaderboard(edition=edition, mode=mode)
    return render(
        request,
        "leaderboards/country_leaderboard.html",
        {
            "edition": edition,
            "leaderboard_tabs": _leaderboard_tabs(request.user),
            "mode": mode,
            "rows": rows,
            "scope": "global",
            "scope_label": "Глобально",
            "mode_label": _mode_label(mode),
            "poll_seconds": 12,
        },
    )


@login_required
def group_country_leaderboard(request, group_id):
    group = get_member_group_or_404(group_id=group_id, user=request.user)
    edition = get_current_edition()
    rows = get_group_country_leaderboard(edition=edition, group=group)
    mode = Ballot.MODE_WITH_UKRAINE if group.includes_ukraine else Ballot.MODE_WITHOUT_UKRAINE
    return render(
        request,
        "leaderboards/country_leaderboard.html",
        {
            "edition": edition,
            "group": group,
            "leaderboard_tabs": _leaderboard_tabs(request.user),
            "rows": rows,
            "scope": "group",
            "scope_label": group.display_name,
            "mode": mode,
            "mode_label": group.mode_label,
            "poll_seconds": 12,
        },
    )


def global_user_leaderboard(request, mode=Ballot.MODE_WITH_UKRAINE):
    if mode not in {Ballot.MODE_WITH_UKRAINE, Ballot.MODE_WITHOUT_UKRAINE}:
        raise Http404("Unknown leaderboard mode.")

    edition = get_current_edition()
    _require_scores_published(edition)
    rows = get_global_user_leaderboard(edition=edition, mode=mode)
    return render(
        request,
        "leaderboards/user_leaderboard.html",
        {
            "edition": edition,
            "leaderboard_tabs": _leaderboard_tabs(request.user),
            "mode": mode,
            "mode_label": _mode_label(mode),
            "rows": rows,
            "scope": "global_users",
            "scope_label": "Користувачі",
        },
    )


@login_required
def group_user_leaderboard(request, group_id):
    group = get_member_group_or_404(group_id=group_id, user=request.user)
    edition = get_current_edition()
    _require_scores_published(edition)
    rows = get_group_user_leaderboard(edition=edition, group=group)
    mode = Ballot.MODE_WITH_UKRAINE if group.includes_ukraine else Ballot.MODE_WITHOUT_UKRAINE
    return render(
        request,
        "leaderboards/user_leaderboard.html",
        {
            "edition": edition,
            "group": group,
            "leaderboard_tabs": _leaderboard_tabs(request.user),
            "mode": mode,
            "mode_label": group.mode_label,
            "rows": rows,
            "scope": "group_users",
            "scope_label": f"{group.display_name}: користувачі",
        },
    )


def _leaderboard_tabs(user):
    tabs = [
        {"scope": "global", "mode": Ballot.MODE_WITH_UKRAINE, "label": "Глобально з Україною"},
        {"scope": "global", "mode": Ballot.MODE_WITHOUT_UKRAINE, "label": "Глобально без України"},
    ]
    if not user.is_authenticated:
        return tabs

    groups = (
        FriendGroup.objects.filter(memberships__user=user)
        .select_related("owner")
        .order_by("name", "id")
        .distinct()
    )
    tabs.extend({"scope": "group", "group": group, "label": group.display_name} for group in groups)
    return tabs


def _require_scores_published(edition):
    if edition is None or edition.state != ContestEdition.STATE_SCORES_PUBLISHED:
        raise Http404("User leaderboard is available only after scores are published.")


def _mode_label(mode):
    if mode == Ballot.MODE_WITHOUT_UKRAINE:
        return "без України"
    return "з Україною"
