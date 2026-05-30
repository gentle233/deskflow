# DeskFlow 自动学习引擎 — 实施方案

> 参考: OpenHuman (tinyhumansai) 学习系统 + 通用桌面 AI 行为学习模式
> 适用: DeskFlow (Flask + HTML/JS + SQLite)

---

## 一、设计目标

| 维度 | 目标 |
|------|------|
| **对用户** | 使用越久越懂你：自动记住常用文件夹、常用短语、周报模式、文件操作习惯 |
| **对开发者** | 增量开发，不改现有核心引擎，依赖 < 3 个轻量库 |
| **对隐私** | 100% 本地，不联网，不记录键盘输入，30天自动清理 |
| **对性能** | 空闲CPU < 0.5%，存储增长 < 5MB/天 |

---

## 二、核心架构

借鉴 OpenHuman 的"采集→评分→注入"三层模型，简化适配到 Flask 架构：

```
┌────────────────────────────────────────────────────────┐
│                    DeskFlow Auto-Learn                   │
├────────────────────────────────────────────────────────┤
│                                                        │
│  Layer 1: 采集层 (Collectors)                            │
│  ┌──────────┐  ┌────────────┐  ┌──────────────────┐    │
│  │ watchdog  │  │  剪贴板    │  │ 对话偏好提取器    │    │
│  │ 文件监听  │  │  轮询器    │  │ (PostTurn Hook)  │    │
│  └─────┬────┘  └─────┬──────┘  └────────┬─────────┘    │
│        │             │                  │              │
│        ▼             ▼                  ▼              │
│  ┌──────────────────────────────────────────────┐      │
│  │         behavior_events (SQLite)              │      │
│  │  事件: file_open / folder_browse / clipboard   │      │
│  │        chat_preference / app_focus             │      │
│  └─────────────────────┬────────────────────────┘      │
│                        │                               │
│  Layer 2: 分析层 (每分钟/每小时 batch)                   │
│  ┌──────────────────────────────────────────────┐      │
│  │  频率分析 → 时间模式 → 短语提取 → 稳定性评分    │      │
│  └─────────────────────┬────────────────────────┘      │
│                        │                               │
│                        ▼                               │
│  ┌──────────────────────────────────────────────┐      │
│  │         learned_patterns (SQLite)             │      │
│  │  类型: frequent_folder / weekly_report /       │      │
│  │        common_phrase / repeated_action         │      │
│  └─────────────────────┬────────────────────────┘      │
│                        │                               │
│  Layer 3: 建议层 / Prompt 注入                         │
│  ┌──────────────────────────────────────────────┐      │
│  │  规则打分器 → 置信度 > 0.7 → 展示/注入         │      │
│  │  · 首页建议卡片  · 快捷指令建议                 │      │
│  │  · 定时提醒  · 系统Prompt注入                  │      │
│  └──────────────────────────────────────────────┘      │
└────────────────────────────────────────────────────────┘
```

---

## 三、数据模型

### 3.1 behavior_events 表 (原始日志)

```sql
CREATE TABLE behavior_events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp   TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    event_type  TEXT NOT NULL,     -- file_open|folder_browse|clipboard|chat_preference|app_focus
    source      TEXT,              -- 'watchdog'|'clipboard_poll'|'chat_hook'|'focus_poll'
    file_path   TEXT,              -- 文件路径
    folder_path TEXT,              -- 文件夹路径
    text_snippet TEXT,             -- 剪贴板内容或偏好陈述（最长500字）
    session_id  TEXT,              -- 关联的对话session
    metadata    TEXT DEFAULT '{}'  -- JSON 扩展字段
);

CREATE INDEX idx_be_time   ON behavior_events(timestamp);
CREATE INDEX idx_be_type   ON behavior_events(event_type);
CREATE INDEX idx_be_file   ON behavior_events(file_path);
CREATE INDEX idx_be_folder ON behavior_events(folder_path);
```

### 3.2 learned_patterns 表 (分析结果)

```sql
CREATE TABLE learned_patterns (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    pattern_type   TEXT NOT NULL,  -- frequent_folder|weekly_report|common_phrase|repeated_action|user_preference
    pattern_key    TEXT NOT NULL,  -- 唯一标识，如 "folder:/home/user/Documents"
    pattern_value  TEXT,           -- 值，如文件夹名或短语文本
    frequency      INTEGER DEFAULT 0,
    confidence     REAL DEFAULT 0.0,  -- 0.0 ~ 1.0
    first_seen     TEXT,
    last_seen      TEXT,
    times_of_day   TEXT,           -- JSON array ["09:00","10:00"...]
    days_of_week   TEXT,           -- JSON array [1,2,3,4,5]
    suggestion     TEXT,           -- 预生成的建议文本
    dismissed      INTEGER DEFAULT 0,  -- 用户是否已忽略
    active         INTEGER DEFAULT 1
);

CREATE UNIQUE INDEX idx_lp_key   ON learned_patterns(pattern_type, pattern_key);
CREATE INDEX idx_lp_active       ON learned_patterns(active, confidence);
```

---

## 四、Phase 1：基础采集（1-2天）

### 4.1 文件结构

```
deskflow/
├── autolearn/
│   ├── __init__.py
│   ├── collector.py       # 采集器：watchdog + 剪贴板 + 焦点
│   ├── analyzer.py        # 分析器：频率/时间/短语
│   ├── suggester.py       # 建议生成器
│   ├── models.py          # 数据模型和DB操作
│   └── hooks.py           # PostTurn Hook（对话偏好提取）
```

### 4.2 依赖

```bash
pip install watchdog pyperclip apscheduler
```

全部轻量级纯 Python，无 GPU/ML 依赖。

### 4.3 Collector — 3 路采集

```python
# autolearn/collector.py

# 1) watchdog 文件监听
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

class FileWatcher(FileSystemEventHandler):
    """监听桌面/文档/下载三个文件夹的文件打开/修改"""
    def on_modified(self, event):
        if not event.is_directory:
            log_event('file_modified', file_path=event.src_path)
    def on_created(self, event):
        log_event('file_created', file_path=event.src_path)

# 2) 剪贴板轮询（每5秒）
def clipboard_poll_loop():
    """监测剪贴板变化，只记录粘贴操作，不记录按键"""
    old = ''
    while running:
        try:
            new = pyperclip.paste()
            if new and new != old and len(new) < 500:
                log_event('clipboard', text_snippet=new)
                old = new
        except: pass
        time.sleep(5)

# 3) 窗口焦点（跨平台）
def get_active_window():
    """返回当前活跃窗口标题"""
    import platform
    if platform.system() == 'Windows':
        import win32gui
        return win32gui.GetWindowText(win32gui.GetForegroundWindow())
    elif platform.system() == 'Linux':
        import subprocess
        return subprocess.getoutput("xdotool getactivewindow getwindowname")
    return ''
```

### 4.4 PostTurn Hook — 对话偏好提取

每轮对话完成后，从用户消息中提取偏好陈述。借鉴 OpenHuman 的 Aho-Corasick 思路，用正则匹配中文偏好句式：

```python
# autolearn/hooks.py

PREFERENCE_PATTERNS = [
    r'(我喜欢|我更倾向|偏好|习惯)(用|使用|读|写)?(.{2,50})',
    r'(不要|别|不用|避免|不喜欢|讨厌)(.{2,50})',
    r'(每周|每天|经常|总是)(.{2,50})',
    r'(帮我|请|麻烦)(.{2,50})',
]
```

匹配结果 → `log_event('chat_preference', text_snippet=matched_phrase)`

---

## 五、Phase 2：分析引擎（2-3天）

### 5.1 频率分析

```python
# autolearn/analyzer.py

def analyze_frequent_folders(window_hours=24, min_count=3):
    """过去N小时内访问超过M次的文件夹"""
    cur.execute("""
        SELECT folder_path, COUNT(*) as cnt
        FROM behavior_events
        WHERE event_type = 'folder_browse' AND timestamp > datetime('now', ?)
        GROUP BY folder_path HAVING cnt >= ?
        ORDER BY cnt DESC
    """, (f'-{window_hours} hours', min_count))
```

### 5.2 时间模式检测

```python
def detect_time_patterns(window_days=14):
    """检测周期性行为：每周X的Y点做什么"""
    cur.execute("""
        SELECT strftime('%w', timestamp) as dow,   -- 0=周日
               strftime('%H', timestamp) as hour,
               file_path,
               COUNT(*) as cnt
        FROM behavior_events
        WHERE event_type = 'file_open' AND timestamp > datetime('now', ?)
        GROUP BY dow, hour, file_path
        HAVING cnt >= 2  -- 至少出现2次
        ORDER BY cnt DESC LIMIT 20
    """, (f'-{window_days} days',))
```

### 5.3 常用短语提取

从剪贴板事件中提取高频短语（借鉴 OpenHuman 的 n-gram 思路）：

```python
def extract_common_phrases(min_freq=3):
    """从剪贴板记录中找高频短语（2-5字词）"""
    # 中文分词（jieba）或简单2-gram
    # 只保留长度5-50字、出现>=3次的短语
```

### 5.4 稳定性评分（简化版）

借鉴 OpenHuman 但大幅简化，不用指数衰减公式：

```python
def calc_confidence(events):
    """基于时间衰减的置信度"""
    if len(events) == 0: return 0.0
    now = datetime.now()
    scores = []
    for e in events:
        age_hours = (now - parse_time(e[0])).total_seconds() / 3600
        score = 1.0 / (1.0 + age_hours / 24)  # 越新越高
        scores.append(score)
    return min(sum(scores) / max(len(scores), 1), 1.0)
```

---

## 六、Phase 3：建议与注入（1-2天）

### 6.1 API 端点

```python
# main.py 新增

@app.route("/api/autolearn/suggestions")
def get_suggestions():
    """获取排名前3的学习建议"""
    patterns = get_active_patterns(limit=3, min_confidence=0.6)
    return jsonify([{
        'id': p.id,
        'type': p.pattern_type,
        'title': generate_title(p),
        'action': generate_action(p),
        'confidence': p.confidence
    } for p in patterns])

@app.route("/api/autolearn/dismiss/<int:pattern_id>")
def dismiss_suggestion(pattern_id):
    """用户忽略某条建议"""
    mark_dismissed(pattern_id)
    return jsonify({"status": "ok"})

@app.route("/api/autolearn/stats")
def get_learning_stats():
    """学习统计（设置页面展示）"""
    total = count_events()
    patterns = count_patterns()
    return jsonify({
        'events_today': count_events_last_24h(),
        'active_patterns': patterns,
        'storage_mb': get_db_size_mb()
    })
```

### 6.2 前端展示

在聊天页面添加"智能建议"面板（侧边栏或下拉）：

```
┌─────────────────────────┐
│ DeskFlow  💬 ⚙️ 📥      │
├─────────────────────────┤
│                         │
│  [聊天记录区域]          │
│                         │
├─────────────────────────┤
│ 💡 为您推荐             │
│ 📂 快速打开: 报销文件    │
│ 💬 常用短语: "请查收"   │
│ 📝 该写周报了           │
│                    [✕]  │
├─────────────────────────┤
│ 输入框                   │
└─────────────────────────┘
```

### 6.3 Prompt 注入（可选）

借鉴 OpenHuman 的方式，在 MASTER_PROMPT 中注入学习到的用户偏好：

```
## 学习到的用户偏好
- 常用文件夹: ~/Desktop/工作报销/
- 常用短语: "请查收附件"
- 偏好简洁回复
```

这样 LLM 会自动适应你的习惯。

---

## 七、隐私与安全（红线）

| 红线 | 说明 |
|------|------|
| ❌ 不记录键盘输入 | 只记录剪贴板变化（粘贴后），不记录击键 |
| ❌ 不截图 | 不截屏、不OCR，避免敏感信息泄露 |
| ❌ 不发云端 | 所有数据 100% 本地 SQLite |
| ❌ 不记录密码 | 排除含 "密码/密码输入" 等关键词的窗口标题 |
| ✅ 一键暂停 | 设置页提供"暂停学习"开关，立即停止所有采集 |
| ✅ 自动清理 | 事件日志保留30天，超出自动删除 |

---

## 八、实施路线图

| Phase | 内容 | 文件 | 预估 |
|-------|------|------|------|
| **P1** | 采集器：watchdog + 剪贴板 + 焦点 + DB | `autolearn/collector.py`, `models.py` | 2天 |
| **P2** | 分析引擎：频率/时间/短语 + 评分 | `autolearn/analyzer.py` + hooks | 3天 |
| **P3** | API + 前端展示 + 建议卡片 | `main.py` + settings.html + app.js | 2天 |
| **P4** | 优化：用户反馈循环 + 数据清理 + 设置 | 各种收尾 | 1天 |

**总计：约 8 天**

---

## 九、与 OpenHuman 的关键差异

| 维度 | OpenHuman | DeskFlow (本方案) |
|------|-----------|-------------------|
| 语言 | Rust + TypeScript | Python + JS |
| 存储 | SQLite + on-disk md | SQLite |
| 画像维度 | 6维（含开发者信息） | 简化：文件/短语/时间/偏好 |
| 稳定性公式 | 指数衰减 + 多类阈值 | 简化版时间衰减 |
| 半衰期 | 7-90天不等 | 统一24小时基准 |
| LLM反思 | 每次对话后LLM提取 | 可选，轻量版 |
| 建议展示 | "Intelligence"面板 | 聊天侧边栏卡片 |
| Prompt注入 | 结构化 section | 可选注入系统提示 |

---

## 十、不建议做的功能

基于 OpenHuman 的经验教训：

1. **不要**一开始就上向量嵌入（sentence-transformers 100MB+，太重）
2. **不要**做 LLM 驱动的反思（每轮对话多一次 API 调用，成本高）
3. **不要**做实时分析（每个事件都分析 → CPU 飙升）→ 用 APScheduler 每分钟批量跑
4. **不要**存储超过 30 天的原始事件 → `DELETE FROM behavior_events WHERE timestamp < datetime('now', '-30 days')`
5. **不要**弹太多建议 → 最多 3 条，用户 dismiss 后 24 小时内不再出现
