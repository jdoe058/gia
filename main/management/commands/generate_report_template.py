from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from main.services.xlsx import build_report_template_xlsx


class Command(BaseCommand):
    help = 'Генерирует эталонный шаблон отчёта в examples/'

    def add_arguments(self, parser):
        parser.add_argument(
            '--output', type=str, default=None,
            help='Путь к файлу (по умолчанию examples/report_template.xlsx)',
        )

    def handle(self, *args, **options):
        output = options['output']
        if output:
            output_path = Path(output).resolve()
        else:
            output_path = Path(settings.BASE_DIR) / 'examples' / 'report_template.xlsx'
            output_path.parent.mkdir(parents=True, exist_ok=True)

        buffer = build_report_template_xlsx()
        output_path.write_bytes(buffer.getvalue())

        self.stdout.write(self.style.SUCCESS(
            f'Шаблон отчёта сгенерирован: {output_path}'
        ))

        