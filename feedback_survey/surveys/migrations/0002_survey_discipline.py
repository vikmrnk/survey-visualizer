from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('surveys', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='survey',
            name='discipline',
            field=models.CharField(blank=True, help_text='Назва дисципліни або курсу', max_length=255),
        ),
    ]

