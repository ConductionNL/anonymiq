# 7. Keep the pre-rename database filename and hostnames

- Status: Accepted

## Context

The service was renamed from OpenAnonymiser to anonymiq. The SQLite database file already sits on the production persistent volume under its old name, and the live DNS names are `api.openanonymiser.*`; `api.anonymiq.*` does not exist yet.

## Decision

The database filename stays `openanonymiser.db` on purpose, and the hostnames stay `api.openanonymiser.*`. The test environment variable is now `ANONYMIQ_BASE_URL`, and `OPENANONYMISER_BASE_URL` is still read so existing scripts keep working.

## Consequences

- Renaming the file would not raise an error: SQLite would create a new, empty database next to the real one and the service would start looking freshly installed. The name moves only together with a volume migration.
- The Helm chart keeps its old name, `charts/openanonymiser`.

## Source

`README.md`, sections "Kubernetes met Helm (productie)" and "Testen (pytest)"; the comment on `DATABASE_URL` in `src/api/documents/settings.py`.
