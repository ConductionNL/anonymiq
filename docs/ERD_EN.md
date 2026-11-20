# Anonymiq Entity Relationship Diagram (ERD)

This document describes the relational database schema for persistent storage of documents, tags, and anonymization events.  
**Note:** PII entities are not stored in the database for privacy reasons; they are processed in-memory and encoded/encrypted in the PDF metadata.

---

## Tables

### documents

| Column Name      | Type         | Description                        |
|------------------|--------------|------------------------------------|
| id               | VARCHAR(32)  | Primary key (UUID hex)             |
| filename         | TEXT         | Original file name                 |
| content_type     | TEXT         | MIME type                          |
| uploaded_at      | TIMESTAMP    | Upload datetime                    |
| source_path      | TEXT         | Path to source file                |
| anonymized_path  | TEXT         | Path to anonymized file (nullable) |

---

### tags

| Column Name      | Type         | Description                        |
|------------------|--------------|------------------------------------|
| id               | VARCHAR(32)  | Primary key (UUID hex)             |
| document_id      | VARCHAR(32)  | FK to documents.id                 |
| name             | TEXT         | Tag name                           |

---

### anonymization_events

| Column Name      | Type         | Description                        |
|------------------|--------------|------------------------------------|
| id               | SERIAL       | Primary key                        |
| document_id      | VARCHAR(32)  | FK to documents.id                 |
| anonymized_at    | TIMESTAMP    | When anonymized                    |
| time_taken       | INTEGER      | Time taken (seconds)               |
| status           | TEXT         | Status text                        |

---

## Relationships

- **documents** 1---* **tags**  
  Each document can have multiple tags.

- **documents** 1---* **anonymization_events**  
  Each document can have multiple anonymization events (audit trail).

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

