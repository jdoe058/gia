from django import forms


class StudentImportForm(forms.Form):
    file = forms.FileField(
        label='XLSX-файл',
        help_text='Файл должен соответствовать шаблону (Фамилия, Имя, Отчество).',
    )

    def clean_file(self):
        f = self.cleaned_data['file']
        if not f.name.lower().endswith('.xlsx'):
            raise forms.ValidationError('Принимаются только файлы .xlsx.')
        if f.size > 1_000_000:
            raise forms.ValidationError('Файл слишком большой (максимум 1 МБ).')
        return f


class StudentLoginForm(forms.Form):
    username = forms.CharField(
        label='Логин',
        max_length=150,
        widget=forms.TextInput(attrs={'autofocus': True, 'autocomplete': 'username'}),
    )
    password = forms.CharField(
        label='Пароль',
        widget=forms.PasswordInput(attrs={'autocomplete': 'current-password'}),
    )

    def clean_username(self):
        return self.cleaned_data['username'].strip().lower()

