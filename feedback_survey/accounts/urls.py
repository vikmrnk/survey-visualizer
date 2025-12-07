from django.contrib.auth.views import LogoutView
from django.urls import path

from .views import ProfileSettingsView, RegisterView, RoleBasedLoginView, RoleRedirectView

app_name = 'accounts'

urlpatterns = [
    path('login/', RoleBasedLoginView.as_view(), name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('register/', RegisterView.as_view(), name='register'),
    path('settings/', ProfileSettingsView.as_view(), name='settings'),
    path('redirect-after-login/', RoleRedirectView.as_view(), name='post-login-redirect'),
]
