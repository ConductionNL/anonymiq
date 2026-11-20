# Architecture decision records

Decisions this repository has already made and written down, collected in one place. Each record cites the file it was taken from; that file stays the source.

| ADR | Title | Status |
|---|---|---|
| [0001](0001-group-code-by-functional-component.md) | Group the code by functional component, each with one public module | Accepted |
| [0002](0002-confine-pymupdf-to-one-module.md) | Use PyMuPDF under AGPL-3.0 and confine it to one module | Accepted |
| [0003](0003-swappable-nlp-engine-and-pattern-recognisers.md) | A swappable NLP engine next to rule-based pattern recognisers | Accepted |
| [0004](0004-http-basic-auth-that-fails-closed.md) | HTTP Basic authentication on every data route, failing closed | Accepted |
| [0005](0005-cors-off-by-default.md) | CORS off by default, explicit origins only | Accepted |
| [0006](0006-reversible-anonymisation-with-encrypted-records.md) | Anonymisation is reversible through encrypted records | Accepted |
| [0007](0007-keep-the-pre-rename-database-filename.md) | Keep the pre-rename database filename and hostnames | Accepted |
| [0008](0008-anonymiq-owns-the-image-object-detector.md) | anonymiq owns the image object detector; OpenRegister owns the seam | Accepted, not built yet |

## Adding a record

Copy the shape of an existing record: title, Status, Context, Decision, Consequences and a Source line naming the file where the decision was made. Number it with the next free number. Company-wide decisions live in hydra, not here.
