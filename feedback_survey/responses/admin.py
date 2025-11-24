from django.contrib import admin

from .models import Answer, ResponseSession


class AnswerInline(admin.TabularInline):
    model = Answer
    extra = 0


@admin.register(ResponseSession)
class ResponseSessionAdmin(admin.ModelAdmin):
    list_display = ('id', 'survey', 'user', 'status', 'started_at', 'completed_at')
    list_filter = ('status', 'started_at', 'completed_at', 'survey')
    search_fields = ('user__username', 'survey__title')
    inlines = [AnswerInline]


@admin.register(Answer)
class AnswerAdmin(admin.ModelAdmin):
    list_display = ('id', 'response_session', 'question', 'selected_choice', 'text_answer')
    list_filter = ('question__survey',)
    search_fields = ('response_session__user__username', 'question__text', 'text_answer')
