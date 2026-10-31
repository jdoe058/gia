import io
from datetime import date

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Border, Side

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from .students import create_student

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
        cell.font = cell.font.copy(bold=True)

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
        cell.font = cell.font.copy(bold=True)

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
        cell.font = cell.font.copy(bold=True)

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

