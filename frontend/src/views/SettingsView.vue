<template>
  <div class="settings-app">
    <div class="settings-header">
      <router-link to="/" class="back-btn">← 回到聊天</router-link>
      <h2>设置与配置</h2>
    </div>
    <div class="settings-content">

      <!-- 1. AI Provider -->
      <div class="section">
        <h3>AI 提供商</h3>
        <div class="card">
          <div class="row">
            <span class="label">提供商</span>
            <span class="value">{{ config.provider || '-' }}</span>
          </div>
          <div class="row">
            <span class="label">模型</span>
            <span class="value">{{ config.model || '自动' }}</span>
          </div>
          <div class="row">
            <span class="label">API Key</span>
            <span class="value">{{ config.api_key || '未设置' }}</span>
          </div>
        </div>
        <button class="reconfig-btn" @click="goHome">重新配置</button>
      </div>

      <!-- 2. Multi-Provider Testing -->
      <div class="section">
        <h3>多提供商测试</h3>
        <div class="card">
          <div id="provider-list">
            <div v-for="p in providers" :key="p.id" class="provider-card">
              <div class="provider-header">
                <div>
                  <span class="provider-name">{{ p.has_key ? '✅' : '⬜' }} {{ p.name }}</span>
                  <span class="provider-model">{{ p.model }}</span>
                </div>
                <span class="provider-desc">{{ p.desc }}</span>
              </div>
              <div class="provider-actions">
                <input
                  type="password"
                  :placeholder="'输入 API Key'"
                  v-model="providerKeys[p.id]"
                  :value="p.has_key ? maskKey(p.key_preview) : ''"
                  class="provider-key-input"
                />
                <button class="btn btn-primary btn-sm" @click="testProvider(p.id)">测试</button>
                <button
                  class="btn btn-success btn-sm"
                  :class="{ disabled: !p.has_key }"
                  @click="setProvider(p.id)"
                >设为当前</button>
              </div>
              <div class="provider-result" :class="providerResults[p.id]?.success ? 'success' : 'error'">
                {{ providerResults[p.id]?.message }}
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 3. Search Settings -->
      <div class="section">
        <h3>搜索设置</h3>
        <div class="card">
          <div class="row">
            <span class="label">搜索提供商</span>
            <select v-model="searchProvider" @change="onSearchProviderChange" class="select-input">
              <option value="ddgs">DuckDuckGo（无需配置）</option>
              <option value="bing">必应搜索 API（需 Key）</option>
            </select>
          </div>
          <div class="row" v-show="searchProvider === 'bing'">
            <span class="label">必应 API Key</span>
            <input
              type="password"
              v-model="bingApiKey"
              placeholder="输入必应 API Key"
              class="text-input flex-1"
            />
          </div>
          <button class="reconfig-btn" @click="saveSearchConfig">保存搜索设置</button>
          <div class="result-msg">{{ searchResultMsg }}</div>
        </div>
      </div>

      <!-- 4. Email Settings -->
      <div class="section">
        <h3>📧 邮件设置</h3>
        <div class="card">
          <div class="row">
            <span class="label">邮箱提供商</span>
            <select v-model="emailConfig.provider" @change="onEmailProviderChange" class="select-input flex-1">
              <option v-for="(prov, key) in emailProviders" :key="key" :value="key">{{ key }}</option>
            </select>
          </div>
          <div class="row">
            <span class="label">IMAP 服务器</span>
            <input type="text" v-model="emailConfig.imap_server" placeholder="imap.qq.com" class="text-input flex-1" />
          </div>
          <div class="row">
            <span class="label">IMAP 端口</span>
            <input type="number" v-model.number="emailConfig.imap_port" class="text-input" style="width:80px" />
          </div>
          <div class="row">
            <span class="label">SMTP 服务器</span>
            <input type="text" v-model="emailConfig.smtp_server" placeholder="smtp.qq.com" class="text-input flex-1" />
          </div>
          <div class="row">
            <span class="label">SMTP 端口</span>
            <input type="number" v-model.number="emailConfig.smtp_port" class="text-input" style="width:80px" />
          </div>
          <div class="row">
            <span class="label">邮箱地址</span>
            <input type="email" v-model="emailConfig.email" placeholder="your@qq.com" class="text-input flex-1" />
          </div>
          <div class="row">
            <span class="label">授权码/密码</span>
            <input type="password" v-model="emailConfig.password" placeholder="QQ邮箱需使用授权码" class="text-input flex-1" />
          </div>
          <div class="row">
            <span class="label">启用</span>
            <label>
              <input type="checkbox" v-model="emailConfig.enabled" /> 启用邮件功能
            </label>
          </div>
          <div class="email-actions">
            <button class="btn btn-primary flex-1" @click="saveEmailConfig">保存配置</button>
            <button class="btn btn-success" @click="testEmailConfig">测试连接</button>
          </div>
          <div class="result-msg" :class="emailMessageClass">{{ emailMessage }}</div>
          <div class="email-tip">
            💡 QQ邮箱需开启 IMAP/SMTP 服务并获取<strong>授权码</strong>（不是登录密码）。
            可在 QQ邮箱 → 设置 → 账户 → POP3/IMAP/SMTP 服务中获取。
          </div>
        </div>
      </div>

      <!-- 5. Shortcuts -->
      <div class="section">
        <h3>快捷指令</h3>
        <div class="card">
          <div class="shortcut-list">
            <div v-for="s in shortcuts" :key="s.trigger" class="row">
              <span>
                <code class="inline-code">{{ s.trigger }}</code>
                <span class="shortcut-desc">{{ s.desc || (s.command || '').slice(0, 20) }}</span>
              </span>
              <button class="btn-icon danger" @click="deleteShortcut(s.trigger)">✕</button>
            </div>
          </div>
          <div class="shortcut-form">
            <input v-model="newShortcutTrigger" placeholder="/前缀" class="text-input flex-1" />
            <input v-model="newShortcutCommand" placeholder="触发后发送的内容" class="text-input flex-2" />
            <button class="btn btn-primary" @click="addShortcut">添加</button>
          </div>
          <div class="result-msg">{{ shortcutMessage }}</div>
        </div>
      </div>

      <!-- 6. Connection Check -->
      <div class="section">
        <h3>连接检查</h3>
        <div class="card">
          <div class="row">
            <span class="label">API 状态</span>
            <span class="status-badge" :class="connectionBadgeClass">{{ connectionStatusText }}</span>
          </div>
          <div class="check-result">{{ connectionResult }}</div>
        </div>
      </div>

      <!-- 7. Feature Status -->
      <div class="section">
        <h3>功能状态</h3>
        <div class="card">
          <div v-for="(feat, idx) in features" :key="idx" class="row">
            <span class="label">{{ feat.label }}</span>
            <span class="value" :style="{ color: feat.color }">{{ feat.value }}</span>
          </div>
          <div class="row">
            <span class="label">提示音</span>
            <label>
              <input type="checkbox" v-model="soundEnabled" @change="onSoundToggle" /> 消息提醒音
            </label>
          </div>
          <div class="row">
            <span class="label">自动学习</span>
            <span class="value">{{ autolearnStats }}</span>
          </div>
        </div>
      </div>

      <!-- 8. File Monitor -->
      <div class="section">
        <h3>📁 文件监控</h3>
        <div class="card">
          <div class="row">
            <span class="label">监控状态</span>
            <span class="status-badge" :class="monitorBadgeClass">{{ monitorStatusText }}</span>
          </div>
          <div class="row" style="justify-content: flex-start; gap: 8px">
            <button class="btn btn-primary" @click="toggleMonitor">
              {{ monitorRunning ? '停止监控' : '启动监控' }}
            </button>
          </div>
          <div class="monitor-section">
            <div class="section-label">监控目录</div>
            <div class="monitor-dirs">
              <div v-if="monitorDirs.length === 0" class="empty-text">暂无监控目录</div>
              <div v-for="d in monitorDirs" :key="d" class="dir-item">
                <span class="dir-path">📂 {{ d }}</span>
                <button class="btn-icon danger" @click="removeMonitorDir(d)">✕</button>
              </div>
            </div>
            <div class="monitor-add-dir">
              <input v-model="newDirPath" type="text" placeholder="输入绝对路径" class="text-input flex-1" />
              <button class="btn btn-primary btn-sm" @click="addMonitorDir">+ 添加</button>
            </div>
            <div class="result-msg">{{ monitorMessage }}</div>
          </div>
          <div class="monitor-section">
            <div class="events-header">
              <span class="section-label">最近文件变化</span>
              <div class="event-tabs">
                <button
                  v-for="tab in eventTabs"
                  :key="tab.type"
                  class="event-tab"
                  :class="{ active: eventType === tab.type }"
                  @click="switchEventTab(tab.type)"
                >{{ tab.label }}</button>
              </div>
            </div>
            <div class="monitor-events">
              <div v-if="monitorEvents.length === 0" class="empty-text-center">暂无文件变化</div>
              <div v-for="e in monitorEvents" :key="e.timestamp + e.file_name" class="event-item">
                <span class="event-icon">{{ eventIcon(e.event_type) }}</span>
                <span class="event-time">{{ e.timestamp ? e.timestamp.slice(11, 19) : '' }}</span>
                <span class="event-file">{{ e.file_name }}</span>
                <span class="event-size">{{ e.file_size > 0 ? formatSize(e.file_size) : '' }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 9. Scheduled Tasks -->
      <div class="section">
        <h3>⏰ 定时任务</h3>
        <div class="card">
          <div v-if="tasks.length === 0" class="empty-text-center">暂无定时任务</div>
          <div class="tasks-list">
            <div v-for="t in tasks" :key="t.id" class="task-card">
              <div class="task-header">
                <span class="task-name">{{ t.name }}</span>
                <span class="status-badge" :class="t.enabled ? 'status-ok' : 'status-wait'">
                  {{ t.enabled ? '✔ 启用' : '⏸ 暂停' }}
                </span>
              </div>
              <div class="task-schedule">
                <span v-if="t.trigger_type === 'cron'">Cron: <code class="inline-code">{{ t.cron }}</code></span>
                <span v-else>每 {{ t.interval_value }} {{ intervalLabel(t.interval_unit) }}</span>
                <span class="task-prompt" :title="t.prompt">{{ truncate(t.prompt, 40) }}</span>
              </div>
              <div class="task-footer">
                <span class="task-times">上次: {{ formatTime(t.last_run) }} · 下次: {{ formatTime(t.next_run) }}</span>
                <div class="task-actions">
                  <button class="btn-icon" title="立即执行" @click="runTask(t.id)">▶</button>
                  <button class="btn-icon" :title="t.enabled ? '暂停' : '启用'" @click="toggleTask(t.id)">
                    {{ t.enabled ? '⏸' : '▶️' }}
                  </button>
                  <button class="btn-icon danger" title="删除" @click="deleteTask(t.id)">🗑</button>
                </div>
              </div>
            </div>
          </div>
          <div class="new-task-section">
            <div class="section-label">新建任务</div>
            <div class="task-form">
              <div class="task-form-row">
                <input v-model="newTask.name" placeholder="任务名称" class="text-input flex-1" />
                <input v-model="newTask.prompt" placeholder="触发后执行的内容（发给 Agent 的指令）" class="text-input flex-3" />
              </div>
              <div class="task-form-row">
                <select v-model="newTask.trigger_type" @change="onTaskTriggerTypeChange" class="select-input">
                  <option value="interval">间隔重复</option>
                  <option value="cron">Cron 定时</option>
                </select>
                <div v-if="newTask.trigger_type === 'interval'" class="task-interval-config">
                  <span class="label">每</span>
                  <input type="number" min="1" v-model.number="newTask.interval_value" class="text-input" style="width:60px" />
                  <select v-model="newTask.interval_unit" class="select-input">
                    <option value="minutes">分钟</option>
                    <option value="hours" selected>小时</option>
                    <option value="days">天</option>
                  </select>
                </div>
                <div v-else class="task-cron-config">
                  <input v-model="newTask.cron" placeholder="如: 0 17 * * 5 (每周五17:00, 周日=0 周一=1)" class="text-input" style="width:300px" />
                  <span class="cron-hint">分 时 日 月 周</span>
                </div>
                <button class="btn btn-primary" @click="createTask">+ 创建</button>
              </div>
            </div>
            <div class="result-msg">{{ taskMessage }}</div>
          </div>
        </div>
      </div>

      <!-- 10. Log Viewer -->
      <div class="section">
        <h3>错误日志</h3>
        <div class="card">
          <div class="log-toolbar">
            <div class="log-tabs">
              <button
                v-for="lvl in logLevels"
                :key="lvl.value"
                class="log-tab"
                :class="{ active: logLevel === lvl.value }"
                @click="switchLogLevel(lvl.value)"
              >{{ lvl.label }}</button>
            </div>
            <div class="log-actions">
              <input v-model="logSearch" type="text" placeholder="搜索..." class="log-search-input" @input="onLogSearchInput" />
              <select v-model="logLinesCount" class="select-input" @change="loadLogs">
                <option value="100">100行</option>
                <option value="200">200行</option>
                <option value="500">500行</option>
                <option value="1000">1000行</option>
              </select>
              <button class="log-action-btn" @click="loadLogs" title="刷新">🔄</button>
              <button class="log-action-btn" @click="scrollLogBottom" title="到底">⬇</button>
              <button class="log-action-btn danger" @click="confirmClearLogs" title="清空">🗑</button>
              <label class="auto-refresh-label">
                <input type="checkbox" v-model="logAutoRefresh" @change="onAutoRefreshChange" /> 自动
              </label>
            </div>
          </div>
          <pre ref="logViewerRef" class="log-viewer" v-html="logHtml"></pre>
          <div class="log-status">{{ logStatus }}</div>
        </div>
      </div>

    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onUnmounted, nextTick } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()

// ─── Helpers ──────────────────────────────────────────────────
function escHtml(s) {
  return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;')
}
function truncate(s, len) {
  if (!s) return ''
  return s.length > len ? escHtml(s.slice(0, len)) + '…' : escHtml(s)
}
function formatSize(bytes) {
  if (!bytes || bytes < 0) return ''
  if (bytes < 1024) return bytes + 'B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + 'KB'
  return (bytes / 1024 / 1024).toFixed(1) + 'MB'
}
function formatTime(ts) {
  if (!ts) return '-'
  return ts.slice(11, 19) + ' ' + ts.slice(0, 10)
}
function intervalLabel(unit) {
  return unit === 'minutes' ? '分钟' : unit === 'hours' ? '小时' : '天'
}
function maskKey(preview) {
  if (!preview) return ''
  return '••••••••' + preview.slice(-4)
}

// ─── API helper ───────────────────────────────────────────────
async function api(url, options = {}) {
  const r = await fetch(url, {
    headers: { 'Content-Type': 'application/json', ...options.headers },
    ...options,
  })
  return r.json()
}

function goHome() {
  router.push('/')
}

// ─── 1. AI Provider ──────────────────────────────────────────
const config = reactive({
  provider: '-',
  model: '自动',
  api_key: '未设置',
})

async function loadConfig() {
  try {
    const data = await api('/api/config')
    Object.assign(config, {
      provider: data.provider || '-',
      model: data.model || '自动',
      api_key: data.api_key || '未设置',
    })
  } catch (e) {
    console.error('loadConfig failed', e)
  }
}

// ─── 2. Multi-Provider Testing ───────────────────────────────
const providers = ref([])
const providerKeys = reactive({})
const providerResults = reactive({})

async function loadProviders() {
  try {
    const data = await api('/api/providers')
    providers.value = data
    data.forEach(p => {
      if (!(p.id in providerKeys)) {
        providerKeys[p.id] = p.has_key ? maskKey(p.key_preview) : ''
      }
    })
  } catch (e) {
    console.error('loadProviders failed', e)
  }
}

async function testProvider(id) {
  providerResults[id] = { message: '⏳ 测试中...', success: null }
  const apiKey = providerKeys[id] && providerKeys[id] !== '********' ? providerKeys[id] : ''
  try {
    const data = await api('/api/providers/test', {
      method: 'POST',
      body: JSON.stringify({ provider: id, api_key: apiKey }),
    })
    if (data.status === 'ok') {
      providerResults[id] = {
        message: `✅ 正常 (${data.latency}s) · 模型: ${data.model} · 回复: "${data.reply}"`,
        success: true,
      }
      if (apiKey) providerKeys[id] = '********'
    } else {
      providerResults[id] = {
        message: `❌ ${data.error}${data.latency ? ` (${data.latency}s)` : ''}`,
        success: false,
      }
    }
  } catch (e) {
    providerResults[id] = { message: '❌ 请求失败: ' + e.message, success: false }
  }
}

async function setProvider(id) {
  providerResults[id] = { message: '⏳ 切换中...', success: null }
  const apiKey = providerKeys[id] && providerKeys[id] !== '********' ? providerKeys[id] : ''
  const body = { provider: id }
  if (apiKey) body.api_key = apiKey
  try {
    const data = await api('/api/providers/set', {
      method: 'POST',
      body: JSON.stringify(body),
    })
    if (data.status === 'ok') {
      providerResults[id] = { message: '✅ 已切换到 ' + id, success: true }
      config.provider = id
      if (apiKey) providerKeys[id] = '********'
      await loadProviders()
    } else {
      providerResults[id] = { message: '❌ ' + (data.error || '切换失败'), success: false }
    }
  } catch (e) {
    providerResults[id] = { message: '❌ ' + e.message, success: false }
  }
}

// ─── 3. Search Settings ──────────────────────────────────────
const searchProvider = ref('ddgs')
const bingApiKey = ref('')
const searchResultMsg = ref('')

async function loadSearchConfig() {
  try {
    const data = await api('/api/config')
    searchProvider.value = data.search_provider || 'ddgs'
    if (data.bing_api_key) {
      bingApiKey.value = '••••••••' + data.bing_api_key.slice(-4)
    }
  } catch (e) {
    console.error('loadSearchConfig failed', e)
  }
}

function onSearchProviderChange() {
  // no-op, just reactive
}

async function saveSearchConfig() {
  try {
    const data = await api('/api/config/search', {
      method: 'POST',
      body: JSON.stringify({
        search_provider: searchProvider.value,
        bing_api_key: bingApiKey.value?.includes('*') ? '' : bingApiKey.value,
      }),
    })
    searchResultMsg.value = data.status === 'ok' ? '✅ 已保存' : '❌ ' + (data.error || '保存失败')
  } catch (e) {
    searchResultMsg.value = '❌ ' + e.message
  }
}

// ─── 4. Email Settings ───────────────────────────────────────
const emailProviders = reactive({})
const emailConfig = reactive({
  provider: '',
  imap_server: '',
  imap_port: 993,
  smtp_server: '',
  smtp_port: 465,
  email: '',
  password: '',
  enabled: false,
})
const emailMessage = ref('')
const emailMessageClass = ref('')

async function loadEmailProviders() {
  try {
    const data = await api('/api/email/providers')
    Object.assign(emailProviders, data)
    await loadEmailConfig()
  } catch (e) {
    console.error('loadEmailProviders failed', e)
  }
}

function onEmailProviderChange() {
  const prov = emailProviders[emailConfig.provider]
  if (!prov) return
  emailConfig.imap_server = prov.imap_server
  emailConfig.imap_port = prov.imap_port
  emailConfig.smtp_server = prov.smtp_server
  emailConfig.smtp_port = prov.smtp_port
}

async function loadEmailConfig() {
  try {
    const data = await api('/api/email/config')
    if (data.provider) {
      emailConfig.provider = data.provider
    }
    onEmailProviderChange()
    emailConfig.email = data.email || ''
    emailConfig.password = data.password || ''
    emailConfig.enabled = data.enabled || false
  } catch (e) {
    console.error('loadEmailConfig failed', e)
  }
}

async function saveEmailConfig() {
  emailMessage.value = '⏳ 保存中...'
  emailMessageClass.value = ''
  try {
    const data = await api('/api/email/config', {
      method: 'POST',
      body: JSON.stringify({
        provider: emailConfig.provider,
        imap_server: emailConfig.imap_server,
        imap_port: emailConfig.imap_port || 993,
        smtp_server: emailConfig.smtp_server,
        smtp_port: emailConfig.smtp_port || 465,
        email: emailConfig.email,
        password: emailConfig.password,
        enabled: emailConfig.enabled,
      }),
    })
    if (data.status === 'ok') {
      emailMessage.value = '✅ 配置已保存'
      emailMessageClass.value = 'success'
      await loadEmailConfig()
    } else {
      emailMessage.value = '❌ ' + (data.error || '保存失败')
      emailMessageClass.value = 'error'
    }
  } catch (e) {
    emailMessage.value = '❌ ' + e.message
    emailMessageClass.value = 'error'
  }
}

async function testEmailConfig() {
  emailMessage.value = '⏳ 正在测试连接...'
  emailMessageClass.value = ''
  try {
    const data = await api('/api/email/test', { method: 'POST' })
    if (data.status === 'ok') {
      emailMessage.value = '✅ ' + data.message
      emailMessageClass.value = 'success'
    } else {
      emailMessage.value = '❌ ' + data.message
      emailMessageClass.value = 'error'
    }
  } catch (e) {
    emailMessage.value = '❌ ' + e.message
    emailMessageClass.value = 'error'
  }
}

// ─── 5. Shortcuts ────────────────────────────────────────────
const shortcuts = ref([])
const newShortcutTrigger = ref('')
const newShortcutCommand = ref('')
const shortcutMessage = ref('')

async function loadShortcuts() {
  try {
    const data = await api('/api/shortcuts')
    shortcuts.value = data
  } catch (e) {
    console.error('loadShortcuts failed', e)
  }
}

async function addShortcut() {
  const t = newShortcutTrigger.value.trim()
  const c = newShortcutCommand.value.trim()
  if (!t || !c) {
    shortcutMessage.value = '请填写触发词和内容'
    return
  }
  try {
    const data = await api('/api/shortcuts', {
      method: 'POST',
      body: JSON.stringify({ trigger: t, command: c }),
    })
    if (data.status === 'ok') {
      shortcutMessage.value = '✅ 已添加'
      newShortcutTrigger.value = ''
      newShortcutCommand.value = ''
      await loadShortcuts()
    } else {
      shortcutMessage.value = '❌ ' + (data.error || '添加失败')
    }
  } catch (e) {
    shortcutMessage.value = '❌ ' + e.message
  }
}

async function deleteShortcut(trigger) {
  try {
    await api('/api/shortcuts', {
      method: 'DELETE',
      body: JSON.stringify({ trigger }),
    })
    await loadShortcuts()
  } catch (e) {
    console.error('deleteShortcut failed', e)
  }
}

// ─── 6. Connection Check ─────────────────────────────────────
const connectionStatus = ref('wait')
const connectionResult = ref('')

const connectionBadgeClass = computed(() => ({
  'status-badge': true,
  'status-ok': connectionStatus.value === 'ok',
  'status-err': connectionStatus.value === 'err',
  'status-wait': connectionStatus.value === 'wait',
}))
const connectionStatusText = computed(() => {
  if (connectionStatus.value === 'ok') return '✔ 正常'
  if (connectionStatus.value === 'err') return '✘ 失败'
  return '检查中...'
})

async function checkConnection() {
  connectionStatus.value = 'wait'
  connectionResult.value = ''
  try {
    const data = await api('/api/provider/check')
    if (data.status === 'ok') {
      connectionStatus.value = 'ok'
    } else {
      connectionStatus.value = 'err'
      connectionResult.value = data.message || '未知错误'
    }
  } catch (e) {
    connectionStatus.value = 'err'
    connectionResult.value = '连接失败: ' + e.message
  }
}

// ─── 7. Feature Status ───────────────────────────────────────
const features = [
  { label: '聊天对话', value: '✔ 已实现', color: undefined },
  { label: '文件查找', value: '✔ 已实现', color: undefined },
  { label: '文档读取/生成', value: '✔ 已实现', color: undefined },
  { label: 'Excel 分析', value: '✔ 已实现', color: undefined },
  { label: '联网搜索', value: '⚠ 服务器可能受限', color: '#faad14' },
  { label: '用户习惯学习', value: '✔ 已实现', color: undefined },
  { label: '文件监控', value: '✔ 已实现', color: undefined },
  { label: '邮件处理', value: '✔ 已实现（需配置）', color: undefined },
  { label: '自动化任务', value: '✔ 已实现', color: undefined },
  { label: '窗口操作', value: '⚠ 仅 Windows', color: '#faad14' },
]

const soundEnabled = ref(true)
const autolearnStats = ref('加载中...')

function onSoundToggle() {
  localStorage.setItem('deskflow_sound', soundEnabled.value ? 'on' : 'off')
}

async function loadAutolearnStats() {
  try {
    const data = await api('/api/autolearn/stats')
    autolearnStats.value = `📊 今日${data.events_today}条事件 · ${data.active_patterns}条模式 · ${data.storage_mb}MB`
  } catch (e) {
    autolearnStats.value = '加载失败'
  }
}

// ─── 8. File Monitor ─────────────────────────────────────────
const monitorRunning = ref(false)
const monitorEventCount = ref(0)
const monitorDirs = ref([])
const monitorEvents = ref([])
const newDirPath = ref('')
const monitorMessage = ref('')
const eventType = ref('')

const eventTabs = [
  { type: '', label: '全部' },
  { type: 'created', label: '新建' },
  { type: 'modified', label: '修改' },
  { type: 'deleted', label: '删除' },
]

const monitorBadgeClass = computed(() => ({
  'status-badge': true,
  'status-ok': monitorRunning.value,
  'status-wait': !monitorRunning.value,
}))
const monitorStatusText = computed(() => {
  if (monitorRunning.value) return `✔ 运行中 (${monitorEventCount.value} 条事件)`
  return '⏸ 已停止'
})

async function loadMonitorStatus() {
  try {
    const data = await api('/api/monitor/status')
    monitorRunning.value = data.running || false
    monitorEventCount.value = data.event_count || 0
    monitorDirs.value = data.watched_dirs || []
  } catch (e) {
    console.error('loadMonitorStatus failed', e)
  }
}

async function toggleMonitor() {
  if (monitorRunning.value) {
    await api('/api/monitor/stop', { method: 'POST' })
  } else {
    await api('/api/monitor/start', { method: 'POST' })
  }
  await loadMonitorStatus()
  await loadEvents()
}

async function addMonitorDir() {
  const path = newDirPath.value.trim()
  if (!path) {
    monitorMessage.value = '请输入路径'
    return
  }
  try {
    const data = await api('/api/monitor/dirs', {
      method: 'POST',
      body: JSON.stringify({ path }),
    })
    if (data.status === 'ok') {
      monitorMessage.value = '✅ 已添加'
      newDirPath.value = ''
      await loadMonitorStatus()
    } else {
      monitorMessage.value = '❌ ' + (data.error || '添加失败')
    }
  } catch (e) {
    monitorMessage.value = '❌ ' + e.message
  }
}

async function removeMonitorDir(path) {
  try {
    await api('/api/monitor/dirs', {
      method: 'DELETE',
      body: JSON.stringify({ path }),
    })
    await loadMonitorStatus()
  } catch (e) {
    console.error('removeMonitorDir failed', e)
  }
}

async function loadEvents() {
  try {
    const data = await api(`/api/monitor/events?count=30&type=${eventType.value}`)
    monitorEvents.value = data
  } catch (e) {
    console.error('loadEvents failed', e)
  }
}

function switchEventTab(type) {
  eventType.value = type
  loadEvents()
}

function eventIcon(eventType) {
  if (eventType === 'created') return '🟢'
  if (eventType === 'modified') return '🔵'
  if (eventType === 'deleted') return '🔴'
  return '🟡'
}

// ─── 9. Scheduled Tasks ──────────────────────────────────────
const tasks = ref([])
const newTask = reactive({
  name: '',
  prompt: '',
  trigger_type: 'interval',
  interval_value: 1,
  interval_unit: 'hours',
  cron: '',
})
const taskMessage = ref('')

async function loadTasks() {
  try {
    const data = await api('/api/tasks')
    tasks.value = data
  } catch (e) {
    console.error('loadTasks failed', e)
  }
}

function onTaskTriggerTypeChange() {
  // handled reactively via v-if
}

async function createTask() {
  const { name, prompt, trigger_type, interval_value, interval_unit, cron } = newTask
  if (!name.trim()) {
    taskMessage.value = '请输入任务名称'
    return
  }
  if (!prompt.trim()) {
    taskMessage.value = '请输入触发内容'
    return
  }
  const body = { name: name.trim(), prompt: prompt.trim(), trigger_type }
  if (trigger_type === 'cron') {
    if (!cron.trim()) {
      taskMessage.value = '请输入 Cron 表达式'
      return
    }
    body.cron = cron.trim()
  } else {
    body.interval_value = interval_value || 1
    body.interval_unit = interval_unit
  }
  try {
    const data = await api('/api/tasks', {
      method: 'POST',
      body: JSON.stringify(body),
    })
    if (data.status === 'ok') {
      taskMessage.value = '✅ 已创建'
      newTask.name = ''
      newTask.prompt = ''
      newTask.interval_value = 1
      newTask.interval_unit = 'hours'
      newTask.cron = ''
      await loadTasks()
    } else {
      taskMessage.value = '❌ ' + (data.error || '创建失败')
    }
  } catch (e) {
    taskMessage.value = '❌ ' + e.message
  }
}

async function toggleTask(id) {
  try {
    await api('/api/tasks/' + id + '/toggle', { method: 'POST' })
    await loadTasks()
  } catch (e) {
    console.error('toggleTask failed', e)
  }
}

async function runTask(id) {
  try {
    await api('/api/tasks/' + id + '/run', { method: 'POST' })
    await loadTasks()
  } catch (e) {
    console.error('runTask failed', e)
  }
}

async function deleteTask(id) {
  if (!confirm('确定要删除此定时任务吗？')) return
  try {
    await api('/api/tasks/' + id, { method: 'DELETE' })
    await loadTasks()
  } catch (e) {
    console.error('deleteTask failed', e)
  }
}

// ─── 10. Log Viewer ─────────────────────────────────────────
const logViewerRef = ref(null)
const logLevel = ref('')
const logSearch = ref('')
const logLinesCount = ref('200')
const logHtml = ref('加载中...')
const logStatus = ref('')
const logAutoRefresh = ref(true)
let logTimer = null
let logRefreshInterval = null

const logLevels = [
  { label: '全部', value: '' },
  { label: 'INFO', value: 'INFO' },
  { label: 'WARN', value: 'WARNING' },
  { label: 'ERROR', value: 'ERROR' },
]

async function loadLogs() {
  const url = `/api/logs?lines=${logLinesCount.value}&level=${logLevel.value}&search=${encodeURIComponent(logSearch.value)}`
  try {
    logHtml.value = '加载中...'
    const data = await api(url)
    if (!data.lines || data.lines.length === 0) {
      logHtml.value = '<span style="color:#6c7086">暂无日志</span>'
    } else {
      logHtml.value = data.lines.map(line => {
        if (line.includes('[ERROR]')) return `<span class="log-line-error">${escHtml(line)}</span>`
        if (line.includes('[WARNING]')) return `<span class="log-line-warning">${escHtml(line)}</span>`
        if (line.includes('[INFO]')) return `<span class="log-line-info">${escHtml(line)}</span>`
        return `<span class="log-line-other">${escHtml(line)}</span>`
      }).join('\n')
    }
    logStatus.value = `共 ${data.total_lines} 行 · 显示 ${data.filtered_lines} 行 · ${data.file_size_mb} MB`
    await nextTick()
    if (logViewerRef.value) {
      logViewerRef.value.scrollTop = logViewerRef.value.scrollHeight
    }
  } catch (e) {
    logHtml.value = '❌ 加载失败: ' + e.message
  }
}

function onLogSearchInput() {
  clearTimeout(logTimer)
  logTimer = setTimeout(loadLogs, 300)
}

function switchLogLevel(level) {
  logLevel.value = level
  loadLogs()
}

function scrollLogBottom() {
  if (logViewerRef.value) {
    logViewerRef.value.scrollTop = logViewerRef.value.scrollHeight
  }
}

function onAutoRefreshChange() {
  // handled via the interval
}

async function confirmClearLogs() {
  if (!confirm('确定要清空所有日志吗？')) return
  if (!confirm('⚠️ 此操作不可撤销，确认清空？')) return
  try {
    const data = await api('/api/logs/clear', { method: 'POST' })
    if (data.status === 'ok') {
      await loadLogs()
    } else {
      alert('清空失败: ' + (data.error || ''))
    }
  } catch (e) {
    alert('清空失败: ' + e.message)
  }
}

// ─── Init ────────────────────────────────────────────────────
onMounted(async () => {
  // Restore sound toggle
  soundEnabled.value = localStorage.getItem('deskflow_sound') !== 'off'

  await Promise.all([
    loadConfig(),
    checkConnection(),
    loadProviders(),
    loadSearchConfig(),
    loadEmailProviders(),
    loadShortcuts(),
    loadMonitorStatus(),
    loadEvents(),
    loadTasks(),
    loadLogs(),
    loadAutolearnStats(),
  ])

  // Auto-refresh logs every 15s
  logRefreshInterval = setInterval(() => {
    if (logAutoRefresh.value) loadLogs()
  }, 15000)

  // Refresh tasks every 30s
  setInterval(loadTasks, 30000)

  // Refresh monitor status every 30s
  setInterval(() => {
    loadMonitorStatus()
    loadEvents()
  }, 30000)
})

onUnmounted(() => {
  clearInterval(logRefreshInterval)
  clearTimeout(logTimer)
})
</script>

<style scoped>
.settings-app {
  max-width: 800px;
  margin: 0 auto;
  background: #fff;
  min-height: 100vh;
  box-shadow: 0 0 20px rgba(0, 0, 0, 0.05);
}

.settings-header {
  display: flex;
  align-items: center;
  padding: 12px 20px;
  border-bottom: 1px solid #eee;
  gap: 12px;
}

.settings-header h2 {
  font-size: 16px;
  font-weight: 600;
  color: #333;
  flex: 1;
}

.back-btn {
  text-decoration: none;
  color: #4a7cff;
  font-size: 14px;
  padding: 4px 12px;
  border: 1px solid #4a7cff;
  border-radius: 6px;
  cursor: pointer;
  background: none;
}

.settings-content {
  padding: 24px 20px;
}

.section {
  margin-bottom: 24px;
}

.section h3 {
  font-size: 14px;
  color: #999;
  margin-bottom: 12px;
}

.card {
  background: #fafafa;
  border-radius: 8px;
  padding: 16px;
  border: 1px solid #eee;
}

.row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 0;
  border-bottom: 1px solid #f0f0f0;
  font-size: 14px;
  gap: 8px;
}

.row:last-child {
  border-bottom: none;
}

.row .label {
  color: #666;
  white-space: nowrap;
}

.row .value {
  color: #333;
  font-weight: 500;
}

.status-badge {
  display: inline-block;
  padding: 2px 10px;
  border-radius: 10px;
  font-size: 12px;
  font-weight: 500;
}

.status-ok {
  background: #f6ffed;
  color: #52c41a;
  border: 1px solid #b7eb8f;
}

.status-err {
  background: #fff2f0;
  color: #ff4d4f;
  border: 1px solid #ffccc7;
}

.status-wait {
  background: #fffbe6;
  color: #faad14;
  border: 1px solid #ffe58f;
}

.reconfig-btn {
  display: block;
  width: 100%;
  padding: 12px;
  background: #4a7cff;
  color: #fff;
  border: none;
  border-radius: 8px;
  font-size: 14px;
  cursor: pointer;
  margin-top: 16px;
  text-align: center;
}

.reconfig-btn:hover {
  background: #3a66d9;
}

.check-result {
  margin-top: 12px;
  font-size: 13px;
  color: #ff4d4f;
}

.btn {
  padding: 6px 16px;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 13px;
  transition: opacity 0.15s;
}

.btn:hover {
  opacity: 0.85;
}

.btn-primary {
  background: #4a7cff;
  color: #fff;
}

.btn-success {
  background: #52c41a;
  color: #fff;
}

.btn-danger {
  background: #ff4d4f;
  color: #fff;
}

.btn-sm {
  padding: 5px 12px;
  font-size: 12px;
}

.btn-icon {
  border: none;
  background: none;
  cursor: pointer;
  font-size: 13px;
  padding: 2px 4px;
}

.btn-icon.danger {
  color: #ff4d4f;
}

.disabled {
  opacity: 0.5;
  pointer-events: none;
}

.text-input {
  padding: 6px 10px;
  border: 1px solid #ddd;
  border-radius: 6px;
  font-size: 13px;
  background: #fff;
  color: #333;
}

.text-input:focus {
  outline: none;
  border-color: #4a7cff;
}

.select-input {
  padding: 6px 10px;
  border: 1px solid #ddd;
  border-radius: 6px;
  font-size: 13px;
  background: #fff;
  color: #333;
}

.select-input:focus {
  outline: none;
  border-color: #4a7cff;
}

.flex-1 {
  flex: 1;
}

.flex-2 {
  flex: 2;
}

.flex-3 {
  flex: 3;
}

.result-msg {
  font-size: 12px;
  color: #999;
  padding: 4px 0;
}

.result-msg.success {
  color: #52c41a;
}

.result-msg.error {
  color: #ff4d4f;
}

.inline-code {
  background: #f0f0f0;
  padding: 2px 6px;
  border-radius: 4px;
  font-family: monospace;
  font-size: 12px;
}

/* ── Provider Cards ── */
.provider-card {
  border: 1px solid #eee;
  border-radius: 8px;
  padding: 10px 12px;
  margin-bottom: 8px;
  background: #fafafa;
}

.provider-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
}

.provider-name {
  font-weight: 600;
  font-size: 14px;
}

.provider-model {
  font-size: 11px;
  color: #999;
  margin-left: 6px;
}

.provider-desc {
  font-size: 11px;
  color: #888;
}

.provider-actions {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  align-items: center;
}

.provider-key-input {
  flex: 2;
  min-width: 150px;
  padding: 6px 10px;
  border: 1px solid #ddd;
  border-radius: 6px;
  font-size: 12px;
}

.provider-result {
  font-size: 11px;
  padding-top: 4px;
}

.provider-result.success {
  color: #52c41a;
}

.provider-result.error {
  color: #ff4d4f;
}

/* ── Shortcuts ── */
.shortcut-list {
  margin-bottom: 4px;
}

.shortcut-desc {
  color: #666;
  margin-left: 8px;
}

.shortcut-form {
  margin-top: 12px;
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

/* ── Email ── */
.email-actions {
  display: flex;
  gap: 8px;
  margin-top: 12px;
  flex-wrap: wrap;
}

.email-tip {
  margin-top: 8px;
  padding: 8px;
  background: #fffbe6;
  border-radius: 6px;
  border: 1px solid #ffe58f;
  font-size: 12px;
  color: #8c6d00;
}

/* ── Monitor ── */
.monitor-section {
  margin-top: 12px;
}

.section-label {
  font-size: 13px;
  color: #666;
  margin-bottom: 6px;
}

.empty-text {
  color: #999;
  font-size: 13px;
}

.empty-text-center {
  padding: 20px;
  text-align: center;
  color: #999;
  font-size: 13px;
}

.dir-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 4px 8px;
  background: #f5f5f5;
  border-radius: 4px;
  margin-bottom: 4px;
}

.dir-path {
  font-size: 12px;
}

.monitor-add-dir {
  display: flex;
  gap: 6px;
  margin-top: 6px;
  flex-wrap: wrap;
}

.events-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
}

.event-tabs {
  display: flex;
  gap: 4px;
}

.event-tab {
  padding: 2px 8px;
  border: 1px solid #ddd;
  border-radius: 4px;
  background: #f5f5f5;
  cursor: pointer;
  font-size: 11px;
  color: #666;
}

.event-tab.active {
  background: #4a7cff;
  color: #fff;
  border-color: #4a7cff;
}

.monitor-events {
  max-height: 250px;
  overflow-y: auto;
  background: #fafafa;
  border-radius: 6px;
  border: 1px solid #eee;
  font-size: 12px;
}

.event-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 10px;
  border-bottom: 1px solid #f0f0f0;
  font-size: 12px;
}

.event-time {
  color: #999;
  min-width: 60px;
}

.event-file {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.event-size {
  color: #888;
}

.event-icon {
  margin-right: 2px;
}

/* ── Tasks ── */
.task-card {
  border: 1px solid #eee;
  border-radius: 8px;
  padding: 10px 12px;
  margin-bottom: 8px;
  background: #fafafa;
}

.task-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 4px;
}

.task-name {
  font-weight: 600;
  font-size: 14px;
}

.task-schedule {
  font-size: 12px;
  color: #666;
  margin-bottom: 4px;
}

.task-prompt {
  margin-left: 6px;
  color: #999;
}

.task-footer {
  font-size: 11px;
  color: #999;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.task-actions {
  display: flex;
  gap: 4px;
}

.new-task-section {
  margin-top: 14px;
  padding-top: 12px;
  border-top: 1px solid #eee;
}

.task-form {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.task-form-row {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  align-items: center;
}

.task-interval-config {
  display: flex;
  gap: 4px;
  align-items: center;
}

.task-cron-config {
  display: flex;
  align-items: center;
  gap: 4px;
}

.cron-hint {
  font-size: 11px;
  color: #999;
}

/* ── Log Viewer ── */
.log-viewer {
  background: #1e1e2e;
  color: #cdd6f4;
  font-family: 'Cascadia Code', 'Fira Code', 'Consolas', monospace;
  font-size: 12px;
  line-height: 1.6;
  padding: 12px;
  border-radius: 8px;
  max-height: 400px;
  overflow-y: auto;
  white-space: pre;
  margin: 0;
  border: 1px solid #313244;
  tab-size: 2;
}

.log-viewer::-webkit-scrollbar {
  width: 6px;
}

.log-viewer::-webkit-scrollbar-track {
  background: #181825;
}

.log-viewer::-webkit-scrollbar-thumb {
  background: #45475a;
  border-radius: 3px;
}

.log-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 8px;
}

.log-tabs {
  display: flex;
  gap: 4px;
}

.log-tab {
  padding: 4px 12px;
  border: 1px solid #ddd;
  border-radius: 6px;
  background: #f5f5f5;
  cursor: pointer;
  font-size: 12px;
  color: #666;
  transition: all 0.15s;
}

.log-tab:hover {
  background: #e8f0ff;
  border-color: #4a7cff;
}

.log-tab.active {
  background: #4a7cff;
  color: #fff;
  border-color: #4a7cff;
}

.log-actions {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.log-search-input {
  padding: 4px 8px;
  border: 1px solid #ddd;
  border-radius: 6px;
  font-size: 12px;
  width: 120px;
}

.log-actions select {
  padding: 4px 6px;
  border: 1px solid #ddd;
  border-radius: 6px;
  font-size: 12px;
  background: #fff;
}

.log-action-btn {
  padding: 4px 8px;
  border: 1px solid #ddd;
  border-radius: 6px;
  background: #fff;
  cursor: pointer;
  font-size: 13px;
}

.log-action-btn:hover {
  background: #f0f0f0;
}

.log-action-btn.danger {
  color: #ff4d4f;
}

.log-status {
  font-size: 11px;
  color: #999;
  padding: 4px 0;
  text-align: right;
}

.auto-refresh-label {
  font-size: 12px;
  color: #888;
  display: flex;
  align-items: center;
  gap: 4px;
}

/* Log line colors */
.log-line-error {
  color: #f38ba8;
}

.log-line-warning {
  color: #fab387;
}

.log-line-info {
  color: #89b4fa;
}

.log-line-other {
  color: #6c7086;
}
</style>
