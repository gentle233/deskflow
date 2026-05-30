"""
DeskFlow 自动学习 — PostTurn Hook
每次对话后从用户消息中提取偏好/习惯信息

借鉴 OpenHuman 的 Aho-Corasick 思路，用正则匹配中文偏好句式
"""
import re
from autolearn.models import log_event

# 中文偏好句式（参考 OpenHuman 的 6 维分类，简化为 DeskFlow 场景）
PREFERENCE_PATTERNS = [
    # 显式偏好 (Explicit)
    (r'(?:我)?(?:喜欢|偏爱|偏好|更爱)(?:用|使用)?(.{2,40})', 'style'),
    (r'(?:我)?(?:习惯|通常|经常|总是|一般)(?:会|都)?(.{2,40})', 'style'),
    (r'(?:我)?(?:不要|别|不用|避免|不喜欢|讨厌|拒绝)(.{2,40})', 'veto'),
    (r'(?:我)?(?:是|是一名|我的角色是|我在)(.{2,40}?(?:工程师|医生|老师|学生|经理|运营|产品|设计))', 'identity'),
    (r'(?:我)?(?:在|正在|想|打算|计划)(?:学|做|搞|写|研究)(.{2,40})', 'goal'),
    (r'每周|每天|每个月|每季度', 'recurrence'),
    # 常用文件夹/文件操作
    (r'(?:帮我|请|麻烦)(?:打开|找|搜索|查)(.{2,40}?(?:文件|文档|文件夹|目录))', 'file_pattern'),
    (r'(?:总是|经常|每次)(?:在|从)(.{2,40}?(?:文件夹|目录|路径|位置))', 'file_pattern'),
    # 工具偏好
    (r'(?:用|使用)(?:的|的是)?(.{2,20}?(?:Excel|Word|WPS|钉钉|微信|企业微信|飞书))', 'tooling'),
]

# 简单词汇匹配（性能优于正则，适合常用词）
FAST_TRIGGERS = [
    '我喜欢', '我习惯', '我经常', '我一般', '我不喜欢', '帮我', '请',
]


def extract_preferences(text: str) -> list:
    """从用户消息中提取偏好陈述，返回 [(偏好文本, 类型), ...]"""
    results = []
    for pattern, ptype in PREFERENCE_PATTERNS:
        matches = re.findall(pattern, text)
        for m in matches:
            # m 可能是 tuple（如果有 group），也可能是 str
            snippet = m if isinstance(m, str) else ' '.join(filter(None, m))
            snippet = snippet.strip().rstrip('。，！？,.!?')
            if len(snippet) >= 4:
                results.append((snippet, ptype))
    return results


def on_user_message(user_input: str, session_id: str = None):
    """用户消息处理钩子 — 由 orchestrator 在每次用户发言后调用"""
    if not user_input or len(user_input) < 4:
        return

    # 检查是否有触发词
    has_trigger = False
    for trigger in FAST_TRIGGERS:
        if trigger in user_input:
            has_trigger = True
            break

    if not has_trigger and len(user_input) > 50:
        # 长消息也可能包含隐式偏好
        pass

    preferences = extract_preferences(user_input)
    for snippet, ptype in preferences:
        log_event('chat_preference', source='chat_hook',
                  text_snippet=f"[{ptype}] {snippet}",
                  session_id=session_id)
