import io
import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.core.files.uploadedfile import SimpleUploadedFile
from openpyxl import load_workbook

from main.models import ReportTemplate, ComputerMapping, Commission
from main.services.xlsx import build_report_template_xlsx, export_student_report_xlsx
from main.services.testing import finish_test, start_test_session


@pytest.fixture
def setup_template(db):
    buffer = build_report_template_xlsx()
    file = SimpleUploadedFile('template.xlsx', buffer.read(), content_type='application/vnd...')
    return ReportTemplate.objects.create(template_type='individual', file=file)


@pytest.fixture
def setup_commission(student_user, db):
    return Commission.objects.create(
        group=student_user.group,
        chairman='Иванов И.И.',
        member1='Петров П.П.',
        member2='Сидоров С.С.',
        member3='Смирнов С.С.',
        secretary='Козлова К.К.'
    )


def test_export_missing_template_raises(student_user, active_session):
    finish_test(active_session)
    with pytest.raises(ValidationError, match='Шаблон'):
        export_student_report_xlsx(student_user, active_session)


def test_export_fills_data(student_user, active_session, setup_template, setup_commission):
    # 56 правильных из 80
    for i in range(80):
        sq = active_session.session_questions.get(position=active_session.current_index)
        ans = sq.question.answers.filter(is_correct=(i < 56)).first()
        from main.services import answer_question
        answer_question(active_session, sq.question_id, ans.id)
    
    finish_test(active_session)
    
    ComputerMapping.objects.create(ip='192.168.1.10', number='Комп-7')

    buffer = export_student_report_xlsx(
        student_user, active_session, client_ip='192.168.1.10'
    )
    
    wb = load_workbook(buffer)
    ws = wb.active

    # Проверяем, что плейсхолдеры заменились
    cells = [cell.value for row in ws.iter_rows() for cell in row if cell.value]
    text = "\n".join(str(c) for c in cells)

    assert 'Иванов' in text
    assert 'sd2101' in text
    assert '34.02.01' in text
    assert 'Сестринское дело' in text
    assert '56' in text
    assert '80' in text
    assert '70,0' in text # процент с запятой
    assert 'Зачёт' in text
    assert 'Комп-7' in text
    assert 'Иванов И.И.' in text # председатель
    assert '{{' not in text # не должно остаться незаполненных плейсхолдеров


def test_export_empty_mapping_and_commission(student_user, active_session, setup_template):
    finish_test(active_session)
    # нет комиссии, нет маппинга, пустой ip
    buffer = export_student_report_xlsx(student_user, active_session, client_ip='1.2.3.4')
    wb = load_workbook(buffer)
    cells = [cell.value for row in wb.active.iter_rows() for cell in row if cell.value]
    text = "\n".join(str(c) for c in cells)

    assert 'Незачёт' in text
    assert '{{computer_number}}' not in text
    assert '{{commission_chairman}}' not in text