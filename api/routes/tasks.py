"""定时任务 API 路由"""
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from core.task_scheduler import (
    list_tasks, create_task, update_task, delete_task,
    toggle_task, run_task_now
)

router = APIRouter()


@router.get("/api/tasks")
async def api_tasks_list():
    """获取所有定时任务"""
    return JSONResponse(list_tasks())


@router.post("/api/tasks")
async def api_tasks_create(request: Request):
    """创建定时任务"""
    body = await request.json()
    return JSONResponse(create_task(body))


@router.put("/api/tasks/{task_id}")
async def api_tasks_update(task_id: str, request: Request):
    """更新定时任务"""
    body = await request.json()
    return JSONResponse(update_task(task_id, body))


@router.delete("/api/tasks/{task_id}")
async def api_tasks_delete(task_id: str):
    """删除定时任务"""
    return JSONResponse(delete_task(task_id))


@router.post("/api/tasks/{task_id}/toggle")
async def api_tasks_toggle(task_id: str):
    """启用/禁用定时任务"""
    return JSONResponse(toggle_task(task_id))


@router.post("/api/tasks/{task_id}/run")
async def api_tasks_run(task_id: str):
    """立即执行定时任务"""
    return JSONResponse(run_task_now(task_id))
