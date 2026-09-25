# Surviving Mars: Relaunched localization

Remis supports initial translation and incremental updates for Surviving Mars: Relaunched `ModItemLocTable` CSVs. It can also prepare a project from an original Workshop package and combine completed language outputs in one local delivery. When creating a project, select “Surviving Mars / Relaunched.” The installation paths in this guide apply to Relaunched; do not assume they apply to the legacy game.

The desktop chat assistant can explain the steps, guide an initial translation, and show a plan for your approval; a chat response does not perform preparation, translation, or export. Use the project UI or Remis Agent API with `workflow: "incremental"` for incremental updates. This game's project UI does not yet provide a dedicated visual proofreading workspace. Format validation is available, and the Agent API can read a translation and save targeted edits after approval and revision checks. Built-in Agent/Codex users can follow the repository [Remis Agent Skill](../../../.agents/skills/remis-agent/SKILL.md), [API reference](../../../.agents/skills/remis-agent/references/api-workflow.md), and this guide. Use the live game-support and scan results for the current capability boundary.

## Start from a Workshop Mod

1. Subscribe to and download the original author's Mod. Select its local `ModContent.fpk`, normally under the chosen Steam library's `steamapps/workshop/content/<game AppID>/<original Workshop ID>/`. Do not use a web URL or your translated copy as the source.
2. Open **Project Management → Create Project**, enter a name and select Surviving Mars. Browse to the FPK in the preparation window. Remis extracts it into isolated storage; you do not need to export CSV or Lua manually in the game editor first.
3. Inspect candidates and choose text-only preparation or a complete internationalized copy. Prefer the complete copy for hard-coded text. Review and approve preparation, then use the returned project. Continue an existing prepared project rather than creating duplicates.
4. Run **Initial Translation** for this project with English source, the requested target languages and provider/model. Approve the translation plan. Source updates use the incremental workflow; adding French or German does not require separate Mods.
5. In **Internationalized Mod Delivery**, select all completed language outputs together, such as `zh-CN-prepared`, `fr-prepared`, and `de-prepared`. Preview and approve **one multilingual Mod package**. Keep language work files for future maintenance; install the returned package folder.
6. Place its contents in `%APPDATA%/Surviving Mars Relaunched/Mods/<output_mod_id>/`, with `metadata.lua` directly inside. Enable a text-only package alongside the original. Enable a complete copy on its own, disabling the original and older patches. Select the language in game and restart to check it.
7. To publish, use the **game's own Mod Editor for manual packing/upload**. After first publishing a complete copy, bind your own returned Workshop ID in its Remis project. Later exports retain that ID for manual updates. Remis does not automatically upload.

For Agent assistance, the built-in chat guides the preparation UI, then can plan initial translation for the created project. Codex uses the preparation, translation and export endpoints documented in the Skill/API reference. A chat explanation does not itself perform installation or editor publishing.

## Supported files

Remis discovers `.csv` files with this exact five-column header:

The current Surviving Mars workflow offers exactly nine target languages:
Simplified Chinese (`zh-CN`), English (`en`), French (`fr`), German (`de`),
Spanish (Spain, `es`), Polish (`pl`), Portuguese (Brazil, `pt-BR`), Russian
(`ru`), and Turkish (`tr`). Other games retain their own language catalogs.

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

## Import and localize a compiled Workshop Mod

Support inspection also reports direct Lua `Untranslated(...)` calls under
`hardcoded_lua`, separately from translatable CSV entries. The ordinary folder
support scan only discovers candidates; the isolated FPK workflow below can
apply explicitly reviewed, supported literal rewrites when building a complete
source copy. Dynamic expressions, aliases, other plain Lua strings, and
incomplete scans remain outside that rewrite boundary and require review. The
intended multilingual workflow uses stable IDs and English fallback in code,
with each language in CSV; see the
[workflow design](../../zh/developer/mars-lua-localization-workflow.md).

Steam Workshop and the game's `PdxMods` cache commonly contain only
`ModContent.fpk`. In Create Project, select “Surviving Mars / Relaunched,” then
choose the archive in the separate FPK preparation window. Remis explains the
available preparation modes before inspecting the archive and text inventory.
Supported FLPK v1 content is read into an isolated run; the original FPK and
Workshop/PdxMods files remain untouched. No Editor-exported CSV or separate
Mod Editor unpack step is required.

After inspection, choose how to prepare the project:

- **Text only (`text_only`)** creates translation CSVs without changing Lua.
  The original Mod remains a required dependency. Choose this when preserving
  the original Mod identity/save association matters or when you do not want a
  replacement Mod. Text still awaiting review is excluded from the translation
  CSV and is not rewritten at delivery.
- **Complete internationalized copy (`source_copy`, the default and
  recommended option)** prepares all assets and converts reviewed hard-coded
  text to stable-ID localization calls; translations remain in per-language
  CSVs. Prefer it when hard-coded text must be covered. At delivery the copy
  gets a new Mod ID and a `[Remis i18n]` title prefix. Disable the original Mod
  and older translation patches before enabling the copy.

Approve the reviewed candidates before preparation. Unknown aliases, complex
dynamic expressions, internal option values, and scan blind spots remain for
human review; candidate counts do not prove complete coverage. Keep the
preparation run ID for future Mod updates and stable ID matching. Continue with
the usual English-source CSV translation workflow, then select target-language
outputs in the project's internationalized Mod delivery panel and review the
preview before approving local output creation.

Delivery offers a complete source copy with every original asset, or a
translation-only package containing language CSVs that depends on the original
Mod. Runtime overlays are an advanced API configuration, not a normal UI
choice. Neither delivery mode installs files, overwrites an existing package,
or publishes to Steam. Install the returned folder manually and check upgrades,
events, technologies, settings, load order, and save behavior in game; Remis
reports runtime verification as false.

In one multilingual export, select all completed language outputs, such as `zh-CN`, `fr`, and `de`, to include them in the same Mod. Prepared outputs such as `fr-prepared` and `de-prepared` are durable translation working files; they are not `installedMods` and should not be discarded as temporary folders. Publish the complete source copy manually with the game's own Mod Editor. After the first publish, bind your own Workshop item ID in Project Management under Internationalized Mod Delivery. Later exports carry that ID, and uploading through Mod Editor updates the same item. Do not bind the original author's ID; Remis never uploads automatically. The panel currently does not offer changing or clearing a saved binding.

**Delivery modes:**

| Mode | Contents | Enable in game |
|---|---|---|
| `text_only` | Completed language CSVs; depends on the original Mod | Keep the original Mod enabled; disable older translation patches to avoid conflicts |
| `source_copy` | All original assets, supported and reviewed source rewrites, selected language CSVs, and a new output Mod ID | Disable the original Mod and older translation patches; enable only the complete copy |

Copy the entire reviewed export folder to `%APPDATA%/Surviving Mars Relaunched/Mods/<output_mod_id>`. Ensure `metadata.lua` sits directly inside `<output_mod_id>` and is not one directory deeper. Enable the required Mod in the launcher, then check text and save behavior in game. Reported Chinese, French, and German examples worked, and manual upload updated the same Workshop item; this does not establish exhaustive text or save compatibility.

For Agent API users, a source copy can have a project-scoped local Workshop ID
binding at `GET` and `PUT /api/agent/projects/{project_id}/mars-pipeline/publication`.
Use the GET response's `revision` in the PUT request. This records the ID for
the source copy only; Remis does not verify ownership, upload files, or publish
to Workshop. Check that the ID belongs to your own published copy. The binding
cannot be silently replaced or cleared through this API.

In Project Management, open the project and select the complete source-copy
mode under Internationalized Mod Delivery. Save your published copy's Workshop
item ID there. This is a persistent project setting: later exports include that
ID, while existing exported folders remain unchanged. The panel and export
preview show the target link. Unbound projects show a create-new warning;
unavailable or corrupt state must not be treated as unbound. A binding change
after preview invalidates that preview. Changing or clearing a saved binding is
not currently offered. Publishing remains a manual Game Editor operation.

On 2026-09-25, the user reported successful deployment and in-game use of the
Chinese Exotic Minerals Expanded source copy. French and German were subsequently
added and checked statically. The user then supplied an in-game French
Applications exotiques screenshot confirming this panel's paragraph breaks,
emphasis colors and accented characters. The user subsequently reported that
German also displayed correctly and that manual publishing updated the same
Workshop item rather than creating another one. These reports do not establish
exhaustive UI or save compatibility coverage. See the
[acceptance record](../../zh/developer/mars-pipeline-acceptance-2026-09-25.md)
for archive scope, checksums, delivery evidence, and remaining validation.

The normal CSV workflow supports initial translation, incremental snapshots/writeback, format validation, and issue export. This new FPK project flow does not yet have a dedicated visual proofreading workspace; targeted Agent reads and saves do not imply that a proofreading UI is available. If there are no usable CSVs, prepare the FPK project before starting the normal translation workflow. Export does not handle fonts, installation, or Workshop publishing. Dynamic scans and delivery previews report `runtime_verified: false`; check language, ModItem references, load order, text coverage, and save behavior in game.
