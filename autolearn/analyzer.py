"""
DeskFlow 自动学习 — 分析引擎

频率分析 + 时间模式 + 短语提取 + 稳定性评分
由 APScheduler 定时调度运行
"""
import json
import os
import re
from datetime import datetime, timedelta
from collections import Counter

from autolearn.models import get_db, upsert_pattern


# ══════════════════════════════════════════════════════════════════════
# 1) 高频文件夹分析
# ══════════════════════════════════════════════════════════════════════

def analyze_frequent_folders(window_hours: int = 24, min_count: int = 3):
    """分析近期高频文件夹"""
    conn = get_db()
    cur = conn.execute("""
        SELECT folder_path, COUNT(*) as cnt
        FROM behavior_events
        WHERE event_type IN ('file_modified','file_created','file_open')
          AND folder_path IS NOT NULL
          AND timestamp > datetime('now', ?)
        GROUP BY folder_path
        HAVING cnt >= ?
        ORDER BY cnt DESC
        LIMIT 10
    """, (f'-{window_hours} hours', min_count))

    for row in cur.fetchall():
        folder = row['folder_path']
        count = row['cnt']
        confidence = min(count / 10.0, 1.0)  # 10次 = 满分
        upsert_pattern(
            'frequent_folder', f"folder:{folder}",
            folder, frequency=count, confidence=confidence,
            suggestion=f"快速打开 {os.path.basename(folder)}"
        )
    conn.close()


# ══════════════════════════════════════════════════════════════════════
# 2) 周期性行为检测
# ══════════════════════════════════════════════════════════════════════

def detect_time_patterns(window_days: int = 14):
    """检测每周期性行为"""
    conn = get_db()
    cur = conn.execute("""
        SELECT strftime('%w', timestamp) as dow,
               strftime('%H', timestamp) as hour,
               file_path,
               folder_path,
               COUNT(*) as cnt
        FROM behavior_events
        WHERE event_type IN ('file_modified','file_created')
          AND timestamp > datetime('now', ?)
        GROUP BY dow, hour, file_path
        HAVING cnt >= 2
        ORDER BY cnt DESC
        LIMIT 20
    """, (f'-{window_days} days',))

    dow_names = ['周日', '周一', '周二', '周三', '周四', '周五', '周六']

    for row in cur.fetchall():
        dow = int(row['dow'])
        hour = row['hour']
        path = row['file_path'] or row['folder_path'] or ''
        count = row['cnt']
        basename = os.path.basename(path) if path else ''

        # 关键词判断是否为周报/日报类文件
        is_report = any(kw in (basename or '').lower() for kw in ['周报', '日报', 'report', 'weekly', 'summary', '总结'])

        if is_report:
            confidence = min(count / 3.0, 1.0)
            upsert_pattern(
                'weekly_report', f"weekly:{path}",
                path, frequency=count, confidence=confidence,
                suggestion=f"📝 又到{dow_names[dow]}了，该写报告了！"
            )
        elif count >= 3:
            confidence = min(count / 5.0, 1.0)
            upsert_pattern(
                'repeated_action', f"action:{dow}:{hour}:{basename}",
                f"{dow_names[dow]} {hour}:00 {basename}",
                frequency=count, confidence=confidence,
                suggestion=f"🔄 你经常在{dow_names[dow]} {hour}:00 打开 {basename}"
            )
    conn.close()


# ══════════════════════════════════════════════════════════════════════
# 3) 常用短语提取
# ══════════════════════════════════════════════════════════════════════

# 中文停用词（过滤无关高频词）
STOP_WORDS = {'的', '了', '在', '是', '我', '有', '和', '就', '不', '人',
              '都', '一', '一个', '上', '也', '很', '到', '说', '要', '去',
              '你', '会', '着', '没有', '看', '好', '自己', '这', '他', '她',
              '它', '们', '那', '什么', '吗', '啊', '哦', '嗯', '呢', '吧'}


def extract_common_phrases(min_freq: int = 3):
    """从剪贴板记录和对话偏好中提取高频短语"""
    conn = get_db()

    texts = []
    cur = conn.execute("""
        SELECT text_snippet FROM behavior_events
        WHERE event_type IN ('clipboard', 'chat_preference')
          AND text_snippet IS NOT NULL
          AND length(text_snippet) BETWEEN 4 AND 200
          AND timestamp > datetime('now', '-30 days')
    """)
    texts = [r['text_snippet'] for r in cur.fetchall()]

    if len(texts) < min_freq:
        conn.close()
        return

    # 收集完整句子（去掉 [type] 前缀）
    sentences = [re.sub(r'^\[.*?\]\s*', '', t).strip() for t in texts]
    sentences = [s for s in sentences if len(s) >= 4]

    # 统计完整句子频率
    sentence_counts = Counter(sentences)
    
    # 统计3-5字短语
    phrase_counts = Counter()
    for s in sentences:
        chars = list(s)
        # 3-gram
        for i in range(len(chars) - 2):
            phrase = ''.join(chars[i:i + 3])
            if not re.match(r'^[\d\W]+$', phrase) and phrase not in STOP_WORDS:
                phrase_counts[phrase] += 1
        # 4-gram
        for i in range(len(chars) - 3):
            phrase = ''.join(chars[i:i + 4])
            if not re.match(r'^[\d\W]+$', phrase):
                phrase_counts[phrase] += 1

    # 先保存完整句子的高频短语
    for sent, count in sentence_counts.most_common(10):
        if count >= min_freq and len(sent) >= 4:
            confidence = min(count / 5.0, 1.0)
            upsert_pattern(
                'common_phrase', f"sentence:{sent}",
                sent, frequency=count, confidence=confidence,
                suggestion=f"💬 常用短语: \"{sent}\""
            )

    # 再保存非子串的高频短语（3-4字）
    saved = set()
    for phrase, count in phrase_counts.most_common(20):
        if count < min_freq:
            continue
        if re.match(r'^[\d\W]+$', phrase):
            continue
        # 跳过已保存句子的子串
        is_substring = any(phrase in s for s in saved if len(s) > len(phrase))
        if is_substring:
            continue
        confidence = min(count / 8.0, 1.0)
        upsert_pattern(
            'common_phrase', f"phrase:{phrase}",
            phrase, frequency=count, confidence=confidence,
            suggestion=f"💬 常用短语: \"{phrase}\""
        )
        saved.add(phrase)
    conn.close()


# ══════════════════════════════════════════════════════════════════════
# 4) 数据清理
# ══════════════════════════════════════════════════════════════════════

def purge_old_data(retention_days: int = 30):
    """清理过期数据"""
    from autolearn.models import purge_old_events
    deleted = purge_old_events(retention_days)
    if deleted:
        print(f"[autolearn] 清理了 {deleted} 条过期事件")


# ══════════════════════════════════════════════════════════════════════
# 5) 主分析循环
# ══════════════════════════════════════════════════════════════════════

def run_analysis():
    """运行所有分析任务（由 APScheduler 调度）"""
    try:
        analyze_frequent_folders(window_hours=24, min_count=3)
        detect_time_patterns(window_days=14)
        extract_common_phrases(min_freq=3)
        print(f"[autolearn] 分析完成 @ {datetime.now().strftime('%H:%M:%S')}")
    except Exception as e:
        print(f"[autolearn] 分析异常: {e}")
