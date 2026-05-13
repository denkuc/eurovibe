from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone

from contest.models import ContestEdition, ContestEntry


ALLOWED_POINTS = (1, 2, 3, 4, 5, 6, 7, 8, 10, 12)
REQUIRED_BALLOT_ITEMS = 10


class Ballot(models.Model):
    MODE_WITH_UKRAINE = "with_ukraine"
    MODE_WITHOUT_UKRAINE = "without_ukraine"

    MODE_CHOICES = [
        (MODE_WITH_UKRAINE, "With Ukraine"),
        (MODE_WITHOUT_UKRAINE, "Without Ukraine"),
    ]

    edition = models.ForeignKey(ContestEdition, related_name="ballots", on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="ballots", on_delete=models.CASCADE)
    mode = models.CharField(max_length=32, choices=MODE_CHOICES)
    submitted_at = models.DateTimeField(default=timezone.now)
    immutable = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-submitted_at", "-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["edition", "user", "mode"], name="unique_ballot_per_user_mode"),
        ]

    def __str__(self):
        return f"{self.user} {self.edition.year} {self.mode}"

    @property
    def is_complete(self):
        return self.items.count() == REQUIRED_BALLOT_ITEMS

    def clean(self):
        super().clean()
        if self.mode not in {self.MODE_WITH_UKRAINE, self.MODE_WITHOUT_UKRAINE}:
            raise ValidationError({"mode": "Unknown voting mode."})


class BallotItem(models.Model):
    ballot = models.ForeignKey(Ballot, related_name="items", on_delete=models.CASCADE)
    points = models.PositiveSmallIntegerField()
    contest_entry = models.ForeignKey(ContestEntry, related_name="ballot_items", on_delete=models.CASCADE)

    class Meta:
        ordering = ["-points"]
        constraints = [
            models.UniqueConstraint(fields=["ballot", "points"], name="unique_points_per_ballot"),
            models.UniqueConstraint(fields=["ballot", "contest_entry"], name="unique_entry_per_ballot"),
            models.CheckConstraint(
                check=Q(points__in=ALLOWED_POINTS),
                name="ballot_item_allowed_points",
            ),
        ]

    def __str__(self):
        return f"{self.ballot}: {self.points} -> {self.contest_entry}"

    def clean(self):
        super().clean()
        if self.points not in ALLOWED_POINTS:
            raise ValidationError({"points": "Unsupported points value."})
        if self.ballot_id and self.contest_entry_id:
            if self.contest_entry.edition_id != self.ballot.edition_id:
                raise ValidationError({"contest_entry": "Entry must belong to the ballot edition."})
            if self.ballot.mode == Ballot.MODE_WITHOUT_UKRAINE and self.contest_entry.is_ukraine:
                raise ValidationError({"contest_entry": "Ukraine cannot receive points in without_ukraine mode."})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)
