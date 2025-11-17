from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('admin_panel', '0021_alter_graderecord_grade_type_gradecolumncontext'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql="""
                        ALTER TABLE admin_panel_graderecord
                        ADD COLUMN IF NOT EXISTS work_type varchar(50) NOT NULL DEFAULT ''
                    """,
                    reverse_sql="""
                        ALTER TABLE admin_panel_graderecord
                        DROP COLUMN IF EXISTS work_type
                    """,
                ),
            ],
            state_operations=[
                migrations.AddField(
                    model_name='graderecord',
                    name='work_type',
                    field=models.CharField(
                        blank=True,
                        default='',
                        help_text='Поле для обратной совместимости с прежними версиями',
                        max_length=50,
                        verbose_name='Тип занятия (устаревшее)'
                    ),
                ),
            ],
        ),
    ]
