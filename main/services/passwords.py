import secrets

PASSWORD_LENGTH = 4
# Только строчные буквы и цифры, без похожих друг на друга символов:
# исключены 0 (ноль), 1 (единица), i, l (эль), o (оу) — их легко спутать
# при чтении с бумаги и ручном вводе.
PASSWORD_ALPHABET = 'abcdefghjkmnpqrstuvwxyz23456789'


def generate_password():
    """Генерирует случайный пароль фиксированной длины."""
    return ''.join(secrets.choice(PASSWORD_ALPHABET) for _ in range(PASSWORD_LENGTH))

