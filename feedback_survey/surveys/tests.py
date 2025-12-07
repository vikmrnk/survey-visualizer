from django.contrib.auth import get_user_model
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta

from .models import Survey, Question, Choice

User = get_user_model()


class SurveyModelTest(TestCase):
    """Юніт-тести для моделі Survey"""
    
    def setUp(self):
        self.teacher = User.objects.create_user(
            username='teacher',
            password='testpass123',
            role=User.Role.TEACHER
        )
    
    def test_survey_creation(self):
        """Тест створення опитування"""
        survey = Survey.objects.create(
            title='Test Survey',
            description='Test Description',
            author=self.teacher,
            status=Survey.Status.DRAFT
        )
        self.assertEqual(survey.title, 'Test Survey')
        self.assertEqual(survey.author, self.teacher)
        self.assertEqual(survey.status, Survey.Status.DRAFT)
    
    def test_survey_str_representation(self):
        """Тест рядкового представлення опитування"""
        survey = Survey.objects.create(
            title='Test Survey',
            author=self.teacher,
            status=Survey.Status.PUBLISHED
        )
        self.assertIn('Test Survey', str(survey))
        self.assertIn('Published', str(survey))
    
    def test_survey_status_choices(self):
        """Тест різних статусів опитування"""
        draft = Survey.objects.create(
            title='Draft',
            author=self.teacher,
            status=Survey.Status.DRAFT
        )
        published = Survey.objects.create(
            title='Published',
            author=self.teacher,
            status=Survey.Status.PUBLISHED
        )
        closed = Survey.objects.create(
            title='Closed',
            author=self.teacher,
            status=Survey.Status.CLOSED
        )
        
        self.assertEqual(draft.status, Survey.Status.DRAFT)
        self.assertEqual(published.status, Survey.Status.PUBLISHED)
        self.assertEqual(closed.status, Survey.Status.CLOSED)


class QuestionModelTest(TestCase):
    """Юніт-тести для моделі Question"""
    
    def setUp(self):
        self.teacher = User.objects.create_user(
            username='teacher',
            password='testpass123',
            role=User.Role.TEACHER
        )
        self.survey = Survey.objects.create(
            title='Test Survey',
            author=self.teacher
        )
    
    def test_question_creation(self):
        """Тест створення питання"""
        question = Question.objects.create(
            survey=self.survey,
            text='Test Question',
            question_type=Question.QuestionType.SCALE,
            order=1
        )
        self.assertEqual(question.text, 'Test Question')
        self.assertEqual(question.question_type, Question.QuestionType.SCALE)
        self.assertEqual(question.order, 1)
    
    def test_question_types(self):
        """Тест різних типів питань"""
        single = Question.objects.create(
            survey=self.survey,
            text='Single',
            question_type=Question.QuestionType.SINGLE
        )
        multiple = Question.objects.create(
            survey=self.survey,
            text='Multiple',
            question_type=Question.QuestionType.MULTIPLE
        )
        scale = Question.objects.create(
            survey=self.survey,
            text='Scale',
            question_type=Question.QuestionType.SCALE
        )
        text = Question.objects.create(
            survey=self.survey,
            text='Text',
            question_type=Question.QuestionType.TEXT
        )
        
        self.assertEqual(single.question_type, Question.QuestionType.SINGLE)
        self.assertEqual(multiple.question_type, Question.QuestionType.MULTIPLE)
        self.assertEqual(scale.question_type, Question.QuestionType.SCALE)
        self.assertEqual(text.question_type, Question.QuestionType.TEXT)
    
    def test_question_ordering(self):
        """Тест порядку питань"""
        q1 = Question.objects.create(
            survey=self.survey,
            text='Question 1',
            order=2
        )
        q2 = Question.objects.create(
            survey=self.survey,
            text='Question 2',
            order=1
        )
        
        questions = list(self.survey.questions.all())
        self.assertEqual(questions[0], q2)  # Менший order перший
        self.assertEqual(questions[1], q1)


class ChoiceModelTest(TestCase):
    """Юніт-тести для моделі Choice"""
    
    def setUp(self):
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
    
    def test_choice_creation(self):
        """Тест створення варіанту відповіді"""
        choice = Choice.objects.create(
            question=self.question,
            text='Option 1',
            order=1
        )
        self.assertEqual(choice.text, 'Option 1')
        self.assertEqual(choice.question, self.question)
        self.assertEqual(choice.order, 1)
    
    def test_choice_ordering(self):
        """Тест порядку варіантів"""
        c1 = Choice.objects.create(question=self.question, text='C1', order=2)
        c2 = Choice.objects.create(question=self.question, text='C2', order=1)
        
        choices = list(self.question.choices.all())
        self.assertEqual(choices[0], c2)
        self.assertEqual(choices[1], c1)


class SurveyViewsTest(TestCase):
    """Інтеграційні тести для views опитувань"""
    
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
            description='Test Description',
            author=self.teacher,
            status=Survey.Status.PUBLISHED,
            start_date=timezone.now() - timedelta(days=1),
            end_date=timezone.now() + timedelta(days=1),
        )
    
    def test_teacher_dashboard_access(self):
        """Тест доступу до дашборду викладача"""
        self.client.login(username='teacher', password='testpass123')
        response = self.client.get(reverse('surveys:teacher-dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Панель управління')
    
    def test_student_cannot_access_teacher_dashboard(self):
        """Тест, що студент не може отримати доступ до дашборду викладача"""
        self.client.login(username='student', password='testpass123')
        response = self.client.get(reverse('surveys:teacher-dashboard'))
        self.assertEqual(response.status_code, 403)  # Forbidden
    
    def test_survey_list_for_student(self):
        """Тест списку опитувань для студента"""
        self.client.login(username='student', password='testpass123')
        response = self.client.get(reverse('surveys:student-survey-list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Test Survey')
    
    def test_survey_create_view(self):
        """Тест створення опитування"""
        self.client.login(username='teacher', password='testpass123')
        response = self.client.get(reverse('surveys:create'))
        self.assertEqual(response.status_code, 200)
    
    def test_survey_creation_post(self):
        """Тест POST запиту для створення опитування"""
        self.client.login(username='teacher', password='testpass123')
        response = self.client.post(reverse('surveys:create'), {
            'title': 'New Survey',
            'description': 'New Description',
            'discipline': 'Test Discipline',
            'status': Survey.Status.DRAFT,
        })
        # Має редіректити після створення
        self.assertEqual(response.status_code, 302)
        
        # Перевірка створення опитування
        survey = Survey.objects.get(title='New Survey')
        self.assertEqual(survey.author, self.teacher)
        self.assertEqual(survey.status, Survey.Status.DRAFT)
    
    def test_survey_edit_view(self):
        """Тест редагування опитування"""
        self.client.login(username='teacher', password='testpass123')
        response = self.client.get(reverse('surveys:edit', args=[self.survey.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Test Survey')
    
    def test_student_cannot_edit_survey(self):
        """Тест, що студент не може редагувати опитування"""
        self.client.login(username='student', password='testpass123')
        response = self.client.get(reverse('surveys:edit', args=[self.survey.pk]))
        self.assertEqual(response.status_code, 403)
    
    def test_survey_manage_list(self):
        """Тест списку опитувань для викладача"""
        self.client.login(username='teacher', password='testpass123')
        response = self.client.get(reverse('surveys:manage-list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Test Survey')
    
    def test_survey_filtering_by_status(self):
        """Тест фільтрації опитувань за статусом"""
        Survey.objects.create(
            title='Draft Survey',
            author=self.teacher,
            status=Survey.Status.DRAFT
        )
        
        self.client.login(username='teacher', password='testpass123')
        response = self.client.get(reverse('surveys:manage-list') + '?status=draft')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Draft Survey')


class SurveyFormsTest(TestCase):
    """Тести для форм опитувань"""
    
    def setUp(self):
        self.teacher = User.objects.create_user(
            username='teacher',
            password='testpass123',
            role=User.Role.TEACHER
        )
    
    def test_survey_form_validation(self):
        """Тест валідації форми опитування"""
        from .forms import SurveyForm
        
        # Тест валідації дат
        form = SurveyForm({
            'title': 'Test Survey',
            'start_date': timezone.now() + timedelta(days=1),
            'end_date': timezone.now(),  # Дата завершення раніше початку
        })
        self.assertFalse(form.is_valid())
        self.assertIn('end_date', form.errors)
    
    def test_survey_form_valid_dates(self):
        """Тест форми з валідними датами"""
        from .forms import SurveyForm
        
        form = SurveyForm({
            'title': 'Test Survey',
            'description': 'Test Description',
            'start_date': timezone.now(),
            'end_date': timezone.now() + timedelta(days=1),
        })
        self.assertTrue(form.is_valid())
