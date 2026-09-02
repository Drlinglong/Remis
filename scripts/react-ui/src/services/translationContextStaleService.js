export const STALE_CONTEXT_CODE = 'context_release_stale_choice_required';
export const STALE_USE_OLD_ARCHIVE = 'use_old_archive';
export const STALE_DISABLE_ARCHIVE = 'disable_archive';

export function getStaleContextDetail(error) {
  const detail = error?.response?.data?.detail;
  return detail?.code === STALE_CONTEXT_CODE ? detail : null;
}

export function buildStaleAcknowledgement(detail, choice) {
  const archive = detail?.context_readiness?.archive || {};
  const releaseId = archive.release_id;
  const sourceSnapshotHash = archive.current_source_snapshot_hash;
  if (!releaseId || !sourceSnapshotHash) return null;
  return {
    choice,
    context_release_id: releaseId,
    source_snapshot_hash: sourceSnapshotHash,
  };
}

export function addStaleContextChoice(payload, detail, choice) {
  const acknowledgement = buildStaleAcknowledgement(detail, choice);
  if (!acknowledgement) return null;
  return {
    ...payload,
    stale_choice: choice,
    stale_acknowledgement: acknowledgement,
  };
}
