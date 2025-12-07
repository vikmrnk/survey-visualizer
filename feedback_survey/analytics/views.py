from __future__ import annotations

import json
from datetime import timedelta

from django.db.models import Avg, Count, Q
from django.db.models.functions import TruncDate
from django.utils import timezone
from django.utils.safestring import mark_safe
from django.views.generic import TemplateView

from accounts.mixins import TeacherOrAdminRequiredMixin
from responses.models import Answer, ResponseSession
from surveys.models import Question, Survey


class SurveyAnalyticsView(TeacherOrAdminRequiredMixin, TemplateView):
    template_name = 'analytics/overview.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        now = timezone.now()

        # Оптимізація: один запит для всіх сесій
        
        all_sessions_qs = ResponseSession.objects.filter(survey__author=user)
        completed_sessions_qs = all_sessions_qs.filter(status=ResponseSession.Status.COMPLETED)
        
        # Підрахунок через один запит
        total_responses = completed_sessions_qs.count()
        all_sessions_count = all_sessions_qs.count()
        response_rate = 0
        if all_sessions_count > 0:
            response_rate = round((total_responses / all_sessions_count) * 100)

        # Середній час заповнення - обчислюємо вручну для коректності
        avg_fill_time = "—"
        sessions_with_time = completed_sessions_qs.filter(
            completed_at__isnull=False,
            started_at__isnull=False
        ).values_list('completed_at', 'started_at')
        
        if sessions_with_time.exists():
            total_seconds = 0
            count = 0
            for completed_at, started_at in sessions_with_time:
                if completed_at and started_at:
                    # Переконуємося, що completed_at >= started_at
                    if completed_at >= started_at:
                        diff = (completed_at - started_at).total_seconds()
                        # Додаткова перевірка на позитивне значення
                        if diff > 0 and diff < 86400:  # Менше 24 годин (розумний ліміт)
                            total_seconds += diff
                            count += 1
            
            if count > 0:
                avg_seconds = total_seconds / count
                # Переконуємося, що результат позитивний
                if avg_seconds > 0:
                    minutes = int(avg_seconds // 60)
                    seconds = int(avg_seconds % 60)
                    avg_fill_time = f"{minutes}хв {seconds}с"
                else:
                    avg_fill_time = "—"

        # Середня оцінка (engagement score) - оптимізовано через bulk запит
        scale_answers_qs = Answer.objects.filter(
            response_session__survey__author=user,
            response_session__status=ResponseSession.Status.COMPLETED,
            question__question_type='scale',
        ).exclude(text_answer='').values_list('text_answer', flat=True)

        engagement_score = "—"
        if scale_answers_qs.exists():
            ratings = []
            for text_val in scale_answers_qs:
                try:
                    val = int(text_val)
                    if 1 <= val <= 5:
                        ratings.append(val)
                except (ValueError, TypeError):
                    pass
            if ratings:
                avg_rating = sum(ratings) / len(ratings)
                # Перетворюємо 1-5 на 1-10 шкалу
                engagement_score = f"{round(avg_rating * 2, 1)}/10"

        ctx["total_responses"] = total_responses
        ctx["avg_fill_time"] = avg_fill_time
        ctx["response_rate"] = f"{response_rate}%"
        ctx["engagement_score"] = engagement_score

        # Відповіді по днях за останній тиждень
        week_ago = now - timedelta(days=7)
        daily_stats = (
            ResponseSession.objects.filter(
                survey__author=user,
                status=ResponseSession.Status.COMPLETED,
                completed_at__gte=week_ago,
            )
            .annotate(day=TruncDate('completed_at'))
            .values('day')
            .annotate(count=Count('id'))
            .order_by('day')
        )

        day_names = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Нд']
        responses_by_day = []
        for stat in daily_stats:
            if stat['day']:
                day_name = day_names[stat['day'].weekday()]
                responses_by_day.append({"day": day_name, "count": stat['count']})

        if not responses_by_day:
            responses_by_day = [{"day": day, "count": 0} for day in day_names]

        ctx["responses_by_day_json"] = mark_safe(
            json.dumps(responses_by_day, ensure_ascii=False),
        )

        # Розподіл оцінок - використовуємо той самий queryset
        rating_distribution = []
        if scale_answers_qs.exists():
            ratings_count = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
            for text_val in scale_answers_qs:
                try:
                    val = int(text_val)
                    if 1 <= val <= 5:
                        ratings_count[val] += 1
                except (ValueError, TypeError):
                    pass
            rating_distribution = [
                {"rating": "5 зірок", "count": ratings_count[5]},
                {"rating": "4 зірки", "count": ratings_count[4]},
                {"rating": "3 зірки", "count": ratings_count[3]},
                {"rating": "2 зірки", "count": ratings_count[2]},
                {"rating": "1 зірка", "count": ratings_count[1]},
            ]

        if not rating_distribution:
            rating_distribution = [{"rating": "Немає даних", "count": 0}]

        ctx["rating_distribution_json"] = mark_safe(
            json.dumps(rating_distribution, ensure_ascii=False),
        )

        # Аналіз питань — оптимізовано через bulk запити
        question_insights = []
        scale_questions = Question.objects.filter(
            survey__author=user,
            question_type='scale',
        )[:10]  # Топ 10 питань
        
        if scale_questions.exists():
            question_ids = list(scale_questions.values_list('id', flat=True))
            
            # Один bulk запит для всіх відповідей
            all_question_answers = Answer.objects.filter(
                question_id__in=question_ids,
                response_session__status=ResponseSession.Status.COMPLETED,
            ).exclude(text_answer='').values('question_id', 'text_answer')
            
            # Групуємо по питаннях
            from collections import defaultdict
            question_ratings = defaultdict(list)
            for ans in all_question_answers:
                try:
                    val = int(ans['text_answer'])
                    if 1 <= val <= 5:
                        question_ratings[ans['question_id']].append(val)
                except (ValueError, TypeError):
                    pass
            
            # Формуємо insights
            questions_dict = {q.id: q for q in scale_questions}
            for q_id, ratings in question_ratings.items():
                if q_id in questions_dict and ratings:
                    question_insights.append({
                        "question": questions_dict[q_id].text[:100],
                        "avg": round(sum(ratings) / len(ratings), 1),
                        "responses": len(ratings),
                    })

        ctx["question_insights"] = question_insights

        return ctx
