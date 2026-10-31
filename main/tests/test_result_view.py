import pytest
from django.urls import reverse

from main.models import Answer, SessionQuestion
from main.services import answer_question, finish_test


def _answer_n(session, n_correct, n_wrong):
    """Отвечает на n_correct правильных и n_wrong неправильных подряд."""
    for _ in range(n_correct):
        sq = session.session_questions.get(position=session.current_index)
        answer = sq.question.answers.get(is_correct=True)
        answer_question(session, sq.question_id, answer.id)
    for _ in range(n_wrong):
        sq = session.session_questions.get(position=session.current_index)
        answer = sq.question.answers.filter(is_correct=False).first()
        answer_question(session, sq.question_id, answer.id)


class TestResultView:
    def test_finished_result_renders(self, client, active_session):
        _answer_n(active_session, 60, 20)
        finish_test(active_session)
        active_session.refresh_from_db()

        client.force_login(active_session.student.user)
        response = client.get(reverse('test_result', args=[active_session.id]))
        assert response.status_code == 200
        content = response.content.decode()
        assert 'Результат тестирования' in content
        assert '60' in content
        assert 'из 80' in content
        assert '75,0%' in content
        assert 'Зачёт' in content

    def test_failed_result_shows_nezachet(self, client, active_session):
        _answer_n(active_session, 40, 40)
        finish_test(active_session)

        client.force_login(active_session.student.user)
        response = client.get(reverse('test_result', args=[active_session.id]))
        content = response.content.decode()
        assert 'Незачёт' in content
        assert 'Зачёт' not in content.replace('Незачёт', '')

    def test_correct_answers_not_shown(self, client, active_session):
        _answer_n(active_session, 5, 2)
        finish_test(active_session)

        client.force_login(active_session.student.user)
        response = client.get(reverse('test_result', args=[active_session.id]))
        content = response.content.decode()

        correct_positions = list(
            active_session.session_questions.filter(is_correct=True)
            .values_list('position', flat=True)
        )
        for pos in correct_positions:
            sq = active_session.session_questions.get(position=pos)
            # точная строка, как она рендерится в шаблоне:
            # "Вопрос {pos+1}. {question_text}"
            assert f'Вопрос {pos + 1}. {sq.question.text}' not in content

    def test_wrong_answers_shown_with_correct(self, client, active_session):
        _answer_n(active_session, 0, 3)
        finish_test(active_session)

        client.force_login(active_session.student.user)
        response = client.get(reverse('test_result', args=[active_session.id]))
        content = response.content.decode()

        wrong = active_session.session_questions.filter(is_correct=False).order_by('position')[:3]
        for sq in wrong:
            assert sq.question.text in content
            assert sq.chosen_answer.text in content
            correct_answer = sq.question.answers.get(is_correct=True)
            assert correct_answer.text in content

    def test_unanswered_shown_as_no_answer(self, client, active_session):
        _answer_n(active_session, 0, 2)
        # остальные 78 не отвечены
        finish_test(active_session)

        client.force_login(active_session.student.user)
        response = client.get(reverse('test_result', args=[active_session.id]))
        content = response.content.decode()
        assert 'Нет ответа' in content

    def test_all_correct_shows_success(self, client, active_session):
        _answer_n(active_session, 80, 0)
        finish_test(active_session)

        client.force_login(active_session.student.user)
        response = client.get(reverse('test_result', args=[active_session.id]))
        content = response.content.decode()
        assert 'Ни одной ошибки' in content
        assert 'Отличный результат' in content

    def test_auto_finishes_if_not_finished(self, client, active_session):
        # не вызываем finish_test — view должен сделать это сам
        _answer_n(active_session, 3, 0)

        client.force_login(active_session.student.user)
        response = client.get(reverse('test_result', args=[active_session.id]))
        assert response.status_code == 200

        active_session.refresh_from_db()
        assert active_session.is_finished
        assert active_session.correct_count == 3

    def test_other_student_404(self, client, active_session, db):
        from main.services import create_student
        finish_test(active_session)

        other = create_student(active_session.student.group, 'Петров', 'Пётр', '')
        client.force_login(other.user)
        response = client.get(reverse('test_result', args=[active_session.id]))
        assert response.status_code == 404

    def test_requires_login(self, client, active_session):
        finish_test(active_session)
        response = client.get(reverse('test_result', args=[active_session.id]))
        assert response.status_code == 302
        assert reverse('login') in response.url