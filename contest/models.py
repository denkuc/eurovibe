from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone


class ContestEdition(models.Model):
    STATE_SETUP = "setup"
    STATE_VOTING_OPEN = "voting_open"
    STATE_VOTING_CLOSED = "voting_closed"
    STATE_OFFICIAL_RESULTS_ENTERED = "official_results_entered"
    STATE_SCORES_PUBLISHED = "scores_published"

    STATE_CHOICES = [
        (STATE_SETUP, "Setup"),
        (STATE_VOTING_OPEN, "Voting open"),
        (STATE_VOTING_CLOSED, "Voting closed"),
        (STATE_OFFICIAL_RESULTS_ENTERED, "Official results entered"),
        (STATE_SCORES_PUBLISHED, "Scores published"),
    ]

    year = models.PositiveIntegerField(unique=True)
    state = models.CharField(max_length=32, choices=STATE_CHOICES, default=STATE_SETUP)
    voting_open_at = models.DateTimeField(blank=True, null=True)
    voting_closed_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-year"]

    def __str__(self):
        return f"{self.year} ({self.state})"

    @property
    def is_setup(self):
        return self.state == self.STATE_SETUP

    @property
    def is_voting_open(self):
        return self.state == self.STATE_VOTING_OPEN

    @property
    def is_voting_closed_or_later(self):
        return self.state in {
            self.STATE_VOTING_CLOSED,
            self.STATE_OFFICIAL_RESULTS_ENTERED,
            self.STATE_SCORES_PUBLISHED,
        }

    @property
    def can_edit_finalists(self):
        return self.is_setup

    @property
    def can_vote(self):
        return self.is_voting_open and self.entries.exists()

    @property
    def can_publish_scores(self):
        return self.state == self.STATE_OFFICIAL_RESULTS_ENTERED

    def open_voting(self):
        if not self.is_setup:
            raise ValidationError("Voting can only be opened from setup state.")
        if not self.entries.exists():
            raise ValidationError("Voting cannot be opened without finalists.")
        self.state = self.STATE_VOTING_OPEN
        self.voting_open_at = timezone.now()

    def close_voting(self):
        if not self.is_voting_open:
            raise ValidationError("Voting can only be closed from voting_open state.")
        self.state = self.STATE_VOTING_CLOSED
        self.voting_closed_at = timezone.now()


class ContestEntry(models.Model):
    edition = models.ForeignKey(ContestEdition, related_name="entries", on_delete=models.CASCADE)
    running_order = models.PositiveSmallIntegerField()
    country_name = models.CharField(max_length=120)
    country_code = models.CharField(max_length=3)
    artist_name = models.CharField(max_length=160)
    song_title = models.CharField(max_length=160)
    is_ukraine = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["edition__year", "running_order"]
        constraints = [
            models.UniqueConstraint(fields=["edition", "running_order"], name="unique_running_order_per_edition"),
            models.UniqueConstraint(
                fields=["edition"],
                condition=Q(is_ukraine=True),
                name="unique_ukraine_entry_per_edition",
            ),
        ]

    def __str__(self):
        return f"{self.running_order}. {self.country_name} - {self.artist_name}"

    def clean(self):
        super().clean()
        if self.edition_id and not self.edition.can_edit_finalists:
            raise ValidationError("Finalists cannot be edited after setup state.")
        if self.is_ukraine:
            duplicate = ContestEntry.objects.filter(edition=self.edition, is_ukraine=True)
            if self.pk:
                duplicate = duplicate.exclude(pk=self.pk)
            if duplicate.exists():
                raise ValidationError({"is_ukraine": "Only one Ukraine entry is allowed per edition."})

    def save(self, *args, **kwargs):
        self.country_code = self.country_code.upper()
        self.full_clean()
        return super().save(*args, **kwargs)

