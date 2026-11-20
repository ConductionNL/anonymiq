# Spec: document anonymisation

## Purpose

Take a PDF, find the personal data in it, redact the chosen entity types from the content stream, and keep an encrypted record in the PDF so an authorised user can restore the original text. Code: `src/api/document_routes.py`, `src/api/documents/` (public module `service.py`; PDF handling in `pdf_xmp.py`).

## Requirements

### Requirement: An uploaded PDF is stored and analysed

anonymiq SHALL serve `POST /api/v1/documents/upload` taking one or more files and optional tags. It SHALL accept only files with the extension `pdf` and answer 422 for any other. For each file it SHALL store the PDF, analyse its text, record the entities found and the tags in the database, and answer with the document's `id`, `filename`, `content_type`, `uploaded_at`, `tags` and its distinct `pii_entities`.

#### Scenario: an upload stores the document, its entities and tags
- GIVEN a PDF in which one name occurs twice, uploaded with tags a and b
- WHEN it is uploaded
- THEN the answer lists the name once as PERSON and both tags, and the database holds the source file, both occurrences and the tags
- Test: pytest `tests/unit/test_document_routes.py::test_upload_stores_the_document_entities_and_tags`

#### Scenario: another extension is refused
- GIVEN a file named brief.txt
- WHEN it is uploaded
- THEN the answer is 422 and names pdf as the supported extension
- Test: pytest `tests/unit/test_document_routes.py::test_upload_refuses_another_extension`

### Requirement: A stored document's metadata can be read

anonymiq SHALL serve `GET /api/v1/documents/{file_id}/metadata` answering the same shape as upload. With `details=true` it SHALL list the distinct stored entities, and analyse the PDF again when none are stored. A file id that is not a UUID SHALL answer 422; an unknown document SHALL answer 404.

#### Scenario: details come from the stored entities
- GIVEN a document with stored entities, including a duplicate and one without a type
- WHEN its metadata is read with details
- THEN the distinct typed entities are listed
- Test: pytest `tests/unit/test_document_routes.py::test_metadata_details_come_from_the_stored_entities`

#### Scenario: details fall back to analysing the PDF
- GIVEN a document whose stored entities are missing, empty or not JSON
- WHEN its metadata is read with details
- THEN the PDF is analysed again and its entities are listed
- Test: pytest `tests/unit/test_document_routes.py::test_metadata_details_fall_back_to_analysing_the_pdf`

#### Scenario: an unknown document
- GIVEN a UUID that no document has
- WHEN its metadata is read
- THEN the answer is 404
- Test: pytest `tests/unit/test_document_routes.py::test_metadata_of_an_unknown_document`

### Requirement: A document is anonymised by true redaction with an encrypted record

anonymiq SHALL serve `POST /api/v1/documents/{file_id}/anonymize` taking `pii_entities_to_anonymize`, a list of supported entity types. It SHALL remove each occurrence of those entities from the PDF's content stream (not draw over it), write a placeholder in its place, and embed in the PDF's XMP metadata a record per occurrence with its position and its text encrypted with AES-GCM under the configured `CRYPTO_KEY`. It SHALL record the run as an event with its status and duration. An unsupported entity type SHALL answer 422, an unknown document 404, and a failed run 500 with its status, removing the partial output.

#### Scenario: anonymisation redacts and records the run
- GIVEN an uploaded PDF in which a name occurs twice
- WHEN PERSON is anonymised
- THEN the answer has status "success (2 entities processed)", the anonymised PDF no longer contains the name, and one event with that status is recorded
- Test: pytest `tests/unit/test_document_routes.py::test_anonymize_redacts_records_an_event_and_stores_the_path`

#### Scenario: an unsupported entity is refused
- GIVEN the entity type SHOE_SIZE
- WHEN it is asked to be anonymised
- THEN the answer is 422
- Test: pytest `tests/unit/test_document_routes.py::test_anonymize_refuses_an_unsupported_entity`

#### Scenario: a failed run is recorded and leaves no output
- GIVEN a redaction that writes a partial file and then fails
- WHEN the document is anonymised
- THEN the answer is 500, the partial file is removed, the failure is recorded as an event and the document has no anonymised path
- Test: pytest `tests/unit/test_document_routes.py::test_a_failed_anonymization_records_the_failure`

### Requirement: The anonymised document is downloaded, and removed unless kept

anonymiq SHALL serve `GET /api/v1/documents/{file_id}/download` returning the anonymised PDF. Unless `keep_on_server=true`, it SHALL remove the anonymised and the source file after sending. A document that was not anonymised SHALL answer 404.

#### Scenario: the files are removed by default
- GIVEN an anonymised document
- WHEN it is downloaded without options
- THEN the PDF is returned, both files are removed, and a second download answers 404
- Test: pytest `tests/unit/test_document_routes.py::test_download_removes_the_files_by_default`

#### Scenario: the files are kept when asked
- GIVEN an anonymised document
- WHEN it is downloaded with `keep_on_server=true`
- THEN the PDF is returned and both files remain
- Test: pytest `tests/unit/test_document_routes.py::test_download_keeps_the_files_when_asked`

#### Scenario: download before anonymising
- GIVEN an uploaded document that was not anonymised
- WHEN it is downloaded
- THEN the answer is 404 "Document not anonymized"
- Test: pytest `tests/unit/test_document_routes.py::test_download_before_anonymizing`

### Requirement: An anonymised PDF can be restored with the right key

anonymiq SHALL serve `POST /api/v1/documents/deanonymize` taking an anonymised PDF and returning it, as `deanonymized_<filename>`, with each record decrypted and its text written back at its position. A PDF without records, a record that does not decrypt with the configured key, or a record that cannot be placed SHALL answer 422; the service SHALL never return such a PDF partly restored. Temporary files SHALL be removed afterwards.

#### Scenario: the redacted text is restored
- GIVEN a PDF anonymised with the configured key
- WHEN it is posted to the de-anonymise route
- THEN the answer contains the original name and no temporary files remain
- Test: pytest `tests/unit/test_document_routes.py::test_deanonymize_restores_the_redacted_text`

#### Scenario: another key is refused
- GIVEN a PDF anonymised with another key
- WHEN it is posted
- THEN the answer is 422 saying the record does not decrypt
- Test: pytest `tests/unit/test_document_routes.py::test_deanonymize_with_another_key_is_a_422`

#### Scenario: a PDF without records is refused
- GIVEN a PDF that was never anonymised
- WHEN it is posted
- THEN the answer is 422
- Test: pytest `tests/unit/test_document_routes.py::test_deanonymize_without_metadata_is_a_422`

#### Scenario: anonymise then restore round trip
- GIVEN a PDF anonymised by the redaction code
- WHEN it is restored
- THEN the original text is back
- Test: pytest `tests/unit/test_restore_pdf.py::test_anonymize_then_restore_brings_the_text_back`
