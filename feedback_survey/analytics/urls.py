from django.urls import path

from .views import AnalyticsOverviewView

app_name = 'analytics'

urlpatterns = [
    path('', AnalyticsOverviewView.as_view(), name='overview'),
]
