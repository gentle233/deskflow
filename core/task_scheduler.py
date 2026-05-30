"""DeskFlow 定时任务 — 用户自定义 cron/interval 任务"""
import json
import os
import uuid
from datetime import datetime
from threading import Lock

from core.config import load_config
from core.logger import logger

TASKS_PATH = os.path.expanduser("~/.deskflow/tasks.json")

# 任务触发时的回调（由 main.py 在初始化时注册）
_on_fire_callback = None
_lock = Lock()


def register_callback(callback):
    """注册任务触发回调 — callback(task, fire_time)"""
    global _on_fire_callback
    _on_fire_callback = callback


# ── 数据读写 ──────────────────────────────────────────────

def _load_tasks() -> list:
    if not os.path.exists(TASKS_PATH):
        return []
    try:
        with open(TASKS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def _save_tasks(tasks: list):
    os.makedirs(os.path.dirname(TASKS_PATH), exist_ok=True)
    with open(TASKS_PATH, "w", encoding="utf-8") as f:
        json.dump(tasks, f, ensure_ascii=False, indent=2)


# ── 公开 API ──────────────────────────────────────────────

def list_tasks() -> list:
    """获取所有任务"""
    with _lock:
        return _load_tasks()


def create_task(data: dict) -> dict:
    """创建任务"""
    name = data.get("name", "").strip()
    trigger_type = data.get("trigger_type", "interval")  # cron | interval
    prompt = data.get("prompt", "").strip()

    if not name:
        return {"status": "error", "error": "任务名不能为空"}
    if not prompt:
        return {"status": "error", "error": "触发内容不能为空"}

    task = {
        "id": "task_" + uuid.uuid4().hex[:8],
        "name": name,
        "enabled": True,
        "trigger_type": trigger_type,
        "prompt": prompt,
        "last_run": None,
        "next_run": None,
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }

    if trigger_type == "cron":
        cron = data.get("cron", "").strip()
        if not cron:
            return {"status": "error", "error": "Cron 表达式不能为空"}
        task["cron"] = cron
    else:
        unit = data.get("interval_unit", "hours")
        value = data.get("interval_value", 1)
        try:
            value = int(value)
        except (ValueError, TypeError):
            return {"status": "error", "error": "间隔值必须是数字"}
        if value < 1:
            return {"status": "error", "error": "间隔至少为 1"}
        task["interval_unit"] = unit
        task["interval_value"] = value

    with _lock:
        tasks = _load_tasks()
        tasks.append(task)
        _save_tasks(tasks)

    # 调度新任务
    _schedule_one(task)

    logger.info("定时任务已创建: %s (%s)", name, trigger_type)
    return {"status": "ok", "task": task}


def update_task(task_id: str, data: dict) -> dict:
    """更新任务（会重新调度）"""
    with _lock:
        tasks = _load_tasks()
        idx = None
        for i, t in enumerate(tasks):
            if t["id"] == task_id:
                idx = i
                break
        if idx is None:
            return {"status": "error", "error": "任务不存在"}

        task = tasks[idx]
        if "name" in data:
            task["name"] = data["name"].strip()
        if "prompt" in data:
            task["prompt"] = data["prompt"].strip()
        if "trigger_type" in data:
            task["trigger_type"] = data["trigger_type"]
        if "cron" in data:
            task["cron"] = data["cron"]
        if "interval_unit" in data:
            task["interval_unit"] = data["interval_unit"]
        if "interval_value" in data:
            task["interval_value"] = data["interval_value"]
        if "enabled" in data:
            task["enabled"] = bool(data["enabled"])

        # 重置 next_run，调度器会重新计算
        task["next_run"] = None
        tasks[idx] = task
        _save_tasks(tasks)

    # 重新调度
    _unschedule(task_id)
    if task["enabled"]:
        _schedule_one(task)

    logger.info("定时任务已更新: %s", task["name"])
    return {"status": "ok", "task": task}


def delete_task(task_id: str) -> dict:
    """删除任务"""
    _unschedule(task_id)
    with _lock:
        tasks = _load_tasks()
        new_tasks = [t for t in tasks if t["id"] != task_id]
        if len(new_tasks) == len(tasks):
            return {"status": "error", "error": "任务不存在"}
        _save_tasks(new_tasks)
    logger.info("定时任务已删除: %s", task_id)
    return {"status": "ok"}


def toggle_task(task_id: str) -> dict:
    """启用/禁用任务"""
    with _lock:
        tasks = _load_tasks()
        for t in tasks:
            if t["id"] == task_id:
                t["enabled"] = not t["enabled"]
                _save_tasks(tasks)
                break
        else:
            return {"status": "error", "error": "任务不存在"}

    # 重新调度
    _unschedule(task_id)
    task = next((t for t in _load_tasks() if t["id"] == task_id), None)
    if task and task["enabled"]:
        _schedule_one(task)

    return {"status": "ok"}


def run_task_now(task_id: str) -> dict:
    """立即执行一次任务"""
    tasks = _load_tasks()
    for t in tasks:
        if t["id"] == task_id:
            _fire_task(t)
            return {"status": "ok", "message": f"已触发: {t['name']}"}
    return {"status": "error", "error": "任务不存在"}


# ── APScheduler 调度 ──────────────────────────────────────

_scheduler = None
_job_map = {}  # task_id -> job_id


def _get_scheduler():
    global _scheduler
    if _scheduler is None:
        from apscheduler.schedulers.background import BackgroundScheduler
        _scheduler = BackgroundScheduler()
        _scheduler.start()
    return _scheduler


def _schedule_one(task: dict):
    """为单个任务创建 APScheduler job"""
    if not task.get("enabled"):
        return
    try:
        sched = _get_scheduler()
        job_id = f"user_task_{task['id']}"

        if task["trigger_type"] == "cron":
            parts = task["cron"].strip().split()
            if len(parts) != 5:
                logger.warning("无效 cron 表达式: %s", task["cron"])
                return
            sched.add_job(
                _fire_task,
                "cron",
                args=[task],
                id=job_id,
                replace_existing=True,
                minute=parts[0],
                hour=parts[1],
                day=parts[2],
                month=parts[3],
                day_of_week=parts[4],
            )
        else:
            unit = task.get("interval_unit", "hours")
            value = int(task.get("interval_value", 1))
            kwargs = {}
            if unit == "minutes":
                kwargs["minutes"] = value
            elif unit == "hours":
                kwargs["hours"] = value
            elif unit == "days":
                kwargs["days"] = value
            else:
                kwargs["hours"] = value
            sched.add_job(
                _fire_task,
                "interval",
                args=[task],
                id=job_id,
                replace_existing=True,
                **kwargs,
            )

        _job_map[task["id"]] = job_id
        # 记录下次运行时间
        job = sched.get_job(job_id)
        if job and job.next_run_time:
            with _lock:
                tasks = _load_tasks()
                for t in tasks:
                    if t["id"] == task["id"]:
                        t["next_run"] = job.next_run_time.isoformat(timespec="seconds")
                        _save_tasks(tasks)
                        break
    except Exception as e:
        logger.error("任务调度失败 [%s]: %s", task.get("name", "?"), e)


def _unschedule(task_id: str):
    """移除任务的 APScheduler job"""
    job_id = _job_map.pop(task_id, None)
    if job_id and _scheduler:
        try:
            _scheduler.remove_job(job_id)
        except Exception:
            pass


def _fire_task(task: dict):
    """任务触发时执行"""
    name = task.get("name", "?")
    prompt = task.get("prompt", "")
    now = datetime.now().isoformat(timespec="seconds")
    logger.info("⏰ 定时任务触发: %s", name)

    # 更新 last_run
    with _lock:
        tasks = _load_tasks()
        for t in tasks:
            if t["id"] == task["id"]:
                t["last_run"] = now
                # 更新 next_run
                if _scheduler:
                    job = _scheduler.get_job(f"user_task_{task['id']}")
                    if job and job.next_run_time:
                        t["next_run"] = job.next_run_time.isoformat(timespec="seconds")
                _save_tasks(tasks)
                break

    # 调用回调（由 main.py 注册，连接 agent 执行 prompt）
    if _on_fire_callback:
        try:
            _on_fire_callback(task, prompt)
        except Exception as e:
            logger.error("任务回调执行失败 [%s]: %s", name, e)


def init_scheduler():
    """应用启动时加载所有已启用的任务"""
    tasks = _load_tasks()
    count = 0
    for t in tasks:
        if t.get("enabled"):
            _schedule_one(t)
            count += 1
    if count:
        logger.info("定时任务调度器已初始化 — %d 个任务已加载", count)
