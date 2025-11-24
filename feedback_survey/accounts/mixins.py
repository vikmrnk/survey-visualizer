from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin

User = get_user_model()


class RolesRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    allowed_roles: tuple[str, ...] = ()

    def test_func(self):
        return bool(self.allowed_roles and self.request.user.role in self.allowed_roles)


class TeacherRequiredMixin(RolesRequiredMixin):
    allowed_roles = (User.Role.TEACHER,)


class StudentRequiredMixin(RolesRequiredMixin):
    allowed_roles = (User.Role.STUDENT,)


class TeacherOrAdminRequiredMixin(RolesRequiredMixin):
    allowed_roles = (User.Role.TEACHER, User.Role.ADMIN)
