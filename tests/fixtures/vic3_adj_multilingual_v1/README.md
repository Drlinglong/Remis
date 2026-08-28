# Victoria 3 multilingual `*_ADJ` fixture v1

This fixture freezes a small, aligned slice of the official Victoria 3
localization corpus for prompt and recipe A/B testing. It is separate from
`translation_quality_benchmark_v1.json` and must not be treated as an
interchangeable revision of that benchmark.

## Coverage

- Source: official English Victoria 3 localization.
- Targets: Simplified Chinese, Japanese, Korean, German, French, Spanish,
  Brazilian Portuguese, Polish, Russian, and Turkish.
- Ten aligned cases per target language: five `*_ADJ` definitions and five
  values that reference one or more `*_ADJ` variables.
- Total: 10 source cases and 100 official target examples.

The selected definition keys are `CHI_ADJ`, `EGY_ADJ`, `USA_ADJ`, `GBR_ADJ`,
and `POR_ADJ`. The reference cases cover a single adjective slot, particles or
suffixes, an official hard-coded rewrite, a hyphenated pair, and two dynamic
adjective slots.

## Intended A/B protocol

The fixture itself is treatment-neutral. The three labels below describe the
original fixture proposal, not a universal arm numbering scheme.

Run the same model and decoding configuration against the same case ordering.
Change only the prompt treatment:

1. **A — value only:** send `source.value` without `source.key`.
2. **B — raw key + value:** send `source.key` and `source.value`.
3. **C — semantic key hint + value:** send the key plus the candidate
   target-language contract being evaluated.

Score definition cases separately from reference cases. Exact agreement with
an official definition is a useful deterministic signal. For full reference
strings, preserve every Paradox token and use the official target as a gold
reference, but do not assume that string equality is the only linguistically
valid translation.

Do not change the fixture between A/B arms. Record the fixture fingerprint,
model/runtime, prompt hash, decoding settings, output, latency, token usage,
cache usage, and any repair pass.

`evaluate_key_context_factorial.py` uses the broader requested 2x2 protocol:
A=value only, B=target-language policy only, C=raw key, and D=raw key plus
policy. Its exploratory E arm supplies a compact semantic contract without the
full language policy. For definition-only A/raw/semantic comparisons, use runner arms A/C/E
and always rely on the emitted `arms` metadata rather than comparing letters
across protocols. Definition and reference results must remain separate.

## Regeneration

The generator requires a local official Victoria 3 installation and performs
no model calls:

```powershell
python scripts/developer_tools/build_vic3_adj_multilingual_fixture.py `
  --corpus-root "I:\SteamLibrary\steamapps\common\Victoria 3\game\localization"
```

Every selected key must occur exactly once in every language. The generated
JSON records relative source paths, line numbers, SHA-256 hashes of the source
files, and a fingerprint of the complete selected snapshot.
