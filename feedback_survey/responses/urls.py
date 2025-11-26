from django.urls import path

from .views import TakeSurveyView, ThankYouView

app_name = 'responses'

urlpatterns = [
    path('take/<int:survey_id>/', TakeSurveyView.as_view(), name='take-survey'),
    path('thank-you/<int:survey_id>/', ThankYouView.as_view(), name='thank-you'),
]
