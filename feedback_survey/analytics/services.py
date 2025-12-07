from __future__ import annotations

import logging
import math
from collections import defaultdict
from statistics import mean, pstdev
from typing import Dict

from responses.models import Answer, ResponseSession
from surveys.models import Question, Survey

logger = logging.getLogger(__name__)


POSITIVE_KEYWORDS = {
    "так",
    "yes",
    "погоджуюся",
    "задоволений",
    "задоволена",
    "чудово",
    "добре",
    "гарно",
    "відмінно",
    "рекомендую",
    "positive",
    "good",
    "great",
    "excellent",
}


def _is_positive_choice(text: str) -> bool:
    normalized = text.strip().lower()
    return any(keyword in normalized for keyword in POSITIVE_KEYWORDS)


def compute_survey_features(survey: Survey) -> Dict[str, float]:
    """
    Aggregate basic statistics for a survey.
    Returns a dictionary containing numerical features that can be used for analytics/ML.
    """
    # Швидка перевірка - якщо немає відповідей, одразу повертаємо
    sessions_qs = ResponseSession.objects.filter(
        survey=survey,
        status=ResponseSession.Status.COMPLETED,
    )
    
    # Оптимізація: об'єднуємо exists() та count() в один запит
    num_responses = sessions_qs.count()
    if num_responses == 0:
        return {"num_responses": 0}
    
    features: dict[str, float] = {
        "num_responses": num_responses,
    }

    # Оптимізація: prefetch questions заздалегідь якщо вони не завантажені
    if not hasattr(survey, '_prefetched_questions'):
        survey.questions.prefetch_related('choices')
    
    # Оптимізація: використовуємо prefetch_related для зменшення запитів
    session_ids = list(sessions_qs.values_list('id', flat=True))
    
    # Один запит для всіх відповідей
    answers = list(Answer.objects.filter(
        response_session_id__in=session_ids
    ).select_related("question", "selected_choice"))

    # Prefetch questions якщо ще не завантажені
    scale_questions = [q for q in survey.questions.all() if q.question_type == Question.QuestionType.SCALE]
    positive_questions = [q for q in survey.questions.all() if q.question_type in [
        Question.QuestionType.SINGLE,
        Question.QuestionType.MULTIPLE,
    ]]

    # Aggregate scale question stats - оптимізовано через фільтрацію
    scale_values_by_question: dict[int, list[float]] = defaultdict(list)
    scale_answers_list = [a for a in answers if a.question.question_type == Question.QuestionType.SCALE]
    for answer in scale_answers_list:
        try:
            value = float(answer.text_answer)
            scale_values_by_question[answer.question_id].append(value)
        except (TypeError, ValueError):
            continue

    for idx, question in enumerate(scale_questions, start=1):
        values = scale_values_by_question.get(question.id, [])
        if not values:
            continue
        features[f"avg_scale_q{idx}"] = mean(values)
        if len(values) > 1:
            features[f"std_scale_q{idx}"] = pstdev(values)
        else:
            features[f"std_scale_q{idx}"] = 0.0

    if scale_values_by_question:
        combined_values = [val for values in scale_values_by_question.values() for val in values]
        if combined_values:
            features["avg_scale_overall"] = mean(combined_values)
            features["std_scale_overall"] = pstdev(combined_values) if len(combined_values) > 1 else 0.0

    # Aggregate positive choice share for single/multiple questions - оптимізовано
    choice_counts_by_question: dict[int, int] = defaultdict(int)
    positive_counts_by_question: dict[int, int] = defaultdict(int)
    
    # Фільтруємо тільки single/multiple відповіді
    choice_answers = [a for a in answers if a.question.question_type in (
        Question.QuestionType.SINGLE,
        Question.QuestionType.MULTIPLE,
    ) and a.selected_choice_id]
    
    for answer in choice_answers:
        choice_counts_by_question[answer.question_id] += 1
        if _is_positive_choice(answer.selected_choice.text):
            positive_counts_by_question[answer.question_id] += 1

    for idx, question in enumerate(positive_questions, start=1):
        total = choice_counts_by_question.get(question.id, 0)
        if total == 0:
            continue
        positive = positive_counts_by_question.get(question.id, 0)
        features[f"positive_share_q{idx}"] = positive / total

    if choice_counts_by_question:
        total_selected = sum(choice_counts_by_question.values())
        total_positive = sum(positive_counts_by_question.values())
        if total_selected:
            features["positive_share_overall"] = total_positive / total_selected

    return features


def _scale_value_to_score(value: float, min_value: float = 1.0, max_value: float = 5.0) -> float:
    if max_value <= min_value:
        return 0.0
    normalized = (value - min_value) / (max_value - min_value)
    return max(0.0, min(1.0, normalized)) * 100


def compute_satisfaction_index(features: dict) -> float:
    """
    Convert aggregated features to a 0-100 satisfaction index.
    """
    scale_scores = []
    positive_scores = []

    for key, value in features.items():
        if value is None:
            continue
        if key.startswith("avg_scale"):
            scale_scores.append(_scale_value_to_score(value))
        elif key.startswith("positive_share"):
            positive_scores.append(value * 100)

    if not scale_scores and not positive_scores:
        return 0.0

    combined = scale_scores + positive_scores
    return sum(combined) / len(combined)


def classify_risk_from_index(index: float, low_threshold: float = 60, high_threshold: float = 75) -> str:
    """
    Map satisfaction index to a qualitative label.
    """
    if index <= low_threshold:
        return "high"
    if index <= high_threshold:
        return "medium"
    return "low"

