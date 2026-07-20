import { describe, expect, it, vi } from 'vitest'
import { copyText, installPrompt } from './codexPrompt'

describe('Remis for Codex install prompt', () => {
  it('stays focused on installation and first-run provider setup', () => {
    expect(installPrompt).toContain('Clone the Remis development checkout')
    expect(installPrompt).toContain('source checkout rather than the packaged Windows installer')
    expect(installPrompt).toContain('read the official Remis Agent Skill')
    expect(installPrompt).toContain('verify that its health endpoint is ready')
    expect(installPrompt).toContain('Remis Settings > API Settings')
    expect(installPrompt).toContain('online provider such as OpenAI or Google Gemini')
    expect(installPrompt).toContain('keyless local provider such as LM Studio or Ollama')
    expect(installPrompt).toContain('no API key is required')
    expect(installPrompt).toContain('never ask me to paste it into chat')
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
