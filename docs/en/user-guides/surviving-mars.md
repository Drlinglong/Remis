# Surviving Mars: Relaunched localization

Remis can treat Surviving Mars: Relaunched `ModItemLocTable` CSV files as a normal localization project. When creating a project, select “Surviving Mars / Relaunched”; the existing source-language, target-language, translation, validation, and incremental-update flow remains the same.

Remis discovers `.csv` files with this exact five-column header:

```text
ID,Text,Translation,VoiceActor,Context
```

`ID` is preserved as an opaque string, `Text` is the source value, and only `Translation` is written. `VoiceActor` and `Context` remain unchanged. Quoted, comma-containing, multiline, and tagged fields are parsed with a standards-compliant CSV reader; unrelated CSV files are ignored.

Surviving Mars tags such as `<em>`, `<resource(res)>`, and `<image UI/... 2000>` must remain exactly identical in the translation, including parameters, case, and multiplicity. Visible text inside tags may be translated. The final validation reports missing or unexpected tags for human review.

Output keeps the CSV's source-relative path and filename. It uses UTF-8 and writes only the third column. It does not create Paradox language folders or rename the CSV. Point the ModItem `Filename` property at the table. The `Language` property controls when it loads; for an unsupported target language, the official ModTools guidance is to set `Language` to English and run the game in English.

## When the existing mod is a Workshop package

Steam Workshop and the game's `PdxMods` cache commonly contain only
`ModContent.fpk`, which is a compiled mod package. Remis cannot read that
package as a CSV source directory. Use the official Mod Editor to copy/unpack
the package into an editable `AppData/Mods/<mod name>` directory, then give
that unpacked source directory to Remis.

For local Mod Editor/game testing, the unpacked directory does not need to be
packed again first. Once `Game.csv`, the ModItem `Filename`, `Language`, and
load order are correct, test that directory directly. If the result is going
to Workshop or must be used as a packaged mod, use the official Mod Editor's
Pack Mod action to generate a new `ModContent.fpk`. Work on a copy rather than
overwriting the Workshop cache; Remis does not currently unpack, pack, or
publish mods automatically.

The current scope covers discovery, initial translation, incremental snapshots/writeback, manual proofreading, format validation, and issue export. It does not create ModItems or Lua, edit the installed game, handle fonts, deploy, or publish to Workshop. Test the generated table in the local game/ModTools before release.
