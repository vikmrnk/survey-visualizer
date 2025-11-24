from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    class Role(models.TextChoices):
        STUDENT = 'student', 'Student'
        TEACHER = 'teacher', 'Teacher'
        ADMIN = 'admin', 'Admin'

    role = models.CharField(max_length=20, choices=Role.choices, default=Role.STUDENT)
    faculty = models.CharField(max_length=255, blank=True)
    academic_group = models.CharField(max_length=255, blank=True)

    def __str__(self) -> str:
        return f'{self.get_full_name() or self.username} ({self.role})'
