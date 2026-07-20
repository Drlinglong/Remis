export const installPrompt = `Clone the Remis development checkout from the official main branch at https://github.com/Drlinglong/Remis. For this Codex-operated setup, use the source checkout rather than the packaged Windows installer so you can read the official Remis Agent Skill bundled in the repository. Follow the development setup, start Remis locally, and verify that its health endpoint is ready.

After the first launch, ask which model provider I want to use. If I choose an online provider such as OpenAI or Google Gemini, briefly explain that its API key is a secret credential used for authentication and possible billing, then guide me to enter it inside Remis Settings > API Settings—never ask me to paste it into chat. If I choose a keyless local provider such as LM Studio or Ollama, explain that no API key is required and help me configure and test its local connection instead.`

export async function copyText(text, clipboard = globalThis.navigator?.clipboard) {
  if (clipboard?.writeText) {
    await clipboard.writeText(text)
    return
  }
  const textarea = document.createElement('textarea')
  textarea.value = text
  textarea.setAttribute('readonly', '')
  textarea.style.position = 'fixed'
  textarea.style.opacity = '0'
  document.body.appendChild(textarea)
  textarea.select()
  document.execCommand('copy')
  textarea.remove()
}
