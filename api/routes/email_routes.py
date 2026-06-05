"""邮件配置路由"""
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from core.logger import logger
from agents.mail import get_email_config, save_email_config, MAIL_PROVIDERS, _connect_imap

router = APIRouter()


@router.get("/api/email/providers")
def email_providers():
    """获取邮箱提供商列表"""
    return JSONResponse({k: {kk: vv for kk, vv in v.items() if kk != "password"}
                    for k, v in MAIL_PROVIDERS.items()})


@router.get("/api/email/config")
def email_get_config():
    """获取邮箱配置（隐藏密码）"""
    cfg = get_email_config()
    safe = dict(cfg)
    if safe.get("password"):
        safe["password"] = "••••••" if safe["password"] else ""
    return JSONResponse(safe)


@router.post("/api/email/config")
def email_save_config():
    """保存邮箱配置"""
    data = request.json or {}
    current = get_email_config()

    # 密码处理：如果传了掩码值 "••••••"，保留旧密码
    if data.get("password") == "••••••":
        data["password"] = current.get("password", "")
        data["password_encoded"] = current.get("password_encoded", False)

    # 如果是新密码且未编码，进行 base64 编码
    if data.get("password") and data["password"] != current.get("password", ""):
        import base64
        data["password"] = base64.b64encode(data["password"].encode()).decode()
        data["password_encoded"] = True

    save_email_config(data)
    logger.info("邮箱配置已更新: %s", data.get("email", "(未设置)"))
    return JSONResponse({"status": "ok"})


@router.post("/api/email/test")
def email_test():
    """测试邮箱连接"""
    cfg = get_email_config()
    if not cfg.get("enabled") or not cfg.get("email") or not cfg.get("password"):
        return JSONResponse({"status": "error", "message": "请先配置邮箱"})
    try:
        conn = _connect_imap(cfg)
        conn.select("INBOX")
        conn.close()
        conn.logout()
        return JSONResponse({"status": "ok", "message": "✅ 连接成功！"})
    except Exception as e:
        return JSONResponse({"status": "error", "message": f"❌ 连接失败: {e}"})
