def is_superadmin(user):
    if not getattr(user, "is_authenticated", False):
        return False
    return user.username == "denkuc" or user.is_staff or user.is_superuser

