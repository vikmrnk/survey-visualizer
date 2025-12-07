from django import forms
from django.forms import inlineformset_factory, BaseInlineFormSet

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
            'order': forms.NumberInput(attrs={'type': 'hidden'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Встановлюємо значення за замовчуванням для order, якщо воно порожнє
        if not self.instance.pk and 'order' in self.fields:
            # Для нових форм встановлюємо order на 0, воно буде оновлено при збереженні
            if not self.initial.get('order'):
                self.initial['order'] = 0
    
    def clean(self):
        cleaned_data = super().clean()
        # Якщо форма призначена до видалення, не валідуємо
        if self.instance and self.instance.pk and cleaned_data.get('DELETE'):
            return cleaned_data
        
        # Встановлюємо значення за замовчуванням для order, якщо воно порожнє
        if 'order' not in cleaned_data or cleaned_data.get('order') is None:
            cleaned_data['order'] = 0
        
        # Перевіряємо, чи форма порожня (для нових форм)
        text = cleaned_data.get('text', '').strip() if cleaned_data.get('text') else ''
        question_type = cleaned_data.get('question_type')
        
        # Якщо форма порожня, не валідуємо (це дозволить ігнорувати порожні форми)
        if not text and not question_type:
            return cleaned_data
        
        # Якщо є хоча б одне поле заповнене, обидва поля обов'язкові
        if (text or question_type) and not text:
            self.add_error('text', 'Введіть текст питання.')
        if (text or question_type) and not question_type:
            self.add_error('question_type', 'Оберіть тип питання.')
        
        return cleaned_data


class QuestionFormSet(BaseInlineFormSet):
    def clean(self):
        """Ігнорує порожні форми при валідації"""
        if any(self.errors):
            return
        
        # Перевіряємо тільки заповнені форми
        for form in self.forms:
            if form in self.deleted_forms:
                continue
            
            # Перевіряємо, чи є cleaned_data (форма була валідована)
            if not hasattr(form, 'cleaned_data') or not form.cleaned_data:
                continue
            
            text = form.cleaned_data.get('text', '').strip() if form.cleaned_data.get('text') else ''
            question_type = form.cleaned_data.get('question_type')
            
            # Якщо форма порожня, пропускаємо валідацію
            if not text and not question_type:
                continue
            
            # Перевіряємо, що обидва поля заповнені для непустих форм
            # Якщо хоча б одне поле заповнене, обидва обов'язкові
            if (text or question_type) and not text:
                raise forms.ValidationError('Введіть текст для всіх питань.')
            if (text or question_type) and not question_type:
                raise forms.ValidationError('Оберіть тип питання для всіх питань.')
    
    def save(self, commit=True):
        """Зберігає тільки непусті форми та обробляє видалення"""
        instances = super().save(commit=False)
        
        # Видаляємо об'єкти, позначені для видалення
        if commit:
            for obj in self.deleted_objects:
                obj.delete()
        
        # Фільтруємо порожні форми
        saved_instances = []
        for instance in instances:
            if instance.text and instance.text.strip() and instance.question_type:
                if commit:
                    instance.save()
                saved_instances.append(instance)
            elif instance.pk:
                # Видаляємо порожні існуючі об'єкти
                if commit:
                    instance.delete()
        
        return saved_instances


class ChoiceForm(forms.ModelForm):
    class Meta:
        model = Choice
        fields = ['text', 'order']
        widgets = {
            'order': forms.HiddenInput(),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # order не обов'язковий – ми самі виставимо його у formset
        self.fields['order'].required = False
    
    def clean(self):
        cleaned_data = super().clean()
        # Якщо форма позначена на видалення – не перевіряємо нічого
        if cleaned_data.get('DELETE'):
            return cleaned_data
        
        text = (cleaned_data.get('text') or '').strip()
        
        # Порожній текст → вважаємо форму "порожньою", не валідуюємо її.
        # BaseChoiceFormSet просто її проігнорує.
        if not text:
            return cleaned_data
        
        cleaned_data['text'] = text
        return cleaned_data


QuestionFormSet = inlineformset_factory(
    Survey,
    Question,
    form=QuestionForm,
    formset=QuestionFormSet,
    fields=['text', 'question_type', 'order'],
    extra=1,
    can_delete=True,
)

class BaseChoiceFormSet(BaseInlineFormSet):
    def save(self, commit=True):
        """
        Зберігаємо лише непорожні варіанти, самі проставляємо order по черзі.
        """
        instances = super().save(commit=False)
        
        saved_instances = []
        current_order = 0
        
        for instance in instances:
            text = (instance.text or '').strip()
            
            # пропускаємо порожні форми
            if not text:
                # якщо це існуючий варіант і текст стерли – видаляємо
                if instance.pk and commit:
                    instance.delete()
                continue
            
            instance.text = text
            
            # якщо order не заданий – ставимо по черзі
            if instance.order is None:
                instance.order = current_order
            current_order += 1
            
            if commit:
                instance.save()
            
            saved_instances.append(instance)
        
        # Видаляємо позначені на видалення
        if commit:
            for obj in self.deleted_objects:
                obj.delete()
        
        return saved_instances


ChoiceFormSet = inlineformset_factory(
    Question,
    Choice,
    form=ChoiceForm,
    formset=BaseChoiceFormSet,
    extra=1,
    can_delete=True,
)

