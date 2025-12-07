from django.contrib.auth import get_user_model
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta

from surveys.models import Survey, Question, Choice
from responses.models import ResponseSession, Answer
from .services import compute_survey_features, compute_satisfaction_index, classify_risk_from_index
from .ml_model import predict_survey_risk_proba

User = get_user_model()


class AnalyticsServicesTest(TestCase):
    """Юніт-тести для analytics/services.py"""
    
    def setUp(self):
        self.teacher = User.objects.create_user(
            username='teacher',
            password='testpass123',
            role=User.Role.TEACHER
        )
        self.student1 = User.objects.create_user(
            username='student1',
            password='testpass123',
            role=User.Role.STUDENT
        )
        self.student2 = User.objects.create_user(
            username='student2',
            password='testpass123',
            role=User.Role.STUDENT
        )
        self.survey = Survey.objects.create(
            title='Test Survey',
            author=self.teacher,
            status=Survey.Status.PUBLISHED
        )
        self.scale_question = Question.objects.create(
            survey=self.survey,
            text='Rate the course',
            question_type=Question.QuestionType.SCALE
        )
        self.single_question = Question.objects.create(
            survey=self.survey,
            text='Are you satisfied?',
            question_type=Question.QuestionType.SINGLE
        )
        self.positive_choice = Choice.objects.create(
            question=self.single_question,
            text='Так, задоволений'
        )
        self.negative_choice = Choice.objects.create(
            question=self.single_question,
            text='Ні'
        )
    
    def test_compute_survey_features_no_responses(self):
        """Тест обчислення ознак для опитування без відповідей"""
        features = compute_survey_features(self.survey)
        self.assertEqual(features['num_responses'], 0)
    
    def test_compute_survey_features_scale_questions(self):
        """Тест обчислення ознак для scale питань"""
        # Створюємо сесії та відповіді
        session1 = ResponseSession.objects.create(
            user=self.student1,
            survey=self.survey,
            status=ResponseSession.Status.COMPLETED
        )
        session2 = ResponseSession.objects.create(
            user=self.student2,
            survey=self.survey,
            status=ResponseSession.Status.COMPLETED
        )
        
        Answer.objects.create(
            response_session=session1,
            question=self.scale_question,
            text_answer='4'
        )
        Answer.objects.create(
            response_session=session2,
            question=self.scale_question,
            text_answer='5'
        )
        
        features = compute_survey_features(self.survey)
        self.assertEqual(features['num_responses'], 2)
        self.assertEqual(features['avg_scale_q1'], 4.5)  # (4 + 5) / 2
        self.assertIn('std_scale_q1', features)
    
    def test_compute_survey_features_positive_share(self):
        """Тест обчислення частки позитивних відповідей"""
        session1 = ResponseSession.objects.create(
            user=self.student1,
            survey=self.survey,
            status=ResponseSession.Status.COMPLETED
        )
        session2 = ResponseSession.objects.create(
            user=self.student2,
            survey=self.survey,
            status=ResponseSession.Status.COMPLETED
        )
        
        # Один позитивний, один негативний
        Answer.objects.create(
            response_session=session1,
            question=self.single_question,
            selected_choice=self.positive_choice
        )
        Answer.objects.create(
            response_session=session2,
            question=self.single_question,
            selected_choice=self.negative_choice
        )
        
        features = compute_survey_features(self.survey)
        self.assertEqual(features['positive_share_q1'], 0.5)  # 1 з 2 позитивних
    
    def test_compute_satisfaction_index(self):
        """Тест обчислення індексу задоволеності"""
        # Створюємо дані для тестування
        session = ResponseSession.objects.create(
            user=self.student1,
            survey=self.survey,
            status=ResponseSession.Status.COMPLETED
        )
        
        Answer.objects.create(
            response_session=session,
            question=self.scale_question,
            text_answer='4'  # 4 з 5 = 75% на шкалі 0-100
        )
        Answer.objects.create(
            response_session=session,
            question=self.single_question,
            selected_choice=self.positive_choice  # 100% позитивний
        )
        
        features = compute_survey_features(self.survey)
        index = compute_satisfaction_index(features)
        
        # Індекс має бути між 0 та 100
        self.assertGreaterEqual(index, 0)
        self.assertLessEqual(index, 100)
        # Приблизно (75 + 100) / 2 = 87.5
        self.assertGreater(index, 80)
    
    def test_compute_satisfaction_index_no_data(self):
        """Тест обчислення індексу без даних"""
        features = {'num_responses': 0}
        index = compute_satisfaction_index(features)
        self.assertEqual(index, 0.0)
    
    def test_classify_risk_from_index(self):
        """Тест класифікації ризику на основі індексу"""
        high_risk = classify_risk_from_index(50)  # < 60
        medium_risk = classify_risk_from_index(65)  # 60-75
        low_risk = classify_risk_from_index(80)  # > 75
        
        self.assertEqual(high_risk, 'high')
        self.assertEqual(medium_risk, 'medium')
        self.assertEqual(low_risk, 'low')


class MLModelTest(TestCase):
    """Тести для ML-моделі"""
    
    def setUp(self):
        self.teacher = User.objects.create_user(
            username='teacher',
            password='testpass123',
            role=User.Role.TEACHER
        )
        self.student = User.objects.create_user(
            username='student',
            password='testpass123',
            role=User.Role.STUDENT
        )
        self.survey = Survey.objects.create(
            title='Test Survey',
            author=self.teacher,
            status=Survey.Status.PUBLISHED
        )
        self.question = Question.objects.create(
            survey=self.survey,
            text='Test Question',
            question_type=Question.QuestionType.SCALE
        )
    
    def test_predict_survey_risk_no_responses(self):
        """Тест передбачення ризику для опитування без відповідей"""
        proba = predict_survey_risk_proba(self.survey)
        self.assertIsNone(proba)
    
    def test_predict_survey_risk_with_responses(self):
        """Тест передбачення ризику для опитування з відповідями"""
        # Створюємо сесію з низькою оцінкою (ризикове опитування)
        session = ResponseSession.objects.create(
            user=self.student,
            survey=self.survey,
            status=ResponseSession.Status.COMPLETED
        )
        Answer.objects.create(
            response_session=session,
            question=self.question,
            text_answer='2'  # Низька оцінка
        )
        
        proba = predict_survey_risk_proba(self.survey)
        # Має повернути ймовірність (або fallback)
        self.assertIsNotNone(proba)
        self.assertGreaterEqual(proba, 0.0)
        self.assertLessEqual(proba, 1.0)
    
    def test_predict_survey_risk_fallback(self):
        """Тест fallback логіки при відсутності ML-моделі"""
        session = ResponseSession.objects.create(
            user=self.student,
            survey=self.survey,
            status=ResponseSession.Status.COMPLETED
        )
        Answer.objects.create(
            response_session=session,
            question=self.question,
            text_answer='1'  # Дуже низька оцінка
        )
        
        proba = predict_survey_risk_proba(self.survey)
        # Навіть без ML-моделі має працювати fallback
        self.assertIsNotNone(proba)
        # Для низького satisfaction_index має бути висока ймовірність ризику
        self.assertGreater(proba, 0.5)


class AnalyticsViewsTest(TestCase):
    """Інтеграційні тести для analytics views"""
    
    def setUp(self):
        self.client = Client()
        self.teacher = User.objects.create_user(
            username='teacher',
            password='testpass123',
            role=User.Role.TEACHER
        )
        self.student = User.objects.create_user(
            username='student',
            password='testpass123',
            role=User.Role.STUDENT
        )
        self.survey = Survey.objects.create(
            title='Test Survey',
            author=self.teacher,
            status=Survey.Status.PUBLISHED
        )
    
    def test_analytics_view_teacher_access(self):
        """Тест доступу до аналітики для викладача"""
        self.client.login(username='teacher', password='testpass123')
        response = self.client.get(reverse('analytics:overview'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Аналітика')
    
    def test_analytics_view_student_denied(self):
        """Тест, що студент не може отримати доступ до аналітики"""
        self.client.login(username='student', password='testpass123')
        response = self.client.get(reverse('analytics:overview'))
        self.assertEqual(response.status_code, 403)


class BuildMLDatasetCommandTest(TestCase):
    """Тести для management command build_ml_dataset"""
    
    def setUp(self):
        self.teacher = User.objects.create_user(
            username='teacher',
            password='testpass123',
            role=User.Role.TEACHER
        )
        self.student = User.objects.create_user(
            username='student',
            password='testpass123',
            role=User.Role.STUDENT
        )
        self.survey = Survey.objects.create(
            title='Test Survey',
            author=self.teacher,
            status=Survey.Status.PUBLISHED
        )
        self.question = Question.objects.create(
            survey=self.survey,
            text='Test Question',
            question_type=Question.QuestionType.SCALE
        )
        
        # Створюємо достатньо відповідей
        for i in range(5):
            session = ResponseSession.objects.create(
                user=self.student,
                survey=self.survey,
                status=ResponseSession.Status.COMPLETED
            )
            Answer.objects.create(
                response_session=session,
                question=self.question,
                text_answer=str(3 + (i % 3))  # Значення 3, 4, 5
            )
    
    def test_build_ml_dataset_command(self):
        """Тест виконання команди генерації датасету"""
        from io import StringIO
        from django.core.management import call_command
        
        output = StringIO()
        call_command('build_ml_dataset', '--min-responses', '5', stdout=output)
        
        # Перевірка, що команда виконалася успішно
        output_str = output.getvalue()
        self.assertIn('Dataset saved', output_str)
        
        # Перевірка створення файлу
        from pathlib import Path
        dataset_path = Path('analytics/data/surveys_ml_dataset.csv')
        self.assertTrue(dataset_path.exists())
        
        # Перевірка вмісту файлу
        import pandas as pd
        df = pd.read_csv(dataset_path)
        self.assertGreater(len(df), 0)
        self.assertIn('survey_id', df.columns)
        self.assertIn('satisfaction_index', df.columns)
        self.assertIn('num_responses', df.columns)
