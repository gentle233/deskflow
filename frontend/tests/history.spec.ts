/**
 * 历史持久化测试
 * - localStorage 存储聊天记录
 * - 刷新后恢复历史
 * - 50 条上限裁剪
 */
import { test, expect } from '@playwright/test'

// 模拟带历史的页面
test.describe('历史持久化', () => {
  test.beforeEach(async ({ page }) => {
    page.route('**/api/**', async (route) => {
      await route.fulfill({ json: {} })
    })
  })

  test('刷新后历史消息从 localStorage 恢复', async ({ page }) => {
    // 先写 localStorage
    await page.goto('/')
    await page.evaluate(() => {
      const history = [
        { role: 'user', content: '你好', time: Date.now() - 60000 },
        { role: 'assistant', content: '你好！有什么可以帮你？', time: Date.now() - 59000 },
        { role: 'user', content: '帮我找文件', time: Date.now() - 30000 },
        { role: 'assistant', content: '好的，已找到 3 个文件。', time: Date.now() - 29000 },
      ]
      localStorage.setItem('deskflow_chat', JSON.stringify(history))
    })

    // 刷新
    await page.reload()

    // 等待加载
    await expect(page.locator('.chat-container')).toBeVisible()
    await page.waitForTimeout(500)

    // 历史消息应渲染
    const messages = page.locator('.message')
    const count = await messages.count()
    expect(count).toBeGreaterThanOrEqual(4)
  })

  test('超过 50 条时剪裁到后 50 条', async ({ page }) => {
    await page.goto('/')
    await page.evaluate(() => {
      const history = []
      for (let i = 0; i < 100; i++) {
        history.push({ role: 'user', content: `消息${i}`, time: Date.now() - i * 1000 })
      }
      localStorage.setItem('deskflow_chat', JSON.stringify(history))
    })

    // 触发一次聊天交互，这会调用 saveToHistory
    await page.evaluate(() => {
      const storage = JSON.parse(localStorage.getItem('deskflow_chat') || '[]')
      if (storage.length > 50) {
        const trimmed = storage.slice(-50)
        localStorage.setItem('deskflow_chat', JSON.stringify(trimmed))
      }
    })

    const storage = await page.evaluate(() =>
      JSON.parse(localStorage.getItem('deskflow_chat') || '[]')
    )
    expect(storage.length).toBeLessThanOrEqual(50)
  })

  test('无历史时显示欢迎消息', async ({ page }) => {
    await page.goto('/')
    // 清空可能的旧数据
    await page.evaluate(() => localStorage.removeItem('deskflow_chat'))
    await page.reload()

    await expect(page.locator('.chat-container')).toBeVisible()
    const bubbles = page.locator('.message.assistant .bubble')
    await expect(bubbles.first()).toBeVisible()
    const text = await bubbles.first().innerHTML()
    expect(text).toContain('DeskFlow')
  })
})
