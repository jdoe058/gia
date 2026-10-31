import io

import pytest
from django.core.exceptions import ValidationError

from main.models import Question
from main.services import import_specialty_questions_xlsx


def _rows_valid():
    """Один вопрос с 4 ответами, один правильный."""
    return [
        ['Вопрос', 'Ответ', 'Правильный'],
        ['Q1', 'A1', 'да'],
        [None, 'A2', None],
        [None, 'A3', None],
        [None, 'A4', None],
    ]


# --- Happy path ---

class TestHappyPath:
    def test_valid_file_creates_questions(self, specialty, make_xlsx):
        file = make_xlsx(_rows_valid())
        count = import_specialty_questions_xlsx(specialty, file)

        assert count == 1
        q = specialty.questions.get()
        assert q.text == 'Q1'
        assert q.answers.count() == 4
        assert q.answers.filter(is_correct=True).count() == 1
        assert q.answers.get(is_correct=True).text == 'A1'


# --- Запрет импорта в непустую специальность ---

class TestNonEmptySpecialty:
    def test_specialty_with_questions_rejected(
        self, specialty_with_questions, make_xlsx,
    ):
        file = make_xlsx(_rows_valid())
        with pytest.raises(ValidationError, match='уже есть вопросы'):
            import_specialty_questions_xlsx(specialty_with_questions, file)


# --- Валидация структуры файла ---

class TestFileStructure:
    def test_wrong_headers_rejected(self, specialty, make_xlsx):
        rows = _rows_valid()
        rows[0] = ['Ответ', 'Вопрос', 'Правильный']
        file = make_xlsx(rows)
        with pytest.raises(ValidationError, match='[Зз]аголовк'):
            import_specialty_questions_xlsx(specialty, file)

    def test_no_questions_in_file_rejected(self, specialty, make_xlsx):
        file = make_xlsx([['Вопрос', 'Ответ', 'Правильный']])
        with pytest.raises(ValidationError, match='нет ни одного вопроса'):
            import_specialty_questions_xlsx(specialty, file)

    def test_not_xlsx_handled(self, specialty):
        file = io.BytesIO(b'this is not an xlsx file')
        with pytest.raises(ValidationError, match='[Фф]айл'):
            import_specialty_questions_xlsx(specialty, file)


# --- Валидация вопросов ---

class TestQuestionValidation:
    def test_question_with_no_answers_rejected(self, specialty, make_xlsx):
        file = make_xlsx([
            ['Вопрос', 'Ответ', 'Правильный'],
            ['Q1', None, None],
        ])
        with pytest.raises(ValidationError, match='ответ'):
            import_specialty_questions_xlsx(specialty, file)

    def test_question_with_one_answer_rejected(self, specialty, make_xlsx):
        file = make_xlsx([
            ['Вопрос', 'Ответ', 'Правильный'],
            ['Q1', 'A1', 'да'],
        ])
        with pytest.raises(ValidationError, match='ответ'):
            import_specialty_questions_xlsx(specialty, file)

    def test_question_with_zero_correct_rejected(self, specialty, make_xlsx):
        file = make_xlsx([
            ['Вопрос', 'Ответ', 'Правильный'],
            ['Q1', 'A1', None],
            [None, 'A2', None],
        ])
        with pytest.raises(ValidationError, match='правильн'):
            import_specialty_questions_xlsx(specialty, file)

    def test_question_with_two_correct_rejected(self, specialty, make_xlsx):
        file = make_xlsx([
            ['Вопрос', 'Ответ', 'Правильный'],
            ['Q1', 'A1', 'да'],
            [None, 'A2', 'да'],
        ])
        with pytest.raises(ValidationError, match='правильн'):
            import_specialty_questions_xlsx(specialty, file)


# --- Валидация текстов ---

class TestTextValidation:
    def test_empty_question_text_rejected(self, specialty, make_xlsx):
        file = make_xlsx([
            ['Вопрос', 'Ответ', 'Правильный'],
            ['   ', 'A1', 'да'],
            [None, 'A2', None],
        ])
        with pytest.raises(ValidationError, match='вопрос'):
            import_specialty_questions_xlsx(specialty, file)

    def test_empty_answer_text_rejected(self, specialty, make_xlsx):
        file = make_xlsx([
            ['Вопрос', 'Ответ', 'Правильный'],
            ['Q1', 'A1', 'да'],
            [None, '   ', None],
        ])
        with pytest.raises(ValidationError, match='ответ'):
            import_specialty_questions_xlsx(specialty, file)


# --- Транзакционность ---

class TestAtomicity:
    def test_atomicity_on_error(self, specialty, make_xlsx):
        file = make_xlsx([
            ['Вопрос', 'Ответ', 'Правильный'],
            ['Q1', 'A1', 'да'],
            [None, 'A2', None],
            ['Q2', 'B1', 'да'],
            [None, 'B2', None],
            ['Q3', 'C1', 'да'],
            [None, 'C2', 'да'],   # ошибка: два правильных
            ['Q4', 'D1', 'да'],
            [None, 'D2', None],
        ])
        with pytest.raises(ValidationError):
            import_specialty_questions_xlsx(specialty, file)

        assert Question.objects.filter(specialty=specialty).count() == 0


# --- Устойчивость парсинга ---

class TestParsingRobustness:
    @pytest.mark.parametrize('flag', ['да', 'ДА', 'Да', '1', 'true', 'yes'])
    def test_correct_flag_variants(self, specialty, make_xlsx, flag):
        file = make_xlsx([
            ['Вопрос', 'Ответ', 'Правильный'],
            ['Q1', 'A1', flag],
            [None, 'A2', None],
        ])
        import_specialty_questions_xlsx(specialty, file)
        assert specialty.questions.get().answers.get(is_correct=True).text == 'A1'

    def test_merged_cells_continue_question(self, specialty, make_xlsx):
        file = make_xlsx([
            ['Вопрос', 'Ответ', 'Правильный'],
            ['Q1', 'A1', 'да'],
            [None, 'A2', None],
            [None, 'A3', None],
            [None, 'A4', None],
        ])
        count = import_specialty_questions_xlsx(specialty, file)
        assert count == 1
        assert specialty.questions.get().answers.count() == 4

