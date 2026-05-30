/**
 * DeskFlow 前端 — Markdown 渲染 + SSE 打字机 + 停止 + 历史持久化
 */
let selectedFile = null;
let abortController = null;
let isStreaming = false;
let lastUserText = '';

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
        if (!text && !selectedFile) return;
        lastUserText = text || (selectedFile ? '\u53d1\u9001\u4e86\u6587\u4ef6: ' + selectedFile.name : '');
        addMessage(lastUserText, 'user');
        input.value = '';
        showTyping();
        sendBtn.disabled = true;
        stopBtn.style.display = 'inline-block';

        const formData = new FormData();
        formData.append('message', text);
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
});
