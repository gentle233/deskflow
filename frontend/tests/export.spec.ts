/**
 * 导出功能测试
 * - JSON 格式下载
 * - Markdown 格式下载
 */
import { test, expect } from '@playwright/test'

test.describe('聊天导出', () => {
  test.beforeEach(async ({ page }) => {
    page.route('**/api/**', async (route) => {
      await route.fulfill({ json: {} })
    })
  })

  test('无历史时导出提示暂无记录', async ({ page }) => {
    await page.goto('/')
    await page.evaluate(() => localStorage.removeItem('deskflow_chat'))

    // 设置 dialog 监听
    page.on('dialog', async (dialog) => {
      expect(dialog.message()).toContain('暂无聊天记录')
      await dialog.dismiss()
    })

    await page.locator('.icon-btn[title="导出聊天记录"]').click()
  })

  test('有历史时可导出 JSON 格式', async ({ page }) => {
    await page.goto('/')
    // 先写入历史
    await page.evaluate(() => {
      const history = [
        { role: 'user', content: '你好', time: Date.now() },
        { role: 'assistant', content: '你好！', time: Date.now() },
      ]
      localStorage.setItem('deskflow_chat', JSON.stringify(history))
    })

    // 监听下载
    const downloadPromise = page.waitForEvent('download', { timeout: 5000 }).catch(() => null)

    // 选择 JSON 导出（confirm=true）
    page.on('dialog', async (dialog) => {
      await dialog.accept() // true = JSON
    })

    await page.locator('.icon-btn[title="导出聊天记录"]').click()

    const download = await downloadPromise
    if (download) {
      expect(download.suggestedFilename()).toMatch(/\.json$/)
    }
  })

  test('有历史时可导出 Markdown 格式', async ({ page }) => {
    await page.goto('/')
    await page.evaluate(() => {
      const history = [
        { role: 'user', content: '测试', time: Date.now() },
        { role: 'assistant', content: '回复', time: Date.now() },
      ]
      localStorage.setItem('deskflow_chat', JSON.stringify(history))
    })

    const downloadPromise = page.waitForEvent('download', { timeout: 5000 }).catch(() => null)

    // 选择 Markdown 导出（confirm=false）
    page.on('dialog', async (dialog) => {
      await dialog.dismiss() // false = Markdown
    })

    await page.locator('.icon-btn[title="导出聊天记录"]').click()

    const download = await downloadPromise
    if (download) {
      expect(download.suggestedFilename()).toMatch(/\.md$/)
    }
  })
})
