import { describe, expect, it, vi } from 'vitest'
import { copyText, installPrompt } from './codexPrompt'

describe('Remis for Codex install prompt', () => {
  it('stays focused on installation and first-run provider setup', () => {
    expect(installPrompt).toContain('Clone and install Remis')
    expect(installPrompt).toContain('read the bundled Agent Skill')
    expect(installPrompt).toContain('verify that it is ready to use')
    expect(installPrompt).toContain('confirm that Remis is ready')
    expect(installPrompt).toContain('Remis Settings > API Settings')
    expect(installPrompt).toContain('external providers such as OpenAI or Google')
    expect(installPrompt).toContain('An API key is a private credential')
    expect(installPrompt).toContain('Local providers such as LM Studio or Ollama do not need one')
    expect(installPrompt).not.toContain('Codex-operated')
    expect(installPrompt).not.toContain('packaged Windows installer')
    expect(installPrompt).not.toContain('ask which model provider')
    expect(installPrompt.length).toBeLessThan(700)
    expect(installPrompt).not.toContain('show me what I can do next')
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
