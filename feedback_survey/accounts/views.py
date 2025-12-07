from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView
from django.shortcuts import redirect
from django.urls import reverse
from django.views import View
from django.views.generic import FormView, TemplateView

from .forms import UserRegistrationForm
from .models import UserProfile

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


class ProfileSettingsView(LoginRequiredMixin, TemplateView):
    template_name = "accounts/settings.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        
        # Отримуємо або створюємо профіль користувача
        profile, created = UserProfile.objects.get_or_create(user=user)
        
        # Завантажуємо налаштування з профілю
        ctx["notify_new_responses"] = profile.notify_new_responses
        ctx["notify_daily_summary"] = profile.notify_daily_summary
        ctx["notify_low_response"] = profile.notify_low_response
        ctx["notify_marketing"] = profile.notify_marketing
        ctx["visibility"] = profile.visibility
        ctx["retention"] = profile.retention
        
        return ctx

    def post(self, request, *args, **kwargs):
        user = request.user
        
        # Оновлюємо дані користувача
        if 'full_name' in request.POST:
            full_name = request.POST['full_name'].strip()
            if full_name:
                parts = full_name.split(' ', 1)
                user.first_name = parts[0]
                if len(parts) > 1:
                    user.last_name = parts[1]
                else:
                    user.last_name = ''
        
        if 'email' in request.POST:
            user.email = request.POST['email'].strip()
        
        if 'department' in request.POST:
            user.faculty = request.POST['department'].strip()
        
        user.save()
        
        # Отримуємо або створюємо профіль
        profile, created = UserProfile.objects.get_or_create(user=user)
        
        # Оновлюємо налаштування сповіщень
        profile.notify_new_responses = 'notify_new_responses' in request.POST
        profile.notify_daily_summary = 'notify_daily_summary' in request.POST
        profile.notify_low_response = 'notify_low_response' in request.POST
        profile.notify_marketing = 'notify_marketing' in request.POST
        
        # Оновлюємо налаштування конфіденційності
        if 'visibility' in request.POST:
            profile.visibility = request.POST['visibility']
        
        if 'retention' in request.POST:
            profile.retention = request.POST['retention']
        
        profile.save()
        
        messages.success(request, "Налаштування збережено.")
        return redirect("accounts:settings")
