from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('admin_panel', '0022_graderecord_work_type_state'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='AttendanceRecord',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('lesson_date', models.DateField(verbose_name='Дата занятия')),
                ('slot_id', models.CharField(blank=True, default='', max_length=20, verbose_name='Пара')),
                ('status', models.CharField(blank=True, choices=[('', 'Присутствовал'), ('absent', 'Отсутствовал'), ('late', 'Опоздал'), ('excused', 'Уважительная причина')], default='', max_length=20, verbose_name='Статус посещаемости')),
                ('comment', models.CharField(blank=True, max_length=255, verbose_name='Комментарий')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Создано')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Обновлено')),
                ('group', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='attendance_records', to='admin_panel.group', verbose_name='Группа')),
                ('student', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='attendance_records', to='admin_panel.student', verbose_name='Студент')),
                ('subject', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='attendance_records', to='admin_panel.subject', verbose_name='Предмет')),
                ('teacher', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='attendance_records', to='admin_panel.teacher', verbose_name='Преподаватель')),
                ('updated_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='updated_attendance_records', to=settings.AUTH_USER_MODEL, verbose_name='Кем обновлено')),
            ],
            options={
                'verbose_name': 'Посещаемость',
                'verbose_name_plural': 'Посещаемость',
                'ordering': ['lesson_date', 'slot_id', 'student__last_name'],
            },
        ),
        migrations.AddConstraint(
            model_name='attendancerecord',
            constraint=models.UniqueConstraint(fields=('student', 'group', 'lesson_date', 'slot_id', 'teacher'), name='unique_student_attendance_per_slot'),
        ),
    ]
