import pytest

from main.models import Answer, Question
from main.services import (
    export_specialty_questions_xlsx,
    import_specialty_questions_xlsx,
)


@pytest.fixture
def specialty_with_three_questions(specialty):
    """Три вопроса с разными текстами и правильными ответами."""
    data = [
        ('Q1 АНАЛИЗ МОЧИ', [
            ('A1', True), ('A2', False), ('A3', False), ('A4', False),
        ]),
        ('Q2 УМЕНЬШЕНИЕ ЧАСТОТЫ', [
            ('B1', False), ('B2', True), ('B3', False), ('B4', False),
        ]),
        ('Q3 РЕАКЦИЯ СРЕДЫ', [
            ('C1', False), ('C2', False), ('C3', False), ('C4', True),
        ]),
    ]
    for q_text, answers in data:
        q = Question.objects.create(specialty=specialty, text=q_text)
        for a_text, is_c in answers:
            Answer.objects.create(question=q, text=a_text, is_correct=is_c)
    return specialty


def _snapshot(specialty):
    """Снимок данных специальности для сравнения после round-trip."""
    result = []
    for q in specialty.questions.order_by('text'):
        answers = sorted(
            [(a.text, a.is_correct) for a in q.answers.all()],
            key=lambda x: x[0],
        )
        result.append((q.text, answers))
    return result


class TestRoundTrip:
    def test_export_import_preserves_data(self, specialty_with_three_questions):
        original = _snapshot(specialty_with_three_questions)

        # экспорт → XLSX
        buffer = export_specialty_questions_xlsx(specialty_with_three_questions)

        # очистка БД (имитируем «импорт в чистую специальность»)
        Question.objects.filter(
            specialty=specialty_with_three_questions,
        ).delete()

        # импорт из того же файла
        count = import_specialty_questions_xlsx(
            specialty_with_three_questions, buffer,
        )

        # сравнение
        assert count == 3
        assert _snapshot(specialty_with_three_questions) == original

