# DeskFlow 安全便利功能 Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** 实现安全便利板块的3项功能 — 快捷指令、聊天历史导出、提示音

**Architecture:** 全部在现有 Flask + 纯前端架构上增量添加，不改动核心引擎。快捷指令用 JSON 文件持久化，聊天历史导出用后端生成文件下载，提示音纯前端 Web Audio API。

**Tech Stack:** Flask, JavaScript (ES6), HTML5 Audio API, localStorage, marked.js

---

### Task 1: 快捷指令 — 后端 API

**Objective:** 提供快捷指令的 CRUD 接口，持久化到 `~/.deskflow/shortcuts.json`

**Files:**
- Create: `~/deskflow/core/shortcuts.py`
- Modify: `~/deskflow/main.py` (新增 3 个 API 端点)

**Step 1: 创建 core/shortcuts.py**

```python
"""快捷指令管理"""
import json, os

SHORTCUTS_PATH = os.path.expanduser("~/.deskflow/shortcuts.json")

DEFAULT_SHORTCUTS = [
    {"trigger": "/date", "command": "今天是几月几号？请告诉我今天的日期", "desc": "查询日期"},
    {"trigger": "/time", "command": "现在几点了？", "desc": "查询时间"},
    {"trigger": "/weather", "command": "今天天气怎么样？", "desc": "查询天气"},
    {"trigger": "/help", "command": "你能做什么？介绍一下你的功能", "desc": "查看帮助"},
]

def load_shortcuts() -> list:
    if not os.path.exists(SHORTCUTS_PATH):
        os.makedirs(os.path.dirname(SHORTCUTS_PATH), exist_ok=True)
        save_shortcuts(DEFAULT_SHORTCUTS)
        return list(DEFAULT_SHORTCUTS)
    with open(SHORTCUTS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def save_shortcuts(shortcuts: list):
    os.makedirs(os.path.dirname(SHORTCUTS_PATH), exist_ok=True)
    with open(SHORTCUTS_PATH, "w", encoding="utf-8") as f:
        json.dump(shortcuts, f, ensure_ascii=False, indent=2)

def add_shortcut(trigger: str, command: str, desc: str = "") -> dict:
    shortcuts = load_shortcuts()
    # 去重
    shortcuts = [s for s in shortcuts if s["trigger"] != trigger]
    shortcuts.append({"trigger": trigger, "command": command, "desc": desc or command[:20]})
    save_shortcuts(shortcuts)
    return {"status": "ok", "shortcuts": shortcuts}

def delete_shortcut(trigger: str) -> dict:
    shortcuts = load_shortcuts()
    shortcuts = [s for s in shortcuts if s["trigger"] != trigger]
    save_shortcuts(shortcuts)
    return {"status": "ok", "shortcuts": shortcuts}
```

**Step 2: 在 main.py 添加 3 个 API 端点**

```python
# 在 main.py 中 imports 区域添加
from core.shortcuts import load_shortcuts, add_shortcut, delete_shortcut

# 在 save_search_config() 之后添加

@app.route("/api/shortcuts", methods=["GET"])
def get_shortcuts():
    """获取所有快捷指令"""
    return jsonify(load_shortcuts())

@app.route("/api/shortcuts", methods=["POST"])
def create_shortcut():
    """添加快捷指令"""
    data = request.json
    if not data or not data.get("trigger") or not data.get("command"):
        return jsonify({"status": "error", "error": "trigger 和 command 不能为空"}), 400
    result = add_shortcut(data["trigger"], data["command"], data.get("desc", ""))
    return jsonify(result)

@app.route("/api/shortcuts/<trigger>", methods=["DELETE"])
def remove_shortcut(trigger):
    """删除快捷指令"""
    result = delete_shortcut(trigger)
    return jsonify(result)
```

**Step 3: 验证**

Run: `cd ~/deskflow && python -c "from core.shortcuts import load_shortcuts; sc = load_shortcuts(); print(f'{len(sc)} shortcuts loaded')"`
Expected: `4 shortcuts loaded`

Run: `python -c "from core.shortcuts import add_shortcut, delete_shortcut; print(add_shortcut('/test', 'test command', '测试')); print(delete_shortcut('/test'))"`
Expected: ok status, shortcuts list returned

**Step 4: 验证 Flask 端点**

```bash
cd ~/deskflow && python main.py &
sleep 1
curl -s http://127.0.0.1:7788/api/shortcuts | python -m json.tool | head -20
kill %1 2>/dev/null
```
Expected: JSON array of 4 default shortcuts

**Step 5: 提交**

```bash
cd ~/deskflow
git add core/shortcuts.py main.py
git commit -m "feat: 快捷指令后端 API — CRUD + JSON持久化"
```

---

### Task 2: 快捷指令 — 前端界面

**Objective:** 设置页面添加快捷指令管理区域，聊天框支持 `/` 触发自动补全

**Files:**
- Modify: `~/deskflow/ui/templates/settings.html`
- Modify: `~/deskflow/ui/static/app.js`

**Step 1: settings.html 添加快捷指令区域**

在搜索设置 section 后面、连接检查 section 之前插入：

```html
<div class="section">
    <h3>快捷指令</h3>
    <div class="card">
        <div id="shortcut-list"></div>
        <div style="margin-top:12px;display:flex;gap:8px;flex-wrap:wrap">
            <input id="sc-trigger" placeholder="/前缀" style="flex:1;min-width:80px;padding:8px;border:1px solid #ddd;border-radius:6px">
            <input id="sc-command" placeholder="触发后发送的内容" style="flex:2;min-width:150px;padding:8px;border:1px solid #ddd;border-radius:6px">
            <button onclick="addShortcut()" style="padding:8px 16px;background:#4a7cff;color:#fff;border:none;border-radius:6px;cursor:pointer">添加</button>
        </div>
        <div id="sc-msg" style="font-size:12px;color:#999;padding:4px 0"></div>
    </div>
</div>
```

**Step 2: settings.html 添加 JS 函数**

```javascript
async function loadShortcuts() {
    const r = await fetch('/api/shortcuts');
    const list = await r.json();
    const el = document.getElementById('shortcut-list');
    el.innerHTML = list.map(s => `
        <div class="row">
            <span><code style="background:#f0f0f0;padding:2px 6px;border-radius:4px">${escapeHtml(s.trigger)}</code>
            <span style="color:#666;margin-left:8px">${escapeHtml(s.desc || s.command.slice(0, 20))}</span></span>
            <button onclick="deleteShortcut('${escapeHtml(s.trigger)}')" style="border:none;background:none;color:#ff4d4f;cursor:pointer;font-size:13px">✕</button>
        </div>
    `).join('');
}
async function addShortcut() {
    const t = document.getElementById('sc-trigger').value.trim();
    const c = document.getElementById('sc-command').value.trim();
    if (!t || !c) { document.getElementById('sc-msg').textContent = '请填写触发词和内容'; return; }
    const r = await fetch('/api/shortcuts', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({trigger:t, command:c})});
    const data = await r.json();
    if (data.status === 'ok') {
        document.getElementById('sc-msg').textContent = '✅ 已添加';
        document.getElementById('sc-trigger').value = '';
        document.getElementById('sc-command').value = '';
        loadShortcuts();
    } else {
        document.getElementById('sc-msg').textContent = '❌ ' + (data.error || '添加失败');
    }
}
async function deleteShortcut(trigger) {
    await fetch(`/api/shortcuts/${encodeURIComponent(trigger)}`, {method:'DELETE'});
    loadShortcuts();
}
function escapeHtml(s) { return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); }
```

在 settings.html 的 loadSearchConfig() 调用后添加 `loadShortcuts();`

**Step 3: app.js 添加快捷指令检测逻辑**

在 send() 函数中，在 `const text = input.value.trim();` 之后添加：

```javascript
// 检查是否是快捷指令
const shortcuts = await (await fetch('/api/shortcuts')).json();
const match = shortcuts.find(s => s.trigger === text);
if (match) { text = match.command; }
```

注意：由于 send() 是 async 函数，这个 fetch 调用是合理的。为了避免每次发送都请求 API，可以在页面加载时缓存一份到变量。

**Step 4: app.js 添加 / 输入提示**

在 input 的 keydown 事件监听中，当输入以 `/` 开头时显示快捷指令提示浮层：

```javascript
// 在 input-area 添加一个提示浮层容器
// <div id="sc-suggest" style="display:none;position:absolute;bottom:100%;left:0;right:0;background:#fff;border:1px solid #ddd;border-radius:8px;max-height:150px;overflow-y:auto;box-shadow:0 -2px 10px rgba(0,0,0,0.1)"></div>

input.addEventListener('input', () => {
    const val = input.value.trim();
    if (val.startsWith('/')) {
        const matched = shortcutsCache.filter(s => s.trigger.startsWith(val));
        if (matched.length > 0) {
            showSuggestions(matched);
        } else {
            hideSuggestions();
        }
    } else {
        hideSuggestions();
    }
});
```

**Step 5: 验证**

```bash
cd ~/deskflow && python main.py &
# 浏览器访问 http://127.0.0.1:7788/settings 查看快捷指令区域
# 测试添加/删除快捷指令
# 测试在聊天输入框输入 /date
kill %1 2>/dev/null
```

**Step 6: 提交**

```bash
git add ui/templates/settings.html ui/static/app.js
git commit -m "feat: 快捷指令前端 — 设置管理 + 聊天框触发"
```

---

### Task 3: 聊天历史导出

**Objective:** 在聊天界面添加导出按钮，支持 JSON 和 Markdown 两种格式下载

**Files:**
- Modify: `~/deskflow/ui/templates/chat.html` (导出按钮)
- Modify: `~/deskflow/ui/static/app.js` (导出逻辑)

**Step 1: chat.html 添加导出按钮**

在 header 的 settings 按钮旁边：

```html
<a href="javascript:void(0)" id="export-btn" title="导出聊天记录" style="margin-right:8px;text-decoration:none;font-size:18px">📥</a>
```

**Step 2: app.js 添加导出函数**

```javascript
function exportHistory(format) {
    const history = JSON.parse(localStorage.getItem('deskflow_history') || '[]');
    if (history.length === 0) {
        alert('暂无聊天记录可导出');
        return;
    }
    
    if (format === 'json') {
        const blob = new Blob([JSON.stringify(history, null, 2)], {type: 'application/json'});
        downloadBlob(blob, `deskflow-history-${Date.now()}.json`);
    } else if (format === 'md') {
        let md = `# DeskFlow 聊天记录\n\n导出时间: ${new Date().toLocaleString()}\n\n---\n\n`;
        for (const msg of history) {
            const role = msg.role === 'user' ? '**你**' : '**DeskFlow**';
            md += `### ${role} (${new Date(msg.time).toLocaleString()})\n\n${msg.content}\n\n---\n\n`;
        }
        const blob = new Blob([md], {type: 'text/markdown'});
        downloadBlob(blob, `deskflow-history-${Date.now()}.md`);
    }
}

function downloadBlob(blob, filename) {
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = filename;
    document.body.appendChild(a); a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
}

// 点击导出按钮时弹出格式选择
document.getElementById('export-btn')?.addEventListener('click', () => {
    const fmt = confirm('点击"确定"导出 JSON 格式，点击"取消"导出 Markdown 格式');
    exportHistory(fmt ? 'json' : 'md');
});
```

**Step 3: 验证**

打开聊天页面 → 有历史记录 → 点击导出按钮 → 下载文件

**Step 4: 提交**

```bash
git add ui/templates/chat.html ui/static/app.js
git commit -m "feat: 聊天历史导出 — JSON + Markdown 格式下载"
```

---

### Task 4: 提示音

**Objective:** 当 Assistant 回复完成时播放提示音（使用 Web Audio API 生成，无需外部音频文件）

**Files:**
- Modify: `~/deskflow/ui/templates/chat.html` (添加设置开关)
- Modify: `~/deskflow/ui/static/app.js` (提示音逻辑)

**Step 1: settings.html 添加提示音开关**

在功能状态 section 的快捷指令后面：

```html
<div class="row">
    <span class="label">提示音</span>
    <label><input type="checkbox" id="sound-toggle" checked> 消息提醒音</label>
</div>
```

JS:
```javascript
// 加载设置
document.getElementById('sound-toggle').checked = localStorage.getItem('deskflow_sound') !== 'off';
document.getElementById('sound-toggle').addEventListener('change', function() {
    localStorage.setItem('deskflow_sound', this.checked ? 'on' : 'off');
});
```

**Step 2: app.js 添加提示音函数**

```javascript
// 使用 Web Audio API 生成提示音（不需要音频文件）
function playNotificationSound() {
    if (localStorage.getItem('deskflow_sound') === 'off') return;
    try {
        const ctx = new (window.AudioContext || window.webkitAudioContext)();
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.connect(gain);
        gain.connect(ctx.destination);
        osc.frequency.value = 660;  // 悦耳的 E5
        osc.type = 'sine';
        gain.gain.setValueAtTime(0.3, ctx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.15);
        osc.start(ctx.currentTime);
        osc.stop(ctx.currentTime + 0.15);
    } catch(e) { /* 静默失败 */ }
}
```

**Step 3: 在 SSE 完成时触发提示音**

在 app.js 的 SSE 读取循环中，当收到 `data.done` 时：

```javascript
} else if (data.done) {
    playNotificationSound();
    saveToHistory(lastUserText, fullText);
}
```

以及在非流式回复（addMessage 直接添加的 assistant 消息）完成时也触发。

**Step 4: 非流式消息也触发提示音**

在 addMessage 函数中，当 role === 'assistant' 时调用：

```javascript
function addMessage(text, role) {
    // ... 现有逻辑 ...
    if (role === 'assistant') {
        setTimeout(playNotificationSound, 100); // 延迟确保 UI 先更新
    }
}
```

**Step 5: 提交**

```bash
git add ui/templates/chat.html ui/templates/settings.html ui/static/app.js
git commit -m "feat: 提示音 — Web Audio API 生成 + 设置开关"
```

---

### Task 5: 收尾 — 更新 TODO.md

**Objective:** 标记 3 项已完成，清理 stub 文件

**Files:**
- Modify: `~/deskflow/TODO.md`

**Step 1: 更新 TODO.md**

将安全便利板块的 3 项标记为 [x]，同时在「重要操作二次确认」标记为 [x]（已在 Phase 3 实现）。

**Step 2: 提交**

```bash
git add TODO.md
git commit -m "docs: 更新 TODO — 安全便利板块 3/3 完成"
```

---

### Task 6: 清理 ai-talent-grader 临时目录

**Objective:** 删除之前为修复终端创建的临时 stub skill

```bash
rm -rf /home/ubuntu/.hermes/skills/ai-talent-grader
```
