/**
 * 页面导航测试
 * - Chat ↔ Settings 路由跳转
 * - 设置页显示配置信息
 */
import { test, expect } from '@playwright/test'

test.describe('页面导航', () => {
  test.beforeEach(async ({ page }) => {
    page.route('**/api/**', async (route) => {
      if (route.request().url().includes('/api/config')) {
        await route.fulfill({
          json: {
            provider: 'deepseek',
            model: 'deepseek-chat',
            api_key: 'sk-1234****5678',
            search_provider: 'ddgs',
          },
        })
      } else {
        await route.fulfill({ json: {} })
      }
    })
  })

  test('首页是聊天页面', async ({ page }) => {
    await page.goto('/')
    await expect(page.locator('.chat-container')).toBeVisible()
    await expect(page.locator('.input-box')).toBeVisible()
  })

  test('从聊天页导航到设置页', async ({ page }) => {
    await page.goto('/')
    await page.locator('.settings-link').click()

    // 等待设置页加载
    await expect(page.locator('.settings-app')).toBeVisible({ timeout: 5000 })
    await expect(page.locator('h2')).toContainText('设置')
  })

  test('设置页显示提供商和模型信息', async ({ page }) => {
    await page.goto('/#/settings')
    await expect(page.locator('.settings-app')).toBeVisible({ timeout: 5000 })
    await page.waitForTimeout(500)

    const text = await page.locator('.settings-content').innerText()
    expect(text).toContain('deepseek')
    expect(text).toContain('AI 提供商')
  })

  test('从设置页返回聊天页', async ({ page }) => {
    await page.goto('/#/settings')
    await expect(page.locator('.settings-app')).toBeVisible({ timeout: 5000 })

    await page.locator('.back-btn').click()
    await expect(page.locator('.chat-container')).toBeVisible({ timeout: 5000 })
  })

  test('设置页有重新配置按钮', async ({ page }) => {
    await page.goto('/#/settings')
    await expect(page.locator('.settings-app')).toBeVisible({ timeout: 5000 })

    const reconfigBtn = page.locator('.reconfig-btn').first()
    await expect(reconfigBtn).toBeVisible()
    await expect(reconfigBtn).toHaveText('重新配置')
  })
})
