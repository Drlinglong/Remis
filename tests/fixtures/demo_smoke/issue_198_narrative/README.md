# Issue #198 narrative smoke fixture

This is a bounded Stellaris source fixture for context, event grouping, recurring terminology, branch facts, and future incremental evidence retraction checks. It follows the release demos' recurring mascot Remis into a new science-fiction story; it does not copy their scenes or prose.

The existing release demos establish Remis as a recurring troublemaker and reformer: in EU5 she is a blunt Roman memory who repairs a bankrupt empire, in Victoria 3 she is a displaced Roman girl whose administrative talent turns into a bid for Constantinople, and in Stellaris she becomes an authoritarian architect of Pax Remisia. They are intentionally small: the Stellaris release demo has three short localization files, while the EU5 and Victoria 3 demos each have one source file. `demo_agent_workshop` is designed around deliberately broken repair cases. The older incremental fixture is useful for a small file-level delta (`35` entries, `6` new, `2` changed, `1` deleted), but it does not keep one narrative chain across independent files or branches. This second authoring pass expands the first structural draft from 41 to 84 entries across seven narrative batches, with scenes and consequences rather than a noun checklist. The fixture still stays outside the release bundle.

## Story synopsis

Remis arrives at the failing Meridian Gate carrying a red ledger chained to her wrist. She bypasses a dead regulator with its clasp, makes a joke about state debts, and forces the gate to reveal forty-eight life signs. The Cartographers' Guild calls her the Red Archivist; the Watch of Quiet Stars calls her the Ledger-Breaker. When the gate receives an impossible signal from Kestrel Reach, Remis identifies an older project hidden inside it: the Accord of Echoes, a memory-routing network built to evacuate people, not conquer them.

The Meridian Council must choose between the Concord reading (the signal carries a genuine refugee roster and the Mercy Protocol should open the gate) and the Warden reading (the signal carries stolen clearance signatures and the gate must be sealed). The branches then have different consequences: one produces a living convoy and an incomplete roster, while the other produces a sealed gate and compromised patrol logs. Remis reforms the archive by making staff sort names by hand, then refuses both final verdicts. The Echo Lattice technology file, council file, resolution, aftershock, and finale deliberately call back to the same people, places, organizations, and project terms.

Intentional consistency traps are: `Remis` / `the Red Archivist` / `the Ledger-Breaker` aliases; `Meridian Gate` versus `Kestrel Reach` as separate places; `Accord of Echoes`, `Mercy Protocol`, `Echo Lattice`, and `Meridian Seal` as distinct concepts; the two incompatible Concord/Warden claims about the same signal; the early “state debts” joke returning as a literal roster of people lost by the system; Stellaris color tags, scopes, escaped dialogue quotes, and `\n\n` paragraph breaks; and event grouping across unrelated key prefixes and files. The manifest explicitly tests the long-distance Red Ledger and Ledger-Breaker callbacks.

## Layout

- `source_mod/` is the baseline source mod.
- `source_mod_modified_deleted/` changes five source entries and removes the technology file. It is a complete future incremental input, not a patch file.
- `manifest.json` is the machine-readable contract for counts, event-chain links, terminology, branch facts, provenance, and the expected variant delta.
- `descriptor.mod` identifies the fixture as a Stellaris mod without requiring a real Workshop ID.

All source text is UTF-8, uses Stellaris `l_english:` localization syntax, and stays under a small distribution footprint. The fixture deliberately has no translations and no provider configuration.

## Usage

Mock smoke should run the deterministic integrity test from the repository root:

```powershell
python -m pytest -q tests/test_issue_198_narrative_fixture.py
```

For an optional live smoke, import `source_mod/` as a Stellaris project in Remis, choose `stellaris`, source language `en`, and a target language such as `zh-CN`. Run `/api/agent/preflight` first, then request a dry-run or translation only with explicit approval. Use the existing local DeepSeek configuration through Remis Settings; never put a key in this fixture, command line, logs, or chat. The live smoke is advisory and should check event grouping, repeated term consistency, preserved Stellaris tags/scopes, and branch-specific context manually. It must not be used as the deterministic fixture gate.

The modified/deleted directory is for a later incremental evidence-retraction smoke: compare it against the baseline, verify changed entries are reprocessed, and verify evidence tied only to the removed technology file can be retracted. No live model call is needed to validate that delta.
