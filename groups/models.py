import secrets
import string

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


JOIN_CODE_ALPHABET = string.ascii_uppercase + string.digits


def generate_join_code():
    return "".join(secrets.choice(JOIN_CODE_ALPHABET) for _ in range(6))


def generate_invite_token():
    return secrets.token_urlsafe(32)


class FriendGroup(models.Model):
    name = models.CharField(max_length=120, blank=True)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="owned_groups", on_delete=models.CASCADE)
    includes_ukraine = models.BooleanField(default=True)
    join_code = models.CharField(max_length=6, unique=True, editable=False)
    invite_token = models.CharField(max_length=64, unique=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "name"]

    def __str__(self):
        return self.display_name

    @property
    def display_name(self):
        return self.name or f"Група {self.owner.username}"

    @property
    def mode_label(self):
        return "з Україною" if self.includes_ukraine else "без України"

    def clean(self):
        super().clean()
        self.join_code = (self.join_code or "").upper()

    def save(self, *args, **kwargs):
        if not self.name:
            self.name = f"Група {self.owner.username}"
        if self.join_code:
            self.join_code = self.join_code.upper()
        else:
            self.join_code = self._new_unique_join_code()
        if not self.invite_token:
            self.invite_token = self._new_unique_invite_token()
        self.full_clean()
        return super().save(*args, **kwargs)

    def rotate_invite_credentials(self):
        self.join_code = self._new_unique_join_code()
        self.invite_token = self._new_unique_invite_token()
        self.save(update_fields=["join_code", "invite_token", "updated_at"])

    @classmethod
    def _new_unique_join_code(cls):
        for _ in range(20):
            code = generate_join_code()
            if not cls.objects.filter(join_code=code).exists():
                return code
        raise ValidationError("Could not generate a unique join code.")

    @classmethod
    def _new_unique_invite_token(cls):
        for _ in range(20):
            token = generate_invite_token()
            if not cls.objects.filter(invite_token=token).exists():
                return token
        raise ValidationError("Could not generate a unique invite token.")


class GroupMembership(models.Model):
    group = models.ForeignKey(FriendGroup, related_name="memberships", on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="group_memberships", on_delete=models.CASCADE)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["joined_at"]
        constraints = [
            models.UniqueConstraint(fields=["group", "user"], name="unique_group_membership"),
        ]

    def __str__(self):
        return f"{self.user} in {self.group}"
