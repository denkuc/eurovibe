from dataclasses import dataclass

from django.core.cache import cache
from django.db.models import Count, Q, Sum

from contest.models import ContestEdition
from voting.models import Ballot, BallotItem, UserScore


GLOBAL_COUNTRY_LEADERBOARD_TTL = 12


@dataclass(frozen=True)
class CountryLeaderboardRow:
    contest_entry_id: int
    country_name: str
    country_code: str
    artist_name: str
    song_title: str
    is_ukraine: bool
    total_points: int
    number_of_voters: int
    count_12: int
    count_10: int
    count_8: int


@dataclass(frozen=True)
class UserLeaderboardRow:
    user_id: int
    username: str
    mode: str
    total_score: int
    exact_hits: int
    top10_hits_wrong_place: int


def get_global_country_leaderboard(*, edition, mode=Ballot.MODE_WITH_UKRAINE):
    if edition is None or mode not in _valid_modes():
        return []

    cache_key = _global_cache_key(edition, mode)
    rows = cache.get(cache_key)
    if rows is None:
        rows = _build_country_leaderboard(edition=edition, mode=mode)
        cache.set(cache_key, rows, GLOBAL_COUNTRY_LEADERBOARD_TTL)
    return rows


def get_group_country_leaderboard(*, edition, group):
    if edition is None or group is None:
        return []

    mode = Ballot.MODE_WITH_UKRAINE if group.includes_ukraine else Ballot.MODE_WITHOUT_UKRAINE
    member_ids = group.memberships.values_list("user_id", flat=True)
    return _build_country_leaderboard(edition=edition, mode=mode, user_ids=member_ids)


def get_global_user_leaderboard(*, edition, mode):
    if edition is None or not _can_show_user_scores(edition) or mode not in _valid_modes():
        return []

    return _build_user_leaderboard(edition=edition, mode=mode)


def get_group_user_leaderboard(*, edition, group):
    if edition is None or group is None or not _can_show_user_scores(edition):
        return []

    mode = Ballot.MODE_WITH_UKRAINE if group.includes_ukraine else Ballot.MODE_WITHOUT_UKRAINE
    member_ids = group.memberships.values_list("user_id", flat=True)
    return _build_user_leaderboard(edition=edition, mode=mode, user_ids=member_ids)


def _build_country_leaderboard(*, edition, mode=None, user_ids=None):
    entries = list(
        edition.entries.order_by("country_name").values(
            "id",
            "country_name",
            "country_code",
            "artist_name",
            "song_title",
            "is_ukraine",
        )
    )
    if not entries:
        return []

    item_filters = Q(ballot__edition=edition, ballot__immutable=True, ballot__submitted_at__isnull=False)
    if mode:
        item_filters &= Q(ballot__mode=mode)
    if user_ids is not None:
        item_filters &= Q(ballot__user_id__in=user_ids)

    totals = {
        row["contest_entry_id"]: row
        for row in BallotItem.objects.filter(item_filters)
        .values("contest_entry_id")
        .annotate(
            total_points=Sum("points"),
            number_of_voters=Count("ballot__user_id", distinct=True),
            count_12=Count("id", filter=Q(points=12)),
            count_10=Count("id", filter=Q(points=10)),
            count_8=Count("id", filter=Q(points=8)),
        )
    }

    rows = []
    for entry in entries:
        stats = totals.get(entry["id"], {})
        rows.append(
            CountryLeaderboardRow(
                contest_entry_id=entry["id"],
                country_name=entry["country_name"],
                country_code=entry["country_code"],
                artist_name=entry["artist_name"],
                song_title=entry["song_title"],
                is_ukraine=entry["is_ukraine"],
                total_points=stats.get("total_points") or 0,
                number_of_voters=stats.get("number_of_voters") or 0,
                count_12=stats.get("count_12") or 0,
                count_10=stats.get("count_10") or 0,
                count_8=stats.get("count_8") or 0,
            )
        )

    return sorted(
        rows,
        key=lambda row: (
            mode == Ballot.MODE_WITHOUT_UKRAINE and not row.is_ukraine,
            -row.total_points,
            -row.number_of_voters,
            -row.count_12,
            -row.count_10,
            -row.count_8,
            row.country_name,
        ),
    )


def _global_cache_key(edition: ContestEdition, mode):
    items = BallotItem.objects.filter(
        ballot__edition=edition,
        ballot__mode=mode,
        ballot__immutable=True,
        ballot__submitted_at__isnull=False,
    )
    latest_item_id = items.order_by("-id").values_list("id", flat=True).first() or 0
    return f"leaderboards:country:global:{edition.id}:{mode}:{items.count()}:{latest_item_id}"


def _build_user_leaderboard(*, edition, mode, user_ids=None):
    score_filters = Q(edition=edition, mode=mode)
    if user_ids is not None:
        score_filters &= Q(user_id__in=user_ids)

    scores = (
        UserScore.objects.filter(score_filters)
        .select_related("user")
        .order_by("-total_score", "-exact_hits", "-top10_hits_wrong_place", "user__username")
    )
    return [
        UserLeaderboardRow(
            user_id=score.user_id,
            username=score.user.username,
            mode=score.mode,
            total_score=score.total_score,
            exact_hits=score.exact_hits,
            top10_hits_wrong_place=score.top10_hits_wrong_place,
        )
        for score in scores
    ]


def _can_show_user_scores(edition):
    return edition.state == ContestEdition.STATE_SCORES_PUBLISHED


def _valid_modes():
    return {Ballot.MODE_WITH_UKRAINE, Ballot.MODE_WITHOUT_UKRAINE}
