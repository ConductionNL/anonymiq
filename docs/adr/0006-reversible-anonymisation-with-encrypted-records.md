# 6. Anonymisation is reversible through encrypted records

- Status: Accepted

## Context

The service replaces personal data with placeholders, and authorised users must be able to get the original back. The original text must not be readable by anyone who only holds the anonymised document.

## Decision

For documents, the findings are applied to a copy of the PDF, and the mapping from placeholder to original is stored encrypted so it can be reversed. The key comes from `CRYPTO_KEY`. The de-anonymise route takes an anonymised PDF and returns it with the original text restored.

## Consequences

- `CRYPTO_KEY` must be set in production; the code logs a warning and falls back to an insecure default when it is not (`src/api/documents/settings.py`).
- A record that does not decrypt with the configured key, or cannot be placed back, makes the restore fail with 422 instead of returning a partly restored document.
- Losing the key makes earlier anonymisations irreversible.

## Source

`ARCHITECTURE.md` (opening paragraph and "How a request flows", step 3); `README.md`, Helm configuration (`cryptoKey`).
