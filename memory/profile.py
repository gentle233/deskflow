"""用户画像管理"""
from memory.store import get_conn

class UserProfile:
    @staticmethod
    def get(key: str, default=None):
        conn = get_conn()
        cur = conn.execute("SELECT value FROM profile WHERE key=?", (key,))
        row = cur.fetchone()
        conn.close()
        return row[0] if row else default

    @staticmethod
    def set(key: str, value: str):
        conn = get_conn()
        conn.execute(
            "INSERT OR REPLACE INTO profile (key, value) VALUES (?, ?)",
            (key, value)
        )
        conn.commit()
        conn.close()

    @staticmethod
    def get_all() -> dict:
        conn = get_conn()
        cur = conn.execute("SELECT key, value FROM profile")
        result = dict(cur.fetchall())
        conn.close()
        return result
