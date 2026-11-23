import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
import { useState } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('../lib/api.js', () => ({ transcribe: vi.fn() }))
vi.mock('../lib/feedback.js', () => ({ startCue: vi.fn(), stopCue: vi.fn(), doneCue: vi.fn() }))
vi.mock('../lib/recorder.js', () => ({ recordingSupported: () => false, startRecording: vi.fn() }))
vi.mock('../lib/speech.js', () => ({ speechSupported: () => true, listen: vi.fn() }))

import { listen } from '../lib/speech.js'
import VoiceComposer from './VoiceComposer.jsx'

// The browser's recognizer, driven by the test: the callbacks VoiceComposer
// passed to listen().
let recognizer

function Composer() {
  const [prompt, setPrompt] = useState('')
  return (
    <VoiceComposer
      prompt={prompt}
      onPromptChange={setPrompt}
      onBuild={() => {}}
      canBuild
      running={false}
      onType={() => {}}
    />
  )
}

function tapMic() {
  fireEvent.click(screen.getByRole('button', { name: 'Tap and describe your app' }))
}

beforeEach(() => {
  listen.mockImplementation((callbacks) => {
    recognizer = callbacks
    return { stop: () => callbacks.onEnd() }
  })
})

afterEach(() => {
  cleanup()
})

describe('VoiceComposer with the browser recognizer', () => {
  it('asks to build what it heard', () => {
    render(<Composer />)
    tapMic()
    act(() => recognizer.onText('a tip calculator'))
    act(() => recognizer.onEnd())
    expect(screen.getByRole('button', { name: 'Build my app' })).toBeTruthy()
    expect(screen.getByText(/tip/)).toBeTruthy()
  })

  it('goes back to the start with a reason when it heard nothing', () => {
    render(<Composer />)
    tapMic()
    fireEvent.click(screen.getByRole('button', { name: 'Stop listening' }))
    expect(screen.getByRole('alert').textContent).toBe("Didn't catch that. Tap the mic and try again.")
    expect(screen.getByRole('button', { name: 'Type instead' })).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Tap and describe your app' })).toBeTruthy()
  })

  it("keeps the recognizer's own error when it heard nothing", () => {
    render(<Composer />)
    tapMic()
    act(() => recognizer.onError('No microphone found. Type your app instead.'))
    act(() => recognizer.onEnd())
    expect(screen.getByRole('alert').textContent).toBe('No microphone found. Type your app instead.')
    expect(screen.getByRole('button', { name: 'Type instead' })).toBeTruthy()
  })

  it('treats only spaces as nothing heard', () => {
    render(<Composer />)
    tapMic()
    act(() => recognizer.onText('   '))
    act(() => recognizer.onEnd())
    expect(screen.queryByRole('button', { name: 'Build my app' })).toBeNull()
    expect(screen.getByRole('button', { name: 'Type instead' })).toBeTruthy()
  })
})
