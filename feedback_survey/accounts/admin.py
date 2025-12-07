from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User, UserProfile


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Academic information', {'fields': ('role', 'faculty', 'academic_group')}),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ('Academic information', {'fields': ('role', 'faculty', 'academic_group')}),
    )
    list_display = ('username', 'email', 'role', 'faculty', 'academic_group', 'is_staff')
    list_filter = BaseUserAdmin.list_filter + ('role',)
    search_fields = BaseUserAdmin.search_fields + ('faculty', 'academic_group')


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'notify_new_responses', 'notify_daily_summary', 'visibility', 'retention')
    list_filter = ('notify_new_responses', 'notify_daily_summary', 'visibility', 'retention')
    search_fields = ('user__username', 'user__email', 'user__first_name', 'user__last_name')
    raw_id_fields = ('user',)
