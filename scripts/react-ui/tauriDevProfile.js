import fs from 'fs';
import path from 'path';

const STABLE_CHANNEL = 'stable';
const AGENT_PREVIEW_CHANNEL = 'agent-preview';

// INTERVIEW STOPGAP: keep Preview WebView storage isolated and its localhost
// origin stable. Replace the localStorage session store separately before the
// Copilot is promoted to a production channel.
export function resolveTauriDevProfile(channelValue, configuredPort) {
  const channel = String(channelValue || STABLE_CHANNEL).trim().toLowerCase();
  if (channel !== STABLE_CHANNEL && channel !== AGENT_PREVIEW_CHANNEL) {
    throw new Error(`Unsupported Remis build channel: ${channel}`);
  }
  const defaultPort = channel === AGENT_PREVIEW_CHANNEL ? 5175 : 5174;
  const port = configuredPort ? Number(configuredPort) : defaultPort;
  if (!Number.isInteger(port) || port < 1 || port > 65535) {
    throw new Error(`Invalid Remis frontend port: ${configuredPort}`);
  }
  return { channel, port, isAgentPreview: channel === AGENT_PREVIEW_CHANNEL };
}

export function loadTauriDevConfig(frontendDirectory, profile) {
  const tauriDirectory = path.join(frontendDirectory, 'src-tauri');
  const readConfig = (name) => JSON.parse(
    fs.readFileSync(path.join(tauriDirectory, name), 'utf-8'),
  );
  const development = readConfig('tauri.dev.conf.json');
  const identity = profile.isAgentPreview
    ? readConfig('tauri.agent-preview.dev.conf.json')
    : {};
  return {
    ...identity,
    bundle: {
      ...identity.bundle,
      ...development.bundle,
    },
    build: {
      ...identity.build,
      ...development.build,
      devUrl: `http://127.0.0.1:${profile.port}`,
      beforeDevCommand: null,
    },
  };
}
