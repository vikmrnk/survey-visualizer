"""
Test settings - використовує SQLite для швидких тестів
"""
from .settings import *

# Override database для тестів - використовуємо SQLite
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',  # In-memory database для швидкості
    }
}

# Вимкнути міграції для тестів (опційно, для швидкості)
# PASSWORD_HASHERS = [
#     'django.contrib.auth.hashers.MD5PasswordHasher',
# ]

