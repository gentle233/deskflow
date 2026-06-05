<template>
  <div class="setup-page">
    <div class="card">
      <div class="steps">
        <div class="step active"></div>
        <div class="step"></div>
      </div>

      <h1>欢迎使用 DeskFlow</h1>
      <p class="sub">先配置 AI 提供商，一次性设置后即可开始使用</p>

      <label>选择 AI 提供商</label>
      <select v-model="provider">
        <option value="deepseek">DeepSeek ★推荐（便宜好用）</option>
        <option value="moonshot">Kimi / 月之暗面</option>
        <option value="tongyi">统一千问（阿里云）</option>
        <option value="zhipu">智谱 GLM</option>
        <option value="openai">OpenAI / ChatGPT</option>
      </select>

      <label>API Key</label>
      <input
        v-model="apiKey"
        type="password"
        placeholder="输入你的 API Key"
        @keyup.enter="submit"
      />
      <p class="hint">还没有 Key？去官网注册一个，通常有免费额度</p>

      <button :disabled="loading" @click="submit">
        {{ loading ? '设置中...' : '完成设置' }}
      </button>

      <p v-if="error" class="error">{{ error }}</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()

const provider = ref('deepseek')
const apiKey = ref('')
const loading = ref(false)
const error = ref('')

async function submit() {
  const key = apiKey.value.trim()
  if (!key) {
    error.value = '请输入 API Key'
    return
  }

  error.value = ''
  loading.value = true

  try {
    const resp = await fetch('/api/setup', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ provider: provider.value, api_key: key })
    })

    if (resp.ok) {
      router.push('/')
    } else {
      const data = await resp.json().catch(() => null)
      error.value = (data && data.message) || '设置失败，请重试'
    }
  } catch {
    error.value = '网络错误，请检查连接后重试'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

.setup-page {
  font-family: -apple-system, "Microsoft YaHei", sans-serif;
  background: #f5f5f5;
  display: flex;
  justify-content: center;
  align-items: center;
  height: 100vh;
  width: 100%;
}

.card {
  background: #fff;
  border-radius: 16px;
  padding: 40px;
  width: 480px;
  box-shadow: 0 4px 24px rgba(0, 0, 0, 0.08);
}

.steps {
  display: flex;
  gap: 8px;
  margin-bottom: 24px;
}

.step {
  flex: 1;
  height: 4px;
  border-radius: 2px;
  background: #e8e8e8;
}

.step.active {
  background: #4a7cff;
}

h1 {
  font-size: 24px;
  color: #333;
  margin-bottom: 8px;
}

p.sub {
  color: #999;
  font-size: 14px;
  margin-bottom: 28px;
}

label {
  display: block;
  font-size: 14px;
  color: #555;
  margin-bottom: 6px;
  margin-top: 16px;
}

select,
input {
  width: 100%;
  padding: 10px 14px;
  border: 1px solid #d9d9d9;
  border-radius: 8px;
  font-size: 14px;
  outline: none;
  transition: border-color 0.2s;
}

select:focus,
input:focus {
  border-color: #4a7cff;
}

.hint {
  font-size: 12px;
  color: #999;
  margin-top: 4px;
}

button {
  width: 100%;
  margin-top: 28px;
  padding: 12px;
  background: #4a7cff;
  color: #fff;
  border: none;
  border-radius: 8px;
  font-size: 16px;
  cursor: pointer;
  transition: background 0.2s;
}

button:hover:not(:disabled) {
  background: #3a66d9;
}

button:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.error {
  margin-top: 12px;
  font-size: 13px;
  color: #e74c3c;
  text-align: center;
}
</style>
