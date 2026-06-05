"""日志路由"""
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from core.logger import logger, get_log_lines, clear_logs as clear_log_files

router = APIRouter()


@router.get("/api/logs")
def api_logs():
    """查看日志"""
    count = request.args.get("lines", 200, type=int)
    level = request.args.get("level", "", type=str)
    search = request.args.get("search", "", type=str)
    count = min(count, 1000)
    return JSONResponse(get_log_lines(count=count, level=level.upper(), search=search))


@router.post("/api/logs/clear")
def api_logs_clear():
    """清空日志"""
    result = clear_log_files()
    return JSONResponse(result)
