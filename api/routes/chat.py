"""DeskFlow — 聊天接口 (FastAPI Router)"""
import os
import json

from fastapi import APIRouter, UploadFile, Form
from fastapi.responses import JSONResponse, Response, StreamingResponse

from main import orchestrator

router = APIRouter()


@router.post("/api/chat")
async def chat(message: str = Form(""), file: UploadFile = None):
    """聊天接口"""
    # 处理上传的文件
    if file:
        upload_dir = os.path.expanduser("~/.deskflow/uploads")
        os.makedirs(upload_dir, exist_ok=True)
        filepath = os.path.join(upload_dir, file.filename)
        content = await file.read()
        with open(filepath, "wb") as f:
            f.write(content)
        text_content = content.decode("utf-8", errors="replace")
        message = f"{message}\n\n[文件内容: {file.filename}]\n{text_content[:3000]}"

    if not orchestrator:
        return JSONResponse({"reply": "⚠️ 请先完成初始配置"})

    try:
        reply = orchestrator.process(message)
    except Exception as e:
        reply = f"⚠️ 处理出错: {str(e)}"
    return JSONResponse({"reply": reply})


@router.post("/api/chat/stream")
async def chat_stream(message: str = Form(""), file: UploadFile = None):
    """流式聊天接口 — SSE"""
    if file:
        upload_dir = os.path.expanduser("~/.deskflow/uploads")
        os.makedirs(upload_dir, exist_ok=True)
        filepath = os.path.join(upload_dir, file.filename)
        content = await file.read()
        with open(filepath, "wb") as f:
            f.write(content)
        text_content = content.decode("utf-8", errors="replace")
        message = f"{message}\n\n[文件内容: {file.filename}]\n{text_content[:3000]}"

    if not orchestrator:
        return JSONResponse({"reply": "请先完成初始配置"})

    async def generate():
        try:
            reply = orchestrator.process(message)
            CHUNK = 3
            for i in range(0, len(reply), CHUNK):
                chunk = reply[i:i + CHUNK]
                data = json.dumps({"token": chunk})
                yield "data: " + data + "\n\n"
            data = json.dumps({"done": True})
            yield "data: " + data + "\n\n"
        except Exception as e:
            data = json.dumps({"error": str(e)})
            yield "data: " + data + "\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
