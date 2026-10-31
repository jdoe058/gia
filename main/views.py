from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from .forms import StudentLoginForm


def login_view(request):
    if request.user.is_authenticated:
        return redirect('student_dashboard')

    if request.method == 'POST':
        form = StudentLoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            password = form.cleaned_data['password']
            user = authenticate(request, username=username, password=password)
            if user is not None:
                login(request, user)
                return redirect('student_dashboard')
            form.add_error(None, 'Неверный логин или пароль')
    else:
        form = StudentLoginForm()

    return render(request, 'main/login.html', {'form': form})


@login_required
def student_dashboard(request):
    return render(request, 'main/dashboard.html')

