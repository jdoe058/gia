import pytest
from django.urls import reverse


# --- Вход ---

class TestLogin:
    def test_valid_credentials_redirect_to_dashboard(
        self, client, student_user,
    ):
        response = client.post(reverse('login'), {
            'username': student_user.login,
            'password': student_user.plain_password,
        })
        assert response.status_code == 302
        assert response.url == reverse('student_dashboard')

        # пользователь реально авторизован
        dashboard = client.get(reverse('student_dashboard'))
        assert dashboard.status_code == 200
        assert dashboard.context['user'] == student_user.user

    def test_invalid_password_shows_error(self, client, student_user):
        response = client.post(reverse('login'), {
            'username': student_user.login,
            'password': 'wrong',
        })
        assert response.status_code == 200
        assert 'Неверный логин или пароль' in response.content.decode()

        # сессия не создана
        assert not client.session.get('_auth_user_id')

    def test_username_case_insensitive(self, client, student_user):
        response = client.post(reverse('login'), {
            'username': student_user.login.upper(),
            'password': student_user.plain_password,
        })
        assert response.status_code == 302
        assert response.url == reverse('student_dashboard')

    def test_admin_rejected_on_login_form(self, client, admin_user):
        response = client.post(reverse('login'), {
            'username': admin_user.username,
            'password': 'adminpass123',
        })
        assert response.status_code == 200
        assert 'форма входа для студентов' in response.content.decode()

        # сессия не создана
        assert not client.session.get('_auth_user_id')

    def test_authenticated_user_redirected_from_login(
        self, client, student_user,
    ):
        client.force_login(student_user.user)
        response = client.get(reverse('login'))
        assert response.status_code == 302
        assert response.url == reverse('student_dashboard')


# --- Кабинет ---

class TestDashboard:
    def test_requires_login(self, client):
        response = client.get(reverse('student_dashboard'))
        assert response.status_code == 302
        assert reverse('login') in response.url
        assert 'next=' in response.url

    def test_student_sees_own_data(self, client, student_user):
        client.force_login(student_user.user)
        response = client.get(reverse('student_dashboard'))
        assert response.status_code == 200
        content = response.content.decode()
        assert student_user.full_name_short in content
        assert student_user.group.name in content

    def test_admin_kicked_from_dashboard(self, client, admin_user):
        client.force_login(admin_user)
        response = client.get(reverse('student_dashboard'))
        assert response.status_code == 302
        assert response.url == reverse('login')

        # сессия очищена
        assert not client.session.get('_auth_user_id')


# --- Logout ---

class TestLogout:
    def test_logout_clears_session(self, client, student_user):
        client.force_login(student_user.user)
        response = client.post(reverse('logout'))
        assert response.status_code == 302
        assert response.url == reverse('login')

        # кабинет снова требует вход
        dashboard = client.get(reverse('student_dashboard'))
        assert dashboard.status_code == 302
        assert reverse('login') in dashboard.url

