from dataclasses import dataclass

from django.core.cache import cache
from django.db.models import Count, Q, Sum

from contest.models import ContestEdition
from voting.models import Ballot, BallotItem


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


def get_global_country_leaderboard(*, edition):
    if edition is None:
        return []

    cache_key = _global_cache_key(edition)
    rows = cache.get(cache_key)
    if rows is None:
        rows = _build_country_leaderboard(edition=edition)
        cache.set(cache_key, rows, GLOBAL_COUNTRY_LEADERBOARD_TTL)
    return rows


def get_group_country_leaderboard(*, edition, group):
    if edition is None or group is None:
        return []

    mode = Ballot.MODE_WITH_UKRAINE if group.includes_ukraine else Ballot.MODE_WITHOUT_UKRAINE
    member_ids = group.memberships.values_list("user_id", flat=True)
    return _build_country_leaderboard(edition=edition, mode=mode, user_ids=member_ids)


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

    item_filters = Q(ballot__edition=edition)
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
            -row.total_points,
            -row.number_of_voters,
            -row.count_12,
            -row.count_10,
            -row.count_8,
            row.country_name,
        ),
    )


def _global_cache_key(edition: ContestEdition):
    items = BallotItem.objects.filter(ballot__edition=edition)
    latest_item_id = items.order_by("-id").values_list("id", flat=True).first() or 0
    return f"leaderboards:country:global:{edition.id}:{items.count()}:{latest_item_id}"
