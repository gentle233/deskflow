"""邮件处理 Agent — IMAP 读取 + SMTP 发送 + LLM 摘要"""
import imaplib
import smtplib
import email
import base64
import json
import os
import re
from email.header import decode_header
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime, timedelta
from typing import Optional

from agents.base_agent import BaseAgent, Task, Result
from core.config import load_config, save_config

# ── 常用邮箱 IMAP/SMTP 配置 ──────────────────────────────────────────────

MAIL_PROVIDERS = {
    "QQ邮箱": {
        "imap_server": "imap.qq.com",
        "imap_port": 993,
        "smtp_server": "smtp.qq.com",
        "smtp_port": 465,
        "use_ssl": True,
    },
    "163邮箱": {
        "imap_server": "imap.163.com",
        "imap_port": 993,
        "smtp_server": "smtp.163.com",
        "smtp_port": 465,
        "use_ssl": True,
    },
    "126邮箱": {
        "imap_server": "imap.126.com",
        "imap_port": 993,
        "smtp_server": "smtp.126.com",
        "smtp_port": 465,
        "use_ssl": True,
    },
    "Outlook/Hotmail": {
        "imap_server": "outlook.office365.com",
        "imap_port": 993,
        "smtp_server": "smtp.office365.com",
        "smtp_port": 587,
        "use_ssl": False,  # STARTTLS
    },
    "Gmail": {
        "imap_server": "imap.gmail.com",
        "imap_port": 993,
        "smtp_server": "smtp.gmail.com",
        "smtp_port": 587,
        "use_ssl": False,  # STARTTLS
    },
    "自定义": {
        "imap_server": "",
        "imap_port": 993,
        "smtp_server": "",
        "smtp_port": 465,
        "use_ssl": True,
    },
}


# ── 工具函数 ──────────────────────────────────────────────────────────────

def _decode_mime(s):
    """解码邮件头（处理 =?utf-8?B?...?= 编码）"""
    if not s:
        return ""
    decoded_parts = decode_header(s)
    result = []
    for part, charset in decoded_parts:
        if isinstance(part, bytes):
            try:
                result.append(part.decode(charset or "utf-8", errors="replace"))
            except (LookupError, UnicodeDecodeError):
                result.append(part.decode("utf-8", errors="replace"))
        else:
            result.append(part)
    return " ".join(result)


def _get_email_body(msg) -> str:
    """从邮件 Message 中提取纯文本正文"""
    if msg.is_multipart():
        text_content = ""
        for part in msg.walk():
            ctype = part.get_content_type()
            cdisp = str(part.get("Content-Disposition", ""))
            if ctype == "text/plain" and "attachment" not in cdisp:
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    try:
                        text_content += payload.decode(charset, errors="replace")
                    except (LookupError, UnicodeDecodeError):
                        text_content += payload.decode("utf-8", errors="replace")
            elif ctype == "text/html" and not text_content and "attachment" not in cdisp:
                # 没有纯文本时fallback到HTML
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    try:
                        html = payload.decode(charset, errors="replace")
                        # 简单去除HTML标签
                        text_content += re.sub(r"<[^>]+>", "", html)[:2000]
                    except (LookupError, UnicodeDecodeError):
                        pass
        return text_content.strip()
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            charset = msg.get_content_charset() or "utf-8"
            try:
                return payload.decode(charset, errors="replace").strip()
            except (LookupError, UnicodeDecodeError):
                return payload.decode("utf-8", errors="replace").strip()
        return ""


def _parse_email(raw_email: bytes) -> dict:
    """解析原始邮件字节为结构化字典"""
    msg = email.message_from_bytes(raw_email)
    subject = _decode_mime(msg.get("Subject", ""))
    sender = _decode_mime(msg.get("From", ""))
    to = _decode_mime(msg.get("To", ""))
    date_str = msg.get("Date", "")

    # 解析日期
    parsed_date = None
    try:
        from email.utils import parsedate_to_datetime
        parsed_date = parsedate_to_datetime(date_str)
        date_str = parsed_date.strftime("%Y-%m-%d %H:%M")
    except Exception:
        pass

    body = _get_email_body(msg)
    # 截断正文防止过大
    if len(body) > 5000:
        body = body[:5000] + "\n...(截断)"

    return {
        "subject": subject or "(无主题)",
        "from": sender,
        "to": to,
        "date": date_str,
        "body": body,
        "parsed_date": parsed_date.isoformat() if parsed_date else "",
    }


# ── 配置管理 ──────────────────────────────────────────────────────────────

def get_email_config() -> dict:
    """获取邮件配置"""
    config = load_config()
    return config.get("email", {})


def save_email_config(email_config: dict):
    """保存邮件配置"""
    config = load_config()
    config["email"] = email_config
    save_config(config)


# ── IMAP 操作 ─────────────────────────────────────────────────────────────

def _connect_imap(cfg: dict) -> Optional[imaplib.IMAP4]:
    """连接 IMAP 服务器"""
    try:
        if cfg.get("use_ssl", True):
            conn = imaplib.IMAP4_SSL(cfg["imap_server"], int(cfg.get("imap_port", 993)))
        else:
            conn = imaplib.IMAP4(cfg["imap_server"], int(cfg.get("imap_port", 143)))
            conn.starttls()

        password = base64.b64decode(cfg["password"]).decode() if cfg.get("password_encoded") else cfg.get("password", "")
        conn.login(cfg["email"], password)
        return conn
    except Exception as e:
        raise Exception(f"IMAP 连接失败: {e}")


def _fetch_emails(cfg: dict, mailbox: str = "INBOX", search_criteria: str = "ALL",
                  max_results: int = 10) -> list[dict]:
    """获取邮件列表"""
    conn = _connect_imap(cfg)
    try:
        conn.select(mailbox)
        _, data = conn.search(None, search_criteria)
        ids = data[0].split() if data[0] else []
        # 取最新的 N 封
        ids = ids[-max_results:]

        results = []
        for mid in ids:
            _, msg_data = conn.fetch(mid, "(RFC822)")
            if msg_data and msg_data[0]:
                raw = msg_data[0][1]
                parsed = _parse_email(raw)
                parsed["id"] = mid.decode()
                results.append(parsed)

        return results
    finally:
        try:
            conn.close()
            conn.logout()
        except Exception:
            pass


# ── SMTP 操作 ─────────────────────────────────────────────────────────────

def _send_email(cfg: dict, to_addr: str, subject: str, body: str) -> str:
    """发送邮件"""
    password = base64.b64decode(cfg["password"]).decode() if cfg.get("password_encoded") else cfg.get("password", "")

    msg = MIMEText(body, "plain", "utf-8")
    msg["From"] = cfg["email"]
    msg["To"] = to_addr
    msg["Subject"] = subject

    try:
        if cfg.get("use_ssl", True):
            conn = smtplib.SMTP_SSL(cfg["smtp_server"], int(cfg.get("smtp_port", 465)))
        else:
            conn = smtplib.SMTP(cfg["smtp_server"], int(cfg.get("smtp_port", 587)))
            conn.starttls()

        conn.login(cfg["email"], password)
        conn.send_message(msg)
        conn.quit()
        return f"✅ 邮件已发送到 {to_addr}，主题: {subject}"
    except Exception as e:
        raise Exception(f"邮件发送失败: {e}")


# ── Agent ─────────────────────────────────────────────────────────────────

PROVIDER_NAMES = "、".join(MAIL_PROVIDERS.keys())


class MailAgent(BaseAgent):
    name = "mail"
    description = f"邮件处理（读取收件箱、搜索邮件、发送邮件、邮件摘要）支持 {PROVIDER_NAMES}"

    def can_handle(self, task: Task) -> bool:
        return task.type in ("mail_read", "mail_send", "mail_summarize", "mail_search")
    
    def _check_config(self) -> dict:
        cfg = get_email_config()
        if not cfg.get("enabled") or not cfg.get("email") or not cfg.get("password"):
            raise Exception("邮件功能未配置，请先在设置中填写邮箱账号和授权码")
        return cfg

    def execute(self, task: Task) -> Result:
        try:
            if task.type == "mail_read":
                return self._read_emails(task)
            elif task.type == "mail_send":
                return self._send(task)
            elif task.type == "mail_summarize":
                return self._summarize(task)
            elif task.type == "mail_search":
                return self._search(task)
            return Result(task.id, False, error=f"不支持: {task.type}")
        except Exception as e:
            return Result(task.id, False, error=str(e))

    def _read_emails(self, task: Task) -> Result:
        """读取收件箱邮件"""
        cfg = self._check_config()
        count = task.params.get("count", 5)
        mailbox = task.params.get("mailbox", "INBOX")
        
        emails = _fetch_emails(cfg, mailbox=mailbox, max_results=count)
        if not emails:
            return Result(task.id, True, summary="收件箱为空", data=[])

        lines = [f"📬 最新 {len(emails)} 封邮件："]
        for i, e in enumerate(emails, 1):
            preview = e["body"][:80].replace("\n", " ") if e["body"] else "(无正文)"
            lines.append(f"\n{i}. [{e['date']}] {e['subject']}")
            lines.append(f"   发件人: {e['from']}")
            lines.append(f"   预览: {preview}…")

        summary = "\n".join(lines)
        return Result(task.id, True, summary=summary, data=emails)

    def _search(self, task: Task) -> Result:
        """搜索邮件"""
        cfg = self._check_config()
        keyword = task.params.get("keyword", "")
        if not keyword:
            return Result(task.id, False, error="请提供搜索关键词")

        # IMAP SEARCH 支持 FROM / SUBJECT / BODY
        conn = _connect_imap(cfg)
        try:
            conn.select("INBOX")
            # 用多条件搜索
            criteria = f'OR OR (FROM "{keyword}") (SUBJECT "{keyword}") (BODY "{keyword}")'
            _, data = conn.search(None, criteria)
            ids = data[0].split() if data[0] else []
            ids = ids[-10:]  # 最多10封

            results = []
            for mid in ids:
                _, msg_data = conn.fetch(mid, "(RFC822)")
                if msg_data and msg_data[0]:
                    parsed = _parse_email(msg_data[0][1])
                    parsed["id"] = mid.decode()
                    results.append(parsed)

            conn.close()
            conn.logout()
        except Exception as e:
            try: conn.logout()
            except: pass
            raise e

        if not results:
            return Result(task.id, True, summary=f"未找到包含 '{keyword}' 的邮件", data=[])

        lines = [f"🔍 找到 {len(results)} 封包含 '{keyword}' 的邮件："]
        for i, e in enumerate(results, 1):
            lines.append(f"\n{i}. [{e['date']}] {e['subject']} — {e['from']}")

        return Result(task.id, True, summary="\n".join(lines), data=results)

    def _send(self, task: Task) -> Result:
        """发送邮件"""
        cfg = self._check_config()
        to_addr = task.params.get("to", "")
        subject = task.params.get("subject", "来自 DeskFlow 的邮件")
        body = task.params.get("body", "")

        if not to_addr:
            return Result(task.id, False, error="请提供收件人地址")
        if "@" not in to_addr:
            return Result(task.id, False, error=f"收件人地址格式不正确: {to_addr}")

        result = _send_email(cfg, to_addr, subject, body)
        return Result(task.id, True, summary=result, data={"to": to_addr, "subject": subject})

    def _summarize(self, task: Task) -> Result:
        """邮件摘要"""
        cfg = self._check_config()
        count = task.params.get("count", 10)
        unread_only = task.params.get("unread_only", True)

        # 获取邮件
        if unread_only:
            emails = _fetch_emails(cfg, search_criteria="UNSEEN", max_results=count)
        else:
            emails = _fetch_emails(cfg, max_results=count)

        if not emails:
            return Result(task.id, True, summary="📭 没有未读邮件，收件箱很干净！", data=[])

        unread_label = "未读" if unread_only else "最新"
        lines = [
            f"📬 您有 {len(emails)} 封{unread_label}邮件：",
            "─" * 40,
        ]
        for i, e in enumerate(emails, 1):
            # 取正文前100字作为摘要
            body_preview = e["body"][:100].replace("\n", " ").strip()
            lines.append(f"\n{i}. 📧 {e['subject']}")
            lines.append(f"   {e['from']}  |  {e['date']}")
            if body_preview:
                lines.append(f"   {body_preview}…")

        summary = "\n".join(lines)
        return Result(task.id, True, summary=summary, data=emails)
