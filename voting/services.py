from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from contest.models import ContestEntry
from groups.models import GroupMembership

from .models import ALLOWED_POINTS, REQUIRED_BALLOT_ITEMS, Ballot, BallotItem


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
            ballot = Ballot.objects.create(edition=edition, user=user, mode=mode, immutable=True)
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
    if Ballot.objects.filter(edition=edition, user=user, mode=mode).exists():
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
