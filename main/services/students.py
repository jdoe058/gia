from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction

from main.models import Student

from .logins import generate_login
from .passwords import generate_password

User = get_user_model()

# Сколько раз пытаемся сгенерировать пароль, если он совпал
# с уже существующим в группе.
PASSWORD_RETRY_LIMIT = 10


def _next_slug(group):
    """
    Возвращает следующий порядковый номер в группе: '01', '02', ...
    Учитывает только существующих студентов, не переиспользует
    удалённые номера.
    """
    last = (
        Student.objects
        .filter(group=group)
        .order_by('-slug')
        .values_list('slug', flat=True)
        .first()
    )
    if last is None:
        return '01'
    return str(int(last) + 1).zfill(len(last))


def _unique_password(group):
    """
    Генерирует пароль, которого ещё нет среди plain_password
    студентов этой группы. При исчерпании попыток — исключение.
    """
    taken = set(
        Student.objects
        .filter(group=group)
        .values_list('plain_password', flat=True)
    )
    for _ in range(PASSWORD_RETRY_LIMIT):
        password = generate_password()
        if password not in taken:
            return password
    raise RuntimeError(
        f'Не удалось сгенерировать уникальный пароль за {PASSWORD_RETRY_LIMIT} попыток. '
        f'Возможно, PASSWORD_LENGTH слишком мал для текущего размера группы.'
    )


@transaction.atomic
def create_student(group, last_name, first_name, middle_name=''):
    """
    Создаёт студента и связанного User в одной транзакции.

    Вычисляет следующий slug, генерирует уникальный пароль в группе,
    собирает логин и создаёт обоих. Возвращает Student.
    """
    slug = _next_slug(group)
    login = generate_login(group, slug)
    password = _unique_password(group)

    user = User.objects.create_user(
        username=login,
        password=password,
        is_active=True,
    )
    student = Student.objects.create(
        user=user,
        group=group,
        last_name=last_name.strip(),
        first_name=first_name.strip(),
        middle_name=(middle_name or '').strip(),
        slug=slug,
        plain_password=password,
    )
    return student

