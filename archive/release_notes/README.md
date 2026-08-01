# Release Notes Archive

This directory is the canonical home for Project Remis release notes.

- Keep release notes out of the repository root.
- Name new files as `RELEASE_NOTES_vX.Y.Z.md`.
- Draft the next patch note here while changes land, instead of reconstructing the release from memory at packaging time.

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
field is injected from this value. The current release note must contain the
same date as `Released on YYYY-MM-DD.`. Run
`python -m pytest -q tests/test_release_metadata.py` before packaging; the gate
checks version synchronization, the release-note date, and the Version Info
binding.
