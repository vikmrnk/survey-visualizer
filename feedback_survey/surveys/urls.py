from django.urls import path

from .views import StudentSurveyListView, TeacherDashboardView

app_name = 'surveys'

urlpatterns = [
    path('student/', StudentSurveyListView.as_view(), name='student-survey-list'),
    path('teacher/', TeacherDashboardView.as_view(), name='teacher-dashboard'),
]
