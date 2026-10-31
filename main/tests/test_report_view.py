import pytest
from django.urls import reverse
from main.services import finish_test


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