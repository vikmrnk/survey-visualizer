# Feedback Survey

A Django-based survey management system for educational institutions.

## Prerequisites

- Python 3.11 or higher
- PostgreSQL 12 or higher
- pip (Python package manager)

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/vikmrnk/survey-visualizer.git
cd kursova
```

### 2. Create and activate a virtual environment

**On macOS/Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
```

**On Windows:**
```bash
python -m venv venv
venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Set up PostgreSQL database

Create a PostgreSQL database:

```sql
CREATE DATABASE survey_db;
CREATE USER survey_user WITH PASSWORD '******';
GRANT ALL PRIVILEGES ON DATABASE db TO user;
```

### 5. Configure environment variables

Create a `.env` file in the `feedback_survey` directory:

```env
DJANGO_SECRET_KEY=your-secret-key-here
POSTGRES_DB=
POSTGRES_USER=
POSTGRES_PASSWORD=
POSTGRES_HOST=
POSTGRES_PORT=
```

**Note:** Generate a secure secret key using:
```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

**Alternative:** If you don't have PostgreSQL, you can temporarily use SQLite by modifying `feedback_survey/feedback_survey/settings.py`:
```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}
```

### 6. Run migrations

```bash
cd feedback_survey
python manage.py migrate
```

### 7. Create a superuser (optional)

```bash
python manage.py createsuperuser
```

### 8. Collect static files

```bash
python manage.py collectstatic --noinput
```

### 9. Run the development server

```bash
python manage.py runserver
```

The application will be available at `http://127.0.0.1:8000/`

## Project Structure

```
kursova/
├── feedback_survey/          # Main Django project
│   ├── accounts/             # User authentication and profiles
│   ├── surveys/               # Survey management
│   ├── responses/             # Survey responses
│   ├── analytics/             # Analytics and ML features
│   └── feedback_survey/       # Project settings
├── requirements.txt           # Python dependencies
└── README.md                 # This file
```

## Features

- User authentication with role-based access (Student, Teacher, Admin)
- Survey creation and management
- Multiple question types (text, single choice, multiple choice, scale)
- Response collection and analytics
- Machine learning-based survey risk assessment
- User profile settings and preferences

## Development

### Running tests

```bash
python manage.py test
```

### Creating migrations

```bash
python manage.py makemigrations
python manage.py migrate
```

## Requirements

- Django 5.2+
- PostgreSQL 12+
- Python 3.11+

## License

[Add your license here]

