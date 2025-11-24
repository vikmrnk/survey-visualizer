from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User


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
