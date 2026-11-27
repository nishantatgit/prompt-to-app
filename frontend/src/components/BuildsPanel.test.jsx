import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

vi.mock('../lib/api.js', () => ({
  joinWaitlist: vi.fn(),
  sendFeedback: vi.fn(),
}))

import BuildsPanel from './BuildsPanel.jsx'

afterEach(cleanup)

const credits = { enabled: false, builds_left: 0, packs: [] }

function heading() {
  return screen.getByRole('heading').textContent
}

describe('BuildsPanel', () => {
  it('says the browser must save site data, not that free builds are used up, without a visitor id', () => {
    const trial = { enabled: true, builds_left: 0, needs_storage: true, bonus_available: false }
    render(<BuildsPanel trial={trial} credits={credits} bonusBuilds={2} />)
    expect(heading()).toBe('Free builds need this browser to save site data')
    expect(screen.queryByText(/used your free builds/)).toBeNull()
    expect(screen.getByText(/add your own AI key below/)).toBeTruthy()
    // Feedback for builds and the waitlist can't help this browser.
    expect(screen.queryByLabelText('Email')).toBeNull()
  })

  it('leaves out the own key hint when own keys are off', () => {
    const trial = { enabled: true, builds_left: 0, needs_storage: true }
    render(<BuildsPanel trial={trial} credits={credits} bonusBuilds={2} ownKeys={false} />)
    expect(screen.queryByText(/own AI key/)).toBeNull()
  })

  it('still says the builds are used up for a browser that used them', () => {
    const trial = { enabled: true, builds_left: 0, needs_storage: false }
    render(<BuildsPanel trial={trial} credits={credits} bonusBuilds={2} />)
    expect(heading()).toBe("You've used your free builds")
  })
})
