from .roles import is_superadmin


def account_roles(request):
    voting_is_available = False
    if request.user.is_authenticated:
        from contest.services import get_current_edition
        from voting.services import get_available_voting_modes

        edition = get_current_edition()
        voting_is_available = bool(edition and edition.can_vote and get_available_voting_modes(request.user, edition))

    return {
        "current_user_is_superadmin": is_superadmin(request.user),
        "current_user_can_vote": voting_is_available,
    }
