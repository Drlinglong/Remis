export const installPrompt = `Install Remis from the official repository at https://github.com/Drlinglong/Remis, start its local service, read the Remis Codex Skill, verify the health endpoint, check the latest official GitHub Release, and guide me through localizing the mod in this workspace.

Before every workflow, check GitHub for a newer Remis Release and tell me the result. If no model provider is configured after first install, stop immediately, guide me to Remis Settings > API Settings, and offer to explain what an API key is. Keep keys inside Remis—never ask me to paste one into chat.

Keep the API on localhost. Never read, display, or transmit model API keys. Inspect the mod and show me a dry-run plan first. Preserve every game key, variable, tag, encoding rule, and folder boundary. Before any paid translation, model-backed repair, export, deployment, or overwrite, show the exact plan and wait for my explicit approval. Report progress and validation from Remis instead of guessing.`

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
