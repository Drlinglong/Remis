// Older snapshots must not restore approval; manual verification can advance uncertainty to resolved.
const phases = { preview: 0, running: 1, succeeded: 2, failed: 2, unknown: 2,
  legal_agreement_required: 2, resolved: 3 };

export function latestPublicationRecord(previous, incoming) {
  if (!incoming) return previous;
  if (!previous || previous.plan_id !== incoming.plan_id) return incoming;
  return phases[incoming.status] < phases[previous.status] ? previous : incoming;
}

export function mergePublicationHistory(previous, incoming) {
  const known = new Map(previous.map((record) => [record.plan_id, record]));
  return incoming.map((record) => latestPublicationRecord(known.get(record.plan_id), record));
}
