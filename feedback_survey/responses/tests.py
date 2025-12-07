from django.contrib.auth import get_user_model
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta

from surveys.models import Survey, Question, Choice
from .models import ResponseSession, Answer

User = get_user_model()


class ResponseSessionModelTest(TestCase):
    """Юніт-тести для моделі ResponseSession"""
    
    def setUp(self):
        self.student = User.objects.create_user(
            username='student',
            password='testpass123',
            role=User.Role.STUDENT
        )
        self.teacher = User.objects.create_user(
            username='teacher',
            password='testpass123',
            role=User.Role.TEACHER
        )
        self.survey = Survey.objects.create(
            title='Test Survey',
            author=self.teacher,
            status=Survey.Status.PUBLISHED,
            start_date=timezone.now() - timedelta(days=1),
            end_date=timezone.now() + timedelta(days=1),
        )
    
    def test_response_session_creation(self):
        """Тест створення сесії відповіді"""
        session = ResponseSession.objects.create(
            user=self.student,
            survey=self.survey,
            status=ResponseSession.Status.IN_PROGRESS
        )
        self.assertEqual(session.user, self.student)
        self.assertEqual(session.survey, self.survey)
        self.assertEqual(session.status, ResponseSession.Status.IN_PROGRESS)
        self.assertIsNotNone(session.started_at)
    
    def test_response_session_statuses(self):
        """Тест різних статусів сесії"""
        in_progress = ResponseSession.objects.create(
            user=self.student,
            survey=self.survey,
            status=ResponseSession.Status.IN_PROGRESS
        )
        completed = ResponseSession.objects.create(
            user=self.student,
            survey=self.survey,
            status=ResponseSession.Status.COMPLETED
        )
        abandoned = ResponseSession.objects.create(
            user=self.student,
            survey=self.survey,
            status=ResponseSession.Status.ABANDONED
        )
        
        self.assertEqual(in_progress.status, ResponseSession.Status.IN_PROGRESS)
        self.assertEqual(completed.status, ResponseSession.Status.COMPLETED)
        self.assertEqual(abandoned.status, ResponseSession.Status.ABANDONED)
    
    def test_response_session_completion(self):
        """Тест завершення сесії"""
        session = ResponseSession.objects.create(
            user=self.student,
            survey=self.survey,
            status=ResponseSession.Status.IN_PROGRESS
        )
        
        session.status = ResponseSession.Status.COMPLETED
        session.completed_at = timezone.now()
        session.save()
        
        self.assertEqual(session.status, ResponseSession.Status.COMPLETED)
        self.assertIsNotNone(session.completed_at)


class AnswerModelTest(TestCase):
    """Юніт-тести для моделі Answer"""
    
    def setUp(self):
        self.student = User.objects.create_user(
            username='student',
            password='testpass123',
            role=User.Role.STUDENT
        )
        self.teacher = User.objects.create_user(
            username='teacher',
            password='testpass123',
            role=User.Role.TEACHER
        )
        self.survey = Survey.objects.create(
            title='Test Survey',
            author=self.teacher
        )
        self.question = Question.objects.create(
            survey=self.survey,
            text='Test Question',
            question_type=Question.QuestionType.SINGLE
        )
        self.choice = Choice.objects.create(
            question=self.question,
            text='Option 1'
        )
        self.session = ResponseSession.objects.create(
            user=self.student,
            survey=self.survey,
            status=ResponseSession.Status.COMPLETED
        )
    
    def test_answer_with_choice(self):
        """Тест відповіді з вибором варіанту"""
        answer = Answer.objects.create(
            response_session=self.session,
            question=self.question,
            selected_choice=self.choice
        )
        self.assertEqual(answer.selected_choice, self.choice)
        # text_answer може бути порожнім рядком замість None
        self.assertIn(answer.text_answer, [None, ''])
    
    def test_answer_with_text(self):
        """Тест текстової відповіді"""
        text_question = Question.objects.create(
            survey=self.survey,
            text='Text Question',
            question_type=Question.QuestionType.TEXT
        )
        answer = Answer.objects.create(
            response_session=self.session,
            question=text_question,
            text_answer='This is a text answer'
        )
        self.assertEqual(answer.text_answer, 'This is a text answer')
        self.assertIsNone(answer.selected_choice)
    
    def test_answer_with_scale(self):
        """Тест відповіді на шкалі"""
        scale_question = Question.objects.create(
            survey=self.survey,
            text='Scale Question',
            question_type=Question.QuestionType.SCALE
        )
        answer = Answer.objects.create(
            response_session=self.session,
            question=scale_question,
            text_answer='4'  # Для scale зберігається в text_answer
        )
        self.assertEqual(answer.text_answer, '4')
        self.assertIsNone(answer.selected_choice)


class TakeSurveyViewTest(TestCase):
    """Інтеграційні тести для TakeSurveyView"""
    
    def setUp(self):
        self.client = Client()
        self.student = User.objects.create_user(
            username='student',
            password='testpass123',
            role=User.Role.STUDENT
        )
        self.teacher = User.objects.create_user(
            username='teacher',
            password='testpass123',
            role=User.Role.TEACHER
        )
        self.survey = Survey.objects.create(
            title='Test Survey',
            description='Test Description',
            author=self.teacher,
            status=Survey.Status.PUBLISHED,
            start_date=timezone.now() - timedelta(days=1),
            end_date=timezone.now() + timedelta(days=1),
        )
        self.question = Question.objects.create(
            survey=self.survey,
            text='Test Question',
            question_type=Question.QuestionType.SCALE
        )
    
    def test_take_survey_access(self):
        """Тест доступу до сторінки проходження опитування"""
        self.client.login(username='student', password='testpass123')
        response = self.client.get(reverse('responses:take-survey', args=[self.survey.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Test Survey')
    
    def test_take_survey_creates_session(self):
        """Тест створення сесії при відкритті опитування"""
        self.client.login(username='student', password='testpass123')
        self.client.get(reverse('responses:take-survey', args=[self.survey.pk]))
        
        session = ResponseSession.objects.filter(
            user=self.student,
            survey=self.survey
        ).first()
        self.assertIsNotNone(session)
        self.assertEqual(session.status, ResponseSession.Status.IN_PROGRESS)
    
    def test_take_survey_prevents_duplicate(self):
        """Тест запобігання повторному проходженню"""
        self.client.login(username='student', password='testpass123')
        
        # Створюємо завершену сесію
        ResponseSession.objects.create(
            user=self.student,
            survey=self.survey,
            status=ResponseSession.Status.COMPLETED
        )
        
        response = self.client.get(reverse('responses:take-survey', args=[self.survey.pk]))
        # Має редіректити на сторінку подяки
        self.assertEqual(response.status_code, 302)
    
    def test_take_survey_validates_required_questions(self):
        """Тест валідації обов'язкових питань"""
        self.client.login(username='student', password='testpass123')
        
        # Відкриваємо опитування
        self.client.get(reverse('responses:take-survey', args=[self.survey.pk]))
        
        # Намагаємося відправити без відповіді
        session = ResponseSession.objects.get(user=self.student, survey=self.survey)
        response = self.client.post(reverse('responses:take-survey', args=[self.survey.pk]), {})
        
        # Має повернути форму з помилками
        self.assertEqual(response.status_code, 200)
        # Перевірка наявності повідомлення про помилку
        messages = list(response.context.get('messages', []))
        self.assertTrue(any('потребує відповіді' in str(msg) for msg in messages))
    
    def test_take_survey_saves_answers(self):
        """Тест збереження відповідей"""
        self.client.login(username='student', password='testpass123')
        
        # Відкриваємо опитування
        self.client.get(reverse('responses:take-survey', args=[self.survey.pk]))
        
        session = ResponseSession.objects.get(user=self.student, survey=self.survey)
        
        # Відправляємо відповідь
        response = self.client.post(reverse('responses:take-survey', args=[self.survey.pk]), {
            f'question_{self.question.pk}': '4'
        })
        
        # Має редіректити на сторінку подяки
        self.assertEqual(response.status_code, 302)
        
        # Перевірка збереження відповіді
        answer = Answer.objects.filter(
            response_session=session,
            question=self.question
        ).first()
        self.assertIsNotNone(answer)
        self.assertEqual(answer.text_answer, '4')
        
        # Перевірка оновлення статусу сесії
        session.refresh_from_db()
        self.assertEqual(session.status, ResponseSession.Status.COMPLETED)
        self.assertIsNotNone(session.completed_at)
    
    def test_take_survey_not_published(self):
        """Тест, що неопубліковане опитування недоступне"""
        draft_survey = Survey.objects.create(
            title='Draft Survey',
            author=self.teacher,
            status=Survey.Status.DRAFT
        )
        
        self.client.login(username='student', password='testpass123')
        response = self.client.get(reverse('responses:take-survey', args=[draft_survey.pk]))
        self.assertEqual(response.status_code, 404)
    
    def test_take_survey_expired(self):
        """Тест, що закінчене опитування недоступне"""
        expired_survey = Survey.objects.create(
            title='Expired Survey',
            author=self.teacher,
            status=Survey.Status.PUBLISHED,
            start_date=timezone.now() - timedelta(days=2),
            end_date=timezone.now() - timedelta(days=1),
        )
        
        self.client.login(username='student', password='testpass123')
        response = self.client.get(reverse('responses:take-survey', args=[expired_survey.pk]))
        # Має редіректити з повідомленням про помилку
        self.assertEqual(response.status_code, 302)


class AnswerTransactionTest(TestCase):
    """Тести транзакційного збереження відповідей"""
    
    def setUp(self):
        self.student = User.objects.create_user(
            username='student',
            password='testpass123',
            role=User.Role.STUDENT
        )
        self.teacher = User.objects.create_user(
            username='teacher',
            password='testpass123',
            role=User.Role.TEACHER
        )
        self.survey = Survey.objects.create(
            title='Test Survey',
            author=self.teacher,
            status=Survey.Status.PUBLISHED
        )
        self.question1 = Question.objects.create(
            survey=self.survey,
            text='Question 1',
            question_type=Question.QuestionType.SCALE
        )
        self.question2 = Question.objects.create(
            survey=self.survey,
            text='Question 2',
            question_type=Question.QuestionType.TEXT
        )
        self.session = ResponseSession.objects.create(
            user=self.student,
            survey=self.survey,
            status=ResponseSession.Status.IN_PROGRESS
        )
    
    def test_all_answers_saved_together(self):
        """Тест, що всі відповіді зберігаються разом"""
        from django.db import transaction
        
        with transaction.atomic():
            Answer.objects.create(
                response_session=self.session,
                question=self.question1,
                text_answer='4'
            )
            Answer.objects.create(
                response_session=self.session,
                question=self.question2,
                text_answer='Test answer'
            )
            self.session.status = ResponseSession.Status.COMPLETED
            self.session.save()
        
        # Перевірка збереження обох відповідей
        answers = Answer.objects.filter(response_session=self.session)
        self.assertEqual(answers.count(), 2)
