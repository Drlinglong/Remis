# Surviving Mars: Relaunched localization

Remis supports the existing Surviving Mars: Relaunched `ModItemLocTable` CSV initial-translation, incremental-update, and proofreading workflows. When creating a project, select “Surviving Mars / Relaunched.” The existing project source/target language and translation flow remains in use; Remis does not create a separate translation Mod.

The desktop chat assistant can guide an initial translation and show its plan for your approval. Use the project UI or Remis Agent API with `workflow: "incremental"` for incremental updates. Codex users can follow the repository [Remis Agent Skill](../../../.agents/skills/remis-agent/SKILL.md) and [API reference](../../../.agents/skills/remis-agent/references/api-workflow.md). Use the live game-support and scan results for the current capability boundary.

Remis discovers `.csv` files with this exact five-column header:

```text
ID,Text,Translation,VoiceActor,Context
```

`ID` must contain ASCII decimal digits and is preserved as an exact string, including leading zeros. `Text` is the source value, and only `Translation` is writable. `VoiceActor` and `Context` remain unchanged. Quoted, comma-containing, multiline, and tagged fields are parsed with a standards-compliant CSV reader; unrelated CSV files are ignored.

Surviving Mars tags such as `<em>`, `<resource(res)>`, and `<image UI/... 2000>` must remain exactly identical in the translation, including spelling, parameters, case, and multiplicity. Text between tags may be translated; tag names and parameters inside angle brackets must not be translated or rewritten. The final validation reports missing or unexpected tags for human review.

Output keeps the CSV's source-relative path and filename. It uses UTF-8 and writes only the third column. It does not create Paradox language folders or rename the CSV. The existing ModItem `Filename` property points at the table, and its `Language` property controls when it loads. For a language not supported by the game, the official ModTools guidance is to set `Language` to English in the ModItem and run the game in English. This is a manual game-side setting, not Agent `custom_lang_config`; Remis does not edit the ModItem or create one for you.

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

The current scope covers CSV discovery, initial translation, incremental snapshots/writeback, manual proofreading, format validation, and issue export. It does not create a separate translation Mod, create ModItems or Lua, edit the installed game, handle fonts, deploy, or publish to Workshop. Dynamic support scans report recognized resource/entry counts, coverage scope, diagnostics, and `runtime_verified: false`; missing or invalid tables block a normal translation plan, while dry-run remains available to inspect diagnostics. Remis does not verify runtime loading.
