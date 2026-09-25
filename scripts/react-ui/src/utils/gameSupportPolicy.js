const NON_PARADOX_WORKFLOW_GAMES = new Set([
  'project_zomboid',
  'rimworld',
  'surviving_mars',
]);

const STRUCTURED_GAME_IDS = new Set(['project_zomboid', 'rimworld']);

export function allowsParadoxDeployment(gameId) {
  return !NON_PARADOX_WORKFLOW_GAMES.has(String(gameId || '').trim().toLowerCase());
}

export function hasStructuredGameSupport(gameId) {
  const normalized = String(gameId || '').trim().toLowerCase();
  return STRUCTURED_GAME_IDS.has(normalized) || normalized === 'surviving_mars';
}
