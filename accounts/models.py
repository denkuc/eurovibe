from django.conf import settings
from django.db import models


class FeedbackMessage(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="feedback_messages",
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
    )
    name = models.CharField(max_length=120, blank=True)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        author = self.user.username if self.user_id else self.name or "Anonymous"
        return f"{author} · {self.created_at:%Y-%m-%d %H:%M}"
