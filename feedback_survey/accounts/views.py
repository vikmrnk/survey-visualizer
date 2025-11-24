from django.contrib.auth import get_user_model, login
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView
from django.shortcuts import redirect
from django.urls import reverse
from django.views import View
from django.views.generic import FormView

from .forms import UserRegistrationForm

User = get_user_model()


def get_role_redirect_url(user: User) -> str:
    if user.role == User.Role.TEACHER:
        return reverse('surveys:teacher-dashboard')
    if user.role == User.Role.STUDENT:
        return reverse('surveys:student-survey-list')
    return reverse('analytics:overview')


class RoleBasedLoginView(LoginView):
    template_name = 'accounts/login.html'
    redirect_authenticated_user = True

    def get_success_url(self):
        return get_role_redirect_url(self.request.user)


class RegisterView(FormView):
    template_name = 'accounts/register.html'
    form_class = UserRegistrationForm

    def form_valid(self, form):
        user = form.save()
        login(self.request, user)
        return redirect(get_role_redirect_url(user))


class RoleRedirectView(LoginRequiredMixin, View):
    def get(self, request):
        return redirect(get_role_redirect_url(request.user))
