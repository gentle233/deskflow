/**
 * 聊天界面核心功能测试
 * - 输入框和发送按钮
 * - SSE 流式响应
 * - Markdown 渲染
 * - 停止生成按钮
 * - 提示音
 */
import { test, expect } from '@playwright/test'

// 模拟 SSE 流式 API 响应
function mockChatApi(page) {
  return page.route('**/api/chat/stream', async (route) => {
    const formData = route.request().postData()
    // 返回模拟的流式响应
    const mockReply = `你好！我是 DeskFlow 桌面助手。

我可以帮你：
- **写文档、报告**
- \`搜索文件\`
- 分析 \`Excel\` 表格

\`\`\`python
print("Hello World")
\`\`\`

> 这是引用文字

| 列A | 列B |
|-----|-----|
| 值1 | 值2 |

[点击访问](https://example.com)

这是回复的结尾。`

    const sseData = []
    // 分块发送
    for (let i = 0; i < mockReply.length; i += 3) {
      const chunk = mockReply.slice(i, i + 3)
      sseData.push(`data: ${JSON.stringify({ token: chunk })}\n\n`)
    }
    sseData.push(`data: ${JSON.stringify({ done: true })}\n\n`)

    await route.fulfill({
      status: 200,
      headers: {
        'Content-Type': 'text/event-stream',
        'Cache-Control': 'no-cache',
      },
      body: sseData.join(''),
    })
  })
}

function mockAPIs(page) {
  // 简答 API
  page.route('**/api/chat', async (route) => {
    await route.fulfill({ json: { reply: '你好！有什么可以帮你的？' } })
  })
  // 快捷指令
  page.route('**/api/shortcuts', async (route) => {
    await route.fulfill({
      json: [
        { trigger: '/hello', command: '你好，帮我介绍一下自己', desc: '打招呼' },
        { trigger: '/file', command: '帮我找一下昨天的文件', desc: '查找文件' },
      ],
    })
  })
  // 学习建议
  page.route('**/api/autolearn/suggestions', async (route) => {
    await route.fulfill({ json: [] })
  })
  // 监控状态
  page.route('**/api/monitor/status', async (route) => {
    await route.fulfill({ json: { event_count: 0 } })
  })
  // 监控事件
  page.route('**/api/monitor/events*', async (route) => {
    await route.fulfill({ json: [] })
  })
}

test.describe('聊天界面', () => {
  test.beforeEach(async ({ page }) => {
    mockAPIs(page)
    mockChatApi(page)
  })

  test('加载后显示欢迎消息', async ({ page }) => {
    await page.goto('/')
    await expect(page.locator('.chat-container')).toBeVisible()
    await expect(page.locator('.title')).toHaveText('DeskFlow')
    const bubbles = page.locator('.bubble')
    await expect(bubbles.first()).toBeVisible()
  })

  test('输入文本后发送按钮可用，空输入时禁用', async ({ page }) => {
    await page.goto('/')
    const sendBtn = page.locator('.send-btn')
    await expect(sendBtn).toBeDisabled()

    await page.locator('.input-box').fill('你好')
    await expect(sendBtn).toBeEnabled()
  })

  test('按回车发送消息，显示用户消息和 AI 流式回复', async ({ page }) => {
    await page.goto('/')
    await page.locator('.input-box').fill('你好')
    await page.locator('.input-box').press('Enter')

    // 用户消息气泡出现
    const userBubbles = page.locator('.message.user .bubble')
    await expect(userBubbles.first()).toBeVisible({ timeout: 5000 })
    await expect(userBubbles.first()).toContainText('你好')

    // AI 回复出现（流式）
    const aiBubbles = page.locator('.message.assistant .bubble')
    await expect(aiBubbles.last()).toBeVisible({ timeout: 5000 })
    // 等待流式完成
    await page.waitForTimeout(1000)
    const text = await aiBubbles.last().innerHTML()
    expect(text).toContain('DeskFlow')
  })

  test('Markdown 渲染正确：代码块、表格、引用、链接', async ({ page }) => {
    await page.goto('/')
    await page.locator('.input-box').fill('markdown test')
    await page.locator('.input-box').press('Enter')

    // 等待回复
    await expect(page.locator('.message.assistant .bubble').last()).toBeVisible({ timeout: 5000 })
    await page.waitForTimeout(1500)

    const content = await page.locator('.message.assistant .bubble').last().innerHTML()

    // 粗体
    expect(content).toContain('<strong>')
    // 行内代码
    expect(content).toContain('<code>')
    // 代码块
    expect(content).toContain('<pre>')
    // 引用
    expect(content).toContain('<blockquote>')
    // 表格
    expect(content).toContain('<table>')
    // 链接
    expect(content).toContain('<a ')
  })

  test('发送后输入框清空', async ({ page }) => {
    await page.goto('/')
    await page.locator('.input-box').fill('测试消息')
    await page.locator('.input-box').press('Enter')

    await expect(page.locator('.input-box')).toHaveValue('')
  })
})
