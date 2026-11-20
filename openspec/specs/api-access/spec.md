# Spec: API access

## Purpose

Decide who may call the service and from where: HTTP Basic authentication on every route that receives personal data, a public health route, and CORS only for explicitly named browser origins. Code: `src/api/auth.py`, `src/api/main.py`, `src/api/config.py`, `src/api/routes.py`.

## Requirements

### Requirement: Every data route requires HTTP Basic credentials and fails closed

All routes under `/api/v1/documents` and the text routes `/api/v1/analyze` and `/api/v1/anonymize` SHALL require HTTP Basic credentials matching `BASIC_AUTH_USERNAME` and `BASIC_AUTH_PASSWORD`, compared in constant time. Missing or wrong credentials SHALL answer 401 with a Basic challenge. When `BASIC_AUTH_PASSWORD` is unset or empty, every such request SHALL answer 401.

#### Scenario: no credentials are refused
- GIVEN a well-formed request to any document route
- WHEN it is sent without credentials
- THEN the answer is 401
- Test: pytest `tests/unit/test_document_auth.py::test_without_credentials_is_refused`, `tests/unit/test_text_auth.py::test_without_credentials_is_refused`

#### Scenario: wrong credentials are refused
- GIVEN a wrong username or password
- WHEN a data route is called
- THEN the answer is 401
- Test: pytest `tests/unit/test_document_auth.py::test_wrong_credentials_are_refused`, `tests/unit/test_text_auth.py::test_wrong_credentials_are_refused`

#### Scenario: no configured password refuses everyone
- GIVEN `BASIC_AUTH_PASSWORD` empty
- WHEN a data route is called, even with an empty password
- THEN the answer is 401
- Test: pytest `tests/unit/test_document_auth.py::test_no_configured_password_refuses_everyone`, `tests/unit/test_text_auth.py::test_no_configured_password_refuses_everyone`

#### Scenario: every document route is covered
- GIVEN the routes in the app's OpenAPI schema
- WHEN the document routes are listed
- THEN each one is in the authentication test table
- Test: pytest `tests/unit/test_document_auth.py::test_the_table_covers_every_document_route`

### Requirement: The health route is public

anonymiq SHALL serve `GET /api/v1/health` without authentication, answering `{"ping": "pong"}`.

#### Scenario: health stays public
- GIVEN no credentials
- WHEN `/api/v1/health` is called
- THEN the answer is 200
- Test: pytest `tests/unit/test_document_auth.py::test_health_stays_public`

### Requirement: CORS answers only explicitly configured origins

CORS SHALL be off unless `ALLOWED_ORIGINS` names origins (comma separated, trailing slash dropped). A configured origin SHALL be echoed in `Access-Control-Allow-Origin`; any other origin SHALL get no such header. A wildcard `*` SHALL stop the application from starting.

#### Scenario: a configured origin is allowed
- GIVEN `ALLOWED_ORIGINS` naming an origin
- WHEN a request comes from that origin
- THEN the answer echoes that origin, not a wildcard
- Test: pytest `tests/unit/test_cors.py::test_a_configured_origin_is_allowed`

#### Scenario: another origin gets no header
- GIVEN a request or preflight from an origin that is not configured
- WHEN it is answered
- THEN it carries no `Access-Control-Allow-Origin` header
- Test: pytest `tests/unit/test_cors.py::test_a_non_allowed_origin_gets_no_allow_header`, `tests/unit/test_cors.py::test_a_non_allowed_origin_preflight_gets_no_allow_header`

#### Scenario: a wildcard is refused at start-up
- GIVEN `ALLOWED_ORIGINS` set to `*`
- WHEN the application starts
- THEN it fails to start
- Test: pytest `tests/unit/test_cors.py::test_a_wildcard_origin_is_refused_at_startup`
