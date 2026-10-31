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