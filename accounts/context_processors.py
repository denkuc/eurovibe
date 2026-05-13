from .roles import is_superadmin


def account_roles(request):
    return {
        "current_user_is_superadmin": is_superadmin(request.user),
    }

