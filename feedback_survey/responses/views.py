from django.contrib import messages
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.views.generic import TemplateView

from accounts.mixins import StudentRequiredMixin
from surveys.models import Choice, Question, Survey

from .models import Answer, ResponseSession


class TakeSurveyView(StudentRequiredMixin, TemplateView):
    template_name = 'responses/take_survey.html'

    def dispatch(self, request, *args, **kwargs):
        self.survey = get_object_or_404(
            Survey,
            pk=self.kwargs['survey_id'],
            status=Survey.Status.PUBLISHED,
        )
        
        # Check if survey is within date range
        now = timezone.now()
        if self.survey.start_date and self.survey.start_date > now:
            messages.error(request, 'Опитування ще не розпочалось.')
            return redirect('surveys:student-survey-list')
        if self.survey.end_date and self.survey.end_date < now:
            messages.error(request, 'Опитування вже завершено.')
            return redirect('surveys:student-survey-list')
        
        # Check if survey has questions
        if not self.survey.questions.exists():
            messages.error(request, 'Це опитування поки не містить питань.')
            return redirect('surveys:student-survey-list')
        
        # Check if already completed
        completed_session = ResponseSession.objects.filter(
            user=request.user,
            survey=self.survey,
            status=ResponseSession.Status.COMPLETED,
        ).first()
        
        if completed_session:
            messages.info(request, 'Ви вже пройшли це опитування.')
            return redirect('responses:thank-you', survey_id=self.survey.pk)
        
        # Get or create in-progress session (reuse existing if any)
        self.session = ResponseSession.objects.filter(
            user=request.user,
            survey=self.survey,
            status=ResponseSession.Status.IN_PROGRESS,
        ).order_by('-started_at').first()
        
        if not self.session:
            self.session = ResponseSession.objects.create(
                user=request.user,
                survey=self.survey,
                status=ResponseSession.Status.IN_PROGRESS,
                started_at=timezone.now(),
            )
        
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['survey'] = self.survey
        context['questions'] = self.survey.questions.all().prefetch_related('choices')
        context['session'] = self.session
        
        # Pre-fill existing answers if any (use string keys for template access)
        existing_answers = {}
        for answer in self.session.answers.select_related('selected_choice').all():
            q_id = str(answer.question_id)
            if answer.question.question_type == Question.QuestionType.MULTIPLE:
                if q_id not in existing_answers:
                    existing_answers[q_id] = []
                if answer.selected_choice_id:
                    existing_answers[q_id].append(str(answer.selected_choice_id))
            else:
                if answer.selected_choice_id:
                    existing_answers[q_id] = str(answer.selected_choice_id)
                elif answer.text_answer:
                    existing_answers[q_id] = answer.text_answer
        context['existing_answers'] = existing_answers
        
        return context

    def post(self, request, *args, **kwargs):
        questions = self.survey.questions.all()
        errors = []
        
        # Validate all questions are answered
        for question in questions:
            if question.question_type == Question.QuestionType.MULTIPLE:
                selected = request.POST.getlist(f'question_{question.pk}')
                if not selected:
                    errors.append(f'Питання "{question.text[:50]}..." потребує відповіді.')
            elif question.question_type == Question.QuestionType.SINGLE:
                selected = request.POST.get(f'question_{question.pk}')
                if not selected:
                    errors.append(f'Питання "{question.text[:50]}..." потребує відповіді.')
            elif question.question_type == Question.QuestionType.SCALE:
                value = request.POST.get(f'question_{question.pk}')
                if not value:
                    errors.append(f'Питання "{question.text[:50]}..." потребує відповіді.')
            elif question.question_type == Question.QuestionType.TEXT:
                value = request.POST.get(f'question_{question.pk}')
                if not value or not value.strip():
                    errors.append(f'Питання "{question.text[:50]}..." потребує відповіді.')
        
        if errors:
            for error in errors:
                messages.error(request, error)
            return self.get(request, *args, **kwargs)
        
        # Save answers in transaction
        try:
            with transaction.atomic():
                # Delete existing answers for this session (in case of resubmission)
                Answer.objects.filter(response_session=self.session).delete()
                
                # Create new answers
                for question in questions:
                    if question.question_type == Question.QuestionType.MULTIPLE:
                        selected_choice_ids = request.POST.getlist(f'question_{question.pk}')
                        for choice_id in selected_choice_ids:
                            choice = get_object_or_404(Choice, pk=choice_id, question=question)
                            Answer.objects.create(
                                response_session=self.session,
                                question=question,
                                selected_choice=choice,
                            )
                    elif question.question_type == Question.QuestionType.SINGLE:
                        choice_id = request.POST.get(f'question_{question.pk}')
                        choice = get_object_or_404(Choice, pk=choice_id, question=question)
                        Answer.objects.create(
                            response_session=self.session,
                            question=question,
                            selected_choice=choice,
                        )
                    elif question.question_type == Question.QuestionType.SCALE:
                        value = request.POST.get(f'question_{question.pk}')
                        # For scale, we'll store the value as text_answer
                        Answer.objects.create(
                            response_session=self.session,
                            question=question,
                            text_answer=value,
                        )
                    elif question.question_type == Question.QuestionType.TEXT:
                        text_value = request.POST.get(f'question_{question.pk}')
                        Answer.objects.create(
                            response_session=self.session,
                            question=question,
                            text_answer=text_value,
                        )
                
                # Mark session as completed
                self.session.status = ResponseSession.Status.COMPLETED
                self.session.completed_at = timezone.now()
                self.session.save()
                
        except Exception as e:
            messages.error(request, f'Помилка збереження відповідей: {str(e)}')
            return self.get(request, *args, **kwargs)
        
        messages.success(request, 'Дякуємо за проходження опитування!')
        return redirect('responses:thank-you', survey_id=self.survey.pk)


class ThankYouView(StudentRequiredMixin, TemplateView):
    template_name = 'responses/thank_you.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['survey'] = get_object_or_404(Survey, pk=self.kwargs['survey_id'])
        return context
