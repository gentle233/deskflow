<template>
  <div class="chat-container" @dragover.prevent @drop.prevent="onDrop">
    <!-- Header -->
    <div class="header">
      <span class="title">DeskFlow</span>
      <span :class="['status-dot', connectionStatus === 'connected' ? 'dot-green' : 'dot-yellow']"></span>
      <span class="status-text">{{ connectionStatus === 'connected' ? '已连接' : '连接中...' }}</span>
      <div class="header-actions">
        <button class="icon-btn" @click="exportChat" title="导出聊天记录">📥</button>
        <button class="icon-btn" @click="toggleLearnPanel" title="学习建议" style="position:relative">
          💡
        </button>
        <button class="icon-btn" @click="toggleMonitorPanel" title="文件变化" style="position:relative">
          📂
          <span v-if="monitorDotVisible" class="monitor-dot"></span>
        </button>
        <router-link to="/settings" class="icon-btn settings-link" title="设置">⚙️</router-link>
      </div>
    </div>

    <!-- Learning suggestions panel -->
    <div v-show="learnPanelOpen" class="panel panel-learn">
      <div class="panel-header">
        <span class="panel-title">💡 智能建议</span>
        <span class="panel-close" @click="learnPanelOpen = false">✕</span>
      </div>
      <div class="panel-body">
        <div v-if="suggestions.length === 0" style="color:#999">暂无建议，多使用后会自动生成</div>
        <div
          v-for="s in suggestions"
          :key="s.id"
          class="suggestion-item"
        >
          <span>{{ s.title }}</span>
          <button class="dismiss-btn" @click="dismissSuggestion(s.id)">✕</button>
        </div>
      </div>
    </div>

    <!-- Monitor events panel -->
    <div v-show="monitorPanelOpen" class="panel panel-monitor">
      <div class="panel-header">
        <span class="panel-title">📂 最近文件变化</span>
        <span class="panel-close" @click="monitorPanelOpen = false">✕</span>
      </div>
      <div class="panel-body">
        <div v-if="monitorEvents.length === 0" style="color:#999">暂无文件变化</div>
        <div
          v-for="(evt, idx) in monitorEvents"
          :key="idx"
          class="monitor-event-item"
        >
          <span>{{ eventIcon(evt.event_type) }}</span>
          <span class="event-time">{{ evt.timestamp ? evt.timestamp.slice(11, 19) : '' }}</span>
          <span class="event-file">{{ evt.file_name }}</span>
        </div>
      </div>
    </div>

    <!-- Messages area -->
    <div ref="chatBoxRef" class="chat-box" @click="hideShortcutSuggestions">
      <div
        v-for="(msg, idx) in messages"
        :key="idx"
        :class="['message', msg.role]"
      >
        <div class="avatar">{{ msg.role === 'assistant' ? 'D' : 'U' }}</div>
        <div class="bubble" v-html="msg.role === 'user' ? escapeHtml(msg.content) : renderMarkdown(msg.content)"></div>
      </div>
      <!-- Typing indicator -->
      <div v-if="showTypingIndicator" class="message assistant">
        <div class="avatar">D</div>
        <div class="bubble">
          <div class="typing">
            <span></span><span></span><span></span>
          </div>
        </div>
      </div>
    </div>

    <!-- Input area -->
    <div class="input-area" ref="inputAreaRef">
      <div v-if="fileHintVisible" class="file-hint">已选中文件，按回车发送后自动读取</div>
      <!-- Shortcut suggestions dropdown -->
      <div
        v-show="shortcutSuggestVisible"
        class="sc-suggest"
      >
        <div
          v-for="s in filteredShortcuts"
          :key="s.trigger"
          class="sc-item"
          @click="applyShortcut(s.trigger)"
          @mouseover="e => e.target.style.background='#f5f5f5'"
          @mouseleave="e => e.target.style.background=''"
        >
          <code class="sc-trigger">{{ s.trigger }}</code>
          <span class="sc-desc">{{ s.desc || (s.command ? s.command.slice(0, 20) : '') }}</span>
        </div>
      </div>
      <textarea
        ref="inputRef"
        v-model="inputText"
        class="input-box"
        rows="2"
        placeholder="说点什么..."
        @keydown="onInputKeydown"
        @input="onInputChange"
      ></textarea>
      <button
        v-show="isStreaming"
        class="stop-btn"
        @click="stopStream"
      >⏹ 停止</button>
      <button
        class="send-btn"
        :disabled="isStreaming || (!inputText.trim() && !selectedFile)"
        @click="send"
      >发送</button>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import { marked } from 'marked'
import { useRouter } from 'vue-router'
import { api } from '../config'

marked.setOptions({ breaks: true, gfm: true })

const router = useRouter()

// ---- State ----
const inputRef = ref(null)
const chatBoxRef = ref(null)
const inputAreaRef = ref(null)

const messages = ref([])
const inputText = ref('')
const isStreaming = ref(false)
const showTypingIndicator = ref(false)
const selectedFile = ref(null)
const fileHintVisible = ref(false)
let abortController = null
let lastUserText = ''

const connectionStatus = ref('connected') // 'connected' | 'connecting'

// Shortcuts
const shortcutsCache = ref([])
const shortcutSuggestVisible = ref(false)

// Learn panel
const learnPanelOpen = ref(false)
const suggestions = ref([])

// Monitor panel
const monitorPanelOpen = ref(false)
const monitorEvents = ref([])
const monitorDotVisible = ref(false)
let lastEventCount = 0
let monitorInterval = null

const STORAGE_KEY = 'deskflow_chat'

// ---- Computed ----
const filteredShortcuts = computed(() => {
  const val = inputText.value.trim()
  if (!val.startsWith('/') || shortcutsCache.value.length === 0) return []
  return shortcutsCache.value.filter(s => s.trigger.startsWith(val))
})

// ---- Methods ----

function escapeHtml(str) {
  if (!str) return ''
  return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
}

function renderMarkdown(text) {
  if (!text) return ''
  try {
    return marked.parse(text)
  } catch (e) {
    return escapeHtml(text)
  }
}

function addMessage(text, role) {
  messages.value.push({ role, content: text })
  scrollToBottom()
  if (role === 'user') {
    saveToHistory(text, '')
  }
}

function showTyping() {
  showTypingIndicator.value = true
  scrollToBottom()
}

function removeTyping() {
  showTypingIndicator.value = false
}

function playNotificationSound() {
  try {
    const ctx = new (window.AudioContext || window.webkitAudioContext)()
    const osc = ctx.createOscillator()
    const gain = ctx.createGain()
    osc.connect(gain)
    gain.connect(ctx.destination)
    osc.frequency.value = 660
    osc.type = 'sine'
    gain.gain.setValueAtTime(0.3, ctx.currentTime)
    gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.15)
    osc.start(ctx.currentTime)
    osc.stop(ctx.currentTime + 0.15)
  } catch (e) {
    // Audio not supported, silently ignore
  }
}

function scrollToBottom() {
  nextTick(() => {
    if (chatBoxRef.value) {
      chatBoxRef.value.scrollTop = chatBoxRef.value.scrollHeight
    }
  })
}

async function send() {
  const text = inputText.value.trim()
  // Resolve shortcut
  let resolvedText = text
  if (text.startsWith('/') && shortcutsCache.value.length > 0) {
    const match = shortcutsCache.value.find(s => s.trigger === text)
    if (match) resolvedText = match.command
  }
  const finalText = resolvedText
  if (!finalText && !selectedFile.value) return

  lastUserText = text || (selectedFile.value ? '已发送了文件: ' + selectedFile.value.name : '')
  addMessage(lastUserText, 'user')
  inputText.value = ''
  shortcutSuggestVisible.value = false
  fileHintVisible.value = false
  showTyping()
  isStreaming.value = true

  const formData = new FormData()
  formData.append('message', finalText)
  if (selectedFile.value) {
    formData.append('file', selectedFile.value)
    selectedFile.value = null
  }

  abortController = new AbortController()

  try {
    const resp = await fetch(api('/api/chat/stream'), {
      method: 'POST',
      body: formData,
      signal: abortController.signal
    })
    if (!resp.ok) throw new Error('HTTP ' + resp.status)

    const reader = resp.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    let fullText = ''

    // Create message bubble
    const msgIndex = messages.value.length
    messages.value.push({ role: 'assistant', content: '' })
    removeTyping()
    scrollToBottom()

    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''
      for (const line of lines) {
        if (!line.startsWith('data: ')) continue
        try {
          const data = JSON.parse(line.slice(6))
          if (data.token) {
            fullText += data.token
            messages.value[msgIndex].content = fullText
            scrollToBottom()
          } else if (data.done) {
            playNotificationSound()
            saveToHistory(lastUserText, fullText)
          } else if (data.error) {
            messages.value[msgIndex].content = '❌ ' + escapeHtml(data.error)
          }
        } catch (e) {
          // skip malformed lines
        }
      }
    }
    // Process remaining buffer
    if (buffer.startsWith('data: ')) {
      try {
        const data = JSON.parse(buffer.slice(6))
        if (data.token) {
          fullText += data.token
          messages.value[msgIndex].content = fullText
          scrollToBottom()
        } else if (data.done) {
          playNotificationSound()
          saveToHistory(lastUserText, fullText)
        }
      } catch (e) {
        // ignore
      }
    }
  } catch (err) {
    if (err.name === 'AbortError') {
      // User stopped - handled below
    } else {
      removeTyping()
      addMessage('⚠️ 连接失败: ' + err.message, 'assistant')
    }
  }

  isStreaming.value = false
  abortController = null
}

function stopStream() {
  if (abortController) {
    abortController.abort()
    isStreaming.value = false
    // Save partial message
    const lastMsg = messages.value[messages.value.length - 1]
    if (lastMsg && lastMsg.role === 'assistant' && lastMsg.content) {
      saveToHistory(lastUserText, lastMsg.content)
    }
  }
}

function onInputKeydown(e) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    if (isStreaming.value) return
    send()
  }
}

function onInputChange() {
  const val = inputText.value.trim()
  if (val.startsWith('/') && shortcutsCache.value.length > 0) {
    const matched = shortcutsCache.value.filter(s => s.trigger.startsWith(val))
    if (matched.length > 0) {
      shortcutSuggestVisible.value = true
      return
    }
  }
  shortcutSuggestVisible.value = false
}

function applyShortcut(trigger) {
  inputText.value = trigger
  shortcutSuggestVisible.value = false
  inputRef.value?.focus()
}

function hideShortcutSuggestions() {
  shortcutSuggestVisible.value = false
}

// ---- Drag & Drop ----
function onDrop(e) {
  fileHintVisible.value = false
  const file = e.dataTransfer.files[0]
  if (file) {
    selectedFile.value = file
    addMessage('已选择文件: ' + file.name, 'user')
  }
}

// ---- History ----
function saveToHistory(userMsg, assistantMsg) {
  let history = JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]')
  if (userMsg) history.push({ role: 'user', content: userMsg, time: Date.now() })
  if (assistantMsg) history.push({ role: 'assistant', content: assistantMsg, time: Date.now() })
  if (history.length > 50) history = history.slice(-50)
  localStorage.setItem(STORAGE_KEY, JSON.stringify(history))
}

function loadHistory() {
  const history = JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]')
  const recent = history.slice(-20)
  for (const msg of recent) {
    messages.value.push({ role: msg.role, content: msg.content })
  }
  nextTick(() => {
    if (chatBoxRef.value) {
      chatBoxRef.value.scrollTop = chatBoxRef.value.scrollHeight
    }
  })
}

// ---- Export ----
function exportChat() {
  const history = JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]')
  if (history.length === 0) {
    alert('暂无聊天记录可导出')
    return
  }
  const isJson = confirm('点击"确定"导出 JSON 格式，点击"取消"导出 Markdown 格式')
  if (isJson) {
    const blob = new Blob([JSON.stringify(history, null, 2)], { type: 'application/json' })
    downloadBlob(blob, 'deskflow-history-' + Date.now() + '.json')
  } else {
    let md = '# DeskFlow 聊天记录\n\n导出时间: ' + new Date().toLocaleString() + '\n\n---\n\n'
    for (const msg of history) {
      const role = msg.role === 'user' ? '**你**' : '**DeskFlow**'
      const time = msg.time ? new Date(msg.time).toLocaleString() : '未知时间'
      md += '### ' + role + ' (' + time + ')\n\n' + msg.content + '\n\n---\n\n'
    }
    const blob = new Blob([md], { type: 'text/markdown' })
    downloadBlob(blob, 'deskflow-history-' + Date.now() + '.md')
  }
}

function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}

// ---- Learning suggestions ----
function toggleLearnPanel() {
  learnPanelOpen.value = !learnPanelOpen.value
  if (learnPanelOpen.value) {
    loadSuggestions()
  }
}

async function loadSuggestions() {
  try {
    const r = await fetch(api('/api/autolearn/suggestions'))
    const data = await r.json()
    suggestions.value = data
  } catch (e) {
    suggestions.value = []
  }
}

async function dismissSuggestion(id) {
  try {
    await fetch(api('/api/autolearn/dismiss/' + id), { method: 'POST' })
    await loadSuggestions()
  } catch (e) {
    // ignore
  }
}

// ---- Monitor events ----
function toggleMonitorPanel() {
  monitorPanelOpen.value = !monitorPanelOpen.value
  if (monitorPanelOpen.value) {
    loadMonitorEvents()
    monitorDotVisible.value = false
  }
}

async function loadMonitorEvents() {
  try {
    const r = await fetch(api('/api/monitor/events?count=5'))
    const data = await r.json()
    monitorEvents.value = data
  } catch (e) {
    monitorEvents.value = []
  }
}

function eventIcon(eventType) {
  switch (eventType) {
    case 'created': return '🟢'
    case 'modified': return '🔵'
    case 'deleted': return '🔴'
    default: return '🟡'
  }
}

// ---- Shortcuts ----
async function loadShortcuts() {
  try {
    const r = await fetch(api('/api/shortcuts'))
    shortcutsCache.value = await r.json()
  } catch (e) {
    shortcutsCache.value = []
  }
}

// ---- Welcome message ----
function addWelcomeMessage() {
  if (messages.value.length === 0) {
    messages.value.push({
      role: 'assistant',
      content: '你好！我是 DeskFlow，你的桌面助手。<br>\n可以直接打字说需求，或拖拽文件到窗口里。'
    })
  }
}

// ---- Lifecycle ----
onMounted(() => {
  loadHistory()
  if (messages.value.length === 0) {
    addWelcomeMessage()
  }
  loadShortcuts()

  // Monitor status polling (every 60s)
  monitorInterval = setInterval(async () => {
    try {
      const r = await fetch(api('/api/monitor/status'))
      const s = await r.json()
      if (s.event_count > lastEventCount && s.event_count > 0) {
        monitorDotVisible.value = true
      }
      lastEventCount = s.event_count
    } catch (e) {
      // ignore
    }
  }, 60000)

  // Click outside to close shortcut suggestions
  document.addEventListener('click', handleClickOutside)
})

onUnmounted(() => {
  if (monitorInterval) {
    clearInterval(monitorInterval)
    monitorInterval = null
  }
  document.removeEventListener('click', handleClickOutside)
})

function handleClickOutside(e) {
  if (inputAreaRef.value && !inputAreaRef.value.contains(e.target)) {
    shortcutSuggestVisible.value = false
  }
}
</script>

<style scoped>
* {
  box-sizing: border-box;
}

.chat-container {
  display: flex;
  flex-direction: column;
  height: 100vh;
  max-width: 800px;
  margin: 0 auto;
  background: #fff;
  box-shadow: 0 0 20px rgba(0,0,0,0.05);
  font-family: -apple-system, "Microsoft YaHei", sans-serif;
}

/* Header */
.header {
  display: flex;
  align-items: center;
  padding: 12px 20px;
  background: #fff;
  border-bottom: 1px solid #eee;
}

.title {
  font-size: 16px;
  font-weight: 600;
  color: #333;
  margin-right: 8px;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  display: inline-block;
  margin-right: 6px;
}

.dot-green {
  background: #52c41a;
}

.dot-yellow {
  background: #faad14;
}

.status-text {
  font-size: 12px;
  color: #999;
  flex: 1;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 4px;
}

.icon-btn {
  border: none;
  background: none;
  cursor: pointer;
  font-size: 18px;
  padding: 4px 6px;
  text-decoration: none;
  color: inherit;
  line-height: 1;
  border-radius: 4px;
  transition: background 0.15s;
}

.icon-btn:hover {
  background: #f0f0f0;
}

.settings-link {
  font-size: 18px;
  display: inline-flex;
  align-items: center;
}

.monitor-dot {
  position: absolute;
  top: -2px;
  right: -4px;
  width: 8px;
  height: 8px;
  background: #ff4d4f;
  border-radius: 50%;
  border: 1px solid #fff;
}

/* Panels */
.panel {
  padding: 8px 16px;
  font-size: 13px;
}

.panel-learn {
  background: #f0f7ff;
  border-bottom: 1px solid #d0e3ff;
}

.panel-monitor {
  background: #fff8f0;
  border-bottom: 1px solid #ffe0b0;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 4px;
}

.panel-title {
  font-weight: 600;
  color: #4a7cff;
}

.panel-monitor .panel-title {
  color: #e67e22;
}

.panel-close {
  cursor: pointer;
  color: #999;
  font-size: 16px;
  line-height: 1;
  padding: 2px;
}

.panel-close:hover {
  color: #666;
}

.panel-body {
  max-height: 150px;
  overflow-y: auto;
}

.suggestion-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 3px 0;
}

.dismiss-btn {
  border: none;
  background: none;
  color: #999;
  cursor: pointer;
  font-size: 12px;
  padding: 2px 4px;
}

.dismiss-btn:hover {
  color: #666;
}

.monitor-event-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 3px 0;
  font-size: 12px;
}

.event-time {
  color: #999;
  min-width: 50px;
}

.event-file {
  flex: 1;
}

/* Chat box */
.chat-box {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
  background: #fafafa;
}

.message {
  display: flex;
  margin-bottom: 20px;
  align-items: flex-start;
}

.message.user {
  flex-direction: row-reverse;
}

.avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  font-weight: 600;
  color: #fff;
  flex-shrink: 0;
}

.message.assistant .avatar {
  background: #4a7cff;
  margin-right: 10px;
}

.message.user .avatar {
  background: #00b578;
  margin-left: 10px;
}

.bubble {
  max-width: 70%;
  padding: 12px 16px;
  border-radius: 12px;
  font-size: 14px;
  line-height: 1.6;
  word-break: break-word;
  white-space: pre-wrap;
}

.message.assistant .bubble {
  background: #fff;
  border: 1px solid #e8e8e8;
  border-top-left-radius: 4px;
}

.message.user .bubble {
  background: #4a7cff;
  color: #fff;
  border-top-right-radius: 4px;
}

/* Input area */
.input-area {
  padding: 12px 20px;
  border-top: 1px solid #eee;
  background: #fff;
  display: flex;
  gap: 10px;
  align-items: flex-end;
  position: relative;
}

.file-hint {
  position: absolute;
  bottom: 80px;
  left: 20px;
  font-size: 12px;
  color: #4a7cff;
  background: #f0f5ff;
  padding: 4px 12px;
  border-radius: 4px;
}

.sc-suggest {
  position: absolute;
  bottom: 100%;
  left: 0;
  right: 0;
  background: #fff;
  border: 1px solid #ddd;
  border-radius: 8px;
  max-height: 150px;
  overflow-y: auto;
  box-shadow: 0 -2px 10px rgba(0,0,0,0.1);
  z-index: 100;
}

.sc-item {
  padding: 8px 12px;
  cursor: pointer;
  border-bottom: 1px solid #f0f0f0;
  font-size: 13px;
}

.sc-item:last-child {
  border-bottom: none;
}

.sc-trigger {
  background: #e8f0ff;
  padding: 1px 5px;
  border-radius: 3px;
  font-family: 'SF Mono', Menlo, monospace;
  font-size: 13px;
}

.sc-desc {
  color: #888;
  margin-left: 8px;
}

.input-box {
  flex: 1;
  border: 1px solid #d9d9d9;
  border-radius: 8px;
  padding: 10px 14px;
  font-size: 14px;
  outline: none;
  resize: none;
  font-family: inherit;
  line-height: 1.5;
}

.input-box:focus {
  border-color: #4a7cff;
}

.send-btn {
  background: #4a7cff;
  color: #fff;
  border: none;
  padding: 10px 24px;
  border-radius: 8px;
  font-size: 14px;
  cursor: pointer;
  transition: background 0.2s;
}

.send-btn:hover {
  background: #3a66d9;
}

.send-btn:active {
  background: #2d52b3;
}

.send-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.stop-btn {
  background: #ff4d4f;
  color: #fff;
  border: none;
  padding: 10px 16px;
  border-radius: 8px;
  font-size: 13px;
  cursor: pointer;
  transition: background 0.2s;
}

.stop-btn:hover {
  background: #e04345;
}

/* Typing animation */
.typing {
  display: flex;
  gap: 4px;
  padding: 4px 0;
}

.typing span {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #bbb;
  animation: typing 1.2s infinite;
}

.typing span:nth-child(2) {
  animation-delay: 0.2s;
}

.typing span:nth-child(3) {
  animation-delay: 0.4s;
}

@keyframes typing {
  0%, 60%, 100% { opacity: 0.3; }
  30% { opacity: 1; }
}

/* Markdown rendering inside bubbles */
.bubble :deep(h1),
.bubble :deep(h2),
.bubble :deep(h3) {
  margin: 8px 0 4px;
  font-size: inherit;
}

.bubble :deep(h1) {
  font-size: 16px;
  font-weight: 700;
}

.bubble :deep(h2) {
  font-size: 15px;
  font-weight: 600;
}

.bubble :deep(h3) {
  font-size: 14px;
  font-weight: 600;
}

.bubble :deep(p) {
  margin: 4px 0;
}

.bubble :deep(ul),
.bubble :deep(ol) {
  margin: 4px 0;
  padding-left: 20px;
}

.bubble :deep(li) {
  margin: 2px 0;
}

.bubble :deep(code) {
  background: #f0f0f0;
  padding: 2px 6px;
  border-radius: 3px;
  font-size: 13px;
  font-family: 'SF Mono', Menlo, monospace;
}

.bubble :deep(pre) {
  background: #1e1e1e;
  color: #d4d4d4;
  padding: 12px;
  border-radius: 8px;
  overflow-x: auto;
  margin: 8px 0;
}

.bubble :deep(pre code) {
  background: none;
  color: inherit;
  padding: 0;
  font-size: 13px;
}

.bubble :deep(blockquote) {
  border-left: 3px solid #4a7cff;
  margin: 8px 0;
  padding: 4px 12px;
  color: #666;
  background: #f8f9ff;
}

.bubble :deep(table) {
  border-collapse: collapse;
  margin: 8px 0;
  font-size: 13px;
  width: 100%;
}

.bubble :deep(th),
.bubble :deep(td) {
  border: 1px solid #ddd;
  padding: 6px 10px;
  text-align: left;
}

.bubble :deep(th) {
  background: #f5f5f5;
  font-weight: 600;
}

.bubble :deep(hr) {
  border: none;
  border-top: 1px solid #eee;
  margin: 12px 0;
}

.bubble :deep(a) {
  color: #4a7cff;
  text-decoration: none;
}

.bubble :deep(a:hover) {
  text-decoration: underline;
}

.bubble :deep(strong) {
  font-weight: 600;
}

@media (max-width: 600px) {
  .chat-container { max-width: 100%; border-radius: 0; }
  .messages { padding: 10px; }
  .bubble { max-width: 90%; font-size: 14px; padding: 10px 14px; }
  .input-area { padding: 8px; }
  .input-area textarea { font-size: 16px; padding: 10px; }
  .header { padding: 10px 12px; }
  .header .title { font-size: 16px; }
  .header-actions .icon-btn { font-size: 20px; min-width: 44px; min-height: 44px; }
  .send-btn, .stop-btn { min-width: 44px; min-height: 44px; }
}
</style>
