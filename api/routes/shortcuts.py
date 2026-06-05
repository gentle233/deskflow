"""快捷指令 API 路由"""
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from core.shortcuts import load_shortcuts, add_shortcut, delete_shortcut

router = APIRouter()


@router.get("/api/shortcuts")
async def get_shortcuts():
    """获取所有快捷指令"""
    return JSONResponse(load_shortcuts())


@router.post("/api/shortcuts")
async def create_shortcut(request: Request):
    """添加快捷指令"""
    body = await request.json()
    if not body or not body.get("trigger") or not body.get("command"):
        return JSONResponse({"status": "error", "error": "trigger 和 command 不能为空"}, status_code=400)
    result = add_shortcut(body["trigger"], body["command"], body.get("desc", ""))
    return JSONResponse(result)


@router.delete("/api/shortcuts")
async def remove_shortcut(request: Request):
    """删除快捷指令"""
    body = await request.json() if request.headers.get("content-type") else {}
    trigger = body.get("trigger", "")
    if not trigger:
        return JSONResponse({"status": "error", "error": "trigger 不能为空"}, status_code=400)
    return JSONResponse(delete_shortcut(trigger))
