import pytest
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils import timezone

from main.models import TestSession
from main.services import start_test_session


class TestHappyPath:
    def test_creates_session_with_80_questions(
        self, student_user, make_questions,
    ):
        make_questions(student_user.group.specialty, 100)
        session = start_test_session(student_user)
        assert session.session_questions.count() == settings.QUESTIONS_PER_TEST

    def test_exactly_80_in_bank_works(self, student_user, make_questions):
        make_questions(student_user.group.specialty, 80)
        session = start_test_session(student_user)
        assert session.session_questions.count() == 80

    def test_questions_belong_to_student_specialty(
        self, student_user, make_questions,
    ):
        make_questions(student_user.group.specialty, 100)
        session = start_test_session(student_user)
        for sq in session.session_questions.all():
            assert sq.question.specialty_id == student_user.group.specialty_id

    def test_questions_are_unique(self, student_user, make_questions):
        make_questions(student_user.group.specialty, 100)
        session = start_test_session(student_user)
        ids = list(session.session_questions.values_list('question_id', flat=True))
        assert len(ids) == len(set(ids))

    def test_answer_order_is_permutation(self, student_user, make_questions):
        make_questions(student_user.group.specialty, 100)
        session = start_test_session(student_user)
        for sq in session.session_questions.all():
            expected = set(sq.question.answers.values_list('id', flat=True))
            actual = sq.answer_order
            assert set(actual) == expected
            assert len(actual) == len(expected)

    def test_deadline_is_90_minutes(self, student_user, make_questions):
        make_questions(student_user.group.specialty, 100)
        session = start_test_session(student_user)
        delta = session.deadline_at - session.started_at
        assert delta.total_seconds() == settings.TEST_DURATION_MINUTES * 60

    def test_returns_session_with_correct_student(
        self, student_user, make_questions,
    ):
        make_questions(student_user.group.specialty, 100)
        session = start_test_session(student_user)
        assert session.student_id == student_user.id
        assert session.specialty_id == student_user.group.specialty_id
        assert session.total_questions == settings.QUESTIONS_PER_TEST


class TestValidation:
    def test_insufficient_questions_raises(self, student_user, make_questions):
        make_questions(student_user.group.specialty, 79)
        with pytest.raises(ValidationError, match='[Нн]едостаточно вопросов'):
            start_test_session(student_user)

    def test_active_session_blocks_new(self, student_user, make_questions):
        make_questions(student_user.group.specialty, 100)
        start_test_session(student_user)
        with pytest.raises(ValidationError, match='уже проходили'):
            start_test_session(student_user)

    def test_finished_session_blocks_new(
        self, student_user, make_questions, specialty,
    ):
        make_questions(specialty, 100)
        TestSession.objects.create(
            student=student_user,
            specialty=specialty,
            started_at=timezone.now(),
            deadline_at=timezone.now(),
            finished_at=timezone.now(),
            total_questions=80,
        )
        with pytest.raises(ValidationError, match='уже проходили'):
            start_test_session(student_user)