# Anonymiq – Use-cases en snelle Swagger handleiding

Deze pagina helpt zowel niet-technische gebruikers als developers om de API direct te testen via de Swagger UI, zonder codewijzigingen.

## Toegang
- Productie Swagger: https://api.openanonymiser.commonground.nu/api/v1/docs
- Staging Swagger: https://api.openanonymiser.accept.commonground.nu/api/v1/docs

---

## Voor leken: wat kun je doen?

- Tekst analyseren: herkent PII (zoals namen, e-mails, telefoons, IBAN, adressen)
- Tekst anonimiseren: vervangt gevonden PII door placeholders
- Documenten uploaden en anonimiseren: upload → anonimiseren → downloaden

### 1) Tekst analyseren (Analyze Text)
1. Ga naar Swagger → POST /api/v1/analyze → “Try it out”.
2. Plak dit voorbeeld:
```json
{
  "text": "Jan Jansen woont op Kerkstraat 10, 1234 AB Amsterdam. IBAN: NL91ABNA0417164300.",
  "language": "nl",
  "entities": ["PERSON", "IBAN", "ADDRESS"]
}
```
3. Klik “Execute”. Je ziet een lijst met gevonden entiteiten en posities.

### 2) Tekst anonimiseren (Anonymize Text)
1. Ga naar POST /api/v1/anonymize → “Try it out”.
2. Plak dit voorbeeld:
```json
{
  "text": "Mail Jan op jan.jansen@example.com of bel 0612345678.",
  "language": "nl",
  "anonymization_strategy": "replace"
}
```
3. Klik “Execute”. Je krijgt `original_text`, `anonymized_text` en `entities_found`.

### 3) Documenten
- Upload: POST /api/v1/documents/upload → “Try it out” → voeg een PDF toe (multipart) → “Execute” → kopieer `id`.
- Anonimiseren: POST /api/v1/documents/{file_id}/anonymize → vul `file_id` + body:
```json
{ "pii_entities_to_anonymize": ["PERSON","EMAIL","PHONE_NUMBER","IBAN","ADDRESS"] }
```
- Download: GET /api/v1/documents/{file_id}/download → vul `file_id` → “Execute”.

Tip: Je kunt entiteiten leeg laten voor “alles”, of expliciet filteren.

---

## Voor developers: sneltest via Swagger

### Endpoints
- Health: GET /api/v1/health
- Tekst:
  - Analyze: POST /api/v1/analyze
  - Anonymize: POST /api/v1/anonymize
- Documenten:
  - Upload: POST /api/v1/documents/upload (multipart)
  - Anonymize: POST /api/v1/documents/{file_id}/anonymize
  - Download: GET /api/v1/documents/{file_id}/download

### Engines (NLP)
- Default: SpaCy (`nl_core_news_md`)
- Optioneel: Transformers (`pdelobelle/robbert-v2-dutch-base`) door `nlp_engine` mee te geven in de payload:
```json
{
  "text": "Voorbeeldtekst",
  "nlp_engine": "transformers"
}
```
Let op: Presidio’s pattern recognizers (zoals IBAN, e-mail, telefoon) gebruiken intern SpaCy; de NER-laag kan wisselen.

#### Welke modellen voor welke entiteiten?
- Pattern recognizers (regelgebaseerd, via Presidio):
  - `IBAN`, `PHONE_NUMBER`, `EMAIL`
- NLP (NER – SpaCy of Transformers, afhankelijk van `nlp_engine`):
  - `PERSON`, `LOCATION`, `ORGANIZATION`
  - `ADDRESS`: alleen via NLP (best‑effort), geen pattern‑recognizer; dekking is model‑afhankelijk

Samengevat: gebruik patterns voor “vormvaste” entiteiten (IBAN/telefoon/e‑mail) en NLP voor “vrije‑tekst” entiteiten (persoon/locatie/organisatie/adres).

### Voorbeeld payloads (Swagger)
- Analyze minimal:
```json
{ "text": "Piet woont in Utrecht." }
```
- Analyze met filters en engine:
```json
{
  "text": "Bel 0612345678 of mail piet@example.com",
  "language": "nl",
  "entities": ["PHONE_NUMBER","EMAIL"],
  "nlp_engine": "spacy"
}
```
- Anonymize:
```json
{
  "text": "IBAN is NL91ABNA0417164300.",
  "language": "nl",
  "anonymization_strategy": "replace"
}
```

---

## Verwachte output (kort)
- Analyze: `pii_entities[]`, `text_length`, optioneel `nlp_engine_used`
- Anonymize: `original_text`, `anonymized_text`, `entities_found[]`
- Document anonymize: `id`, `filename`, `pii_entities`, `status`, `time_taken`

---

## Troubleshooting
- “Validation Error”: check verplichte velden of bestandsformaat.
- Geen entiteiten gevonden? Probeer zonder filters, of controleer `language`.
- API versies en docs:
  - OpenAPI JSON: /api/v1/openapi.json
  - Swagger UI: /api/v1/docs


