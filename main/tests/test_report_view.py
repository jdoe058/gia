from django.core.files.uploadedfile import SimpleUploadedFile

from main.models import ReportTemplate

import pytest
from django.urls import reverse
from main.services import finish_test, build_report_template_xlsx


class TestReportView:
    def test_requires_login(self, client, active_session):
        response = client.get(reverse('student_report', args=[active_session.id]))
        assert response.status_code == 302
        assert reverse('login') in response.url

    def test_other_student_404(self, client, active_session, db):
        from main.services import create_student
        other = create_student(active_session.student.group, 'Петров', 'Пётр', '')
        client.force_login(other.user)
        response = client.get(reverse('student_report', args=[active_session.id]))
        assert response.status_code == 404

    def test_redirects_if_not_finished(self, client, active_session):
        client.force_login(active_session.student.user)
        response = client.get(reverse('student_report', args=[active_session.id]), follow=True)
        assert response.status_code == 200
        assert 'Сначала завершите тестирование' in response.content.decode()

    def test_downloads_xlsx(self, client, active_session, setup_template):
        finish_test(active_session)
        client.force_login(active_session.student.user)
        
        response = client.get(reverse('student_report', args=[active_session.id]))
        
        assert response.status_code == 200
        assert response['Content-Type'] == 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        assert 'attachment; filename=' in response['Content-Disposition']
        assert len(response.content) > 0

    def test_missing_template_shows_error(self, client, active_session):
        finish_test(active_session)
        client.force_login(active_session.student.user)
        
        # Шаблон не загружен (setup_template не используется)
        response = client.get(reverse('student_report', args=[active_session.id]), follow=True)
        
        assert response.status_code == 200
        assert 'Шаблон индивидуального отчёта не загружен' in response.content.decode()


@pytest.fixture
def setup_summary_template(db):
    buffer = build_report_template_xlsx()
    file = SimpleUploadedFile('summary.xlsx', buffer.read(), content_type='application/vnd...')
    return ReportTemplate.objects.create(template_type='summary', file=file)


@pytest.fixture
def setup_individual_template(db):
    buffer = build_report_template_xlsx()
    file = SimpleUploadedFile('individual.xlsx', buffer.read(), content_type='application/vnd...')
    return ReportTemplate.objects.create(template_type='individual', file=file)


class TestAdminReportViews:
    def test_group_summary_download(
        self, admin_client, student_user, setup_summary_template
    ):
        url = reverse('admin:main_group_export_summary', args=[student_user.group.id])
        response = admin_client.get(url)
        
        assert response.status_code == 200
        assert response['Content-Type'] == 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        assert 'summary_' in response['Content-Disposition']

    def test_group_summary_missing_template(
        self, admin_client, student_user, follow=True
    ):
        url = reverse('admin:main_group_export_summary', args=[student_user.group.id])
        response = admin_client.get(url, follow=True)
        
        # Редирект на страницу группы с сообщением
        assert response.status_code == 200
        assert 'Шаблон сводного отчёта не загружен' in response.content.decode()

    def test_student_report_download(
        self, admin_client, student_user, setup_individual_template
    ):
        url = reverse('admin:main_student_export_report', args=[student_user.id])
        response = admin_client.get(url)
        
        assert response.status_code == 200
        assert response['Content-Type'] == 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        assert 'report_' in response['Content-Disposition']