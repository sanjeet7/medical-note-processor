# Part 3: RAG Pipeline

Retrieval-Augmented Generation for answering medical questions using a curated knowledge base of clinical guidelines.

## Architecture

```
                              User Question
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────┐
│                        RAG Service                               │
│                   (src/rag/service.py)                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   ┌─────────────────────────────────────────────────────────┐   │
│   │              Step 1: Query Reformulation                 │   │
│   │                                                          │   │
│   │   "What is target LDL for diabetics?"                   │   │
│   │                    │                                     │   │
│   │                    ▼                                     │   │
│   │   • "LDL cholesterol target diabetic patients"          │   │
│   │   • "diabetes mellitus lipid goals"                     │   │
│   │   • "glycemic control cholesterol targets"              │   │
│   └─────────────────────────────────────────────────────────┘   │
│                            │                                     │
│                            ▼                                     │
│   ┌─────────────────────────────────────────────────────────┐   │
│   │              Step 2: Vector Search                       │   │
│   │                                                          │   │
│   │ Query expand + embedding ──▶ FAISS Index ──▶ Top-K chunks│   │
│   │                                                          │   │
│   │   Uses: text-embedding-3-small (OpenAI)                 │   │
│   │   Index: FAISS IndexFlatIP (inner product)              │   │
│   └─────────────────────────────────────────────────────────┘   │
│                            │                                     │
│                            ▼                                     │
│   ┌─────────────────────────────────────────────────────────┐   │
│   │              Step 3: LLM Boolean Filtering               │   │
│   │                                                          │   │
│   │   For each candidate chunk:                              │   │
│   │   "Is this chunk relevant to the question?"             │   │
│   │                    │                                     │   │
│   │                    ▼                                     │   │
│   │   { "relevant": true/false, "reasoning": "..." }        │   │
│   └─────────────────────────────────────────────────────────┘   │
│                            │                                     │
│                            ▼                                     │
│   ┌─────────────────────────────────────────────────────────┐   │
│   │              Step 4: Answer Generation                   │   │
│   │                                                          │   │
│   │   Context: [1] chunk1  [2] chunk2  [3] chunk3           │   │
│   │                    │                                     │   │
│   │                    ▼                                     │   │
│   │   "According to guidelines, target LDL is <100 mg/dL    │   │
│   │    for diabetic patients [1]. For high-risk patients,   │   │
│   │    <70 mg/dL may be recommended [2]."                   │   │
│   └─────────────────────────────────────────────────────────┘   │
│                            │                                     │
│                            ▼                                     │
│   ┌─────────────────────────────────────────────────────────┐   │
│   │              Step 5: Confidence Assessment               │   │
│   │                                                          │   │
│   │   LLM evaluates: completeness, source support, clarity  │   │
│   │   Returns: { "confidence": 0.85, "reasoning": "..." }   │   │
│   └─────────────────────────────────────────────────────────┘   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
                         RAGAnswer Response
                    (answer + citations + confidence)
```

## Knowledge Base

The RAG pipeline uses 4 medical guidelines stored in `data/medical_guidelines/`:

| Guideline | Topics Covered |
|-----------|----------------|
| `diabetes_guideline.txt` | A1C targets, glucose monitoring, hypoglycemia, insulin therapy |
| `hypertension_guideline.txt` | BP targets, lifestyle modifications, medication classes |
| `hyperlipidemia_guideline.txt` | LDL/HDL targets, statin therapy, risk stratification |
| `post_surgical_care_guideline.txt` | Wound care, pain management, physical therapy |

### Chunking Strategy

Documents are chunked using  boundaries (placeholder for LLM based intelligent boundary selection + dynamic metadata extraction):

```
┌──────────────────────────────────────────────────────────────┐
│  Document Text                                                │
├──────────────────────────────────────────────────────────────┤
│  Section 1: Introduction                                      │
│  ─────────────────────────                                   │
│  ...content...                                                │
│                            ◄── Detects section boundary   │
│  Section 2: Treatment Goals                                   │
│  ──────────────────────────                                  │
│  ...content...                                                │
└──────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌───────────────┐  ┌───────────────┐  ┌───────────────┐
│   Chunk 1     │  │   Chunk 2     │  │   Chunk 3     │
│               │  │               │  │               │
│ section_title │  │ section_title │  │ section_title │
│ document_name │  │ document_name │  │ document_name │
│ chunk_index   │  │ chunk_index   │  │ chunk_index   │
└───────────────┘  └───────────────┘  └───────────────┘

Settings:
• chunk_size: 500 tokens
• chunk_overlap: 100 tokens
• Encoding: cl100k_base (GPT-5 compatible)
```

## Vector Store

FAISS is used for efficient similarity search:

```python
# Index configuration
index = faiss.IndexFlatIP(embedding_dim)  # Inner product (cosine similarity)

# Persistence
data/faiss_db/
├── index.faiss      # Vector index
└── metadata.json    # Chunk metadata (document name, section, text)
```

## API Endpoint

### POST /answer_question

Ask medical questions answered from the guideline knowledge base.

| Field | Type | Description |
|-------|------|-------------|
| `question` | string | Medical question (1-2000 chars) |

**Response:**

```json
{
  "answer": "According to the diabetes guidelines, target LDL for diabetic patients is <100 mg/dL [1]. For patients with cardiovascular disease history, a more aggressive target of <70 mg/dL is recommended [2].",
  "sources": [
    {
      "id": 1,
      "document": "diabetes_guideline.txt",
      "section": "Cardiovascular Risk Management",
      "text": "LDL cholesterol target: <100 mg/dL for all diabetic patients..."
    },
    {
      "id": 2,
      "document": "hyperlipidemia_guideline.txt",
      "section": "High-Risk Patients",
      "text": "For patients with established CVD, target LDL <70 mg/dL..."
    }
  ],
  "confidence": 0.85,
  "retrieved_count": 3
}
```

## Key Design Decisions

### 1. Query Reformulation
Original queries are expanded into multiple variations to improve recall:
- Medical synonyms and terminology
- Different phrasings of the same question
- Related concepts

### 2. Hybrid Retrieval
Combines vector search with LLM boolean filtering:
- **Vector search**: Fast approximate matching via FAISS
- **LLM filtering**: Precise relevance check eliminates false positives

### 3. Source Citations
Every claim in the answer includes inline citations `[1]`, `[2]` that map to the `sources` array, enabling verification.

### 4. Confidence Scoring
LLM evaluates answer quality based on:
- Completeness (does it fully answer the question?)
- Source support (is it well-grounded in retrieved chunks?)
- Clarity (is it specific and actionable?)

Low confidence answers include a disclaimer recommending professional consultation.

## Tests

```bash
make test-part3  # 5 tests
```

| Test | Description |
|------|-------------|
| `test_answer_question_endpoint` | Endpoint returns answer with citations |
| `test_answer_includes_sources` | Response includes source citations |
| `test_confidence_scoring` | Confidence score in valid range |
| `test_empty_question_validation` | Empty question returns 422 |
| `test_query_reformulation` | Multiple query variants generated |

