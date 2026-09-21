# Release Notes Archive

This directory contains published and historical Project Remis release notes.

- Keep release notes out of the repository root.
- Name new files as `RELEASE_NOTES_vX.Y.Z.md`.
- Keep the current unreleased development record in
  `docs/zh/developer/release-vX.Y.Z.md` (and its maintained language
  counterparts), not in this archive. Promote a release record here only as
  an explicit post-release documentation step.

## Required structure

Each language section starts with `Highlights` / `主要更新`. This is a short,
nontechnical summary for people who use Remis rather than develop it. Include
only changes they are likely to care about:

- an important new capability;
- a major change to an existing workflow;
- a major UI, UX, or interaction change;
- a major change to how Remis is used; or
- a change that may affect an existing project or require user action.

Do not put refactors, filenames, internal architecture, issue numbers, test
commands, parser behavior, or security implementation details in Highlights.
Translate implementation details into their user-visible result when that
result is important. For example, say that the Workshop preview now accurately
reproduces links, lists, and separators instead of describing the BBCode parser.

Place implementation information below Highlights under
`Engineering quality and reliability` / `工程质量与可靠性`. Compatibility,
known boundaries, validation evidence, and installer details may use their own
sections after that. English and Chinese sections must remain equivalent in
meaning, but should read naturally in each language.

## Release metadata gate

Every release must update `releaseDate` in
`scripts/react-ui/package.json`. The Settings > Version Info > Last Updated
field is injected from this value. The current release record under
`docs/zh/developer/release-vX.Y.Z.md` must contain the same release date; a
published archived note uses the same date in its `Released on YYYY-MM-DD.`
line. Run
`python -m pytest -q tests/test_release_metadata.py` before packaging; the gate
checks version synchronization, the current release-record date, and the
Version Info binding.
