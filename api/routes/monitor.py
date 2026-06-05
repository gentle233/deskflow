"""文件监控 API 路由"""
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from core.file_monitor import get_monitor

router = APIRouter()


@router.get("/api/monitor/status")
async def monitor_status():
    """文件监控状态"""
    m = get_monitor()
    return JSONResponse(m.get_status())


@router.post("/api/monitor/start")
async def monitor_start():
    """启动文件监控"""
    m = get_monitor()
    ok = m.start()
    return JSONResponse({"status": "ok" if ok else "already_running", "running": m.is_running})


@router.post("/api/monitor/stop")
async def monitor_stop():
    """停止文件监控"""
    m = get_monitor()
    m.stop()
    return JSONResponse({"status": "ok", "running": False})


@router.get("/api/monitor/events")
async def monitor_events(request: Request):
    """获取文件变化事件"""
    count = request.query_params.get("count", 50)
    event_type = request.query_params.get("type", "")
    search = request.query_params.get("search", "")
    try:
        count = int(count)
    except (ValueError, TypeError):
        count = 50
    count = min(count, 200)
    m = get_monitor()
    events = m.get_events(count=count, event_type=event_type, search=search)
    return JSONResponse(events)


@router.post("/api/monitor/dirs")
async def monitor_add_dir(request: Request):
    """添加监控目录"""
    body = await request.json()
    path = body.get("path", "")
    if not path:
        return JSONResponse({"status": "error", "error": "path 不能为空"}, status_code=400)
    m = get_monitor()
    return JSONResponse(m.add_directory(path))


@router.delete("/api/monitor/dirs")
async def monitor_remove_dir(request: Request):
    """移除监控目录"""
    body = await request.json()
    path = body.get("path", "")
    if not path:
        return JSONResponse({"status": "error", "error": "path 不能为空"}, status_code=400)
    m = get_monitor()
    return JSONResponse(m.remove_directory(path))
