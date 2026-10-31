from datetime import date
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from main.models import Specialty
from main.services import export_specialty_questions_xlsx


class Command(BaseCommand):
    help = 'Экспортирует вопросы специальности в XLSX (для проверки сервиса)'

    def add_arguments(self, parser):
        parser.add_argument('slug', type=str, help='Слаг специальности, например sd')
        parser.add_argument(
            '--output', type=str, default=None,
            help='Путь к выходному файлу (по умолчанию <slug>_YYMMDD.xlsx)',
        )

    def handle(self, *args, **options):
        slug = options['slug']
        try:
            specialty = Specialty.objects.get(slug=slug)
        except Specialty.DoesNotExist:
            raise CommandError(f'Специальность со слагом "{slug}" не найдена')

        count = specialty.questions.count()
        if count == 0:
            raise CommandError(
                f'У специальности "{specialty.name}" нет вопросов — экспортировать нечего'
            )

        default_name = f'{slug}_{date.today().strftime("%y%m%d")}.xlsx'
        output = options['output'] or default_name
        output_path = Path(output).resolve()

        buffer = export_specialty_questions_xlsx(specialty)
        output_path.write_bytes(buffer.getvalue())

        size_kb = output_path.stat().st_size / 1024
        self.stdout.write(self.style.SUCCESS(
            f'Экспортировано {count} вопросов в {output_path} ({size_kb:.1f} КБ)'
        ))