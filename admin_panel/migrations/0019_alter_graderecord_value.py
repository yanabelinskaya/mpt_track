from django.db import migrations, models
import django.core.validators


class Migration(migrations.Migration):

    dependencies = [
        ('admin_panel', '0018_graderecord'),
    ]

    operations = [
        migrations.AlterField(
            model_name='graderecord',
            name='value',
            field=models.PositiveSmallIntegerField(
                validators=[
                    django.core.validators.MinValueValidator(1),
                    django.core.validators.MaxValueValidator(5),
                ],
                verbose_name='Оценка',
            ),
        ),
    ]
