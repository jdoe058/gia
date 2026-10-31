import io

import pytest
from openpyxl import Workbook

from django.contrib.auth import get_user_model

from main.models import Answer, Question, Specialty
from main.services import start_test_session


@pytest.fixture
def make_xlsx():
    """
    Возвращает функцию, которая собирает XLSX из списка строк (list of lists).

    Каждая строка — список из 3 ячеек: Вопрос, Ответ, Правильный.
    Значение None в ячейке = пустая ячейка. Возвращает BytesIO.
    """
    def _make(rows):
        wb = Workbook()
        ws = wb.active
        for row in rows:
            ws.append(row)
        buffer = io.BytesIO()
        wb.save(buffer)
        buffer.seek(0)
        return buffer

    return _make


@pytest.fixture
def specialty(db):
    return Specialty.objects.create(
        code='34.02.01', name='Сестринское дело', slug='sd',
    )


@pytest.fixture
def specialty_with_questions(specialty):
    q = Question.objects.create(specialty=specialty, text='Старый вопрос')
    Answer.objects.create(question=q, text='A1', is_correct=True)
    Answer.objects.create(question=q, text='A2')
    return specialty


User = get_user_model()


@pytest.fixture
def student_user(db, specialty):
    """
    Студент с логином и паролем, готовый к входу.
    Использует существующую фикстуру specialty (слаг 'sd').
    """
    from main.models import Group
    from main.services import create_student

    group = Group.objects.create(
        name='СД-21', slug='sd21', course=2,
        financing='budget', base='9', specialty=specialty,
    )
    return create_student(group, 'Иванов', 'Иван', 'Иванович')


@pytest.fixture
def admin_user(db):
    return User.objects.create_superuser(
        username='admin', password='adminpass123',
    )


@pytest.fixture
def make_questions():
    """
    Возвращает функцию, которая создаёт N вопросов с 4 ответами
    (первый правильный) в указанной специальности.
    """
    def _make(specialty, count):
        for i in range(count):
            q = Question.objects.create(
                specialty=specialty,
                text=f'Вопрос {i + 1}',
            )
            for j, correct in enumerate([True, False, False, False]):
                Answer.objects.create(
                    question=q,
                    text=f'Ответ {i + 1}.{j + 1}',
                    is_correct=correct,
                )

    return _make


@pytest.fixture
def active_session(student_user, make_questions):
    """Готовая сессия студента с 80 вопросами."""
    make_questions(student_user.group.specialty, 100)
    return start_test_session(student_user)

