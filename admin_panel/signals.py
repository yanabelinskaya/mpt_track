# admin_panel/signals.py

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from .models import Student, Group

@receiver(pre_save, sender=Student)
def sync_student_dates_with_group(sender, instance, **kwargs):
    """Синхронизирует даты студента с датами группы при изменении группы"""
    
    if instance.group:
        # Проверяем, изменилась ли группа
        group_changed = False
        
        if instance.pk:  # Существующий студент
            try:
                old_instance = Student.objects.get(pk=instance.pk)
                group_changed = (old_instance.group != instance.group)
            except Student.DoesNotExist:
                group_changed = True
        else:
            # Новый студент
            group_changed = True
        
        # Если группа изменилась, обновляем даты
        if group_changed:
            print(f"Группа студента {instance.get_full_name()} изменилась на {instance.group.code}")
            
            # Обновляем даты из группы
            if instance.group.enrollment_date:
                instance.enrollment_date = instance.group.enrollment_date
                print(f"Дата поступления обновлена: {instance.enrollment_date}")
            
            if instance.group.graduation_date:
                instance.graduation_date = instance.group.graduation_date
                print(f"Дата выпуска обновлена: {instance.graduation_date}")

@receiver(post_save, sender=Group)
def update_students_dates_when_group_changes(sender, instance, **kwargs):
    """Обновляет даты всех студентов группы при изменении дат группы"""
    
    # Обновляем даты всех студентов этой группы
    students_updated = instance.students.update(
        enrollment_date=instance.enrollment_date,
        graduation_date=instance.graduation_date
    )
    
    if students_updated > 0:
        print(f"Обновлены даты для {students_updated} студентов группы {instance.code}")
