from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from django.utils import timezone

from main.services.xlsx import export_student_report_xlsx, get_client_ip

from .forms import StudentLoginForm
from .models import Answer, TestSession
from .services import answer_question, finish_test, start_test_session


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
            # Если это администратор, пускаем его в админку
            if user.is_staff:
                login(request, user)
                return redirect('admin:index')
            else:
                # Если это какой-то странный юзер без профиля и без прав
                form.add_error(
                    None,
                    'Это форма входа для студентов. Администратор входит через /admin/.',
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

    if session.is_expired:
        finish_test(session)
        return redirect('test_result', session_id=session.id)

    if session.is_finished:
        return redirect('test_result', session_id=session.id)

    if session.current_index >= session.total_questions:
        finish_test(session)
        return redirect('test_result', session_id=session.id)

    sq = session.session_questions.select_related('question').get(
        position=session.current_index,
    )

    # ответы в порядке answer_order
    answer_ids = sq.answer_order
    answer_map = {
        a.id: a for a in Answer.objects.filter(id__in=answer_ids)
    }
    answers = [answer_map[aid] for aid in answer_ids if aid in answer_map]

    context = {
        'session': session,
        'sq': sq,
        'question': sq.question,
        'answers': answers,
        'position': session.current_index + 1,
        'total': session.total_questions,
        'deadline_iso': session.deadline_at.isoformat(),
    }
    return render(request, 'main/test.html', context)


@login_required
@require_POST
def answer_view(request, session_id):
    if not hasattr(request.user, 'student_profile'):
        return redirect('login')

    student = request.user.student_profile
    session = get_object_or_404(
        TestSession, id=session_id, student=student,
    )

    try:
        question_id = int(request.POST.get('question_id', 0))
        answer_id = int(request.POST.get('answer_id', 0))
    except (TypeError, ValueError):
        messages.error(request, 'Некорректный ответ.')
        return redirect('test', session_id=session.id)

    try:
        next_sq = answer_question(session, question_id, answer_id)
    except ValidationError as exc:
        for msg in exc.messages:
            messages.error(request, msg)
        return redirect('test', session_id=session.id)

    if next_sq is None:
        finish_test(session)
        return redirect('test_result', session_id=session.id)

    return redirect('test', session_id=session.id)


@login_required
def result_view(request, session_id):
    if not hasattr(request.user, 'student_profile'):
        return redirect('login')

    student = request.user.student_profile
    session = get_object_or_404(
        TestSession, id=session_id, student=student,
    )

    if not session.is_finished:
        finish_test(session)
        session.refresh_from_db()

    wrong_questions = list(
        session.session_questions
        .filter(Q(is_correct=False) | Q(chosen_answer__isnull=True))
        .select_related('question', 'chosen_answer')
        .order_by('position')
    )

    correct_answers = {
        a.question_id: a
        for a in Answer.objects.filter(
            question_id__in=[sq.question_id for sq in wrong_questions],
            is_correct=True,
        )
    }
    for sq in wrong_questions:
        sq.correct_answer = correct_answers.get(sq.question_id)

    context = {
        'session': session,
        'wrong_questions': wrong_questions,
    }
    return render(request, 'main/result.html', context)


@login_required
def student_report_view(request, session_id):
    if not hasattr(request.user, 'student_profile'):
        return redirect('login')

    student = request.user.student_profile
    session = get_object_or_404(TestSession, id=session_id, student=student)

    if not session.is_finished:
        messages.error(request, 'Сначала завершите тестирование, чтобы скачать отчёт.')
        return redirect('student_dashboard')

    try:
        client_ip = get_client_ip(request)
        buffer = export_student_report_xlsx(student, session, client_ip)
    except ValidationError as exc:
        for msg in exc.messages:
            messages.error(request, msg)
        return redirect('student_dashboard')

    filename = f'report_{student.login}_{timezone.now().strftime("%y%m%d")}.xlsx'
    response = HttpResponse(
        buffer.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


def root_view(request):
    if request.user.is_authenticated:
        if hasattr(request.user, 'student_profile'):
            return redirect('student_dashboard')
        return redirect('admin:index')
    return redirect('login')

