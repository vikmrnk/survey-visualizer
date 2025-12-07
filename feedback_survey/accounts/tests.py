from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

User = get_user_model()


class UserModelTest(TestCase):
    """Юніт-тести для моделі User"""
    
    def test_user_creation(self):
        """Тест створення користувача з роллю"""
        user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
            role=User.Role.STUDENT
        )
        self.assertEqual(user.role, User.Role.STUDENT)
        self.assertEqual(user.username, 'testuser')
        self.assertTrue(user.check_password('testpass123'))
    
    def test_user_str_representation(self):
        """Тест рядкового представлення користувача"""
        user = User.objects.create_user(
            username='testuser',
            role=User.Role.TEACHER
        )
        self.assertIn('testuser', str(user))
        self.assertIn('teacher', str(user))
    
    def test_user_roles(self):
        """Тест різних ролей користувачів"""
        student = User.objects.create_user(
            username='student',
            role=User.Role.STUDENT
        )
        teacher = User.objects.create_user(
            username='teacher',
            role=User.Role.TEACHER
        )
        admin = User.objects.create_user(
            username='admin',
            role=User.Role.ADMIN
        )
        
        self.assertEqual(student.role, User.Role.STUDENT)
        self.assertEqual(teacher.role, User.Role.TEACHER)
        self.assertEqual(admin.role, User.Role.ADMIN)


class UserViewsTest(TestCase):
    """Інтеграційні тести для views користувачів"""
    
    def test_login_view(self):
        """Тест сторінки входу"""
        response = self.client.get(reverse('accounts:login'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'login', status_code=200)
    
    def test_register_view(self):
        """Тест сторінки реєстрації"""
        response = self.client.get(reverse('accounts:register'))
        self.assertEqual(response.status_code, 200)
    
    def test_user_registration(self):
        """Тест реєстрації нового користувача"""
        response = self.client.post(reverse('accounts:register'), {
            'username': 'newuser',
            'email': 'newuser@example.com',
            'password1': 'testpass123',
            'password2': 'testpass123',
            'role': User.Role.STUDENT,
        })
        # Після реєстрації має бути редірект
        self.assertIn(response.status_code, [200, 302])
        
        # Перевірка створення користувача
        user = User.objects.get(username='newuser')
        self.assertEqual(user.role, User.Role.STUDENT)
    
    def test_role_based_redirect(self):
        """Тест редіректу після входу залежно від ролі"""
        student = User.objects.create_user(
            username='student',
            password='testpass123',
            role=User.Role.STUDENT
        )
        self.client.login(username='student', password='testpass123')
        
        response = self.client.get(reverse('home'))
        # Має редіректити на список опитувань для студентів
        self.assertEqual(response.status_code, 302)
        
        teacher = User.objects.create_user(
            username='teacher',
            password='testpass123',
            role=User.Role.TEACHER
        )
        self.client.login(username='teacher', password='testpass123')
        
        response = self.client.get(reverse('home'))
        # Має редіректити на дашборд викладача
        self.assertEqual(response.status_code, 302)
