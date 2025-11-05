from __future__ import annotations

from typing import Optional, Dict, Any

from django.utils import timezone
from django.utils.timesince import timesince

try:
    from .models import ActivityLog
    MODELS_AVAILABLE = True
except Exception:
    ActivityLog = None  # type: ignore
    MODELS_AVAILABLE = False


def serialize_activity_log(log: "ActivityLog", now: Optional[timezone.datetime] = None) -> Dict[str, Any]:
    if now is None:
        now = timezone.now()

    user_display = 'Система'
    if getattr(log, 'user', None):
        full_name = log.user.get_full_name()
        user_display = full_name or log.user.username

    return {
        'id': log.id,
        'description': log.description,
        'action_type': log.action_type,
        'icon': getattr(log, 'icon_name', None) or getattr(log, 'icon', '') or 'bi-clock-history',
        'created_iso': log.created_at.isoformat(),
        'created_display': f"{timesince(log.created_at, now)} назад",
        'user_display': user_display,
    }


def log_activity(user, action_type: str, description: str, icon: str = '', metadata: Optional[Dict[str, Any]] = None):
    if not MODELS_AVAILABLE or not description:
        return None

    valid_types = {choice[0] for choice in ActivityLog.ACTION_CHOICES}
    if action_type not in valid_types:
        action_type = ActivityLog.ACTION_OTHER

    try:
        return ActivityLog.objects.create(
            user=user if getattr(user, 'is_authenticated', False) else None,
            action_type=action_type,
            description=description,
            icon=(icon or '').strip(),
            metadata=metadata if isinstance(metadata, dict) else None,
        )
    except Exception as exc:
        print(f'Не удалось записать активность: {exc}')
        return None
