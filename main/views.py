from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import StudentLoginForm
from .models import TestSession
from .services import start_test_session


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

    student = request.user.student_profile
    specialty = student.group.specialty

    active_session = TestSession.objects.filter(
        student=student, specialty=specialty, finished_at__isnull=True,
    ).first()
    finished_session = TestSession.objects.filter(
        student=student, specialty=specialty, finished_at__isnull=False,
    ).first()

    questions_available = specialty.questions.count()
    questions_needed = settings.QUESTIONS_PER_TEST
    enough_questions = questions_available >= questions_needed

    context = {
        'student': student,
        'specialty': specialty,
        'active_session': active_session,
        'finished_session': finished_session,
        'questions_available': questions_available,
        'questions_needed': questions_needed,
        'enough_questions': enough_questions,
        'duration_minutes': settings.TEST_DURATION_MINUTES,
        'pass_threshold': settings.PASS_THRESHOLD_PERCENT,
    }
    return render(request, 'main/dashboard.html', context)


@login_required
@require_POST
def start_test_view(request):
    if not hasattr(request.user, 'student_profile'):
        return redirect('login')

    student = request.user.student_profile
    try:
        session = start_test_session(student)
    except ValidationError as exc:
        for msg in exc.messages:
            messages.error(request, msg)
        return redirect('student_dashboard')

    return redirect('test', session_id=session.id)


@login_required
def test_view(request, session_id):
    if not hasattr(request.user, 'student_profile'):
        return redirect('login')

    student = request.user.student_profile
    session = get_object_or_404(
        TestSession, id=session_id, student=student,
    )

    if session.is_finished:
        return redirect('student_dashboard')

    # Заглушка — страница прохождения появится в блоке Г
    return render(request, 'main/test_stub.html', {'session': session})
