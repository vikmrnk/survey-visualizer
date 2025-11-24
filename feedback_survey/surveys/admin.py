from django.contrib import admin

from .models import Choice, Question, Survey


class ChoiceInline(admin.TabularInline):
    model = Choice
    extra = 1


class QuestionInline(admin.TabularInline):
    model = Question
    extra = 1


@admin.register(Survey)
class SurveyAdmin(admin.ModelAdmin):
    list_display = ('title', 'author', 'status', 'start_date', 'end_date', 'target')
    list_filter = ('status', 'start_date', 'end_date')
    search_fields = ('title', 'description', 'target')
    inlines = [QuestionInline]


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ('text', 'survey', 'question_type', 'order')
    list_filter = ('question_type', 'survey')
    ordering = ('survey', 'order')
    inlines = [ChoiceInline]


@admin.register(Choice)
class ChoiceAdmin(admin.ModelAdmin):
    list_display = ('text', 'question', 'order')
    ordering = ('question', 'order')
