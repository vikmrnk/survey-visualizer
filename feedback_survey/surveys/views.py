from django.contrib import messages
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import CreateView, ListView, TemplateView, UpdateView

from accounts.mixins import (
    StudentRequiredMixin,
    TeacherOrAdminRequiredMixin,
)

from .forms import ChoiceFormSet, QuestionFormSet, SurveyFilterForm, SurveyForm
from .models import Survey


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
        context = super().get_context_data(**kwargs)
        teacher_surveys = Survey.objects.filter(author=self.request.user)
        context['survey_count'] = teacher_surveys.count()
        context['active_count'] = teacher_surveys.filter(
            status=Survey.Status.PUBLISHED,
        ).count()
        context['latest_surveys'] = teacher_surveys.order_by('-updated_at')[:5]
        return context


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
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['filter_form'] = self.get_filter_form()
        params = self.request.GET.copy()
        params.pop('page', None)
        context['filters_query'] = params.urlencode()
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
        return self.render_to_response(
            self._get_context(question_formset, choice_formsets),
        )

    def post(self, request, *args, **kwargs):
        question_formset = QuestionFormSet(
            request.POST,
            instance=self.survey,
            prefix='questions',
        )
        if question_formset.is_valid():
            question_formset.save()
            self.survey.refresh_from_db()
            choice_formsets = self._build_choice_formsets(bound=True)
            if self._save_choice_formsets(choice_formsets):
                messages.success(request, 'Питання та варіанти збережено.')
                return redirect('surveys:question-builder', pk=self.survey.pk)
        else:
            choice_formsets = self._build_choice_formsets(bound=True)
            messages.error(request, 'Перевірте помилки у списку питань.')
        return self.render_to_response(
            self._get_context(question_formset, choice_formsets),
        )

    def _build_choice_formsets(self, bound: bool = False):
        formsets = []
        for question in self.survey.questions.all():
            prefix = f'choices-{question.pk}'
            if bound and f'{prefix}-TOTAL_FORMS' in self.request.POST:
                formset = ChoiceFormSet(
                    self.request.POST,
                    instance=question,
                    prefix=prefix,
                )
            else:
                formset = ChoiceFormSet(instance=question, prefix=prefix)
            formsets.append((question, formset))
        return formsets

    def _save_choice_formsets(self, formsets):
        has_errors = False
        for question, formset in formsets:
            if not formset.is_bound:
                continue
            if formset.is_valid():
                formset.save()
            else:
                has_errors = True
        if has_errors:
            messages.error(self.request, 'Перевірте помилки у варіантах відповідей.')
        return not has_errors

    def _get_context(self, question_formset, choice_formsets):
        return {
            'survey': self.survey,
            'question_formset': question_formset,
            'choice_formsets': choice_formsets,
        }
