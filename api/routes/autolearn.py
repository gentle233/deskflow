"""自动学习路由"""
import os
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from autolearn.models import get_active_patterns, dismiss_pattern, count_events_last_24h, get_db_size_mb

router = APIRouter()


def _autolearn_title(pattern: dict) -> str:
    """为学习模式生成友好标题"""
    pt = pattern['pattern_type']
    val = pattern['pattern_value'] or ''
    if pt == 'frequent_folder':
        return f'📂 快速打开: {os.path.basename(val) or val}'
    elif pt == 'weekly_report':
        return f'📝 写周报时间'
    elif pt == 'common_phrase':
        return f'💬 常用短语: "{val}"'
    elif pt == 'repeated_action':
        return f'🔄 重复操作: {val[:20]}'
    elif pt == 'user_preference':
        return f'💡 {val[:30]}'
    return f'🔔 {val[:30]}'


@router.get("/api/autolearn/suggestions")
def autolearn_suggestions():
    """获取学习建议"""
    patterns = get_active_patterns(limit=3, min_confidence=0.5)
    return JSONResponse([{
        'id': p['id'],
        'type': p['pattern_type'],
        'key': p['pattern_key'],
        'value': p['pattern_value'],
        'title': _autolearn_title(p),
        'confidence': p['confidence']
    } for p in patterns])


@router.post("/api/autolearn/dismiss/{pattern_id}")
def autolearn_dismiss(pattern_id: int):
    """忽略建议"""
    dismiss_pattern(pattern_id)
    return JSONResponse({"status": "ok"})


@router.get("/api/autolearn/stats")
def autolearn_stats():
    """学习统计"""
    return JSONResponse({
        'events_today': count_events_last_24h(),
        'active_patterns': len(get_active_patterns(limit=100, min_confidence=0)),
        'storage_mb': get_db_size_mb()
    })
