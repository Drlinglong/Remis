export const installPrompt = `Install the latest stable Remis from the official repository at https://github.com/Drlinglong/Remis, read the official Remis Agent Skill, start Remis locally, and verify that its health endpoint is ready.

After the first launch, briefly explain what an API key is used for, then guide me through configuring a model provider and API key in Remis Settings > API Settings.`

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
