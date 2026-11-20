# Anonymiq Entiteit-Relatie Diagram (ERD)

Dit document beschrijft het relationele databasemodel voor het opslaan van documenten, tags en anonimiseer-gebeurtenissen.  
**Let op:** PII-entiteiten worden om privacyredenen niet in de database opgeslagen; deze worden in-memory verwerkt en versleuteld/opgenomen in de PDF-metadata.

---

## Tabellen

### documents

| Kolomnaam         | Type         | Omschrijving                               |
|-------------------|--------------|--------------------------------------------|
| id                | VARCHAR(32)  | Primaire sleutel (UUID hex)                |
| filename          | TEXT         | Originele bestandsnaam                     |
| content_type      | TEXT         | MIME-type                                  |
| uploaded_at       | TIMESTAMP    | Uploaddatum                                |
| source_path       | TEXT         | Pad naar bronbestand                       |
| anonymized_path   | TEXT         | Pad naar geanonimiseerd bestand (optioneel) |

---

### tags

| Kolomnaam         | Type         | Omschrijving                   |
|-------------------|--------------|--------------------------------|
| id                | VARCHAR(32)  | Primaire sleutel (UUID hex)    |
| document_id       | VARCHAR(32)  | FK naar documents.id           |
| name              | TEXT         | Naam van de tag                |

---

### anonymization_events

| Kolomnaam         | Type         | Omschrijving                         |
|-------------------|--------------|--------------------------------------|
| id                | SERIAL       | Primaire sleutel                     |
| document_id       | VARCHAR(32)  | FK naar documents.id                 |
| anonymized_at     | TIMESTAMP    | Moment van anonimisering             |
| time_taken        | INTEGER      | Benodigde tijd (seconden)            |
| status            | TEXT         | Statustekst                          |

---

## Relaties

- **documents** 1---* **tags**  
  Elk document kan meerdere tags hebben.

- **documents** 1---* **anonymization_events**  
  Elk document kan meerdere anonimiseer-gebeurtenissen hebben (audit trail).

---

## Diagram

```plaintext
+-------------------+        +-------------------+
|    documents      |<------>|       tags        |
+-------------------+        +-------------------+
| id (PK)           | 1    * | id (PK)           |
| filename          |        | document_id (FK)  |
| content_type      |        | name              |
| uploaded_at       |        +-------------------+
| source_path       |
| anonymized_path   |
+-------------------+
        |
        | 1
        |
        | *
+--------------------------+
|   anonymization_events   |
+--------------------------+
| id (PK)                 |
| document_id (FK)        |
| anonymized_at           |
| time_taken              |
| status                  |
+--------------------------