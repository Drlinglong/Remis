---
name: remis-chinese-conversion
description: Convert existing Chinese text between simplified/traditional forms or regional vocabulary through Remis and zhconvert. Use for deterministic Chinese conversion, Taiwan/Hong Kong usage, or literal replacement rules; this is not English translation or model proofreading.
---

# Remis Chinese Conversion

Read [the API contract](../../../docs/zh/developer/chinese-conversion-agent-api.md).

- Preflight the active localhost Remis and check chinese_conversion capability; the formal release may lack this development feature.
- Read service-info for supported modes/modules and attribution. Public calls currently need no key; do not describe that as permanent unlimited free licensing. Preserve the service notice and link.
- Use already supplied or registered Chinese text. Bind IDs before conversion; never send an entire CSV container or source tree for uncontrolled replacement.
- Preserve the user's selected mode. Traditional is character conversion; Taiwan/Hongkong include regional vocabulary. Neither accepts complex natural-language translation instructions.
- Use only explicitly chosen literal rules. Do not automatically impose a retranslation glossary when the user chose official/common legacy names.
- Call /convert with existing conversion authorization, approved=true and a stable business key. Keep requests within 100 entries/200,000 characters. No LLM calls are made.
- Save job IDs and read report/artifacts. Count parser failures, missing/empty results and token/newline errors separately. valid only describes recognized structural checks, not language certification.
- After a disconnect or restart, list old jobs before submitting again. The same key reads retained results; failed/unknown calls are not silently retried. This service does not have a remotely retrievable Batch ID.
- Results are candidates; apply/export/install/Steam publication require their existing managed workflows and corresponding user scope.

When preparing a hybrid community patch, reuse historical text only after matching exact ID plus English and checking structure. Convert official Chinese for the remaining rows. English without an existing Chinese translation needs a separately authorized translation model, not a conversion fallback.

For an independent Mars base-game patch, use [the governed delivery API](../../../docs/zh/developer/mars-base-patch-agent-api.md). It checks every candidate against historical CSV or retained Remis conversion/native artifacts, freezes a preview, then exports an editable Mod with no source-Mod dependency. Do not use bulk proofreading saves to fabricate a translation job. Packaging approval does not authorize Steam upload. Retain the plan ID, local output and hashes; stop on any provenance/dynamic-token error. The exporter permits recorded localized presentation differences only when the selected origin remains intact. Runtime testing remains separate.
