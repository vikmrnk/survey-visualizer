from django.urls import path

from .views import (
    StudentSurveyListView,
    SurveyCreateView,
    SurveyManageListView,
    SurveyQuestionBuilderView,
    SurveyUpdateView,
    TeacherDashboardView,
)

app_name = 'surveys'

urlpatterns = [
    path('student/', StudentSurveyListView.as_view(), name='student-survey-list'),
    path('teacher/', TeacherDashboardView.as_view(), name='teacher-dashboard'),
    path('teacher/surveys/', SurveyManageListView.as_view(), name='manage-list'),
    path('teacher/surveys/create/', SurveyCreateView.as_view(), name='create'),
    path('teacher/surveys/<int:pk>/edit/', SurveyUpdateView.as_view(), name='edit'),
    path('teacher/surveys/<int:pk>/questions/', SurveyQuestionBuilderView.as_view(), name='question-builder'),
]
