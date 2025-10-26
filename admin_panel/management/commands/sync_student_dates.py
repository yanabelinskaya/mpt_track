# admin_panel/management/commands/sync_student_dates.py

from django.core.management.base import BaseCommand
from admin_panel.models import Student

class Command(BaseCommand):
    help = 'Синхронизирует даты студентов с их группами'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Показать что будет изменено без сохранения',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        # Находим студентов с группами
        students_with_groups = Student.objects.filter(group__isnull=False).select_related('group')
        
        updated_count = 0
        
        for student in students_with_groups:
            needs_update = False
            changes = []
            
            # Проверяем дату поступления
            if student.enrollment_date != student.group.enrollment_date:
                needs_update = True
                changes.append(f"поступление: {student.enrollment_date} -> {student.group.enrollment_date}")
                if not dry_run:
                    student.enrollment_date = student.group.enrollment_date
            
            # Проверяем дату выпуска
            if student.graduation_date != student.group.graduation_date:
                needs_update = True
                changes.append(f"выпуск: {student.graduation_date} -> {student.group.graduation_date}")
                if not dry_run:
                    student.graduation_date = student.group.graduation_date
            
            if needs_update:
                updated_count += 1
                self.stdout.write(
                    f"{student.get_full_name()} ({student.group.code}): {', '.join(changes)}"
                )
                
                if not dry_run:
                    student.save()
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING(f'ТЕСТОВЫЙ РЕЖИМ: Будет обновлено {updated_count} студентов')
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(f'Обновлено {updated_count} студентов')
            )
