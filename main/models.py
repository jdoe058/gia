from django.db import models

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

