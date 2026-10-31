from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator, RegexValidator
from django.utils import timezone


class Specialty(models.Model):
    code = models.CharField('Код', max_length=20, unique=True)
    name = models.CharField('Название', max_length=200)
    slug = models.SlugField(
        'Слаг',
        max_length=20,
        unique=True,
        validators=[
            RegexValidator(
                regex=r'^[a-z0-9]+$',
                message='Только строчные латинские буквы и цифры, без пробелов и дефисов.',
            ),
        ],
        help_text='Короткий идентификатор для файлов и URL. Например: sd.',
    )

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


class Question(models.Model):
    specialty = models.ForeignKey(
        Specialty,
        on_delete=models.CASCADE,
        related_name='questions',
        verbose_name='Специальность',
    )
    text = models.TextField('Текст вопроса')
    created_at = models.DateTimeField('Создан', auto_now_add=True)

    class Meta:
        verbose_name = 'Вопрос'
        verbose_name_plural = 'Вопросы'
        ordering = ['specialty', 'id']

    def __str__(self):
        return self.text[:80]


class Answer(models.Model):
    question = models.ForeignKey(
        Question,
        on_delete=models.CASCADE,
        related_name='answers',
        verbose_name='Вопрос',
    )
    text = models.TextField('Текст ответа')
    is_correct = models.BooleanField('Правильный', default=False)

    class Meta:
        verbose_name = 'Ответ'
        verbose_name_plural = 'Ответы'
        ordering = ['id']

    def __str__(self):
        return self.text[:80]


class TestSession(models.Model):
    __test__ = False
    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name='test_sessions',
        verbose_name='Студент',
    )
    specialty = models.ForeignKey(
        Specialty,
        on_delete=models.PROTECT,
        related_name='test_sessions',
        verbose_name='Специальность',
    )
    started_at = models.DateTimeField('Начат', default=timezone.now)
    deadline_at = models.DateTimeField('Дедлайн')
    finished_at = models.DateTimeField('Завершён', null=True, blank=True)
    total_questions = models.PositiveSmallIntegerField('Всего вопросов')
    correct_count = models.PositiveSmallIntegerField('Правильных', default=0)
    passed = models.BooleanField('Зачёт', default=False)
    current_index = models.PositiveSmallIntegerField('Текущий вопрос', default=0)

    class Meta:
        verbose_name = 'Сессия тестирования'
        verbose_name_plural = 'Сессии тестирования'
        ordering = ['-started_at']
        constraints = [
            models.UniqueConstraint(
                fields=['student', 'specialty'],
                name='unique_test_session_per_specialty',
            ),
        ]

    @property
    def is_finished(self):
        return self.finished_at is not None

    @property
    def is_expired(self):
        from django.utils import timezone
        return not self.is_finished and timezone.now() > self.deadline_at

    @property
    def percent_correct(self):
        if not self.total_questions:
            return 0
        return round(self.correct_count * 100 / self.total_questions, 1)

    def __str__(self):
        return f'{self.student} — {self.specialty} — {self.started_at:%d.%m.%Y}'


class SessionQuestion(models.Model):
    session = models.ForeignKey(
        TestSession,
        on_delete=models.CASCADE,
        related_name='session_questions',
        verbose_name='Сессия',
    )
    question = models.ForeignKey(
        Question,
        on_delete=models.PROTECT,
        verbose_name='Вопрос',
    )
    position = models.PositiveSmallIntegerField('Позиция')
    answer_order = models.JSONField('Порядок ответов', default=list)
    chosen_answer = models.ForeignKey(
        Answer,
        on_delete=models.PROTECT,
        null=True, blank=True,
        verbose_name='Выбранный ответ',
    )
    is_correct = models.BooleanField('Правильный', default=False)
    answered_at = models.DateTimeField('Отвечен', null=True, blank=True)

    class Meta:
        verbose_name = 'Вопрос сессии'
        verbose_name_plural = 'Вопросы сессии'
        ordering = ['session', 'position']
        constraints = [
            models.UniqueConstraint(
                fields=['session', 'position'],
                name='unique_question_position_in_session',
            ),
        ]

    def __str__(self):
        return f'{self.session} — Q{self.position + 1}'


class ComputerMapping(models.Model):
    ip = models.GenericIPAddressField('IP-адрес', unique=True)
    number = models.CharField('Номер компьютера', max_length=20)

    class Meta:
        verbose_name = 'Маппинг IP → компьютер'
        verbose_name_plural = 'Маппинг IP → компьютер'
        ordering = ['ip']

    def __str__(self):
        return f'{self.ip} → {self.number}'


class ReportTemplate(models.Model):
    TYPE_INDIVIDUAL = 'individual'
    TYPE_SUMMARY = 'summary'
    TYPE_CHOICES = [
        (TYPE_INDIVIDUAL, 'Индивидуальный (для студента)'),
        (TYPE_SUMMARY, 'Сводный (для группы)'),
    ]

    template_type = models.CharField(
        'Тип шаблона',
        max_length=20,
        choices=TYPE_CHOICES,
        unique=True,
    )
    file = models.FileField(
        'Файл шаблона',
        upload_to='report_templates/',
        help_text='XLSX-шаблон с плейсхолдерами вида {{student_full_name}}.',
    )
    uploaded_at = models.DateTimeField('Загружен', auto_now=True)

    class Meta:
        verbose_name = 'Шаблон отчёта'
        verbose_name_plural = 'Шаблоны отчётов'
        ordering = ['template_type']

    def __str__(self):
        return self.get_template_type_display()

    def save(self, *args, **kwargs):
        old = ReportTemplate.objects.filter(pk=self.pk).first() if self.pk else None
        if old and old.file and old.file != self.file:
            old.file.delete(save=False)
        super().save(*args, **kwargs)


class Commission(models.Model):
    group = models.OneToOneField(
        Group,
        on_delete=models.CASCADE,
        related_name='commission',
        verbose_name='Группа',
    )
    chairman = models.CharField('Председатель', max_length=200, blank=True)
    member1 = models.CharField('Член комиссии 1', max_length=200, blank=True)
    member2 = models.CharField('Член комиссии 2', max_length=200, blank=True)
    member3 = models.CharField('Член комиссии 3', max_length=200, blank=True)
    secretary = models.CharField('Секретарь', max_length=200, blank=True)

    class Meta:
        verbose_name = 'Комиссия'
        verbose_name_plural = 'Комиссии'
        ordering = ['group']

    def __str__(self):
        return f'Комиссия группы {self.group.name}'

