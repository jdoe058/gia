import pytest
from django.urls import reverse
from django.utils import timezone

from main.models import Answer, TestSession


def _current_sq(session):
    return session.session_questions.get(position=session.current_index)


class TestTestView:
    def test_shows_current_question(self, client, active_session):
        client.force_login(active_session.student.user)
        response = client.get(reverse('test', args=[active_session.id]))
        assert response.status_code == 200
        sq = _current_sq(active_session)
        content = response.content.decode()
        assert sq.question.text in content
        assert 'Вопрос <strong>1</strong>' in content or 'Вопрос 1' in content

    def test_answers_in_answer_order(self, client, active_session):
        client.force_login(active_session.student.user)
        response = client.get(reverse('test', args=[active_session.id]))
        sq = _current_sq(active_session)
        content = response.content.decode()
        positions = [content.index(f'value="{aid}"') for aid in sq.answer_order]
        assert positions == sorted(positions)

    def test_expired_finishes_and_redirects(self, client, active_session):
        active_session.deadline_at = timezone.now() - timezone.timedelta(seconds=1)
        active_session.save(update_fields=['deadline_at'])

        client.force_login(active_session.student.user)
        response = client.get(reverse('test', args=[active_session.id]))
        assert response.status_code == 302
        assert reverse('test_result', args=[active_session.id]) in response.url

        active_session.refresh_from_db()
        assert active_session.is_finished

    def test_finished_redirects(self, client, active_session):
        from main.services import finish_test
        finish_test(active_session)

        client.force_login(active_session.student.user)
        response = client.get(reverse('test', args=[active_session.id]))
        assert response.status_code == 302
        assert reverse('test_result', args=[active_session.id]) in response.url

    def test_all_answered_finishes(self, client, active_session):
        active_session.current_index = active_session.total_questions
        active_session.save(update_fields=['current_index'])

        client.force_login(active_session.student.user)
        response = client.get(reverse('test', args=[active_session.id]))
        assert response.status_code == 302
        assert reverse('test_result', args=[active_session.id]) in response.url

        active_session.refresh_from_db()
        assert active_session.is_finished

    def test_other_student_404(self, client, active_session, db):
        from main.services import create_student
        other = create_student(
            active_session.student.group, 'Петров', 'Пётр', '',
        )
        client.force_login(other.user)
        response = client.get(reverse('test', args=[active_session.id]))
        assert response.status_code == 404


class TestAnswerView:
    def test_correct_answer_redirects_to_next(self, client, active_session):
        sq = _current_sq(active_session)
        answer = sq.question.answers.get(is_correct=True)

        client.force_login(active_session.student.user)
        response = client.post(
            reverse('answer', args=[active_session.id]),
            {'question_id': sq.question_id, 'answer_id': answer.id},
        )
        assert response.status_code == 302
        assert reverse('test', args=[active_session.id]) in response.url

        active_session.refresh_from_db()
        assert active_session.current_index == 1

    def test_last_answer_finishes_and_redirects(self, client, active_session):
        # перематываем на последний вопрос
        for _ in range(active_session.total_questions - 1):
            sq = _current_sq(active_session)
            answer = sq.question.answers.get(is_correct=True)
            client.force_login(active_session.student.user) if not client.session.get('_auth_user_id') else None
            from main.services import answer_question
            answer_question(active_session, sq.question_id, answer.id)
        active_session.refresh_from_db()

        sq = _current_sq(active_session)
        answer = sq.question.answers.get(is_correct=True)
        client.force_login(active_session.student.user)
        response = client.post(
            reverse('answer', args=[active_session.id]),
            {'question_id': sq.question_id, 'answer_id': answer.id},
        )
        assert response.status_code == 302
        assert reverse('test_result', args=[active_session.id]) in response.url

        active_session.refresh_from_db()
        assert active_session.is_finished

    def test_get_not_allowed(self, client, active_session):
        client.force_login(active_session.student.user)
        response = client.get(reverse('answer', args=[active_session.id]))
        assert response.status_code == 405

    def test_invalid_question_id_shows_error(self, client, active_session):
        client.force_login(active_session.student.user)
        response = client.post(
            reverse('answer', args=[active_session.id]),
            {'question_id': 'not_a_number', 'answer_id': 1},
            follow=True,
        )
        assert response.status_code == 200
        assert 'Некорректный ответ' in response.content.decode()

