import io
from openpyxl import load_workbook
import pytest
from django.core.exceptions import ValidationError

from main.models import ComputerMapping
from main.services import import_computer_mapping_xlsx, export_computer_mapping_xlsx


def _rows_valid():
    return [
        ['IP', 'Номер'],
        ['192.168.1.10', '1'],
        ['192.168.1.11', '2'],
        ['10.0.0.5', 'Комп-3'],
    ]


class TestImportMappingHappyPath:
    def test_valid_file_creates_mappings(self, make_xlsx, db):
        file = make_xlsx(_rows_valid())
        count = import_computer_mapping_xlsx(file)

        assert count == 3
        assert ComputerMapping.objects.count() == 3
        m = ComputerMapping.objects.get(ip='192.168.1.11')
        assert m.number == '2'
        assert ComputerMapping.objects.filter(ip='10.0.0.5', number='Комп-3').exists()


class TestImportMappingValidation:
    def test_wrong_headers_rejected(self, make_xlsx, db):
        rows = _rows_valid()
        rows[0] = ['IP-адрес', 'Номер']
        file = make_xlsx(rows)
        with pytest.raises(ValidationError, match='[Зз]аголовк'):
            import_computer_mapping_xlsx(file)

    def test_invalid_ip_rejected(self, make_xlsx, db):
        file = make_xlsx([
            ['IP', 'Номер'],
            ['192.168.1.999', '1'],
        ])
        with pytest.raises(ValidationError, match='IP'):
            import_computer_mapping_xlsx(file)

    def test_empty_number_rejected(self, make_xlsx, db):
        file = make_xlsx([
            ['IP', 'Номер'],
            ['192.168.1.10', '   '],
        ])
        with pytest.raises(ValidationError, match='[Нн]омер'):
            import_computer_mapping_xlsx(file)

    def test_duplicate_ip_in_file_rejected(self, make_xlsx, db):
        file = make_xlsx([
            ['IP', 'Номер'],
            ['192.168.1.10', '1'],
            ['192.168.1.10', '2'],
        ])
        with pytest.raises(ValidationError, match='дубликат'):
            import_computer_mapping_xlsx(file)

    def test_existing_mappings_block_import(self, make_xlsx, db):
        ComputerMapping.objects.create(ip='1.1.1.1', number='1')
        file = make_xlsx(_rows_valid())
        
        with pytest.raises(ValidationError, match='уже загружен'):
            import_computer_mapping_xlsx(file)

    def test_atomicity_on_error(self, make_xlsx, db):
        file = make_xlsx([
            ['IP', 'Номер'],
            ['192.168.1.10', '1'],
            ['192.168.1.11', '2'],
            ['999.999.999.999', '3'],  # ошибка в 3-й строке
        ])
        with pytest.raises(ValidationError):
            import_computer_mapping_xlsx(file)

        # ничего не сохранилось
        assert ComputerMapping.objects.count() == 0


class TestExportMapping:
    def test_export_mapping(self, db):
        ComputerMapping.objects.create(ip='192.168.1.10', number='1')
        ComputerMapping.objects.create(ip='10.0.0.5', number='Комп-3')

        buffer = export_computer_mapping_xlsx()
        wb = load_workbook(buffer)
        ws = wb.active

        assert ws.cell(row=1, column=1).value == 'IP'
        assert ws.cell(row=1, column=2).value == 'Номер'
        
        # сортировка по ip: '10.0.0.5' будет первым, '192.168.1.10' вторым
        assert ws.cell(row=2, column=1).value == '10.0.0.5'
        assert ws.cell(row=2, column=2).value == 'Комп-3'
        
        assert ws.cell(row=3, column=1).value == '192.168.1.10'
        assert ws.cell(row=3, column=2).value == '1'

    def test_export_empty_mapping(self, db):
        buffer = export_computer_mapping_xlsx()
        wb = load_workbook(buffer)
        ws = wb.active
        assert ws.max_row == 1  # только шапка

