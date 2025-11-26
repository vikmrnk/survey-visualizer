from django import forms
from django.forms import inlineformset_factory

from .models import Choice, Question, Survey


class SurveyFilterForm(forms.Form):
    status = forms.ChoiceField(
        choices=[('', 'Усі статуси'), *Survey.Status.choices],
        required=False,
        label='Статус',
    )
    discipline = forms.ChoiceField(required=False, label='Дисципліна')
    start_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date'}),
        label='Початок після',
    )
    end_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date'}),
        label='Завершення до',
    )

    def __init__(self, *args, discipline_choices: list[str] | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        choices = [('', 'Усі дисципліни')]
        if discipline_choices:
            choices += [(value, value) for value in discipline_choices]
        self.fields['discipline'].choices = choices


class SurveyForm(forms.ModelForm):
    datetime_format = '%Y-%m-%dT%H:%M'
    start_date = forms.DateTimeField(
        required=False,
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local'}, format=datetime_format),
        input_formats=[datetime_format],
        label='Дата початку',
    )
    end_date = forms.DateTimeField(
        required=False,
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local'}, format=datetime_format),
        input_formats=[datetime_format],
        label='Дата завершення',
    )

    class Meta:
        model = Survey
        fields = ['title', 'description', 'target', 'discipline', 'start_date', 'end_date']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
        }

    def clean(self):
        cleaned_data = super().clean()
        start = cleaned_data.get('start_date')
        end = cleaned_data.get('end_date')
        if start and end and start > end:
            self.add_error('end_date', 'Дата завершення має бути після дати початку.')
        return cleaned_data


class QuestionForm(forms.ModelForm):
    class Meta:
        model = Question
        fields = ['text', 'question_type', 'order']
        widgets = {
            'text': forms.Textarea(attrs={'rows': 2}),
        }


class ChoiceForm(forms.ModelForm):
    class Meta:
        model = Choice
        fields = ['text', 'order']


QuestionFormSet = inlineformset_factory(
    Survey,
    Question,
    form=QuestionForm,
    fields=['text', 'question_type', 'order'],
    extra=1,
    can_delete=True,
)

ChoiceFormSet = inlineformset_factory(
    Question,
    Choice,
    form=ChoiceForm,
    extra=1,
    can_delete=True,
)

