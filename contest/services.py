import csv
from io import StringIO

from django.core.exceptions import ValidationError
from django.db import transaction

from .models import ContestEdition, ContestEntry, OfficialResult
from .seed_data import DEV_FINALISTS


def get_current_edition():
    return ContestEdition.objects.order_by("-year").first()


def is_setup(edition):
    return bool(edition and edition.is_setup)


def is_voting_open(edition):
    return bool(edition and edition.is_voting_open)


def is_voting_closed_or_later(edition):
    return bool(edition and edition.is_voting_closed_or_later)


def can_edit_finalists(edition):
    return bool(edition and edition.can_edit_finalists)


def can_vote(edition):
    return bool(edition and edition.can_vote)


def can_publish_scores(edition):
    return bool(edition and edition.can_publish_scores)


FINALIST_FIELDS = ("running_order", "country_code", "country_name", "artist_name", "song_title", "is_ukraine")


def parse_finalists_csv(text):
    reader = csv.DictReader(StringIO((text or "").strip()))
    if not reader.fieldnames:
        raise ValidationError("CSV must include a header row.")

    missing = [field for field in FINALIST_FIELDS[:-1] if field not in reader.fieldnames]
    if missing:
        raise ValidationError(f"Missing finalist columns: {', '.join(missing)}.")

    finalists = []
    for line_number, row in enumerate(reader, start=2):
        try:
            running_order = int((row.get("running_order") or "").strip())
        except ValueError as exc:
            raise ValidationError(f"Line {line_number}: running_order must be an integer.") from exc

        finalist = {
            "running_order": running_order,
            "country_code": (row.get("country_code") or "").strip().upper(),
            "country_name": (row.get("country_name") or "").strip(),
            "artist_name": (row.get("artist_name") or "").strip(),
            "song_title": (row.get("song_title") or "").strip(),
            "is_ukraine": _parse_bool(row.get("is_ukraine")),
        }
        empty_fields = [key for key, value in finalist.items() if key != "is_ukraine" and not value]
        if empty_fields:
            raise ValidationError(f"Line {line_number}: empty fields: {', '.join(empty_fields)}.")
        finalists.append(finalist)

    _validate_finalist_rows(finalists)
    return finalists


@transaction.atomic
def replace_finalists_from_csv(*, edition, text):
    if edition is None:
        raise ValidationError("Create an edition before importing finalists.")
    if not edition.can_edit_finalists:
        raise ValidationError("Finalists can only be imported in setup state.")

    finalists = parse_finalists_csv(text)
    edition.entries.all().delete()
    for finalist in finalists:
        ContestEntry.objects.create(edition=edition, **finalist)
    return len(finalists)


@transaction.atomic
def seed_finalists(*, edition):
    if edition is None:
        raise ValidationError("Create an edition before seeding finalists.")
    if not edition.can_edit_finalists:
        raise ValidationError("Finalists can only be seeded in setup state.")

    edition.entries.update(is_ukraine=False)
    for finalist in DEV_FINALISTS:
        ContestEntry.objects.update_or_create(
            edition=edition,
            running_order=finalist["running_order"],
            defaults={
                "country_name": finalist["country_name"],
                "country_code": finalist["country_code"],
                "artist_name": finalist["artist_name"],
                "song_title": finalist["song_title"],
                "is_ukraine": finalist.get("is_ukraine", False),
            },
        )
    return len(DEV_FINALISTS)


def parse_official_results_csv(*, edition, text):
    if edition is None:
        raise ValidationError("Create an edition before entering official results.")

    reader = csv.DictReader(StringIO((text or "").strip()))
    if not reader.fieldnames:
        raise ValidationError("CSV must include a header row.")
    if "final_rank" not in reader.fieldnames or "entry_id" not in reader.fieldnames:
        raise ValidationError("Official results CSV must include final_rank and entry_id columns.")

    results = []
    for line_number, row in enumerate(reader, start=2):
        try:
            final_rank = int(row["final_rank"])
            entry_id = int(row["entry_id"])
        except (TypeError, ValueError) as exc:
            raise ValidationError(f"Line {line_number}: final_rank and entry_id must be integers.") from exc
        try:
            jury_points = _parse_optional_int(row.get("jury_points"))
            televote_points = _parse_optional_int(row.get("televote_points"))
            total_points = _parse_optional_int(row.get("total_points"))
        except ValueError as exc:
            raise ValidationError(f"Line {line_number}: points columns must be integers.") from exc
        if total_points == 0 and (jury_points or televote_points):
            total_points = jury_points + televote_points
        results.append(
            {
                "final_rank": final_rank,
                "entry_id": entry_id,
                "jury_points": jury_points,
                "televote_points": televote_points,
                "total_points": total_points,
            }
        )

    validate_official_results(edition=edition, rankings=results)
    return results


def validate_official_results(*, edition, rankings):
    if edition.state not in {
        ContestEdition.STATE_VOTING_CLOSED,
        ContestEdition.STATE_OFFICIAL_RESULTS_ENTERED,
    }:
        raise ValidationError("Official results can only be entered after voting is closed and before scores are published.")

    entries = set(edition.entries.values_list("id", flat=True))
    ranks = [_result_value(result, "final_rank", 0) for result in rankings]
    entry_ids = [_result_value(result, "entry_id", 1) for result in rankings]

    expected_ranks = set(range(1, len(entries) + 1))
    if set(ranks) != expected_ranks or len(ranks) != len(set(ranks)):
        raise ValidationError("Official results must contain every rank from 1 to the number of finalists exactly once.")
    if set(entry_ids) != entries or len(entry_ids) != len(set(entry_ids)):
        raise ValidationError("Official results must contain every finalist from the current edition exactly once.")


@transaction.atomic
def save_official_results(*, edition, rankings):
    validate_official_results(edition=edition, rankings=rankings)
    edition.official_results.all().delete()
    OfficialResult.objects.bulk_create(
        [
            OfficialResult(
                edition=edition,
                final_rank=_result_value(result, "final_rank", 0),
                contest_entry_id=_result_value(result, "entry_id", 1),
                jury_points=_result_value(result, "jury_points", default=0),
                televote_points=_result_value(result, "televote_points", default=0),
                total_points=_result_value(result, "total_points", default=0),
            )
            for result in sorted(rankings, key=lambda item: _result_value(item, "final_rank", 0))
        ]
    )
    from voting.models import UserScore

    UserScore.objects.filter(edition=edition).delete()
    edition.state = ContestEdition.STATE_OFFICIAL_RESULTS_ENTERED
    edition.save(update_fields=["state", "updated_at"])
    return len(rankings)


def _validate_finalist_rows(finalists):
    if not finalists:
        raise ValidationError("CSV must contain at least one finalist.")
    running_orders = [row["running_order"] for row in finalists]
    if len(running_orders) != len(set(running_orders)):
        raise ValidationError("running_order values must be unique.")
    if sorted(running_orders) != list(range(1, len(finalists) + 1)):
        raise ValidationError("running_order values must be contiguous from 1.")
    if sum(1 for row in finalists if row["is_ukraine"]) > 1:
        raise ValidationError("Only one finalist can be marked as Ukraine.")


def _parse_bool(value):
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "так"}


def _parse_optional_int(value):
    if value is None or str(value).strip() == "":
        return 0
    return int(str(value).strip())


def _result_value(result, key, index=None, default=None):
    if isinstance(result, dict):
        return result.get(key, default)
    if index is None or index >= len(result):
        return default
    return result[index]
