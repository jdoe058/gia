import io

from openpyxl import Workbook, load_workbook

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from openpyxl import Workbook, load_workbook

from .students import create_student

TEMPLATE_HEADERS = ['Фамилия', 'Имя', 'Отчество']
TEMPLATE_EXAMPLES = [
    ['Иванов Апостал', 'Иван', 'Иванович'],
    ['Петров', 'Пётр', ''],
    ['Сидорова', 'Анна Степанида', 'Сергеевна'],
]

IMPORT_HEADERS = ('Фамилия', 'Имя', 'Отчество')

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

