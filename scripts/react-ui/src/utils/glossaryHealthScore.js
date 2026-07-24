const PENALTY_RULES = {
  error: { points: 8 },
  warning: { points: 3 },
  info: { points: 1 },
};

const cappedIssueCount = (issue) => {
  const count = Number(issue?.count);
  if (!Number.isFinite(count) || count <= 0) return 0;
  return Math.min(Math.floor(count), 10);
};

export const getGlossaryHealthPenaltyBreakdown = (issues = []) => {
  const breakdown = {
    error: { findings: 0, penalty: 0 },
    warning: { findings: 0, penalty: 0 },
    info: { findings: 0, penalty: 0 },
  };

  for (const issue of Array.isArray(issues) ? issues : []) {
    const category = issue?.severity === 'error'
      ? 'error'
      : issue?.severity === 'warning'
        ? 'warning'
        : (issue?.severity === 'info' ? 'info' : null);
    if (!category) continue;

    const findings = cappedIssueCount(issue);
    breakdown[category].findings += findings;
    breakdown[category].penalty += findings * PENALTY_RULES[category].points;
  }

  return {
    ...breakdown,
    totalPenalty: breakdown.error.penalty + breakdown.warning.penalty + breakdown.info.penalty,
  };
};
