/**
 * DeskFlow 前端 — Markdown 渲染 + SSE 打字机 + 停止 + 历史持久化
 */
let selectedFile = null;
let abortController = null;
let isStreaming = false;
let lastUserText = '';
let shortcutsCache = [];

if (typeof marked !== 'undefined') {
    marked.setOptions({ breaks: true, gfm: true });
}

document.addEventListener('DOMContentLoaded', () => {
    const input = document.getElementById('input-box');
    const sendBtn = document.getElementById('send-btn');
    const stopBtn = document.getElementById('stop-btn');
    const chatBox = document.getElementById('chat-box');
    loadHistory();

    input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); if (isStreaming) return; send(); }
    });
    sendBtn.addEventListener('click', send);
    stopBtn.addEventListener('click', stopStream);

    document.body.addEventListener('dragover', (e) => { e.preventDefault(); showFileHint(); });
    document.body.addEventListener('dragleave', () => hideFileHint());
    document.body.addEventListener('drop', (e) => {
        e.preventDefault(); hideFileHint();
        const file = e.dataTransfer.files[0];
        if (file) { selectedFile = file; addMessage('\u5df2\u9009\u62e9\u6587\u4ef6: ' + file.name, 'user'); }
    });

    input.addEventListener('paste', (e) => {
        for (let item of e.clipboardData.items) {
            if (item.kind === 'file') {
                selectedFile = item.getAsFile();
                addMessage('\u5df2\u7c98\u8d34\u6587\u4ef6: ' + selectedFile.name, 'user');
            }
        }
    });

    async function send() {
        const text = input.value.trim();
        // 快捷指令检测
        let resolvedText = text;
        if (text.startsWith('/') && shortcutsCache.length > 0) {
            const match = shortcutsCache.find(s => s.trigger === text);
            if (match) resolvedText = match.command;
        }
        const finalText = resolvedText;
        if (!finalText && !selectedFile) return;
        lastUserText = text || (selectedFile ? '已发送了文件: ' + selectedFile.name : '');
        addMessage(lastUserText, 'user');
        input.value = '';
        // 隐藏提示浮层
        hideSuggestions();
        showTyping();
        sendBtn.disabled = true;
        stopBtn.style.display = 'inline-block';

        const formData = new FormData();
        formData.append('message', finalText);
        if (selectedFile) { formData.append('file', selectedFile); selectedFile = null; }

        abortController = new AbortController();
        isStreaming = true;

        try {
            const resp = await fetch('/api/chat/stream', {
                method: 'POST', body: formData, signal: abortController.signal
            });
            if (!resp.ok) throw new Error('HTTP ' + resp.status);

            const reader = resp.body.getReader();
            const decoder = new TextDecoder();
            let buffer = '';
            let fullText = '';

            const msgDiv = document.createElement('div');
            msgDiv.className = 'message assistant';
            msgDiv.innerHTML = '<div class="avatar">D</div><div class="bubble"></div>';
            chatBox.appendChild(msgDiv);
            const bubble = msgDiv.querySelector('.bubble');
            removeTyping();

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split('\n');
                buffer = lines.pop() || '';
                for (const line of lines) {
                    if (!line.startsWith('data: ')) continue;
                    try {
                        const data = JSON.parse(line.slice(6));
                        if (data.token) {
                            fullText += data.token;
                            bubble.innerHTML = renderMarkdown(fullText);
                            chatBox.scrollTop = chatBox.scrollHeight;
                        } else if (data.done) {
                            saveToHistory(lastUserText, fullText);
                        } else if (data.error) {
                            bubble.innerHTML = '\u274c ' + escapeHtml(data.error);
                        }
                    } catch(e) {}
                }
            }
            if (buffer.startsWith('data: ')) {
                try {
                    const data = JSON.parse(buffer.slice(6));
                    if (data.token) { fullText += data.token; bubble.innerHTML = renderMarkdown(fullText); }
                    else if (data.done) { saveToHistory(lastUserText, fullText); }
                } catch(e) {}
            }
        } catch (err) {
            if (err.name === 'AbortError') {}
            else { removeTyping(); addMessage('\u26a0\ufe0f \u8fde\u63a5\u5931\u8d25: ' + err.message, 'assistant'); }
        }
        isStreaming = false; abortController = null;
        sendBtn.disabled = false; stopBtn.style.display = 'none';
    }

    function stopStream() {
        if (abortController) {
            abortController.abort();
            isStreaming = false;
            const lastMsg = chatBox.querySelector('.message:last-child .bubble');
            if (lastMsg) { const text = lastMsg.textContent || ''; if (text) saveToHistory(lastUserText, text); }
        }
    }

    function addMessage(text, role) {
        const div = document.createElement('div');
        div.className = 'message ' + role;
        const content = role === 'user' ? escapeHtml(text) : renderMarkdown(text);
        div.innerHTML = '<div class="avatar">' + (role === 'assistant' ? 'D' : 'U') + '</div><div class="bubble">' + content + '</div>';
        chatBox.appendChild(div);
        chatBox.scrollTop = chatBox.scrollHeight;
        if (role === 'user') saveToHistory(text, '');
    }

    function renderMarkdown(text) {
        if (typeof marked === 'undefined') return escapeHtml(text);
        try { return marked.parse(text); } catch(e) { return escapeHtml(text); }
    }

    function showTyping() {
        if (document.getElementById('typing-indicator')) return;
        const div = document.createElement('div');
        div.className = 'message assistant'; div.id = 'typing-indicator';
        div.innerHTML = '<div class="avatar">D</div><div class="bubble"><div class="typing"><span></span><span></span><span></span></div></div>';
        chatBox.appendChild(div); chatBox.scrollTop = chatBox.scrollHeight;
    }

    function removeTyping() {
        const el = document.getElementById('typing-indicator'); if (el) el.remove();
    }

    function showFileHint() { const el = document.getElementById('file-hint'); if (el) el.style.display = 'block'; }
    function hideFileHint() { const el = document.getElementById('file-hint'); if (el) el.style.display = 'none'; }
    function escapeHtml(str) { return str.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }

    // 导出聊天记录
    document.getElementById('export-btn')?.addEventListener('click', () => {
        const history = JSON.parse(localStorage.getItem('deskflow_history') || '[]');
        if (history.length === 0) { alert('暂无聊天记录可导出'); return; }
        const fmt = confirm('点击"确定"导出 JSON 格式，点击"取消"导出 Markdown 格式');
        if (fmt) {
            const blob = new Blob([JSON.stringify(history, null, 2)], {type: 'application/json'});
            downloadBlob(blob, 'deskflow-history-' + Date.now() + '.json');
        } else {
            let md = '# DeskFlow 聊天记录\n\n导出时间: ' + new Date().toLocaleString() + '\n\n---\n\n';
            for (const msg of history) {
                const role = msg.role === 'user' ? '**你**' : '**DeskFlow**';
                const time = msg.time ? new Date(msg.time).toLocaleString() : '未知时间';
                md += '### ' + role + ' (' + time + ')\n\n' + msg.content + '\n\n---\n\n';
            }
            const blob = new Blob([md], {type: 'text/markdown'});
            downloadBlob(blob, 'deskflow-history-' + Date.now() + '.md');
        }
    });
    function downloadBlob(blob, filename) {
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url; a.download = filename;
        document.body.appendChild(a); a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    }

    // History
    const STORAGE_KEY = 'deskflow_history';
    function saveToHistory(userMsg, assistantMsg) {
        let history = JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]');
        if (userMsg) history.push({ role: 'user', content: userMsg, time: Date.now() });
        if (assistantMsg) history.push({ role: 'assistant', content: assistantMsg, time: Date.now() });
        if (history.length > 50) history = history.slice(-50);
        localStorage.setItem(STORAGE_KEY, JSON.stringify(history));
    }
    function loadHistory() {
        const history = JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]');
        const recent = history.slice(-20);
        for (const msg of recent) {
            const div = document.createElement('div');
            div.className = 'message ' + msg.role;
            const content = msg.role === 'user' ? escapeHtml(msg.content) : renderMarkdown(msg.content);
            div.innerHTML = '<div class="avatar">' + (msg.role === 'assistant' ? 'D' : 'U') + '</div><div class="bubble">' + content + '</div>';
            chatBox.appendChild(div);
        }
        chatBox.scrollTop = chatBox.scrollHeight;
    }

    // 快捷指令 — 加载缓存
    async function loadShortcutsCache() {
        try {
            const r = await fetch('/api/shortcuts');
            shortcutsCache = await r.json();
        } catch(e) { shortcutsCache = []; }
    }
    loadShortcutsCache();

    // 快捷指令 — 输入提示
    const scSuggest = document.getElementById('sc-suggest');
    input.addEventListener('input', () => {
        const val = input.value.trim();
        if (val.startsWith('/') && shortcutsCache.length > 0) {
            const matched = shortcutsCache.filter(s => s.trigger.startsWith(val));
            if (matched.length > 0) {
                scSuggest.innerHTML = matched.map(s =>
                    `<div style="padding:8px 12px;cursor:pointer;border-bottom:1px solid #f0f0f0;font-size:13px" onmouseover="this.style.background='#f5f5f5'" onmouseout="this.style.background=''" onclick="document.getElementById('input-box').value='${escHtml(s.trigger)}';document.getElementById('sc-suggest').style.display='none';document.getElementById('input-box').focus()">
                        <code style="background:#e8f0ff;padding:1px 5px;border-radius:3px">${escHtml(s.trigger)}</code>
                        <span style="color:#888;margin-left:8px">${escHtml(s.desc || s.command.slice(0, 20))}</span>
                    </div>`
                ).join('');
                scSuggest.style.display = 'block';
                return;
            }
        }
        scSuggest.style.display = 'none';
    });
    function hideSuggestions() { if (scSuggest) scSuggest.style.display = 'none'; }
    // Click outside to close
    document.addEventListener('click', (e) => { if (scSuggest && !e.target.closest('#input-area')) scSuggest.style.display = 'none'; });
});
