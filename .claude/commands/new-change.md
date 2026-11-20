---
description: Start an OpenSpec change under openspec/changes/
---

Start a new OpenSpec change named `$ARGUMENTS` (kebab-case, named by what it does).

1. Read `openspec/config.yaml` for the rules, and `openspec/changes/object-detection-in-page-images/` as the example of the house format.
2. Create `openspec/changes/<name>/` with the same files that change has:
   - `.openspec.yaml` with `schema: spec-driven` and `created: <today, YYYY-MM-DD>`.
   - `proposal.md`: what changes and why. Name the OpenRegister change on the other side of any HTTP contract, and state what happens when a model or a class is not available.
   - `specs/<capability>/spec.md`: `## ADDED Requirements` (or MODIFIED / REMOVED), each `### Requirement:` with SHALL statements and `#### Scenario:` blocks. Each scenario names the pytest test that proves it.
   - `tasks.md`: numbered checkbox tasks; every task names the pytest test that proves it, failing before and passing after.
3. Compare with the current specs in `openspec/specs/<capability>/spec.md` so the delta modifies the right capability.

The `openspec` CLI is not a dependency of this repository. If it is installed, `openspec validate <name> --type change --strict` checks the change, as the existing `tasks.md` asks.
