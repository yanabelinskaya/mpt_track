from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('admin_panel', '0023_attendancerecord'),
    ]

    operations = [
        migrations.AddField(
            model_name='scheduleweek',
            name='change_markers',
            field=models.JSONField(blank=True, default=list, verbose_name='Маркеры изменений'),
        ),
    ]
