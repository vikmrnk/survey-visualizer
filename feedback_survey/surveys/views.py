from django.contrib import messages
from django.db.models import Q, Count
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.utils.safestring import mark_safe
from django.views.generic import CreateView, ListView, TemplateView, UpdateView

from accounts.mixins import (
    StudentRequiredMixin,
    TeacherOrAdminRequiredMixin,
)
from responses.models import ResponseSession

from .forms import ChoiceFormSet, QuestionFormSet, SurveyFilterForm, SurveyForm
from .models import Survey


# Кеш для результатів ризику в межах одного запиту
_risk_cache = {}


def get_survey_risk_proba(survey):
    """
    Ліниво імпортує ML-предиктор і повертає ризик,
    або None, якщо ML недоступний.
    """
    try:
        from analytics.ml_model import predict_survey_risk_proba
    except Exception:
        return None
    
    try:
        return predict_survey_risk_proba(survey)
    except Exception:
        return None


def _build_risk_metadata(survey):
    # Використовуємо кеш для уникнення повторних обчислень
    cache_key = f"survey_{survey.id}"
    if cache_key in _risk_cache:
        return _risk_cache[cache_key]
    
    proba = get_survey_risk_proba(survey)
    if proba is None:
        result = {
            'risk_level': 'no-data',
            'risk_label': 'Немає даних',
            'risk_probability': None,
        }
    elif proba >= 0.7:
        result = {
            'risk_level': 'high',
            'risk_label': 'Високий',
            'risk_probability': round(proba, 2),
        }
    elif proba >= 0.4:
        result = {
            'risk_level': 'medium',
            'risk_label': 'Середній',
            'risk_probability': round(proba, 2),
        }
    else:
        result = {
            'risk_level': 'low',
            'risk_label': 'Низький',
            'risk_probability': round(proba, 2),
        }
    
    _risk_cache[cache_key] = result
    return result


class StudentSurveyListView(StudentRequiredMixin, TemplateView):
    template_name = 'surveys/student_survey_list.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        now = timezone.now()
        from responses.models import ResponseSession
        
        # Get published surveys within date range
        available_surveys = Survey.objects.filter(
            status=Survey.Status.PUBLISHED,
        ).filter(
            Q(start_date__lte=now) | Q(start_date__isnull=True),
            Q(end_date__gte=now) | Q(end_date__isnull=True),
        )
        
        # Exclude surveys already completed by this student
        completed_survey_ids = ResponseSession.objects.filter(
            user=self.request.user,
            status=ResponseSession.Status.COMPLETED,
            survey__in=available_surveys,
        ).values_list('survey_id', flat=True)
        
        context['surveys'] = available_surveys.exclude(id__in=completed_survey_ids)
        return context


class TeacherDashboardView(TeacherOrAdminRequiredMixin, TemplateView):
    template_name = 'surveys/teacher_dashboard.html'

    def get_context_data(self, **kwargs):
        import json
        from datetime import timedelta
        from django.db.models import Avg, Count
        from django.db.models.functions import TruncDate
        from responses.models import Answer

        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        now = timezone.now()

        surveys_qs = Survey.objects.filter(author=user)
        total_surveys = surveys_qs.count()
        active_count = surveys_qs.filter(status=Survey.Status.PUBLISHED).count()

        # Загальна кількість завершених відповідей
        completed_sessions = ResponseSession.objects.filter(
            survey__author=user,
            status=ResponseSession.Status.COMPLETED,
        )
        total_responses = completed_sessions.count()

        # Всі сесії (для розрахунку completion rate)
        all_sessions = ResponseSession.objects.filter(survey__author=user)
        all_sessions_count = all_sessions.count()
        completion_rate = 0
        if all_sessions_count > 0:
            completion_rate = round((total_responses / all_sessions_count) * 100)

        # Середня оцінка по scale-питаннях
        scale_answers = Answer.objects.filter(
            response_session__survey__author=user,
            response_session__status=ResponseSession.Status.COMPLETED,
            question__question_type='scale',
        ).exclude(text_answer='')
        
        avg_rating = None
        if scale_answers.exists():
            # text_answer містить числове значення для scale
            ratings = []
            for ans in scale_answers:
                try:
                    ratings.append(int(ans.text_answer))
                except (ValueError, TypeError):
                    pass
            if ratings:
                avg_rating = round(sum(ratings) / len(ratings), 1)

        ctx["active_surveys"] = active_count
        ctx["total_responses"] = total_responses
        ctx["completion_rate"] = f"{completion_rate}%"
        ctx["avg_rating"] = f"{avg_rating}/5" if avg_rating else "—"

        # Тренд відповідей за останній тиждень (реальні дані)
        week_ago = now - timedelta(days=7)
        daily_stats = (
            ResponseSession.objects.filter(
                survey__author=user,
                started_at__gte=week_ago,
            )
            .annotate(day=TruncDate('started_at'))
            .values('day')
            .annotate(
                responses=Count('id'),
                completed=Count('id', filter=Q(status=ResponseSession.Status.COMPLETED)),
            )
            .order_by('day')
        )

        # Перетворюємо на список з назвами днів
        day_names = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Нд']
        dashboard_data = []
        for stat in daily_stats:
            day_name = day_names[stat['day'].weekday()] if stat['day'] else '?'
            dashboard_data.append({
                "name": day_name,
                "responses": stat['responses'],
                "completed": stat['completed'],
            })

        # Якщо немає даних, показуємо порожній графік
        if not dashboard_data:
            dashboard_data = [{"name": day, "responses": 0, "completed": 0} for day in day_names[:6]]

        ctx["dashboard_trend_json"] = mark_safe(json.dumps(dashboard_data, ensure_ascii=False))

        # Статистика задоволеності на основі scale-відповідей
        satisfaction_stats = []
        if scale_answers.exists():
            ratings_count = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
            for ans in scale_answers:
                try:
                    val = int(ans.text_answer)
                    if 1 <= val <= 5:
                        ratings_count[val] += 1
                except (ValueError, TypeError):
                    pass
            total_ratings = sum(ratings_count.values())
            if total_ratings > 0:
                satisfaction_stats = [
                    {"label": "5 - Відмінно", "value": ratings_count[5], "color": "#16a34a"},
                    {"label": "4 - Добре", "value": ratings_count[4], "color": "#4C7EFF"},
                    {"label": "3 - Нормально", "value": ratings_count[3], "color": "#8BA8FF"},
                    {"label": "2 - Погано", "value": ratings_count[2], "color": "#fbbf24"},
                    {"label": "1 - Дуже погано", "value": ratings_count[1], "color": "#ef4444"},
                ]

        if not satisfaction_stats:
            satisfaction_stats = [
                {"label": "Немає даних", "value": 1, "color": "#e5e7eb"},
            ]

        ctx["satisfaction_stats_json"] = mark_safe(
            json.dumps(satisfaction_stats, ensure_ascii=False),
        )

        # Недавні опитування з кількістю відповідей
        recent = surveys_qs.annotate(
            responses_count=Count(
                'response_sessions',
                filter=Q(response_sessions__status=ResponseSession.Status.COMPLETED),
            )
        ).order_by("-created_at")[:4]
        ctx["recent_surveys"] = recent

        return ctx


class SurveyAuthorMixin(TeacherOrAdminRequiredMixin):
    model = Survey
    form_class = SurveyForm

    def get_queryset(self):
        return Survey.objects.filter(author=self.request.user)


class SurveyManageListView(SurveyAuthorMixin, ListView):
    template_name = 'surveys/manage_list.html'
    context_object_name = 'surveys'
    paginate_by = 10

    def get_discipline_choices(self):
        return list(
            Survey.objects.filter(author=self.request.user)
            .exclude(discipline='')
            .values_list('discipline', flat=True)
            .distinct()
        )

    def get_filter_form(self):
        if not hasattr(self, '_filter_form'):
            self._filter_form = SurveyFilterForm(
                self.request.GET or None,
                discipline_choices=self.get_discipline_choices(),
            )
        return self._filter_form

    def get_queryset(self):
        queryset = Survey.objects.filter(author=self.request.user).order_by('-created_at')
        
        # Простий фільтр по статусу через query param
        status_param = self.request.GET.get('status')
        if status_param:
            queryset = queryset.filter(status=status_param)
        else:
            # Fallback на форму фільтрації
            form = self.get_filter_form()
            if form.is_valid():
                status = form.cleaned_data.get('status')
                if status:
                    queryset = queryset.filter(status=status)
                discipline = form.cleaned_data.get('discipline')
                if discipline:
                    queryset = queryset.filter(discipline=discipline)
                start_date = form.cleaned_data.get('start_date')
                if start_date:
                    queryset = queryset.filter(start_date__date__gte=start_date)
                end_date = form.cleaned_data.get('end_date')
                if end_date:
                    queryset = queryset.filter(end_date__date__lte=end_date)
        
        # Prefetch questions та responses для оптимізації ML обчислень
        queryset = queryset.prefetch_related(
            'questions',
            'questions__choices',
        )
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['filter_form'] = self.get_filter_form()
        params = self.request.GET.copy()
        params.pop('page', None)
        context['filters_query'] = params.urlencode()
        surveys_page = context.get('surveys')
        if hasattr(surveys_page, 'object_list'):
            survey_list = surveys_page.object_list
        else:
            survey_list = surveys_page
        
        # Обчислення ризику увімкнено
        ENABLE_RISK_COMPUTATION = True
        
        # Очищаємо кеш при кожному запиті
        global _risk_cache
        _risk_cache.clear()
        
        if ENABLE_RISK_COMPUTATION:
            # Оптимізація: обчислюємо ризик тільки для опитувань з достатньою кількістю відповідей
            from responses.models import ResponseSession
            survey_ids = [s.id for s in survey_list]
            
            if survey_ids:
                # Один запит для підрахунку відповідей по кожному опитуванню
                response_counts = dict(
                    ResponseSession.objects.filter(
                        survey_id__in=survey_ids,
                        status=ResponseSession.Status.COMPLETED
                    ).values('survey_id').annotate(
                        count=Count('id')
                    ).values_list('survey_id', 'count')
                )
                
                MIN_RESPONSES_FOR_RISK = 3
                context['survey_rows'] = []
                for survey in survey_list:
                    response_count = response_counts.get(survey.id, 0)
                    if response_count < MIN_RESPONSES_FOR_RISK:
                        context['survey_rows'].append({
                            'survey': survey,
                            'risk_level': 'no-data',
                            'risk_label': 'Немає даних',
                            'risk_probability': None,
                        })
                    else:
                        context['survey_rows'].append({
                            'survey': survey,
                            **_build_risk_metadata(survey),
                        })
            else:
                context['survey_rows'] = []
        else:
            # Швидкий шлях без обчислення ризику
            context['survey_rows'] = [
                {
                    'survey': survey,
                    'risk_level': 'no-data',
                    'risk_label': 'Не обчислено',
                    'risk_probability': None,
                }
                for survey in survey_list
            ]
        return context


class SurveyCreateView(SurveyAuthorMixin, CreateView):
    template_name = 'surveys/survey_form.html'
    success_url = reverse_lazy('surveys:manage-list')

    def form_valid(self, form):
        form.instance.author = self.request.user
        response = self._handle_status_and_save(form)
        if response is not None:
            return response
        messages.success(self.request, 'Опитування збережено.')
        return redirect(self.get_success_url())

    def _handle_status_and_save(self, form):
        action = self.request.POST.get('action', 'draft')
        desired_status = Survey.Status.PUBLISHED if action == 'publish' else Survey.Status.DRAFT
        self.object = form.save(commit=False)
        self.object.status = desired_status
        self.object.author = getattr(self.object, 'author', self.request.user)
        self.object.save()
        form.save_m2m()
        if desired_status == Survey.Status.PUBLISHED and not self.object.questions.exists():
            form.add_error(None, 'Неможливо опублікувати опитування без питань.')
            self.object.status = Survey.Status.DRAFT
            self.object.save(update_fields=['status'])
            messages.error(self.request, 'Додайте хоча б одне питання перед публікацією.')
            return self.form_invalid(form)
        return None


class SurveyUpdateView(SurveyAuthorMixin, UpdateView):
    template_name = 'surveys/survey_form.html'
    success_url = reverse_lazy('surveys:manage-list')

    def form_valid(self, form):
        response = self._handle_status_and_save(form)
        if response is not None:
            return response
        messages.success(self.request, 'Зміни збережено.')
        return redirect(self.get_success_url())

    def _handle_status_and_save(self, form):
        action = self.request.POST.get('action', 'draft')
        desired_status = Survey.Status.PUBLISHED if action == 'publish' else Survey.Status.DRAFT
        self.object = form.save(commit=False)
        self.object.status = desired_status
        self.object.save()
        form.save_m2m()
        if desired_status == Survey.Status.PUBLISHED and not self.object.questions.exists():
            form.add_error(None, 'Неможливо опублікувати опитування без питань.')
            self.object.status = Survey.Status.DRAFT
            self.object.save(update_fields=['status'])
            messages.error(self.request, 'Додайте хоча б одне питання перед публікацією.')
            return self.form_invalid(form)
        return None


class SurveyQuestionBuilderView(SurveyAuthorMixin, TemplateView):
    template_name = 'surveys/question_builder.html'

    def dispatch(self, request, *args, **kwargs):
        self.survey = get_object_or_404(
            Survey,
            pk=self.kwargs['pk'],
            author=request.user,
        )
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        question_formset = QuestionFormSet(
            instance=self.survey,
            prefix='questions',
        )
        choice_formsets = self._build_choice_formsets()
        
        # Додаємо порожні formsets для нових питань у formset
        new_choice_formsets = self._build_new_choice_formsets(question_formset, bound=False)
        
        return self.render_to_response(
            self._get_context(question_formset, choice_formsets, new_choice_formsets),
        )

    def post(self, request, *args, **kwargs):
        question_formset = QuestionFormSet(
            request.POST,
            instance=self.survey,
            prefix='questions',
        )
        if question_formset.is_valid():
            from django.db import transaction
            with transaction.atomic():
                questions = question_formset.save()
                self.survey.refresh_from_db()
                
                choice_formsets = []
                has_errors = False
                
                # Створюємо маппінг між індексами форм та збереженими питаннями
                question_index_map = {}
                saved_questions = list(questions)
                saved_idx = 0
                
                for idx, form in enumerate(question_formset.forms):
                    if form in question_formset.deleted_forms:
                        continue
                    if form.instance.pk:
                        question_index_map[idx] = form.instance.pk
                    elif saved_idx < len(saved_questions):
                        question_index_map[idx] = saved_questions[saved_idx].pk
                        saved_idx += 1
                
                # Обробляємо formsets для всіх питань
                for question in self.survey.questions.all():
                    prefix = f'choices-{question.pk}'
                    
                    # Перевіряємо, чи це нове питання (має дані з префіксом choices-new-{idx})
                    new_prefix = None
                    for idx, question_id in question_index_map.items():
                        if question_id == question.id:
                            test_prefix = f'choices-new-{idx}'
                            if f'{test_prefix}-TOTAL_FORMS' in request.POST:
                                new_prefix = test_prefix
                                break
                    
                    if new_prefix:
                        # Це нове питання - обробляємо з перейменованим префіксом
                        if question.question_type in ['single', 'multiple']:
                            # Створюємо новий QueryDict з перейменованими ключами
                            post_data = request.POST.copy()
                            post_data._mutable = True
                            for key in list(post_data.keys()):
                                if key.startswith(new_prefix):
                                    new_key = key.replace(new_prefix, prefix)
                                    post_data[new_key] = post_data.pop(key)
                            
                            formset = ChoiceFormSet(post_data, instance=question, prefix=prefix)
                            if formset.is_valid():
                                formset.save()
                            else:
                                has_errors = True
                            choice_formsets.append((question, formset))
                        else:
                            # Для питань інших типів видаляємо всі варіанти
                            question.choices.all().delete()
                            formset = ChoiceFormSet(instance=question, prefix=prefix)
                            choice_formsets.append((question, formset))
                    else:
                        # Існуюче питання - обробляємо зі стандартним префіксом
                        if question.question_type in ['single', 'multiple']:
                            # Перевіряємо, чи є management_form дані в POST
                            if f'{prefix}-TOTAL_FORMS' in request.POST:
                                formset = ChoiceFormSet(request.POST, instance=question, prefix=prefix)
                                if formset.is_valid():
                                    formset.save()
                                else:
                                    has_errors = True
                                choice_formsets.append((question, formset))
                            else:
                                # Якщо немає management_form даних, створюємо порожній formset
                                # Це означає, що варіанти не були передані (можливо, питання щойно змінило тип)
                                # Але все одно додаємо formset до списку, щоб він відображався в шаблоні
                                formset = ChoiceFormSet(instance=question, prefix=prefix)
                                choice_formsets.append((question, formset))
                        else:
                            # Для питань інших типів видаляємо всі варіанти
                            question.choices.all().delete()
                            formset = ChoiceFormSet(instance=question, prefix=prefix)
                            choice_formsets.append((question, formset))
                
                if has_errors:
                    # Збираємо детальні помилки
                    error_messages = []
                    for question, formset in choice_formsets:
                        if not formset.is_valid():
                            for form in formset.forms:
                                if form.errors:
                                    for field, errors in form.errors.items():
                                        for error in errors:
                                            error_messages.append(f'Питання "{question.text[:50] if question.text else "Без назви"}": {field} - {error}')
                            if formset.non_form_errors():
                                for error in formset.non_form_errors():
                                    error_messages.append(f'Питання "{question.text[:50] if question.text else "Без назви"}": {error}')
                    
                    # Додаємо загальну інформацію про помилки
                    if error_messages:
                        messages.error(request, 'Помилки у варіантах відповідей: ' + '; '.join(error_messages[:5]))  # Показуємо перші 5 помилок
                    else:
                        # Якщо немає конкретних помилок, але has_errors = True, показуємо загальне повідомлення
                        messages.error(request, 'Перевірте помилки у варіантах відповідей. Можливо, деякі варіанти порожні або мають невалідні дані.')
                    
                    choice_formsets = self._build_choice_formsets(bound=True)
                    new_choice_formsets = self._build_new_choice_formsets(question_formset, bound=True)
                    return self.render_to_response(
                        self._get_context(question_formset, choice_formsets, new_choice_formsets),
                    )
            
            messages.success(request, 'Питання та варіанти збережено.')
            return redirect('surveys:question-builder', pk=self.survey.pk)
        else:
            # Збираємо детальні помилки валідації питань
            error_messages = []
            for form in question_formset.forms:
                if form.errors:
                    for field, errors in form.errors.items():
                        for error in errors:
                            question_text = form.cleaned_data.get('text', 'Без назви') if hasattr(form, 'cleaned_data') and form.cleaned_data else 'Без назви'
                            error_messages.append(f'Питання "{question_text[:50]}": {field} - {error}')
            if question_formset.non_form_errors():
                for error in question_formset.non_form_errors():
                    error_messages.append(str(error))
            
            if error_messages:
                messages.error(request, 'Помилки у списку питань: ' + '; '.join(error_messages[:5]))
            else:
                messages.error(request, 'Перевірте помилки у списку питань.')
            
            choice_formsets = self._build_choice_formsets(bound=True)
            new_choice_formsets = self._build_new_choice_formsets(question_formset, bound=True)
        return self.render_to_response(
            self._get_context(question_formset, choice_formsets, new_choice_formsets),
        )

    def _build_choice_formsets(self, bound: bool = False):
        formsets = []
        for question in self.survey.questions.all():
            prefix = f'choices-{question.pk}'
            # Для питань типу single/multiple завжди створюємо formset
            if question.question_type in ['single', 'multiple']:
                if bound and f'{prefix}-TOTAL_FORMS' in self.request.POST:
                    formset = ChoiceFormSet(
                        self.request.POST,
                        instance=question,
                        prefix=prefix,
                    )
                else:
                    formset = ChoiceFormSet(instance=question, prefix=prefix)
                formsets.append((question, formset))
            else:
                # Для питань інших типів також створюємо порожній formset для відображення
                formset = ChoiceFormSet(instance=question, prefix=prefix)
                formsets.append((question, formset))
        return formsets
    
    def _build_new_choice_formsets(self, question_formset, bound: bool = False):
        """Створює formsets для нових питань у question_formset"""
        new_choice_formsets = {}
        for idx, form in enumerate(question_formset.forms):
            if not form.instance.pk:
                from .models import Question
                question_type = 'text'
                if hasattr(form, 'cleaned_data') and form.cleaned_data:
                    question_type = form.cleaned_data.get('question_type', 'text')
                elif bound and hasattr(self.request, 'POST'):
                    field_name = f'{question_formset.prefix}-{idx}-question_type'
                    if field_name in self.request.POST:
                        question_type = self.request.POST[field_name]
                temp_question = Question(survey=self.survey, question_type=question_type)
                prefix = f'choices-new-{idx}'
                if bound and f'{prefix}-TOTAL_FORMS' in self.request.POST:
                    formset = ChoiceFormSet(self.request.POST, instance=temp_question, prefix=prefix)
                else:
                    formset = ChoiceFormSet(instance=temp_question, prefix=prefix)
                new_choice_formsets[idx] = (temp_question, formset)
        return new_choice_formsets

    def _save_choice_formsets(self, formsets):
        has_errors = False
        for question, formset in formsets:
            if not formset.is_bound:
                continue
            # Обробляємо варіанти тільки для питань типу single/multiple
            if question.question_type in ['single', 'multiple']:
                if formset.is_valid():
                    formset.save()
                else:
                    has_errors = True
            else:
                # Для питань інших типів видаляємо всі варіанти
                question.choices.all().delete()
        if has_errors:
            messages.error(self.request, 'Перевірте помилки у варіантах відповідей.')
        return not has_errors

    def _get_context(self, question_formset, choice_formsets, new_choice_formsets=None):
        context = {
            'survey': self.survey,
            'question_formset': question_formset,
            'choice_formsets': choice_formsets,
        }
        if new_choice_formsets is not None:
            context['new_choice_formsets'] = new_choice_formsets
        return context
