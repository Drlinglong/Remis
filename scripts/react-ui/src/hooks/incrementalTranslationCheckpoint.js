export const buildCheckpointStatusPayload = ({ project, sourcePath, targetLangs }) => {
  const normalizedTargetLangs = Array.isArray(targetLangs) ? targetLangs.filter(Boolean) : [];
  if (!project?.project_id || !sourcePath || normalizedTargetLangs.length === 0) {
    return null;
  }

  return {
    project_id: project.project_id,
    mod_name: sourcePath.split(/[\\/]/).pop(),
    target_lang_codes: normalizedTargetLangs,
  };
};

export const requestIncrementalCheckpointStatus = async ({
  project,
  sourcePath,
  targetLangs,
  translationService,
}) => {
  const payload = buildCheckpointStatusPayload({ project, sourcePath, targetLangs });
  if (!payload) {
    return { found: false, info: null, skipped: true };
  }

  const response = await translationService.getCheckpointStatus(payload);
  const info = response.data;
  const found = Boolean(info?.exists && info.completed_count > 0);

  return {
    found,
    info: found ? info : null,
    skipped: false,
  };
};
