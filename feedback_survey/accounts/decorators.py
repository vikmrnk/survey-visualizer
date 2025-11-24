from functools import wraps

from django.contrib.auth import REDIRECT_FIELD_NAME, get_user_model
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied
from django.urls import reverse_lazy

User = get_user_model()


def role_required(role, login_url=None, redirect_field_name=REDIRECT_FIELD_NAME):
    login_url = login_url or reverse_lazy('accounts:login')

    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect_to_login(request.get_full_path(), login_url, redirect_field_name)
            if request.user.role != role:
                raise PermissionDenied
            return view_func(request, *args, **kwargs)

        return _wrapped_view

    return decorator


def teacher_required(view_func=None, **kwargs):
    decorator = role_required(User.Role.TEACHER, **kwargs)
    if view_func:
        return decorator(view_func)
    return decorator


def student_required(view_func=None, **kwargs):
    decorator = role_required(User.Role.STUDENT, **kwargs)
    if view_func:
        return decorator(view_func)
    return decorator
