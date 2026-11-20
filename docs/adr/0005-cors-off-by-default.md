# 5. CORS off by default, explicit origins only

- Status: Accepted

## Context

The known machine caller, OpenRegister, calls the service server to server and sends no Origin header, so it needs no CORS. A wildcard origin together with credentials would let any web page drive the document routes with a browser's stored credentials.

## Decision

CORS is off by default. Only a browser front end on another origin needs it, and that origin is named explicitly in `app.cors.allowedOrigins` in the Helm values, or in `ALLOWED_ORIGINS` (comma separated). A wildcard `*` is refused at start-up. The ingress sets no CORS headers of its own.

## Consequences

- With no origins configured, no response carries an `Access-Control-Allow-Origin` header.
- The development UI in `docker-compose.yaml` lists its own origin, `http://localhost:8002`.
- A misconfigured wildcard stops the service from starting instead of opening it.

## Source

`README.md`, section "Productie setup", item 2 (CORS); the comments in `src/api/main.py` and `src/api/config.py`.
