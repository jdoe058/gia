import io

from openpyxl import Workbook

TEMPLATE_HEADERS = ['Фамилия', 'Имя', 'Отчество']
TEMPLATE_EXAMPLES = [
    ['Иванов', 'Иван', 'Иванович'],
    ['Петров', 'Пётр', ''],
    ['Сидорова', 'Анна', 'Сергеевна'],
]


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

