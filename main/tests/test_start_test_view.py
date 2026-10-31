import pytest
from django.urls import reverse

from main.models import TestSession


class TestStartTestView:
    def test_requires_login(self, client):
        response = client.post(reverse('start_test'))
        assert response.status_code == 302
        assert reverse('login') in response.url

    def test_requires_post(self, client, student_user):
        client.force_login(student_user.user)
        response = client.get(reverse('start_test'))
        assert response.status_code == 405

    def test_success_creates_session_and_redirects(
        self, client, student_user, make_questions,
    ):
        make_questions(student_user.group.specialty, 100)
        client.force_login(student_user.user)
        response = client.post(reverse('start_test'))
        assert response.status_code == 302

        session = TestSession.objects.get(student=student_user)
        assert response.url == reverse('test', args=[session.id])
        assert session.session_questions.count() == 80

    def test_insufficient_questions_shows_error(
        self, client, student_user, make_questions,
    ):
        make_questions(student_user.group.specialty, 79)
        client.force_login(student_user.user)
        response = client.post(reverse('start_test'), follow=True)
        assert response.status_code == 200
        content = response.content.decode()
        assert 'Недостаточно вопросов' in content
        assert not TestSession.objects.filter(student=student_user).exists()

    def test_second_start_blocked(
        self, client, student_user, make_questions,
    ):
        make_questions(student_user.group.specialty, 100)
        client.force_login(student_user.user)
        client.post(reverse('start_test'))

        response = client.post(reverse('start_test'), follow=True)
        content = response.content.decode()
        assert 'уже проходили' in content
        assert TestSession.objects.filter(student=student_user).count() == 1


class TestTestView:
    def test_requires_login(self, client, student_user, make_questions):
        make_questions(student_user.group.specialty, 100)
        client.force_login(student_user.user)
        client.post(reverse('start_test'))
        session = TestSession.objects.get(student=student_user)

        client.logout()
        response = client.get(reverse('test', args=[session.id]))
        assert response.status_code == 302
        assert reverse('login') in response.url

    def test_other_student_session_404(
        self, client, student_user, make_questions, db,
    ):
        """Чужой session_id — 404, не показываем."""
        from main.models import Group, Student
        from main.services import create_student
        from django.contrib.auth import get_user_model

        make_questions(student_user.group.specialty, 100)
        client.force_login(student_user.user)
        client.post(reverse('start_test'))
        session = TestSession.objects.get(student=student_user)

        # второй студент в той же группе
        other = create_student(
            student_user.group, 'Петров', 'Пётр', '',
        )
        client.force_login(other.user)
        response = client.get(reverse('test', args=[session.id]))
        assert response.status_code == 404


class TestDashboardStates:
    def test_shows_start_button_when_no_session(
        self, client, student_user, make_questions,
    ):
        make_questions(student_user.group.specialty, 100)
        client.force_login(student_user.user)
        response = client.get(reverse('student_dashboard'))
        content = response.content.decode()
        assert 'Начать тест' in content
        assert 'Продолжить' not in content

    def test_shows_continue_when_active(
        self, client, student_user, make_questions,
    ):
        make_questions(student_user.group.specialty, 100)
        client.force_login(student_user.user)
        client.post(reverse('start_test'))
        response = client.get(reverse('student_dashboard'))
        content = response.content.decode()
        assert 'Продолжить' in content
        assert 'Начать тест' not in content

    def test_shows_result_when_finished(
        self, client, student_user, make_questions,
    ):
        from django.utils import timezone
        make_questions(student_user.group.specialty, 100)
        TestSession.objects.create(
            student=student_user,
            specialty=student_user.group.specialty,
            started_at=timezone.now(),
            deadline_at=timezone.now(),
            finished_at=timezone.now(),
            total_questions=80,
            correct_count=60,
            passed=False,
        )
        client.force_login(student_user.user)
        response = client.get(reverse('student_dashboard'))
        content = response.content.decode()
        assert 'Незачёт' in content
        assert '60' in content

    def test_shows_insufficient_when_bank_small(
        self, client, student_user, make_questions,
    ):
        make_questions(student_user.group.specialty, 50)
        client.force_login(student_user.user)
        response = client.get(reverse('student_dashboard'))
        content = response.content.decode()
        assert 'Недостаточно вопросов' in content
        assert '50 из 80' in content