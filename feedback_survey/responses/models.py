from django.conf import settings
from django.db import models


class ResponseSession(models.Model):
    class Status(models.TextChoices):
        IN_PROGRESS = 'in_progress', 'In progress'
        COMPLETED = 'completed', 'Completed'
        ABANDONED = 'abandoned', 'Abandoned'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='response_sessions',
    )
    survey = models.ForeignKey(
        'surveys.Survey',
        on_delete=models.CASCADE,
        related_name='response_sessions',
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.IN_PROGRESS)
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ('user', 'survey', 'started_at')

    def __str__(self) -> str:
        return f'Session #{self.pk} — {self.user} / {self.survey}'


class Answer(models.Model):
    response_session = models.ForeignKey(
        ResponseSession,
        on_delete=models.CASCADE,
        related_name='answers',
    )
    question = models.ForeignKey(
        'surveys.Question',
        on_delete=models.CASCADE,
        related_name='answers',
    )
    selected_choice = models.ForeignKey(
        'surveys.Choice',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='answers',
    )
    text_answer = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['question', 'pk']

    def __str__(self) -> str:
        return f'Answer #{self.pk} to {self.question}'
