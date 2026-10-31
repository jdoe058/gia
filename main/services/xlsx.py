import io
from copy import copy
from datetime import date

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Border, Side

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from .students import create_student
from main.models import Answer, Question

TEMPLATE_HEADERS = ['Фамилия', 'Имя', 'Отчество']
TEMPLATE_EXAMPLES = [
    ['Иванов Апостал', 'Иван', 'Иванович'],
    ['Петров', 'Пётр', ''],
    ['Сидорова', 'Анна Степанида', 'Сергеевна'],
]

IMPORT_HEADERS = ('Фамилия', 'Имя', 'Отчество')


def export_group_xlsx(group):
    """
    Возвращает BytesIO с XLSX-раздаткой для группы.

    Структура:
    - строка 1: специальность, группа, дата одной строкой через запятую;
    - строка 2: пустая (отступ перед таблицей);
    - строка 3: заголовки колонок (ФИО, Логин, Пароль);
    - строки 4+: студенты, отсортированные по slug.
    """
    wb = Workbook()
    ws = wb.active
    ws.title = 'Раздатка'

    specialty = group.specialty
    title = (
        f'{specialty.name} ({specialty.code}), '
        f'{group.name}, '
        f'{date.today().strftime("%d.%m.%Y")}'
    )
    ws.append([title])
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=3)
    ws.cell(row=1, column=1).font = ws.cell(row=1, column=1).font.copy(
        bold=True, size=12
    )
    ws.cell(row=1, column=1).alignment = ws.cell(row=1, column=1).alignment.copy(
        horizontal='center'
    )

    ws.append([])

    ws.append(['ФИО', 'Логин', 'Пароль'])
    for cell in ws[3]:
        font = copy(cell.font)
        font.bold = True
        cell.font = font

    students = group.students.select_related('user').order_by('slug')
    for student in students:
        ws.append([student.full_name_short, student.login, student.plain_password])

    ws.column_dimensions['A'].width = 30
    ws.column_dimensions['B'].width = 15
    ws.column_dimensions['C'].width = 12

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer


def build_import_template_xlsx():
    """
    Возвращает BytesIO с XLSX-шаблоном для загрузки студентов.

    Структура: три колонки (Фамилия, Имя, Отчество) с тремя примерами.
    Отчество может быть пустым — это иллюстрирует вторая строка.
    """
    wb = Workbook()
    ws = wb.active
    ws.title = 'Студенты'

    ws.append(TEMPLATE_HEADERS)
    for row in TEMPLATE_EXAMPLES:
        ws.append(row)

    ws.column_dimensions['A'].width = 20
    ws.column_dimensions['B'].width = 20
    ws.column_dimensions['C'].width = 25

    # Жирная шапка — чтобы при открытии сразу бросалась в глаза
    for cell in ws[1]:
        font = copy(cell.font)
        font.bold = True
        cell.font = font

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer


def import_students_from_xlsx(group, file_obj):
    """
    Импортирует студентов из XLSX в указанную группу.

    Требования:
    - Группа должна быть пустой (иначе — ошибка).
    - Первая строка файла — заголовки: Фамилия, Имя, Отчество.
    - Фамилия и Имя обязательны, Отчество — опционально.
    - Полностью пустые строки пропускаются.
    - При любой ошибке — откат всей транзакции.

    Возвращает количество созданных студентов.
    """
    if group.students.exists():
        raise ValidationError(
            f'В группе «{group.name}» уже есть студенты. '
            f'Удалите группу целиком, чтобы загрузить новый список.'
        )

    try:
        wb = load_workbook(file_obj, data_only=True)
    except Exception as exc:
        raise ValidationError(f'Не удалось прочитать файл: {exc}')

    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    wb.close()

    if not rows:
        raise ValidationError('Файл пуст.')

    header = tuple((c or '').strip() if c is not None else '' for c in rows[0][:3])
    if header != IMPORT_HEADERS:
        raise ValidationError(
            f'Неверные заголовки. Ожидается: {", ".join(IMPORT_HEADERS)}. '
            f'Получено: {", ".join(header)}.'
        )

    errors = []
    valid_rows = []
    for idx, row in enumerate(rows[1:], start=2):
        cells = list(row[:3]) + [None] * (3 - len(row[:3]))
        last_name = (cells[0] or '').strip() if cells[0] is not None else ''
        first_name = (cells[1] or '').strip() if cells[1] is not None else ''
        middle_name = (cells[2] or '').strip() if cells[2] is not None else ''

        if not last_name and not first_name and not middle_name:
            continue

        if not last_name:
            errors.append(f'Строка {idx}: пустая фамилия.')
            continue
        if not first_name:
            errors.append(f'Строка {idx}: пустое имя.')
            continue

        valid_rows.append((last_name, first_name, middle_name))

    if errors:
        raise ValidationError(errors)

    if not valid_rows:
        raise ValidationError('В файле нет ни одной заполненной строки.')

    try:
        with transaction.atomic():
            for last_name, first_name, middle_name in valid_rows:
                create_student(group, last_name, first_name, middle_name)
    except IntegrityError as exc:
        raise ValidationError(f'Ошибка при сохранении: {exc}')

    return len(valid_rows)


def export_specialty_questions_xlsx(specialty):
    """
    Возвращает BytesIO с XLSX-файлом вопросов специальности.

    Формат:
    - колонки: Вопрос | Ответ | Правильный
    - одна строка = один ответ
    - ячейка вопроса объединена на все ответы вопроса
    - в колонке «Правильный» — «да» у правильного ответа, пусто у остальных
    - текст вопросов и ответов переносится по словам
    - начало каждого вопроса отделено горизонтальной чертой
    """
    wb = Workbook()
    ws = wb.active
    ws.title = 'Вопросы'

    ws.append(['Вопрос', 'Ответ', 'Правильный'])
    for cell in ws[1]:
        font = copy(cell.font)
        font.bold = True
        cell.font = font

    wrap_top = Alignment(wrap_text=True, vertical='top', horizontal='left')
    wrap_center = Alignment(wrap_text=True, vertical='top', horizontal='center')
    top_border = Border(top=Side(style='thin', color='999999'))

    questions = specialty.questions.prefetch_related('answers').order_by('id')

    current_row = 2
    for question in questions:
        answers = list(question.answers.all())

        if not answers:
            cell_q = ws.cell(row=current_row, column=1, value=question.text)
            cell_q.alignment = wrap_top
            cell_q.border = top_border
            ws.cell(row=current_row, column=2, value='').alignment = wrap_top
            ws.cell(row=current_row, column=2).border = top_border
            ws.cell(row=current_row, column=3, value='').alignment = wrap_center
            ws.cell(row=current_row, column=3).border = top_border
            current_row += 1
            continue

        start_row = current_row
        for idx, answer in enumerate(answers):
            cell_q = ws.cell(
                row=current_row, column=1,
                value=question.text if idx == 0 else None,
            )
            cell_a = ws.cell(row=current_row, column=2, value=answer.text)
            cell_c = ws.cell(
                row=current_row, column=3,
                value='да' if answer.is_correct else '',
            )
            cell_q.alignment = wrap_top
            cell_a.alignment = wrap_top
            cell_c.alignment = wrap_center

            if idx == 0:
                cell_q.border = top_border
                cell_a.border = top_border
                cell_c.border = top_border

            current_row += 1

        end_row = current_row - 1
        if end_row > start_row:
            ws.merge_cells(
                start_row=start_row, start_column=1,
                end_row=end_row, end_column=1,
            )

    ws.column_dimensions['A'].width = 60
    ws.column_dimensions['B'].width = 40
    ws.column_dimensions['C'].width = 12

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer


QUESTIONS_HEADERS = ('Вопрос', 'Ответ', 'Правильный')
CORRECT_FLAG_VALUES = {'да', '1', 'true', 'yes'}


def import_specialty_questions_xlsx(specialty, file_obj):
    """
    Импортирует вопросы специальности из XLSX.

    Формат:
    - заголовки: Вопрос | Ответ | Правильный
    - одна строка = один ответ; ячейка вопроса объединена на все ответы
    - «Правильный»: «да» (или 1/true/yes) у правильного, пусто у остальных
    - у вопроса минимум 2 ответа, ровно 1 правильный

    Требования:
    - специальность пуста
    - при любой ошибке — откат всей транзакции

    Возвращает количество созданных вопросов.
    """
    if specialty.questions.exists():
        raise ValidationError(
            f'У специальности «{specialty.name}» уже есть вопросы. '
            f'Удалите их перед повторной загрузкой.'
        )

    try:
        wb = load_workbook(file_obj, data_only=True)
    except Exception as exc:
        raise ValidationError(f'Не удалось прочитать файл: {exc}')

    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    wb.close()

    if not rows:
        raise ValidationError('Файл пуст.')

    header = tuple(
        (c or '').strip() if c is not None else ''
        for c in rows[0][:3]
    )
    if header != QUESTIONS_HEADERS:
        raise ValidationError(
            f'Неверные заголовки. Ожидается: {", ".join(QUESTIONS_HEADERS)}. '
            f'Получено: {", ".join(header)}.'
        )

    errors = []
    blocks = []  # [(текст_вопроса, [(текст_ответа, is_correct), ...]), ...]
    cur_text = None
    cur_row = None
    cur_answers = []

    def _flush():
        nonlocal cur_text, cur_row, cur_answers
        if cur_text is None:
            return
        if not cur_answers:
            errors.append(f'Строка {cur_row}: у вопроса нет ответов.')
        elif len(cur_answers) < 2:
            errors.append(f'Строка {cur_row}: у вопроса меньше 2 ответов.')
        else:
            correct = sum(1 for _, c in cur_answers if c)
            if correct != 1:
                errors.append(
                    f'Строка {cur_row}: у вопроса {correct} правильных ответов, '
                    f'должен быть ровно 1.'
                )
            else:
                blocks.append((cur_text, list(cur_answers)))
        cur_text = None
        cur_row = None
        cur_answers = []

    for idx, row in enumerate(rows[1:], start=2):
        cells = list(row[:3]) + [None] * (3 - len(row[:3]))
        raw_q, raw_a, raw_f = cells[0], cells[1], cells[2]

        # полностью пустая строка — пропускаем
        if raw_q is None and raw_a is None and raw_f is None:
            continue

        q_cell = (raw_q or '').strip() if raw_q is not None else None
        a_cell = (raw_a or '').strip() if raw_a is not None else ''
        f_cell = (raw_f or '').strip() if raw_f is not None else ''

        if raw_q is not None:
            # новая строка вопроса — закрываем предыдущий блок
            _flush()
            if not q_cell:
                errors.append(f'Строка {idx}: пустой текст вопроса.')
                continue
            cur_text = q_cell
            cur_row = idx
            cur_answers = []
        elif cur_text is None:
            errors.append(f'Строка {idx}: ответ без вопроса.')
            continue

        if not a_cell:
            errors.append(f'Строка {idx}: пустой текст ответа.')
            continue

        cur_answers.append((a_cell, f_cell.lower() in CORRECT_FLAG_VALUES))

    _flush()

    if errors:
        raise ValidationError(errors)

    if not blocks:
        raise ValidationError('В файле нет ни одного вопроса.')

    try:
        with transaction.atomic():
            for q_text, answers in blocks:
                question = Question.objects.create(specialty=specialty, text=q_text)
                Answer.objects.bulk_create([
                    Answer(question=question, text=a_text, is_correct=is_c)
                    for a_text, is_c in answers
                ])
    except IntegrityError as exc:
        raise ValidationError(f'Ошибка при сохранении: {exc}')

    return len(blocks)

