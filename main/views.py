from django.contrib.auth import authenticate, login, logout
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
            if user is None:
                form.add_error(None, 'Неверный логин или пароль')
            elif not hasattr(user, 'student_profile'):
                form.add_error(
                    None,
                    'Это форма входа для студентов. '
                    'Администратор входит через /admin/.',
                )
            else:
                login(request, user)
                return redirect('student_dashboard')
    else:
        form = StudentLoginForm()

    return render(request, 'main/login.html', {'form': form})


def logout_view(request):
    logout(request)
    return redirect('login')


@login_required
def student_dashboard(request):
    if not hasattr(request.user, 'student_profile'):
        logout(request)
        return redirect('login')
    return render(request, 'main/dashboard.html')