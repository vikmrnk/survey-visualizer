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


class UserProfile(models.Model):
    """Профіль користувача для збереження налаштувань"""
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='profile',
        primary_key=True,
    )
    
    # Налаштування сповіщень
    notify_new_responses = models.BooleanField(default=True, verbose_name='Сповіщення про нові відповіді')
    notify_daily_summary = models.BooleanField(default=True, verbose_name='Щоденне резюме')
    notify_low_response = models.BooleanField(default=True, verbose_name='Сповіщення про низький рівень відповідей')
    notify_marketing = models.BooleanField(default=False, verbose_name='Маркетингові оновлення')
    
    # Налаштування конфіденційності
    visibility = models.CharField(
        max_length=20,
        choices=[
            ('private', 'Тільки я'),
            ('department', 'Члени кафедри'),
            ('university', 'Всі в університеті'),
        ],
        default='private',
        verbose_name='Видимість опитування',
    )
    
    retention = models.CharField(
        max_length=20,
        choices=[
            ('1y', '1 рік'),
            ('2y', '2 роки'),
            ('unlimited', 'Без обмежень'),
        ],
        default='1y',
        verbose_name='Збереження даних',
    )
    
    class Meta:
        verbose_name = 'Профіль користувача'
        verbose_name_plural = 'Профілі користувачів'
    
    def __str__(self) -> str:
        return f'Профіль {self.user.username}'
