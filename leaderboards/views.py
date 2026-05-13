from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from contest.services import get_current_edition
from groups.models import FriendGroup
from groups.services import get_member_group_or_404
from voting.models import Ballot

from .services import get_global_country_leaderboard, get_group_country_leaderboard


def global_country_leaderboard(request):
    edition = get_current_edition()
    rows = get_global_country_leaderboard(edition=edition)
    return render(
        request,
        "leaderboards/country_leaderboard.html",
        {
            "edition": edition,
            "leaderboard_tabs": _leaderboard_tabs(request.user),
            "rows": rows,
            "scope": "global",
            "scope_label": "Глобально",
            "mode_label": "усі бюлетені",
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


def _leaderboard_tabs(user):
    tabs = [{"scope": "global", "label": "Глобально", "url_name": "leaderboards:global_countries"}]
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
