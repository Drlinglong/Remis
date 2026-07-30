export async function openExternalUrl(url) {
  if (!/^https?:\/\//i.test(url)) {
    throw new Error('Only HTTP(S) external links are supported.');
  }

  if (globalThis.__TAURI_INTERNALS__) {
    const { open } = await import('@tauri-apps/plugin-shell');
    await open(url);
    return true;
  }

  return Boolean(globalThis.window?.open(url, '_blank', 'noopener,noreferrer'));
}
