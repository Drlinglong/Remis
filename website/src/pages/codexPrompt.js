export const installPrompt = `Clone and install Remis from https://github.com/Drlinglong/Remis, read the bundled Agent Skill, start it locally, and verify that it is ready to use.

When installation succeeds, confirm that Remis is ready. Then briefly explain that external providers such as OpenAI or Google require an API key to access their services. An API key is a private credential that may be linked to billing; enter it only in Remis Settings > API Settings, never in chat. Local providers such as LM Studio or Ollama do not need one.`

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
