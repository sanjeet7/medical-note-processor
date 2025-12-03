# Part 1: FastAPI Backend

A REST API foundation using FastAPI and SQLAlchemy ORM with PostgreSQL.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        FastAPI Application                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────────┐  │
│  │   Endpoints  │───▶│   Schemas    │───▶│     Models       │  │
│  │  (main.py)   │    │ (Pydantic)   │    │  (SQLAlchemy)    │  │
│  └──────────────┘    └──────────────┘    └────────┬─────────┘  │
│                                                    │            │
│  ┌──────────────────────────────────────────────────┐          │
│  │              Dependency Injection                 │          │
│  │                   get_db()                        │          │
│  └──────────────────────────────────────────────────┘          │
│                           │                                     │
└───────────────────────────┼─────────────────────────────────────┘
                            ▼
                  ┌──────────────────┐
                  │    PostgreSQL    │
                  │    Database      │
                  └──────────────────┘
```

## Database Schema

```
┌─────────────────────────────────────────────────────────────────┐
│                         documents                                │
├─────────────────────────────────────────────────────────────────┤
│  id            │ INTEGER      │ PRIMARY KEY, AUTO INCREMENT     │
│  title         │ VARCHAR(255) │ NOT NULL                        │
│  content       │ TEXT         │ NOT NULL                        │
│  doc_type      │ VARCHAR(50)  │ DEFAULT 'general'               │
│  doc_metadata  │ JSON         │ DEFAULT {}                      │
│  created_at    │ DATETIME     │ DEFAULT UTC NOW                 │
├─────────────────────────────────────────────────────────────────┤
│                    ▲                                             │
│                    │ 1:N                                         │
│                    ▼                                             │
├─────────────────────────────────────────────────────────────────┤
│                      extracted_notes                             │
├─────────────────────────────────────────────────────────────────┤
│  id              │ INTEGER │ PRIMARY KEY                        │
│  document_id     │ INTEGER │ FOREIGN KEY → documents.id         │
│  structured_data │ JSON    │ NOT NULL (Part 4 output)           │
│  entity_counts   │ JSON    │ Summary counts                     │
│  fhir_bundle     │ JSON    │ Cached FHIR output (Part 5)        │
│  created_at      │ DATETIME│ DEFAULT UTC NOW                    │
├─────────────────────────────────────────────────────────────────┤
│                       llm_cache                                  │
├─────────────────────────────────────────────────────────────────┤
│  id           │ INTEGER     │ PRIMARY KEY                       │
│  prompt_hash  │ VARCHAR(64) │ UNIQUE INDEX (SHA-256)            │
│  prompt       │ TEXT        │ Original prompt                   │
│  response     │ TEXT        │ LLM response                      │
│  provider     │ VARCHAR(50) │ 'openai' or 'anthropic'           │
│  model        │ VARCHAR(100)│ Model name                        │
│  created_at   │ DATETIME    │ DEFAULT UTC NOW                   │
└─────────────────────────────────────────────────────────────────┘
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check - returns `{"status": "ok"}` |
| GET | `/documents` | List all document IDs |
| GET | `/documents/{id}` | Get document by ID |
| POST | `/documents` | Create new document |
| PUT | `/documents/{id}` | Update document (partial) |
| DELETE | `/documents/{id}` | Delete document |

## Key Design Decisions

### 1. Dependency Injection
Database sessions are managed via FastAPI's dependency injection:
```python
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

### 2. Pydantic Validation
All requests/responses use Pydantic schemas with validation:
- `DocumentCreate`: Required title (1-255 chars), content (min 1 char)
- `DocumentUpdate`: All fields optional for partial updates
- `DocumentResponse`: Includes auto-generated `id` and `created_at`

### 3. Document Types
The `doc_type` field supports categorization:
- `soap_note`: Clinical SOAP notes (6 pre-seeded)
- `guideline`: Medical guidelines (used by RAG in Part 3 but indexed in vector db directly)
- `general`: Default for user-created documents

## Seeded Data

On startup, 6 SOAP notes are automatically loaded from `data/soap_notes/`:

| ID | Title | Patient | Content |
|----|-------|---------|---------|
| 1 | SOAP Note - soap_01 | patient--001 | Annual physical, overweight |
| 2 | SOAP Note - soap_02 | patient--001 | Hyperlipidemia follow-up |
| 3 | SOAP Note - soap_03 | patient--005 | Flu shot visit |
| 4 | SOAP Note - soap_04 | Arjun Singh | Seasonal allergies |
| 5 | SOAP Note - soap_05 | Emily Williams | Post-surgical knee follow-up |
| 6 | SOAP Note - soap_06 | Emily Williams | Physical therapy |

## Tests

```bash
make test-part1  # 8 tests
```

| Test | Description |
|------|-------------|
| `test_health_check` | Verifies `/health` returns `{"status": "ok"}` |
| `test_get_documents` | List documents returns array of IDs |
| `test_create_document` | Create returns 201 with document |
| `test_create_document_validation` | Empty title returns 422 |
| `test_get_document_by_id` | Retrieve specific document |
| `test_get_document_not_found` | Non-existent ID returns 404 |
| `test_update_document` | Partial update works |
| `test_delete_document` | Delete returns 204, subsequent GET returns 404 |

