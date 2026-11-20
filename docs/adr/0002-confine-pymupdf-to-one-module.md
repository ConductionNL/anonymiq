# 2. Use PyMuPDF under AGPL-3.0 and confine it to one module

- Status: Accepted (2026-10-29)

## Context

PDF anonymisation must remove text from the content stream, not draw a box over it: text left recoverable under a black box is exactly the failure this service exists to prevent. PyMuPDF (`pymupdf`) does this with `add_redact_annot` and `apply_redactions`, but Artifex licenses it under AGPL-3.0 or a commercial licence. No library with a permissive licence redacts content streams: `pypdfium2` reads text with positions but cannot redact, `pypdf` could rewrite content streams but safe text removal would be ours to build and prove, and `pdfplumber` and `pdfminer.six` only extract.

## Decision

Conduction accepts the dependency and uses PyMuPDF under AGPL-3.0. Production code imports `pymupdf` in exactly one module, `src/api/documents/pdf_xmp.py`. Every other part of the service reaches PDF handling through that module's functions, and the routes through `src/api/documents/service.py`. Tests may import it to build and read fixtures.

## Consequences

- New code does not import `pymupdf` anywhere else in `src/api/`; it adds a function to `pdf_xmp.py` instead.
- A later swap, to a permissive library or a commercial Artifex licence, touches one file.
- anonymiq stays EUPL-1.2, whose compatibility clause covers distribution together with AGPL-3.0 code.

## Source

`ARCHITECTURE.md`, section "PyMuPDF (AGPL-3.0) is confined to one module".
