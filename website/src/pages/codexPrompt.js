export const installPrompt = `Install the latest stable Remis from the official repository at https://github.com/Drlinglong/Remis, read the official Remis Agent Skill, start Remis locally, and verify that its health endpoint is ready.

After the first launch, tell me that Remis needs a configured model provider before it can translate. Guide me to Remis Settings > API Settings to choose a provider and enter its API key inside Remis. If I do not know what an API key is, offer to explain it. Never ask me to paste the key into chat.

Once setup is complete, connect Remis to the mod in this workspace and show me what I can do next.`

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
