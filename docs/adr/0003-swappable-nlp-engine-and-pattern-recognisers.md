# 3. A swappable NLP engine next to rule-based pattern recognisers

- Status: Accepted

## Context

In the proof of concept spaCy was hard-coded, so adding a model such as a transformers model needed many code changes, and the configuration of recognisers and models was spread over the code. Some personal data has a fixed shape (an IBAN, a phone number, an e-mail address); other personal data is free text (a name, a place, an organisation).

## Decision

The service is built on Microsoft Presidio and supports several NLP models, spaCy or HuggingFace transformers, without changes to the API or its logic. The NLP engine is chosen by configuration (`DEFAULT_NLP_ENGINE`, default spaCy with `nl_core_news_md`) and can be overridden per request with `nlp_engine`.

Entities with a fixed shape are found by pattern recognisers (regular expressions registered with Presidio). Free-text entities (`PERSON`, `LOCATION`, `ORGANIZATION`, and `ADDRESS` on a best-effort basis) are found by the NLP engine. The results of both are combined.

## Consequences

- A new model is added behind the engine abstraction in `src/api/analysis/nlp/`, not in the routes.
- Coverage of free-text entities such as `ADDRESS` depends on the model chosen.
- Presidio itself always runs the pattern recognisers on spaCy, whichever engine finds the named entities, so the spaCy model is needed in every deployment.

## Source

`README.md` (introduction and "Welke modellen voor welke entiteiten?"), `docs/lessons_learned.md`, `PROJECT_OVERVIEW.md` ("NLP & entiteiten").
