from .models import ContestEdition


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

