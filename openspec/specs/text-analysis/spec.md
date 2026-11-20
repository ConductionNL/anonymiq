# Spec: text analysis

## Purpose

Find personal data in a Dutch (or English) text and return it, or return the text with every finding replaced by its entity type. This is the capability OpenRegister calls over HTTP. Code: `src/api/text_routes.py`, `src/api/analysis/` (public module `analyzer.py`), `src/api/analysis/patterns.py`.

## Requirements

### Requirement: The analyze route returns the entities found in a text

anonymiq SHALL serve `POST /api/v1/analyze` taking JSON `text`, optional `language` (default `DEFAULT_LANGUAGE`, `nl`), optional `entities` and optional `nlp_engine` (default `DEFAULT_NLP_ENGINE`, `spacy`). It SHALL strip the text, run the chosen NLP engine and the pattern recognisers, and answer 200 with `pii_entities` (each with `entity_type`, `text`, `start`, `end` and `score`), `text_length`, `processing_time_ms` and `nlp_engine_used`. A blank or missing score SHALL be answered as null.

#### Scenario: analysis with the defaults
- GIVEN a text with surrounding spaces
- WHEN it is posted to `/api/v1/analyze` with no options
- THEN the answer is 200 with the entities found, the length of the stripped text and the default engine, and the analyzer was called with the default entities and language
- Test: pytest `tests/unit/test_text_routes.py::test_analyze_with_defaults`

#### Scenario: analysis with options
- GIVEN a request with `language` en, `entities` EMAIL and `nlp_engine` transformers
- WHEN it is posted
- THEN the transformers engine is built and asked for EMAIL in English, and `nlp_engine_used` is transformers
- Test: pytest `tests/unit/test_text_routes.py::test_analyze_with_options`

#### Scenario: a blank score becomes null
- GIVEN a model that returns an empty string as score
- WHEN its results are turned into entities
- THEN the score is null, while a numeric or non-blank score is kept
- Test: pytest `tests/unit/test_text_routes.py::test_score_normalisation`

### Requirement: The anonymize route replaces each finding with its entity type

anonymiq SHALL serve `POST /api/v1/anonymize` with the same fields as analyze plus `anonymization_strategy` (one of `replace`, `mask`, `redact`, `hash`; default `replace`). It SHALL answer 200 with `original_text`, `anonymized_text`, `entities_found`, `text_length`, `processing_time_ms`, `nlp_engine_used` and `anonymization_strategy`. In `anonymized_text` every finding SHALL be replaced by its entity type in angle brackets, for example `PERSON` becomes the placeholder `<PERSON>`. Today the strategy is validated and echoed in the answer, but the replacement is the entity type placeholder whichever strategy is chosen.

#### Scenario: anonymisation with the defaults
- GIVEN the text "Jan Jansen mailt jan@example.nl"
- WHEN it is posted to `/api/v1/anonymize`
- THEN `anonymized_text` is "`<PERSON>` mailt `<EMAIL>`", `anonymization_strategy` is replace, and both entities are listed
- Test: pytest `tests/unit/test_text_routes.py::test_anonymize_with_defaults`

#### Scenario: anonymisation with options
- GIVEN a request with `entities` PERSON, `language` en, `nlp_engine` transformers and strategy mask
- WHEN it is posted
- THEN the analyzer is asked for PERSON in English and the answer echoes mask and transformers
- Test: pytest `tests/unit/test_text_routes.py::test_anonymize_with_options`

### Requirement: Invalid requests and analyzer failures are refused

A request with a blank text, a language other than `nl` or `en`, or an entity type outside `PERSON`, `LOCATION`, `PHONE_NUMBER`, `EMAIL`, `ORGANIZATION`, `IBAN`, `DATE_TIME` and `ADDRESS` SHALL answer 422; so SHALL an unknown anonymisation strategy. An error inside the analyzer SHALL answer 500 with the reason, never 200.

#### Scenario: invalid requests are a 422
- GIVEN a blank text, the language de, or the entity SHOE_SIZE
- WHEN it is posted to either text route
- THEN the answer is 422
- Test: pytest `tests/unit/test_text_routes.py::test_invalid_requests_are_a_422`

#### Scenario: an unknown strategy is a 422
- GIVEN the strategy shred
- WHEN it is posted to `/api/v1/anonymize`
- THEN the answer is 422
- Test: pytest `tests/unit/test_text_routes.py::test_an_unknown_strategy_is_a_422`

#### Scenario: an analyzer error is a 500
- GIVEN an analyzer that raises "no model"
- WHEN a text is posted to either route
- THEN the answer is 500 with the detail "Text analysis failed: no model" or "Text anonymization failed: no model"
- Test: pytest `tests/unit/test_text_routes.py::test_an_analyzer_error_is_a_500`

### Requirement: NLP and pattern results are combined without duplicates

The analyzer SHALL combine the NLP engine's results with the pattern recognisers' results and SHALL keep only the first result for each span and entity type. When specific entity types are requested (other than the full default list), it SHALL keep only results of those types. A failing pattern analysis SHALL be logged and SHALL leave the NLP results in place.

#### Scenario: results are combined
- GIVEN an NLP result for a person and a pattern result for an e-mail address
- WHEN the text is analysed
- THEN both are returned
- Test: pytest `tests/unit/test_text_analyzer.py::test_nlp_and_pattern_results_are_combined`

#### Scenario: duplicate spans are dropped
- GIVEN two results of one type over the same span
- WHEN the text is analysed
- THEN one is returned
- Test: pytest `tests/unit/test_text_analyzer.py::test_duplicate_spans_of_one_type_are_dropped`

#### Scenario: requested types filter the results
- GIVEN a request for EMAIL only
- WHEN the text is analysed
- THEN only the e-mail result is returned
- Test: pytest `tests/unit/test_text_analyzer.py::test_requested_entities_filter_the_combined_results`

#### Scenario: a failing pattern analysis is skipped
- GIVEN pattern recognisers that raise an error
- WHEN the text is analysed
- THEN the NLP results are still returned
- Test: pytest `tests/unit/test_text_analyzer.py::test_a_failing_pattern_analysis_is_skipped`

### Requirement: The NLP engine is chosen by configuration or per request

The analyzer SHALL load the spaCy engine (default model `nl_core_news_md`) or the transformers engine (default model `pdelobelle/robbert-v2-dutch-base`) as asked, and SHALL raise an error for any other engine name. The pattern recognisers SHALL run on Presidio's spaCy engine whichever engine finds the named entities.

#### Scenario: the default model follows the engine
- GIVEN the engine spacy or transformers and no model name
- WHEN the analyzer is built
- THEN it loads that engine's default model
- Test: pytest `tests/unit/test_text_analyzer.py::test_the_default_model_follows_the_engine`

#### Scenario: the pattern analyzer uses spaCy and the Dutch recognisers
- GIVEN any engine choice
- WHEN the analyzer is built
- THEN Presidio's analyzer runs on spaCy with, in order, the phone number, IBAN, BSN, date, e-mail, passport and identity card, driving licence and case number recognisers
- Test: pytest `tests/unit/test_text_analyzer.py::test_the_pattern_analyzer_uses_spacy_and_the_dutch_recognizers`

### Requirement: Dutch pattern recognisers find fixed-shape personal data

The recognisers registered with the analyzer SHALL find Dutch phone numbers (`PHONE_NUMBER`), Dutch and international IBANs (`IBAN`), BSNs (`BSN`), dates in numeric and spelled-out Dutch forms (`DATE_TIME`), e-mail addresses (`EMAIL`), passport and identity card numbers (`ID_NO`), driving licence numbers (`DRIVERS_LICENSE`) and case and file numbers (`CASE_NO`). Their entity, language, patterns and scores SHALL stay as pinned by the tests, because they decide what gets redacted.

#### Scenario: each recogniser finds its entity in running text
- GIVEN a typical value in a sentence, such as "rekening NL91 ABNA 0417 1643 00."
- WHEN its recogniser analyses the sentence
- THEN the value is found
- Test: pytest `tests/unit/test_pattern_recognizers.py::test_recognizer_finds_its_entity`

#### Scenario: the configuration is pinned
- GIVEN the recogniser classes
- WHEN their configuration and regular expressions are read
- THEN entity, language, pattern names, scores and regular expressions match the pinned table
- Test: pytest `tests/unit/test_pattern_recognizers.py::test_recognizer_configuration`, `tests/unit/test_pattern_recognizers.py::test_regex_of_every_pattern_is_pinned`
