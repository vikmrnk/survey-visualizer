from django.db.models import Q
from django.utils import timezone
from django.views.generic import TemplateView

from accounts.mixins import StudentRequiredMixin, TeacherRequiredMixin

from .models import Survey


class StudentSurveyListView(StudentRequiredMixin, TemplateView):
    template_name = 'surveys/student_survey_list.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        now = timezone.now()
        context['surveys'] = Survey.objects.filter(
            status=Survey.Status.PUBLISHED,
        ).filter(
            Q(start_date__lte=now) | Q(start_date__isnull=True),
            Q(end_date__gte=now) | Q(end_date__isnull=True),
        )
        return context


class TeacherDashboardView(TeacherRequiredMixin, TemplateView):
    template_name = 'surveys/teacher_dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['survey_count'] = Survey.objects.filter(author=self.request.user).count()
        context['active_count'] = Survey.objects.filter(
            author=self.request.user,
            status=Survey.Status.PUBLISHED,
        ).count()
        return context
