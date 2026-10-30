from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator, RegexValidator


class Specialty(models.Model):
    code = models.CharField('Код', max_length=20, unique=True)
    name = models.CharField('Название', max_length=200)

    class Meta:
        verbose_name = 'Специальность'
        verbose_name_plural = 'Специальности'
        ordering = ['code']

    def __str__(self):
        return f'{self.code} {self.name}'


class Group(models.Model):
    COURSE_CHOICES = [
        (1, '1 курс'),
        (2, '2 курс'),
        (3, '3 курс'),
        (4, '4 курс'),
        (5, '5 курс'),
    ]
    FINANCING_CHOICES = [
        ('budget', 'Бюджет'),
        ('contract', 'Договор'),
    ]
    BASE_CHOICES = [
        ('9', '9 классов'),
        ('11', '11 классов'),
    ]

    name = models.CharField('Название', max_length=50)
    slug = models.SlugField(
        'Слаг для логина',
        max_length=20,
        unique=True,
        validators=[
            RegexValidator(
                regex=r'^[a-z0-9]+$',
                message='Только строчные латинские буквы и цифры, без пробелов и дефисов.',
            ),
        ],
        help_text='Например: sd21. Входит в состав логина студента.',
    )
    course = models.PositiveSmallIntegerField(
        'Курс',
        choices=COURSE_CHOICES,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
    )
    financing = models.CharField(
        'Вид финансирования',
        max_length=10,
        choices=FINANCING_CHOICES,
    )
    base = models.CharField(
        'База',
        max_length=2,
        choices=BASE_CHOICES,
    )
    specialty = models.ForeignKey(
        Specialty,
        on_delete=models.PROTECT,
        related_name='groups',
        verbose_name='Специальность',
    )

    class Meta:
        verbose_name = 'Группа'
        verbose_name_plural = 'Группы'
        ordering = ['specialty', 'slug']

    def __str__(self):
        return self.name

class Student(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='student_profile',
        verbose_name='Пользователь',
    )
    group = models.ForeignKey(
        Group,
        on_delete=models.CASCADE,
        related_name='students',
        verbose_name='Группа',
    )
    last_name = models.CharField('Фамилия', max_length=100)
    first_name = models.CharField('Имя', max_length=100)
    middle_name = models.CharField('Отчество', max_length=100, blank=True)
    slug = models.CharField(
        'Порядковый номер',
        max_length=10,
        help_text='Например: 01. Генерируется автоматически при загрузке.',
    )
    plain_password = models.CharField('Пароль', max_length=20)

    class Meta:
        verbose_name = 'Студент'
        verbose_name_plural = 'Студенты'
        ordering = ['group', 'slug']
        unique_together = ('group', 'slug')

    @property
    def login(self):
        return f'{self.group.slug}{self.slug}'.lower()

    @property
    def full_name_short(self):
        initials = f'{self.first_name[0]}.' if self.first_name else ''
        if self.middle_name:
            initials += f'{self.middle_name[0]}.'
        return f'{self.last_name} {initials}'.strip()

    def __str__(self):
        return f'{self.full_name_short} ({self.login})'

