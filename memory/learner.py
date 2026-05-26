"""自动学习引擎"""
from memory.store import get_conn

class Learner:
    """观察用户行为，自动推论偏好"""

    OBSERVATIONS = []

    @staticmethod
    def observe(action: str, detail: str = ""):
        conn = get_conn()
        conn.execute(
            "INSERT INTO history (role, content) VALUES (?, ?)",
            ("observation", f"{action}: {detail}")
        )
        conn.commit()
        conn.close()
