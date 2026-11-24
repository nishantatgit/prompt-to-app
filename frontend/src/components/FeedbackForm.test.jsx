import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

vi.mock('../lib/api.js', () => ({
  sendFeedback: vi.fn(),
}))

import { sendFeedback } from '../lib/api.js'
import FeedbackForm from './FeedbackForm.jsx'

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('FeedbackForm', () => {
  it('shows a failed send as an alert in the error color, not the green of success', async () => {
    sendFeedback.mockRejectedValue(new Error("Thanks! That's plenty of feedback for today."))
    render(<FeedbackForm jobId="abc" />)
    fireEvent.click(screen.getByRole('button', { name: 'Not right' }))
    fireEvent.change(screen.getByLabelText('Your feedback'), { target: { value: 'The list did not save.' } })
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'Send feedback' }))
    })
    const alert = screen.getByRole('alert')
    expect(alert.textContent).toBe("Thanks! That's plenty of feedback for today.")
    expect(alert.className).toContain('text-danger')
    expect(alert.className).not.toContain('text-accent')
  })

  it('thanks the person in green when it was sent', async () => {
    sendFeedback.mockResolvedValue({ ok: true, bonus_builds: 0 })
    render(<FeedbackForm jobId="abc" />)
    fireEvent.click(screen.getByRole('button', { name: 'Good' }))
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'Send feedback' }))
    })
    expect(screen.queryByRole('alert')).toBeNull()
    expect(screen.getByText(/Thank you!/).className).toContain('text-accent')
  })

  it('counts emoji as the server does when saying a message earns bonus builds', () => {
    render(<FeedbackForm jobId="abc" bonus={2} />)
    fireEvent.click(screen.getByRole('button', { name: 'Good' }))
    const box = screen.getByLabelText('Your feedback')
    // 10 emoji: 20 by JavaScript's count, 10 by the server's, so no bonus yet
    fireEvent.change(box, { target: { value: '👍'.repeat(10) } })
    expect(screen.getByText(/Write a sentence or two/)).toBeTruthy()
    fireEvent.change(box, { target: { value: 'The todo list saved fine.' } })
    expect(screen.getByText(/Sending this gets you/)).toBeTruthy()
  })
})
