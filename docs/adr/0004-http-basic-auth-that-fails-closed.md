# 4. HTTP Basic authentication on every data route, failing closed

- Status: Accepted

## Context

Text and documents reach this service before redaction, so every request body carries personal data. OpenRegister is the main caller and can send a username and password to an external OpenAnonymiser backend.

## Decision

All routes under `/api/v1/documents` and the text routes `/api/v1/analyze` and `/api/v1/anonymize` require HTTP Basic credentials. Without a configured password the service refuses every one of those requests with 401. Only `/api/v1/health` stays public. In Kubernetes the credentials come from a secret named in `app.auth.existingSecret`; locally and in docker-compose they are `BASIC_AUTH_USERNAME` and `BASIC_AUTH_PASSWORD`.

## Consequences

- A deployment that forgets the password is closed, not open.
- The dependency sits on the routers (`documents_router` in `src/api/document_routes.py`, `text_analysis_router` in `src/api/text_routes.py`), so a route added to them later is protected without remembering to.
- Credentials are compared in constant time (`src/api/auth.py`).

## Source

`README.md`, section "Productie setup", item 1 (Authenticatie); the comments in `src/api/auth.py`, `src/api/document_routes.py` and `src/api/text_routes.py`.
