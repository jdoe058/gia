import random
from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from main.models import Question, SessionQuestion, TestSession


def start_test_session(student):
    """
    Создаёт сессию тестирования для студента.

    Берёт settings.QUESTIONS_PER_TEST случайных вопросов из банка
    специальности студента, перемешивает ответы, сохраняет порядок
    в SessionQuestion.answer_order.

    Требования:
    - в банке достаточно вопросов;
    - у студента ещё нет сессии по этой специальности.

    Возвращает TestSession.
    """
    specialty = student.group.specialty
    bank_qs = Question.objects.filter(specialty=specialty)
    bank_count = bank_qs.count()
    if bank_count < settings.QUESTIONS_PER_TEST:
        raise ValidationError(
            f'Недостаточно вопросов: в банке {bank_count}, '
            f'нужно {settings.QUESTIONS_PER_TEST}.'
        )

    if TestSession.objects.filter(
        student=student, specialty=specialty,
    ).exists():
        raise ValidationError(
            'Вы уже проходили тест по этой специальности. '
            'Обратитесь к администратору для сброса.'
        )

    question_ids = list(bank_qs.values_list('id', flat=True))
    chosen_ids = random.sample(question_ids, settings.QUESTIONS_PER_TEST)

    questions = {
        q.id: q
        for q in Question.objects
        .filter(id__in=chosen_ids)
        .prefetch_related('answers')
    }

    now = timezone.now()
    deadline = now + timedelta(minutes=settings.TEST_DURATION_MINUTES)

    try:
        with transaction.atomic():
            session = TestSession.objects.create(
                student=student,
                specialty=specialty,
                started_at=now,
                deadline_at=deadline,
                total_questions=settings.QUESTIONS_PER_TEST,
            )

            session_questions = []
            for position, q_id in enumerate(chosen_ids):
                q = questions[q_id]
                answer_ids = list(q.answers.values_list('id', flat=True))
                random.shuffle(answer_ids)
                session_questions.append(SessionQuestion(
                    session=session,
                    question=q,
                    position=position,
                    answer_order=answer_ids,
                ))
            SessionQuestion.objects.bulk_create(session_questions)
    except IntegrityError as exc:
        raise ValidationError(f'Ошибка при создании сессии: {exc}')

    return session


def finish_test(session):
    """
    Завершает сессию: считает правильные, ставит passed и finished_at.
    Идемпотентно — повторный вызов ничего не меняет.
    """
    if session.is_finished:
        return session

    correct = session.session_questions.filter(is_correct=True).count()
    total = session.total_questions
    # без float: correct * 100 / total >= threshold
    # → correct * 100 >= total * threshold
    passed = correct * 100 >= total * settings.PASS_THRESHOLD_PERCENT

    with transaction.atomic():
        session.correct_count = correct
        session.passed = passed
        session.finished_at = timezone.now()
        session.save(update_fields=['correct_count', 'passed', 'finished_at'])

    return session


def answer_question(session, question_id, answer_id):
    """
    Сохраняет ответ студента на текущий вопрос сессии.

    Возвращает следующую SessionQuestion или None, если это был последний
    (сессия при этом НЕ завершается — это делает вызывающий код).
    """
    if session.is_finished:
        raise ValidationError('Тест уже завершён.')

    if session.is_expired:
        raise ValidationError('Время теста истекло.')

    try:
        sq = SessionQuestion.objects.select_related('question').get(
            session=session, question_id=question_id,
        )
    except SessionQuestion.DoesNotExist:
        raise ValidationError('Вопрос не принадлежит этой сессии.')

    if sq.position != session.current_index:
        raise ValidationError('Это не текущий вопрос.')

    if sq.chosen_answer_id is not None:
        raise ValidationError('Ответ на этот вопрос уже дан.')

    answer = sq.question.answers.filter(id=answer_id).first()
    if answer is None:
        raise ValidationError('Ответ не принадлежит этому вопросу.')

    with transaction.atomic():
        sq.chosen_answer = answer
        sq.is_correct = answer.is_correct
        sq.answered_at = timezone.now()
        sq.save(update_fields=['chosen_answer', 'is_correct', 'answered_at'])

        session.current_index += 1
        session.save(update_fields=['current_index'])

    return session.session_questions.filter(position=session.current_index).first()

