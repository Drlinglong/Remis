# Project Archive: structure, publish, and review

> Open **Quality & Terminology → Project Archive** in the sidebar.
> The feature is available in Remis 3.2.0 stable and Agent Preview. Agents can
> read published archives, but cannot start archive analysis directly.

The Project Archive turns source localization into traceable project context.
It does not rewrite the source mod. Terminology candidates still require an
explicit decision in the glossary review court before they enter the project
glossary.

This is context engineering, not a longer prompt or a chat transcript. Remis
structures source knowledge, records where each result came from, publishes an
immutable version, checks that version before translation reuse, and exposes
bounded published views to the Agent.

## Choose the analysis scope

One workflow supports two scopes:

- **Terminology only** finds terminology candidates for glossary review.
- **Full archive** also produces project, entity, and event summaries, then
  publishes an immutable Context Release.

Changing from terminology-only analysis to a full archive rereads the source.
The source snapshot, analysis scope, model, and upstream run remain attached to
the published release.

## Inspect a published Context Release

The published view is read-only. It exposes:

- release identity, source snapshot, analysis scope, model, and timestamp;
- project, entity, and event summaries;
- effective values and any inherited human overrides;
- source paths, citations, coverage, and provenance on demand.

Deterministic backend rules calculate mention counts, source-entry coverage,
local-unit coverage, and event-chain coverage. The model may propose surface
forms, candidate types, and semantic names, but it does not decide the numeric
evidence or silently promote a candidate into the glossary.

## Draft without overwriting history

Choose **Start a draft from this release** to create an editable child draft.
You can adjust summaries, preferred names and aliases, entity types, event
membership, relationships, and notes. Existing human overrides are marked as
inherited.

Saving changes only updates the draft. Publishing requires another explicit
confirmation and creates a new immutable child release with its parent ID. The
previous release remains unchanged.

## Reuse context safely

Remis compares the selected release with the current source snapshot. A mismatch
marks the release as stale. Translation cannot silently treat stale context as
current: the user must explicitly choose whether to reuse the old release or
continue without it.

A selected release can supply bounded context to the translation workflow and
the Agent read API. Translation applies the readiness check; Agent endpoints
expose published context and traceability. The release ID and source snapshot
make the selection inspectable later.

## Review terminology separately

Archive analysis can identify glossary candidates, but `glossary_eligible` does
not mean approved. A term enters the project glossary only after an explicit
human decision in the review court.

For the Chinese interface and more detailed candidate-governance rules, see the
[Chinese Project Archive guide](../../zh/user-guides/mod-archive.md).
