from django.views.generic import TemplateView

from accounts.mixins import TeacherOrAdminRequiredMixin


class AnalyticsOverviewView(TeacherOrAdminRequiredMixin, TemplateView):
    template_name = 'analytics/overview.html'
