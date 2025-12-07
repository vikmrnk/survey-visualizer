from django.urls import path

from .views import SurveyAnalyticsView

app_name = 'analytics'

urlpatterns = [
    path('overview/', SurveyAnalyticsView.as_view(), name='overview'),
]
