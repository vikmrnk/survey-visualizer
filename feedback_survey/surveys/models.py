from django.conf import settings
from django.db import models


class Survey(models.Model):
    class Status(models.TextChoices):
        DRAFT = 'draft', 'Draft'
        PUBLISHED = 'published', 'Published'
        CLOSED = 'closed', 'Closed'

    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='surveys',
    )
    start_date = models.DateTimeField(null=True, blank=True)
    end_date = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    target = models.CharField(
        max_length=255,
        blank=True,
        help_text='Intended audience such as course, faculty, or group',
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f'{self.title} ({self.get_status_display()})'


class Question(models.Model):
    class QuestionType(models.TextChoices):
        SINGLE = 'single', 'Single choice'
        MULTIPLE = 'multiple', 'Multiple choice'
        SCALE = 'scale', 'Scale'
        TEXT = 'text', 'Free text'

    survey = models.ForeignKey(Survey, on_delete=models.CASCADE, related_name='questions')
    text = models.TextField()
    question_type = models.CharField(max_length=20, choices=QuestionType.choices)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order', 'id']

    def __str__(self) -> str:
        return f'{self.survey.title} — {self.text[:50]}'


class Choice(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='choices')
    text = models.CharField(max_length=255)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order', 'id']

    def __str__(self) -> str:
        return f'{self.question.text[:30]} → {self.text}'
