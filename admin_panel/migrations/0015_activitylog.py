from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('admin_panel', '0014_subjectassignment'),
    ]

    operations = [
        migrations.CreateModel(
            name='ActivityLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('action_type', models.CharField(choices=[('create', 'Создание'), ('update', 'Изменение'), ('delete', 'Удаление'), ('view', 'Просмотр'), ('navigation', 'Навигация'), ('other', 'Другое')], default='other', max_length=32, verbose_name='Тип действия')),
                ('description', models.TextField(verbose_name='Описание действия')),
                ('icon', models.CharField(blank=True, max_length=64, verbose_name='Иконка')),
                ('metadata', models.JSONField(blank=True, null=True, verbose_name='Дополнительные данные')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Дата и время')),
                ('user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='activity_logs', to=settings.AUTH_USER_MODEL, verbose_name='Пользователь')),
            ],
            options={
                'verbose_name': 'Запись активности',
                'verbose_name_plural': 'Журнал активности',
                'ordering': ['-created_at'],
            },
        ),
    ]
