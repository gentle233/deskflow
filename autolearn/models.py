"""
DeskFlow 自动学习 — 数据模型 & DB 操作
"""
import json
import os
import sqlite3
from datetime import datetime, timedelta

DB_PATH = os.path.expanduser("~/.deskflow/autolearn.db")


def get_db() -> sqlite3.Connection:
    """获取数据库连接（WAL模式，线程安全）"""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def init_db():
    """初始化数据库表"""
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS behavior_events (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp   TEXT NOT NULL DEFAULT (datetime('now','localtime')),
            event_type  TEXT NOT NULL,
            source      TEXT,
            file_path   TEXT,
            folder_path TEXT,
            text_snippet TEXT,
            session_id  TEXT,
            metadata    TEXT DEFAULT '{}'
        );

        CREATE INDEX IF NOT EXISTS idx_be_time   ON behavior_events(timestamp);
        CREATE INDEX IF NOT EXISTS idx_be_type   ON behavior_events(event_type);
        CREATE INDEX IF NOT EXISTS idx_be_file   ON behavior_events(file_path);
        CREATE INDEX IF NOT EXISTS idx_be_folder ON behavior_events(folder_path);

        CREATE TABLE IF NOT EXISTS learned_patterns (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            pattern_type   TEXT NOT NULL,
            pattern_key    TEXT NOT NULL,
            pattern_value  TEXT,
            frequency      INTEGER DEFAULT 0,
            confidence     REAL DEFAULT 0.0,
            first_seen     TEXT,
            last_seen      TEXT,
            times_of_day   TEXT DEFAULT '[]',
            days_of_week   TEXT DEFAULT '[]',
            suggestion     TEXT,
            dismissed      INTEGER DEFAULT 0,
            active         INTEGER DEFAULT 1
        );

        CREATE UNIQUE INDEX IF NOT EXISTS idx_lp_key ON learned_patterns(pattern_type, pattern_key);
        CREATE INDEX IF NOT EXISTS idx_lp_active ON learned_patterns(active, confidence);
    """)
    conn.commit()
    conn.close()


# ── 事件日志 ──────────────────────────────────────────────────────────────

def log_event(event_type: str, source: str = None, file_path: str = None,
              folder_path: str = None, text_snippet: str = None,
              session_id: str = None, metadata: dict = None):
    """记录一条行为事件"""
    conn = get_db()
    conn.execute(
        """INSERT INTO behavior_events 
           (event_type, source, file_path, folder_path, text_snippet, session_id, metadata)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (event_type, source, file_path, folder_path,
         (text_snippet or '')[:500], session_id,
         json.dumps(metadata or {}, ensure_ascii=False))
    )
    conn.commit()
    conn.close()


def get_events(event_type: str = None, since_hours: int = 24, limit: int = 500):
    """获取事件记录"""
    conn = get_db()
    if event_type:
        cur = conn.execute(
            """SELECT * FROM behavior_events 
               WHERE event_type = ? AND timestamp > datetime('now', ?)
               ORDER BY timestamp DESC LIMIT ?""",
            (event_type, f'-{since_hours} hours', limit)
        )
    else:
        cur = conn.execute(
            """SELECT * FROM behavior_events 
               WHERE timestamp > datetime('now', ?)
               ORDER BY timestamp DESC LIMIT ?""",
            (f'-{since_hours} hours', limit)
        )
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def count_events_last_24h() -> int:
    conn = get_db()
    cur = conn.execute(
        "SELECT COUNT(*) as cnt FROM behavior_events WHERE timestamp > datetime('now', '-1 day')"
    )
    cnt = cur.fetchone()['cnt']
    conn.close()
    return cnt


def get_db_size_mb() -> float:
    if os.path.exists(DB_PATH):
        return round(os.path.getsize(DB_PATH) / (1024 * 1024), 2)
    return 0.0


# ── 学习模式 ──────────────────────────────────────────────────────────────

def upsert_pattern(pattern_type: str, pattern_key: str, pattern_value: str,
                   frequency: int = 1, confidence: float = 0.0,
                   suggestion: str = None):
    """新增或更新一条学习模式"""
    conn = get_db()
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    existing = conn.execute(
        "SELECT * FROM learned_patterns WHERE pattern_type=? AND pattern_key=?",
        (pattern_type, pattern_key)
    ).fetchone()

    if existing:
        conn.execute(
            """UPDATE learned_patterns SET frequency=frequency+?, confidence=?,
               last_seen=?, suggestion=COALESCE(?, suggestion)
               WHERE id=?""",
            (frequency, confidence, now, suggestion, existing['id'])
        )
    else:
        conn.execute(
            """INSERT INTO learned_patterns 
               (pattern_type, pattern_key, pattern_value, frequency, confidence,
                first_seen, last_seen, suggestion)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (pattern_type, pattern_key, pattern_value, frequency,
             confidence, now, now, suggestion)
        )
    conn.commit()
    conn.close()


def get_active_patterns(limit: int = 5, min_confidence: float = 0.5):
    """获取活跃的学习模式"""
    conn = get_db()
    cur = conn.execute(
        """SELECT * FROM learned_patterns 
           WHERE active=1 AND dismissed=0 AND confidence>=?
           ORDER BY confidence DESC LIMIT ?""",
        (min_confidence, limit)
    )
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def dismiss_pattern(pattern_id: int):
    conn = get_db()
    conn.execute("UPDATE learned_patterns SET dismissed=1 WHERE id=?", (pattern_id,))
    conn.commit()
    conn.close()


# ── 数据清理 ──────────────────────────────────────────────────────────────

def purge_old_events(retention_days: int = 30):
    """清理超过保留期的原始事件"""
    conn = get_db()
    cur = conn.execute(
        "DELETE FROM behavior_events WHERE timestamp < datetime('now', ?)",
        (f'-{retention_days} days',)
    )
    deleted = cur.rowcount
    conn.commit()
    conn.close()
    return deleted
