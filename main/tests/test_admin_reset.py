import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from main.models import SessionQuestion, TestSession

User = get_user_model()


@pytest.fixture
def admin_client(client, db):
    """Клиент, залогиненный как суперпользователь."""
    admin = User.objects.create_superuser(
        username='admin', password='adminpass123',
    )
    client.force_login(admin)
    return client


class TestResetSessionsAction:
    def test_resets_selected_sessions(
        self, admin_client, student_user, make_questions,
    ):
        from main.services import start_test_session
        make_questions(student_user.group.specialty, 100)
        session = start_test_session(student_user)
        assert SessionQuestion.objects.filter(session=session).count() == 80

        response = admin_client.post(
            reverse('admin:main_testsession_changelist'),
            {
                'action': 'reset_sessions',
                '_selected_action': [session.id],
            },
            follow=True,
        )
        assert response.status_code == 200
        assert not TestSession.objects.filter(id=session.id).exists()
        assert SessionQuestion.objects.filter(session_id=session.id).count() == 0

    def test_reset_allows_new_test(
        self, admin_client, student_user, make_questions,
    ):
        from main.services import start_test_session
        make_questions(student_user.group.specialty, 100)
        session = start_test_session(student_user)

        # сбрасываем
        admin_client.post(
            reverse('admin:main_testsession_changelist'),
            {
                'action': 'reset_sessions',
                '_selected_action': [session.id],
            },
        )

        # можно стартовать заново
        new_session = start_test_session(student_user)
        assert new_session.id != session.id
        assert new_session.session_questions.count() == 80

    def test_message_reports_count(
        self, admin_client, student_user, make_questions,
    ):
        from main.services import start_test_session
        make_questions(student_user.group.specialty, 100)
        session = start_test_session(student_user)

        response = admin_client.post(
            reverse('admin:main_testsession_changelist'),
            {
                'action': 'reset_sessions',
                '_selected_action': [session.id],
            },
            follow=True,
        )
        content = response.content.decode()
        assert 'Сброшено сессий: 1' in content

    def test_multiple_sessions_reset(
        self, admin_client, student_user, make_questions, db,
    ):
        from main.models import Group
        from main.services import create_student, start_test_session

        make_questions(student_user.group.specialty, 100)
        s1 = start_test_session(student_user)

        # второй студент в другой группе с той же специальностью
        # (или в той же — тогда нужно переопределить specialty у студента)
        # создаём группу с другой специальностью не нужно —
        # просто второго студента в той же группе
        other = create_student(
            student_user.group, 'Петров', 'Пётр', '',
        )
        s2 = start_test_session(other)

        response = admin_client.post(
            reverse('admin:main_testsession_changelist'),
            {
                'action': 'reset_sessions',
                '_selected_action': [s1.id, s2.id],
            },
            follow=True,
        )
        assert not TestSession.objects.filter(id__in=[s1.id, s2.id]).exists()
        content = response.content.decode()
        assert 'Сброшено сессий: 2' in content

    def test_delete_selected_removed(
        self, admin_client, student_user, make_questions,
    ):
        """Стандартный delete_selected убран из доступных действий."""
        from main.services import start_test_session
        make_questions(student_user.group.specialty, 100)
        start_test_session(student_user)  # <-- без сессии changelist пуст

        response = admin_client.get(
            reverse('admin:main_testsession_changelist'),
        )
        content = response.content.decode()
        assert 'Сбросить сессии' in content
        assert 'Удалить выбранные' not in content