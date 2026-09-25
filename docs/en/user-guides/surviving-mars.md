# Surviving Mars: Relaunched localization

Remis supports the existing Surviving Mars: Relaunched `ModItemLocTable` CSV initial-translation, incremental-update, and proofreading workflows. It can also generate an independent translation-only Mod from an existing project translation output. When creating a project, select “Surviving Mars / Relaunched.”

The desktop chat assistant can guide an initial translation and show its plan for your approval. Use the project UI or Remis Agent API with `workflow: "incremental"` for incremental updates. The chat assistant can explain translation-Mod export but does not call the export API. Codex users can follow the repository [Remis Agent Skill](../../../.agents/skills/remis-agent/SKILL.md) and [API reference](../../../.agents/skills/remis-agent/references/api-workflow.md). Use the live game-support and scan results for the current capability boundary.

Remis discovers `.csv` files with this exact five-column header:

```text
ID,Text,Translation,VoiceActor,Context
```

An official Mod Editor export may begin with the exact line `sep=,` before the
header; Remis recognizes and preserves it. Editable Mods under
`%APPDATA%/Surviving Mars Relaunched/Mods/<Mod name>` can be imported directly;
other application directories in AppData remain protected.

`ID` must contain ASCII decimal digits and is preserved as an exact string, including leading zeros. `Text` is the source value, and only `Translation` is writable. `VoiceActor` and `Context` remain unchanged. Quoted, comma-containing, multiline, and tagged fields are parsed with a standards-compliant CSV reader; unrelated CSV files are ignored.

Surviving Mars tags such as `<em>`, `<resource(res)>`, and `<image UI/... 2000>` must remain exactly identical in the translation, including spelling, parameters, case, and multiplicity. Text between tags may be translated; tag names and parameters inside angle brackets must not be translated or rewritten. The final validation reports missing or unexpected tags for human review.

Output keeps the CSV's source-relative path and filename. It uses UTF-8 and writes only the third column. It does not create Paradox language folders or rename the CSV. In the original Mod, `ModItem.Filename` points at the table and `Language` controls when it loads. For a language not supported by the game, the official ModTools guidance is to set `Language` to English in the original ModItem and run the game in English. This is a manual game-side setting, not Agent `custom_lang_config`. Remis leaves the original Mod untouched; an independent translation package creates its own registration files and `ModItemLocTable`.

## Generate an independent translation Mod from existing translations

Paragraph separators must be real line breaks inside CSV cells, not the literal
backslash and letter n (`\n`). Remis restores newlines according to the Mars
format and checks paragraph separator runs. Lost breaks or newly introduced
literal newline escapes block package export. Intentional literal sequences in
the source are preserved instead of being globally decoded.

The exporter wraps an already-generated target-language CSV output. It does not translate additional content or copy scripts, images, or other assets from the original Mod. Use the project's local export action when available, or follow the API reference:

1. Call preflight before each new workflow, then read `GET /api/agent/projects/{project_id}/translation-package/options`. Choose an existing output from `translation_outputs` and a target from `languages`; `game_language` is the token for the generated ModItem.
2. Create a preview with `POST /api/agent/projects/{project_id}/translation-package/plan`. Review the project, selected translations, target language, package contents, and risk fields. The plan makes no paid API call, does not overwrite an existing package, and does not write into the game directory.
3. Show the concrete plan and obtain explicit approval. Then call `POST /api/agent/projects/{project_id}/translation-package` with its `plan_id` and `approved: true`. The result provides a local package path, file list, and manual-install instructions; `runtime_verified` remains `false`.

CSV files retain their selected output-relative directories and names. The package's `metadata.loctables` and `items.lua` refer to them through the SDK virtual resource path `Mod/<generated package ID>/Localization/...`, rather than a bare filename. The package creates its own `metadata.lua` and `items.lua` containing a `ModItemLocTable`; it declares the original Mod as a required `ModDependency`, with major/minor version defaults kept at `0`. To install it, copy the entire returned package folder into `%APPDATA%/Surviving Mars Relaunched/Mods`, enable both the original Mod and generated translation Mod, then select the target language in game. The package copies no original assets, does not modify the original Mod, and contains no hard-coded absolute paths. Remis language code `zh-CN` maps to the SDK token `Schinese`; always use `game_language` returned by options, not the display name. If the plan's `warnings` reports that the matching language pack was not present in the local installation, a recognized token does not prove that the installed game includes the language pack.

The local Relaunched SDK documents this contract in `ModItemLocTable.md.html`, while `Mod.lua`'s `UpdateLocTables` and `ModsLoadLocTables` show table registration and loading by Mod order. `ModItem.lua` provides the language enum, and `localization.lua` maps `zh-CN` to `Schinese`. SDK `ModDependency` defaults `required` to true and major/minor versions to `0`. Remis follows these local SDK contracts when generating the lightweight package, but has not verified the package in a running game.

## When the existing mod is a Workshop package

Steam Workshop and the game's `PdxMods` cache commonly contain only
`ModContent.fpk`, which is a compiled mod package. Remis cannot read that
package as a CSV source directory. Use the official Mod Editor to copy/unpack
the package into an editable `AppData/Mods/<mod name>` directory, then give
that unpacked source directory to Remis.

The editable source directory can be provided directly to Remis. If a
compressed Mod package is needed, use the official Mod Editor's Pack Mod
action to generate `ModContent.fpk`. Work on a copy rather than overwriting
the Workshop cache; Remis does not unpack, pack, or publish mods automatically.
For in-game acceptance, verify the ModItem `Filename`, `Language`, and load
order; Remis's static and dynamic scans do not verify actual game loading.

The current scope covers CSV discovery, initial translation, incremental snapshots/writeback, manual proofreading, format validation, issue export, and approval-gated local translation-Mod generation from existing CSV outputs. The package creates its own ModItem and registration files without changing the original Mod. It does not translate additional source, cover hard-coded `Untranslated(...)` strings, create game assets, handle fonts, deploy, or publish to Workshop. Dynamic support scans report recognized resource/entry counts, coverage scope, diagnostics, and `runtime_verified: false`; missing or invalid tables block a normal translation plan, while dry-run remains available to inspect diagnostics. Check the selected language, ModItem file reference, and load order in game; runtime loading has not been verified by Remis.
