# Victoria 3 `TAG_ADJ` composition companion fixture v1

This fixture is a deliberately small Simplified Chinese companion to the
frozen `vic3_adj_multilingual_v1` corpus. It tests the contract between a
reusable `TAG_ADJ` definition and a sentence that consumes that variable. It
does not replace or modify the multilingual fixture, and it is not a model
output set.

The policy text is intentionally abstract: it tells a prompt arm to keep
definition morphology separate from use-site Chinese syntax, but does not
teach the model which concrete phrase takes a linker. The gold values are
fixture annotations and may therefore name the expected rendered strings.

Four paired examples are included. Portuguese and Bharat/Indian references are
official. The Hungarian definition is official but its `power` reference is a
clearly marked synthetic minimal pair. The fourth case reuses the official BHT
definition with a synthetic `|l` reference so the parser and renderer also
exercise modifier preservation. The two-entry American/British lexical table
is a frozen control shared by all arms.

For each case, `rendered.expected` is produced by substituting the definition
gold into the protected variable base key while retaining the reference's
surrounding grammar and modifiers. `grammar_expectation.requires_linker`
groups the positive and negative contrast; it is an evaluation annotation, not
prompt text.
