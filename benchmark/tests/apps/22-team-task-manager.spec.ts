import { test, expect, type Page } from '@playwright/test'
import { getApp, getAppUrl, tagsFor } from '../../helpers/apps'
import { newVisitor, signUp, testEmail } from '../../helpers/auth'
import { button, field, shown, unique } from '../../helpers/storage'

// Pass check: a team owner invites a member by email with a role, creates a
// task and assigns it to them; the member signs up with that email and sees
// the team and the task assigned to them.

const app = getApp(22)
const url = getAppUrl(app.id)

// Create a team when the app asks for one first.
async function createTeamIfAsked(page: Page) {
  const name = page.getByRole('textbox', { name: /team( name)?|workspace|organi[sz]ation/i }).first()
  if ((await name.count()) > 0 && (await name.isVisible())) {
    await name.fill(unique('Bench team'))
    await button(page, /create|save|start|next|continue/i).click()
  }
}

async function invite(page: Page, email: string) {
  const open = page.getByRole('button', { name: /invite|add (a )?member|members|team/i }).first()
  if ((await field(page, /e-?mail/i).count()) === 0 && (await open.count()) > 0) await open.click()
  await field(page, /e-?mail/i).fill(email)
  const role = page.getByRole('combobox', { name: /role/i }).first()
  if ((await role.count()) > 0) {
    const member = (await role.locator('option').allTextContents()).find((o) => /member|editor|user/i.test(o))
    if (member) await role.selectOption({ label: member })
  } else {
    const radio = page.getByRole('radio', { name: /member|editor/i }).first()
    if ((await radio.count()) > 0) await radio.check()
  }
  await button(page, /invite|send|add/i).click()
  await expect(shown(page, email)).toBeVisible({ timeout: 10_000 })
}

async function createAssignedTask(page: Page, title: string, assignee: string) {
  const open = page.getByRole('button', { name: /new task|add task|create task/i }).first()
  if ((await field(page, /task|title/i).count()) === 0 && (await open.count()) > 0) await open.click()
  await field(page, /task|title/i).fill(title)
  const assign = page.getByRole('combobox', { name: /assign|owner|who/i }).first()
  const option = (await assign.locator('option').allTextContents()).find((o) => o.includes(assignee.split('@')[0]))
  expect(option, 'the invited member can be chosen as assignee').toBeTruthy()
  await assign.selectOption({ label: option! })
  await button(page, /add|create|save|assign/i).click()
  await expect(shown(page, title)).toBeVisible({ timeout: 10_000 })
}

test.describe(`#${app.id} ${app.slug} | specific`, { tag: tagsFor(app) }, () => {
  test.skip(!url, 'Not deployed yet')
  test.setTimeout(90_000)

  test.beforeEach(async ({ page }) => {
    await page.goto(url!)
  })

  test('roles can be chosen when inviting', async ({ page }) => {
    await signUp(page, testEmail('owner'))
    await createTeamIfAsked(page)
    const roles = page.getByRole('combobox', { name: /role/i }).or(page.getByRole('radio', { name: /admin|member|owner|editor|viewer/i }))
    const open = page.getByRole('button', { name: /invite|add (a )?member|members|team/i }).first()
    if ((await roles.count()) === 0 && (await open.count()) > 0) await open.click()
    await expect(roles.first()).toBeVisible()
  })

  test('an invited member sees the task assigned to them', async ({ page, browser }) => {
    const member = testEmail('member')
    const task = unique('Prepare the pitch deck')
    await signUp(page, testEmail('owner'))
    await createTeamIfAsked(page)
    await invite(page, member)
    await createAssignedTask(page, task, member)

    const { context, page: other } = await newVisitor(browser, url!)
    try {
      await signUp(other, member)
      const accept = other.getByRole('button', { name: /accept|join/i }).first()
      if ((await accept.count()) > 0) await accept.click()
      await expect(shown(other, task)).toBeVisible({ timeout: 15_000 })
    } finally {
      await context.close()
    }
  })

  test('someone not invited does not see the team task', async ({ page, browser }) => {
    const task = unique('Secret roadmap')
    await signUp(page, testEmail('owner'))
    await createTeamIfAsked(page)
    await invite(page, testEmail('member'))
    await createAssignedTask(page, task, 'member')

    const { context, page: stranger } = await newVisitor(browser, url!)
    try {
      await signUp(stranger, testEmail('stranger'))
      await stranger.waitForTimeout(3000)
      await expect(shown(stranger, task)).toHaveCount(0)
    } finally {
      await context.close()
    }
  })
})

