# 1. Group the code by functional component, each with one public module

- Status: Accepted

## Context

The service has three kinds of work: answering HTTP requests, finding personal data in text, and handling PDF documents with their records and database. Grouping the code by FastAPI layer would spread each of these over several directories and let any module import any other.

## Decision

The Python code under `src/api/` is grouped by what the service does, not by FastAPI layer. Each component is a directory with one public module, and other components import only that module:

- Text analysis, `src/api/analysis/`, public module `analyzer.py`.
- Documents, `src/api/documents/`, public module `service.py`.
- API, the modules directly in `src/api/`, which nothing imports.

Dependencies run one way: the API uses Documents and Text analysis, and Documents uses Text analysis. Text analysis depends on neither. Each component reads its own settings from the environment. The web interface in `src/ui/` talks to the API over HTTP only.

## Consequences

- A new module goes into the component whose work it does.
- When another component needs something internal, the public module of the owning component is extended; the internal module is not imported directly.
- A reviewer can check a change against the boundaries by looking at its imports.

## Source

`ARCHITECTURE.md`, sections "Functional components" and "Boundaries".
