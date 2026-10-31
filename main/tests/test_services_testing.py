import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from main.models import SessionQuestion
from main.services import answer_question, finish_test


def _current_sq(session):
    return session.session_questions.get(position=session.current_index)


def _correct_answer(sq):
    return sq.question.answers.get(is_correct=True)


def _incorrect_answer(sq):
    return sq.question.answers.filter(is_correct=False).first()


# --- answer_question ---

class TestAnswerQuestion:
    def test_saves_correct_answer(self, active_session):
        sq = _current_sq(active_session)
        answer = _correct_answer(sq)

        answer_question(active_session, sq.question_id, answer.id)

        sq.refresh_from_db()
        assert sq.chosen_answer_id == answer.id
        assert sq.is_correct is True
        assert sq.answered_at is not None

    def test_saves_incorrect_answer(self, active_session):
        sq = _current_sq(active_session)
        answer = _incorrect_answer(sq)

        answer_question(active_session, sq.question_id, answer.id)

        sq.refresh_from_db()
        assert sq.is_correct is False

    def test_increments_current_index(self, active_session):
        initial = active_session.current_index
        sq = _current_sq(active_session)
        answer = _correct_answer(sq)

        answer_question(active_session, sq.question_id, answer.id)

        active_session.refresh_from_db()
        assert active_session.current_index == initial + 1

    def test_returns_next_question(self, active_session):
        sq = _current_sq(active_session)
        answer = _correct_answer(sq)

        next_sq = answer_question(active_session, sq.question_id, answer.id)

        assert next_sq is not None
        assert next_sq.position == 1

    def test_returns_none_on_last_question(self, active_session):
        # перематываем сессию до последнего вопроса
        for _ in range(79):
            sq = _current_sq(active_session)
            answer_question(
                active_session, sq.question_id, _correct_answer(sq).id,
            )

        # последний
        sq = _current_sq(active_session)
        result = answer_question(
            active_session, sq.question_id, _correct_answer(sq).id,
        )

        assert result is None

    def test_finished_session_raises(self, active_session):
        finish_test(active_session)
        sq = active_session.session_questions.first()
        answer = _correct_answer(sq)

        with pytest.raises(ValidationError, match='завершён'):
            answer_question(active_session, sq.question_id, answer.id)

    def test_expired_session_raises(self, active_session):
        # сдвигаем дедлайн в прошлое
        active_session.deadline_at = timezone.now() - timezone.timedelta(seconds=1)
        active_session.save(update_fields=['deadline_at'])

        sq = _current_sq(active_session)
        answer = _correct_answer(sq)

        with pytest.raises(ValidationError, match='истекло'):
            answer_question(active_session, sq.question_id, answer.id)

    def test_foreign_question_raises(self, active_session, make_questions):
        # создаём вопросы для другой специальности
        from main.models import Specialty
        other_spec = Specialty.objects.create(
            code='99.99.99', name='Другая', slug='other',
        )
        make_questions(other_spec, 1)
        foreign_q = other_spec.questions.first()

        with pytest.raises(ValidationError, match='не принадлежит'):
            answer_question(active_session, foreign_q.id, foreign_q.answers.first().id)

    def test_wrong_position_raises(self, active_session):
        # пытаемся ответить на вопрос «из будущего»
        future_sq = active_session.session_questions.get(position=5)
        answer = _correct_answer(future_sq)

        with pytest.raises(ValidationError, match='не текущий'):
            answer_question(active_session, future_sq.question_id, answer.id)

    def test_already_answered_raises(self, active_session):
        sq = _current_sq(active_session)
        answer = _correct_answer(sq)
        answer_question(active_session, sq.question_id, answer.id)

        # пытаемся ответить повторно — но current_index уже сдвинут,
        # поэтому сначала проверим через прямой вызов с position
        sq_refreshed = SessionQuestion.objects.get(pk=sq.pk)
        with pytest.raises(ValidationError):
            answer_question(active_session, sq_refreshed.question_id, answer.id)

    def test_answer_not_of_question_raises(self, active_session):
        sq = _current_sq(active_session)
        # ответ из другого вопроса
        other_sq = active_session.session_questions.get(position=1)
        foreign_answer = other_sq.question.answers.first()

        with pytest.raises(ValidationError, match='не принадлежит'):
            answer_question(active_session, sq.question_id, foreign_answer.id)


# --- finish_test ---

class TestFinishTest:
    def test_counts_correct(self, active_session):
        # отвечаем на 3 вопроса, 2 правильно, 1 неправильно
        sq = _current_sq(active_session)
        answer_question(active_session, sq.question_id, _correct_answer(sq).id)
        sq = _current_sq(active_session)
        answer_question(active_session, sq.question_id, _correct_answer(sq).id)
        sq = _current_sq(active_session)
        answer_question(active_session, sq.question_id, _incorrect_answer(sq).id)

        finish_test(active_session)

        assert active_session.correct_count == 2
        assert active_session.finished_at is not None

    def test_passed_at_threshold(self, active_session):
        # 56 из 80 = 70% → passed
        for _ in range(56):
            sq = _current_sq(active_session)
            answer_question(active_session, sq.question_id, _correct_answer(sq).id)
        for _ in range(24):
            sq = _current_sq(active_session)
            answer_question(active_session, sq.question_id, _incorrect_answer(sq).id)

        finish_test(active_session)

        assert active_session.correct_count == 56
        assert active_session.passed is True

    def test_failed_below_threshold(self, active_session):
        # 55 из 80 = 68.75% → not passed
        for _ in range(55):
            sq = _current_sq(active_session)
            answer_question(active_session, sq.question_id, _correct_answer(sq).id)
        for _ in range(25):
            sq = _current_sq(active_session)
            answer_question(active_session, sq.question_id, _incorrect_answer(sq).id)

        finish_test(active_session)

        assert active_session.passed is False

    def test_idempotent(self, active_session):
        finish_test(active_session)
        first_finished = active_session.finished_at
        first_correct = active_session.correct_count

        finish_test(active_session)
        active_session.refresh_from_db()

        assert active_session.finished_at == first_finished
        assert active_session.correct_count == first_correct

    def test_unanswered_are_wrong(self, active_session):
        # отвечаем на 0 вопросов
        finish_test(active_session)
        assert active_session.correct_count == 0
        assert active_session.passed is False