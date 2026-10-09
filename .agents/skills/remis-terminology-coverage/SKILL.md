---
name: remis-terminology-coverage
description: Disabled developer experiment. Load only after an explicit experimental workflow request and verification that live terminology_coverage capabilities report supported=true. Never propose or enable this workflow for ordinary users.
---

# Remis Terminology Coverage

This workflow is disabled by default. Check `/api/agent/capabilities` first and stop
when `supported` is false. Do not enable environment flags automatically. The developer
must explicitly opt in and restart Remis; paid operations still require authorization.
See [experimental API policy](../../../docs/zh/developer/advanced-agent-policy.md).

Read [the quality API guide](../../../docs/zh/developer/localization-quality-agent-api.md)
for payloads and the existing-project-archive bridge. Use the existing Remis glossary as the editable
source; coverage reports and term releases are frozen evidence, not a second editable dictionary.

- Call `/api/agent/preflight` and capabilities on the active localhost backend.
- Find existing scans using GET `/api/agent/terminology-coverage/scans?project_id=PROJECT_ID&limit=50&offset=0`.
  Reuse a matching frozen report before starting another scan. Keep the project, scan and storage
  identities in a handoff record so a different agent can retrieve the same evidence.
- Select registered project source file IDs, glossary ID and content locale. For Mars, source names
  come from Context fields; a five-column table may carry official reference text in Translation.
  Only matching source ID plus English can supply a reference; missing or changed references stay visible.
- Create `/api/agent/terminology-coverage/scans`, then read the persisted report. Look at repeated names,
  building/technology/resource/trait/UI fields, uncovered spellings, observed inflections and examples.
  Lexical coverage is not concept correctness; ordinary words and unrelated same-spelling concepts
  do not automatically deserve a glossary entry.
- Same-object names can include upgrades and alternative buildings. Only a verified inflection is
  a strong alias candidate; do not merge every name attached to an object.
- Import selected uncovered candidates through the scan's `/candidates` endpoint with existing scope
  authorization. This reuses the project archive's candidate store and preserves confirmed decisions.
  Candidate import is not target-language approval and does not modify the glossary.
- Review translations/senses/aliases through the existing glossary Agent APIs. Keep model suggestions
  distinguishable from human confirmation; preserve confidence, object identity, source IDs and evidence.
  Freeze a new dictionary version after actual changes. Never overwrite a dictionary snapshot used by
  a previous test or pending Batch.

The current deterministic scan finds structured names and observed variants; it does not establish
complete terminology extraction for every game format. Report that boundary and keep ambiguous cases
pending. Model translation or audit requires its separately authorized provider/model scope.
