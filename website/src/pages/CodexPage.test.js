import { describe, expect, it, vi } from 'vitest'
import { copyText, installPrompt } from './codexPrompt'

describe('Remis for Codex install prompt', () => {
  it('stays focused on installation and first-run provider setup', () => {
    expect(installPrompt).toContain('Install the latest stable Remis')
    expect(installPrompt).toContain('read the official Remis Agent Skill')
    expect(installPrompt).toContain('verify that its health endpoint is ready')
    expect(installPrompt).toContain('Remis Settings > API Settings')
    expect(installPrompt).toContain('If I do not know what an API key is, offer to explain it')
    expect(installPrompt).toContain('Never ask me to paste the key into chat')
    expect(installPrompt).not.toContain('Before every workflow')
    expect(installPrompt).not.toContain('explicit approval')
  })

  it('copies the complete prompt through the browser clipboard contract', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined)

    await copyText(installPrompt, { writeText })

    expect(writeText).toHaveBeenCalledOnce()
    expect(writeText).toHaveBeenCalledWith(installPrompt)
  })
})
