let selectedFile = null;

document.addEventListener('DOMContentLoaded', () => {
    const input = document.getElementById('input-box');
    const sendBtn = document.getElementById('send-btn');
    const chatBox = document.getElementById('chat-box');

    // 回车发送
    input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            send();
        }
    });
    sendBtn.addEventListener('click', send);

    // 文件拖拽
    document.body.addEventListener('dragover', (e) => {
        e.preventDefault();
        document.getElementById('file-hint').style.display = 'block';
    });
    document.body.addEventListener('dragleave', () => {
        document.getElementById('file-hint').style.display = 'none';
    });
    document.body.addEventListener('drop', (e) => {
        e.preventDefault();
        document.getElementById('file-hint').style.display = 'none';
        const file = e.dataTransfer.files[0];
        if (file) {
            selectedFile = file;
            addMessage('已选择文件: ' + file.name, 'user');
        }
    });

    // 粘贴图片/文件
    input.addEventListener('paste', (e) => {
        const items = e.clipboardData.items;
        for (let item of items) {
            if (item.kind === 'file') {
                selectedFile = item.getAsFile();
                addMessage('已粘贴文件: ' + selectedFile.name, 'user');
            }
        }
    });

    async function send() {
        const text = input.value.trim();
        if (!text && !selectedFile) return;

        const userMsg = text || `发送了文件: ${selectedFile?.name}`;
        addMessage(userMsg, 'user');
        input.value = '';
        showTyping();

        try {
            const formData = new FormData();
            formData.append('message', text);
            if (selectedFile) {
                formData.append('file', selectedFile);
                selectedFile = null;
            }
            const resp = await fetch('/api/chat', { method: 'POST', body: formData });
            const data = await resp.json();
            removeTyping();
            addMessage(data.reply, 'assistant');
        } catch (err) {
            removeTyping();
            addMessage('网络错误，请检查连接', 'assistant');
        }
    }

    function addMessage(text, role) {
        const div = document.createElement('div');
        div.className = 'message ' + role;
        div.innerHTML = '<div class="avatar">' + (role === 'assistant' ? 'D' : 'U') + '</div>'
            + '<div class="bubble">' + escapeHtml(text) + '</div>';
        chatBox.appendChild(div);
        chatBox.scrollTop = chatBox.scrollHeight;
    }

    function showTyping() {
        const div = document.createElement('div');
        div.className = 'message assistant';
        div.id = 'typing-indicator';
        div.innerHTML = '<div class="avatar">D</div><div class="bubble"><div class="typing">'
            + '<span></span><span></span><span></span></div></div>';
        chatBox.appendChild(div);
        chatBox.scrollTop = chatBox.scrollHeight;
    }

    function removeTyping() {
        const el = document.getElementById('typing-indicator');
        if (el) el.remove();
    }

    function escapeHtml(str) {
        return str.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
    }
});
