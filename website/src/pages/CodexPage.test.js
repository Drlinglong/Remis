import { describe, expect, it, vi } from 'vitest'
import { copyText, installPrompt } from './codexPrompt'

describe('Remis for Codex install prompt', () => {
  it('includes the mandatory setup, release, secret, and approval boundaries', () => {
    expect(installPrompt).toContain('check the latest official GitHub Release')
    expect(installPrompt).toContain('Remis Settings > API Settings')
    expect(installPrompt).toContain('offer to explain what an API key is')
    expect(installPrompt).toContain('never ask me to paste one into chat')
    expect(installPrompt).toContain('wait for my explicit approval')
    expect(installPrompt).toContain('Keep the API on localhost')
  })

  it('copies the complete prompt through the browser clipboard contract', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined)

    await copyText(installPrompt, { writeText })

    expect(writeText).toHaveBeenCalledOnce()
    expect(writeText).toHaveBeenCalledWith(installPrompt)
  })
})
