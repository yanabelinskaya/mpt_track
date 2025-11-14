from django import template

register = template.Library()


@register.filter
def dict_get(value, key):
    """Безопасное получение значения из словаря по ключу"""
    if isinstance(value, dict):
        return value.get(key, '')
    return ''
