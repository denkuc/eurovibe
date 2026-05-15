from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from contest.models import ContestEdition, ContestEntry
from groups.models import GroupMembership

from .models import ALLOWED_POINTS, REQUIRED_BALLOT_ITEMS, Ballot, BallotItem, UserScore


POINT_TO_PREDICTED_RANK = {
    12: 1,
    10: 2,
    8: 3,
    7: 4,
    6: 5,
    5: 6,
    4: 7,
    3: 8,
    2: 9,
    1: 10,
}


def get_available_voting_modes(user, edition):
    if not user or not user.is_authenticated or edition is None:
        return []

    memberships = GroupMembership.objects.filter(user=user)
    modes = []
    if memberships.filter(group__includes_ukraine=True).exists():
        modes.append(Ballot.MODE_WITH_UKRAINE)
    if memberships.filter(group__includes_ukraine=False).exists():
        modes.append(Ballot.MODE_WITHOUT_UKRAINE)
    return modes


def submit_ballot(*, user, edition, mode, assignments):
    normalized = _normalize_assignments(assignments)
    _validate_submission(user=user, edition=edition, mode=mode, normalized=normalized)

    try:
        with transaction.atomic():
            ballot, _created = Ballot.objects.select_for_update().get_or_create(
                edition=edition,
                user=user,
                mode=mode,
                defaults={"immutable": False},
            )
            if ballot.is_submitted:
                raise ValidationError("Ballot for this mode already exists.")
            ballot.items.all().delete()
            ballot.immutable = True
            ballot.submitted_at = timezone.now()
            ballot.save(update_fields=["immutable", "submitted_at"])
            items = [
                BallotItem(ballot=ballot, points=points, contest_entry_id=entry_id)
                for points, entry_id in normalized
            ]
            for item in items:
                item.full_clean()
            BallotItem.objects.bulk_create(items)
            return ballot
    except IntegrityError as exc:
        raise ValidationError("Ballot could not be submitted. It may already exist or contain duplicates.") from exc


def save_ballot_draft(*, user, edition, mode, assignments):
    normalized = _normalize_assignments(assignments)
    _validate_draft(user=user, edition=edition, mode=mode, normalized=normalized)

    try:
        with transaction.atomic():
            ballot, _created = Ballot.objects.select_for_update().get_or_create(
                edition=edition,
                user=user,
                mode=mode,
                defaults={"immutable": False},
            )
            if ballot.is_submitted:
                raise ValidationError("Confirmed ballots cannot be edited.")
            ballot.items.all().delete()
            ballot.immutable = False
            ballot.submitted_at = None
            ballot.save(update_fields=["immutable", "submitted_at"])
            items = [
                BallotItem(ballot=ballot, points=points, contest_entry_id=entry_id)
                for points, entry_id in normalized
            ]
            for item in items:
                item.full_clean()
            BallotItem.objects.bulk_create(items)
            return ballot
    except IntegrityError as exc:
        raise ValidationError("Draft could not be saved. It may contain duplicates.") from exc


@transaction.atomic
def calculate_user_scores(*, edition):
    if edition.state != ContestEdition.STATE_OFFICIAL_RESULTS_ENTERED:
        raise ValidationError("User scores can only be calculated after official results are entered.")
    if edition.official_results.count() != edition.entries.count():
        raise ValidationError("Official results must contain the full finalist order.")

    official_by_mode = {
        Ballot.MODE_WITH_UKRAINE: _official_top_by_mode(edition=edition, mode=Ballot.MODE_WITH_UKRAINE),
        Ballot.MODE_WITHOUT_UKRAINE: _official_top_by_mode(edition=edition, mode=Ballot.MODE_WITHOUT_UKRAINE),
    }
    calculated_at = timezone.now()
    count = 0

    for ballot in Ballot.objects.filter(edition=edition, immutable=True, submitted_at__isnull=False).prefetch_related("items"):
        official_top = official_by_mode[ballot.mode]
        exact_hits = 0
        wrong_place_hits = 0
        for item in ballot.items.all():
            predicted_rank = POINT_TO_PREDICTED_RANK[item.points]
            official_rank = official_top.get(item.contest_entry_id)
            if official_rank is None:
                continue
            if official_rank == predicted_rank:
                exact_hits += 1
            else:
                wrong_place_hits += 1

        UserScore.objects.update_or_create(
            edition=edition,
            user=ballot.user,
            mode=ballot.mode,
            defaults={
                "exact_hits": exact_hits,
                "top10_hits_wrong_place": wrong_place_hits,
                "total_score": exact_hits * 2 + wrong_place_hits,
                "calculated_at": calculated_at,
            },
        )
        count += 1

    return count


@transaction.atomic
def publish_user_scores(*, edition):
    if edition.state != ContestEdition.STATE_OFFICIAL_RESULTS_ENTERED:
        raise ValidationError("Scores can only be published after official results are entered.")
    if not UserScore.objects.filter(edition=edition).exists():
        raise ValidationError("Calculate user scores before publishing.")
    edition.state = ContestEdition.STATE_SCORES_PUBLISHED
    edition.save(update_fields=["state", "updated_at"])


def _normalize_assignments(assignments):
    if isinstance(assignments, dict):
        raw_pairs = list(assignments.items())
    else:
        raw_pairs = []
        for assignment in assignments or []:
            if isinstance(assignment, dict):
                raw_pairs.append((assignment.get("points"), assignment.get("contest_entry")))
            else:
                raw_pairs.append((assignment[0], assignment[1]))

    normalized = []
    errors = []
    for points, entry_id in raw_pairs:
        try:
            normalized.append((int(points), int(entry_id)))
        except (TypeError, ValueError):
            errors.append("Assignments must contain integer points and entry ids.")

    if errors:
        raise ValidationError(errors)
    return normalized


def _validate_submission(*, user, edition, mode, normalized):
    if not user or not user.is_authenticated:
        raise ValidationError("Authentication is required to submit a ballot.")
    if edition is None or not edition.can_vote:
        raise ValidationError("Voting is not open for this edition.")
    if mode not in {Ballot.MODE_WITH_UKRAINE, Ballot.MODE_WITHOUT_UKRAINE}:
        raise ValidationError("Unknown voting mode.")
    if mode not in get_available_voting_modes(user, edition):
        raise ValidationError("User does not have access to this voting mode.")
    if Ballot.objects.filter(edition=edition, user=user, mode=mode, immutable=True, submitted_at__isnull=False).exists():
        raise ValidationError("Ballot for this mode already exists.")
    if len(normalized) != REQUIRED_BALLOT_ITEMS:
        raise ValidationError(f"Ballot must contain exactly {REQUIRED_BALLOT_ITEMS} items.")

    points = [point for point, _entry_id in normalized]
    entry_ids = [entry_id for _point, entry_id in normalized]

    if set(points) != set(ALLOWED_POINTS) or len(points) != len(set(points)):
        raise ValidationError("Ballot must use each allowed points value exactly once.")
    if len(entry_ids) != len(set(entry_ids)):
        raise ValidationError("Ballot cannot contain duplicate entries.")

    entries = {
        entry.id: entry
        for entry in ContestEntry.objects.filter(id__in=entry_ids).only("id", "edition_id", "is_ukraine")
    }
    if len(entries) != len(entry_ids):
        raise ValidationError("Every ballot entry must exist.")
    if any(entry.edition_id != edition.id for entry in entries.values()):
        raise ValidationError("Every ballot entry must belong to the current edition.")
    if mode == Ballot.MODE_WITHOUT_UKRAINE and any(entry.is_ukraine for entry in entries.values()):
        raise ValidationError("Ukraine cannot receive points in without_ukraine mode.")


def _validate_draft(*, user, edition, mode, normalized):
    if not user or not user.is_authenticated:
        raise ValidationError("Authentication is required to save a draft.")
    if edition is None or not edition.can_vote:
        raise ValidationError("Voting is not open for this edition.")
    if mode not in {Ballot.MODE_WITH_UKRAINE, Ballot.MODE_WITHOUT_UKRAINE}:
        raise ValidationError("Unknown voting mode.")
    if mode not in get_available_voting_modes(user, edition):
        raise ValidationError("User does not have access to this voting mode.")

    points = [point for point, _entry_id in normalized]
    entry_ids = [entry_id for _point, entry_id in normalized]

    if any(point not in ALLOWED_POINTS for point in points) or len(points) != len(set(points)):
        raise ValidationError("Draft cannot contain duplicate or unsupported points.")
    if len(entry_ids) != len(set(entry_ids)):
        raise ValidationError("Draft cannot contain duplicate entries.")
    if not entry_ids:
        return

    entries = {
        entry.id: entry
        for entry in ContestEntry.objects.filter(id__in=entry_ids).only("id", "edition_id", "is_ukraine")
    }
    if len(entries) != len(entry_ids):
        raise ValidationError("Every draft entry must exist.")
    if any(entry.edition_id != edition.id for entry in entries.values()):
        raise ValidationError("Every draft entry must belong to the current edition.")
    if mode == Ballot.MODE_WITHOUT_UKRAINE and any(entry.is_ukraine for entry in entries.values()):
        raise ValidationError("Ukraine cannot receive points in without_ukraine mode.")


def _official_top_by_mode(*, edition, mode):
    results = list(edition.official_results.select_related("contest_entry").order_by("final_rank"))
    if mode == Ballot.MODE_WITHOUT_UKRAINE:
        results = [result for result in results if not result.contest_entry.is_ukraine]
    return {result.contest_entry_id: index for index, result in enumerate(results[:10], start=1)}
