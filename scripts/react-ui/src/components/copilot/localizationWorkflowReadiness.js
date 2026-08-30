function normalizeText(value) {
  return String(value || '')
    .normalize('NFKC')
    .toLocaleLowerCase()
    .replace(/[^\p{L}\p{N}]+/gu, ' ')
    .trim()
    .replace(/\s+/g, ' ');
}

function normalizeGame(value) {
  const normalized = normalizeText(value).replace(/\s+/g, '');
  if (normalized === 'victoria3') return 'vic3';
  return normalized;
}

export function getLocalizationWorkflowMissingInputs(args = {}) {
  const hasProjectReference = Boolean(args.project_id || args.project_name);
  const projectMode = args.project_mode
    || (hasProjectReference && !args.folder_path ? 'existing' : 'new');
  const targets = args.target_languages
    || args.target_lang_codes
    || (args.target_language ? [args.target_language] : []);
  const missing = [];

  if (projectMode === 'existing' && !hasProjectReference) missing.push('已有项目');
  if (projectMode === 'new' && !args.folder_path) missing.push('Mod 路径');
  if (projectMode === 'new' && !args.game_id) missing.push('游戏');
  if (projectMode === 'new' && !args.source_language) missing.push('源语言');
  if (!Array.isArray(targets) || targets.filter(Boolean).length === 0) missing.push('目标语言');
  return missing;
}

export function resolveCopilotProject(projects, args = {}) {
  const candidates = (projects || []).filter(Boolean);
  if (args.project_id) {
    const matches = candidates.filter((project) => String(project.project_id) === String(args.project_id));
    return { project: matches.length === 1 ? matches[0] : null, matchCount: matches.length };
  }

  const requestedName = normalizeText(args.project_name);
  if (!requestedName) return { project: null, matchCount: 0 };
  const gameHint = normalizeGame(args.game_id);
  const gameCandidates = gameHint
    ? candidates.filter((project) => normalizeGame(project.game_id) === gameHint)
    : candidates;
  const exact = gameCandidates.filter((project) => normalizeText(project.name) === requestedName);
  if (exact.length === 1) return { project: exact[0], matchCount: 1 };
  if (exact.length > 1) return { project: null, matchCount: exact.length };

  // A model may omit a suffix such as the game name. Accept only a unique,
  // substantial containment match; never choose between multiple candidates.
  const partial = requestedName.length >= 8
    ? gameCandidates.filter((project) => {
      const candidateName = normalizeText(project.name);
      return candidateName.includes(requestedName) || requestedName.includes(candidateName);
    })
    : [];
  return { project: partial.length === 1 ? partial[0] : null, matchCount: partial.length };
}
