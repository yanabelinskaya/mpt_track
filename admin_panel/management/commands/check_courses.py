from django.core.management.base import BaseCommand
from admin_panel.models import Group
from datetime import datetime

class Command(BaseCommand):
    help = 'Проверяет правильность определения курсов для групп'

    def handle(self, *args, **options):
        current_year = datetime.now().year
        current_month = datetime.now().month
        
        if current_month >= 9:
            academic_year_start = current_year
        else:
            academic_year_start = current_year - 1
        
        course_enrollment_years = {
            1: academic_year_start,
            2: academic_year_start - 1,
            3: academic_year_start - 2,
            4: academic_year_start - 3,
        }
        
        self.stdout.write(f"Учебный год: {academic_year_start}")
        self.stdout.write("Года поступления по курсам:")
        for course, year in course_enrollment_years.items():
            self.stdout.write(f"  {course} курс: {year} год")
        
        self.stdout.write("\nАнализ групп:")
        
        groups = Group.objects.filter(is_active=True).order_by('enrollment_date')
        
        for group in groups:
            if group.enrollment_date:
                enrollment_year = group.enrollment_date.year
                calculated_course = None
                
                for course, year in course_enrollment_years.items():
                    if enrollment_year == year:
                        calculated_course = course
                        break
                
                if calculated_course:
                    self.stdout.write(
                        f"✅ {group.code}: {enrollment_year} год → {calculated_course} курс"
                    )
                else:
                    self.stdout.write(
                        self.style.WARNING(
                            f"⚠️  {group.code}: {enrollment_year} год → НЕ ОПРЕДЕЛЕН"
                        )
                    )
            else:
                self.stdout.write(
                    self.style.ERROR(
                        f"❌ {group.code}: дата поступления не указана"
                    )
                )
