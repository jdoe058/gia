from django import forms

class StudentImportForm(forms.Form):
    file = forms.FileField(
        label='XLSX-файл',
        help_text='Файл должен соответствовать шаблону.',
        widget=forms.FileInput(attrs={'class': 'form-control'})
    )

class StudentLoginForm(forms.Form):
    username = forms.CharField(
        label='Логин',
        max_length=150,
        widget=forms.TextInput(attrs={
            'autofocus': True, 
            'autocomplete': 'username',
            'class': 'form-control'
        }),
    )
    password = forms.CharField(
        label='Пароль',
        widget=forms.PasswordInput(attrs={
            'autocomplete': 'current-password',
            'class': 'form-control'
        }),
    )

    def clean_username(self):
        return self.cleaned_data['username'].strip().lower()

