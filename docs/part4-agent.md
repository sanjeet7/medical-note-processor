# Part 4: Agent for Structured Data Extraction

Intelligent agent system that extracts structured medical data from unstructured SOAP notes, enriches with ICD-10 and RxNorm codes via NIH APIs, and outputs FHIR-aligned Pydantic models.

## Architecture

```
                            SOAP Note Input
                                   │
                                   ▼
┌──────────────────────────────────────────────────────────────────┐
│                      ExtractionAgent                              │
│                  (ReAct-Style Orchestrator)                       │
├──────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │                   TrajectoryLogger                           │ │
│  │  Records: step_name, tool, input, output, duration, status  │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                              │                                    │
│  ┌───────────────────────────┼───────────────────────────────┐   │
│  │                           ▼                               │   │
│  │   Step 1: EXTRACT ENTITIES                                │   │
│  │   ┌─────────────────────────────────────────────────┐    │   │
│  │   │         EntityExtractionTool (LLM)              │    │   │
│  │   │                                                  │    │   │
│  │   │   SOAP Note ──▶ Structured JSON ──▶ RawExtraction   │   │
│  │   │                                                  │    │   │
│  │   │   Extracts: patient, conditions, medications,   │    │   │
│  │   │            vitals, labs, procedures, plans      │    │   │
│  │   └─────────────────────────────────────────────────┘    │   │
│  │                           │                               │   │
│  │                           ▼                               │   │
│  │   Step 2: ENRICH CONDITIONS (Parallel)                    │   │
│  │   ┌─────────────────────────────────────────────────┐    │   │
│  │   │           ICD10LookupTool                       │    │   │
│  │   │                                                  │    │   │
│  │   │   "Hyperlipidemia" ──▶ NIH API ──▶ E78.5        │    │   │
│  │   │   "Type 2 Diabetes" ──▶ NIH API ──▶ E11.9      │    │   │
│  │   └─────────────────────────────────────────────────┘    │   │
│  │                           │                               │   │
│  │                           ▼                               │   │
│  │   Step 3: ENRICH MEDICATIONS (Parallel)                   │   │
│  │   ┌─────────────────────────────────────────────────┐    │   │
│  │   │          RxNormLookupTool                       │    │   │
│  │   │                                                  │    │   │
│  │   │   "atorvastatin" ──▶ NIH API ──▶ RxCUI 83367   │    │   │
│  │   │   "lisinopril" ──▶ NIH API ──▶ RxCUI 29046     │    │   │
│  │   └─────────────────────────────────────────────────┘    │   │
│  │                           │                               │   │
│  │                           ▼                               │   │
│  │   Step 4: TRANSFORM                                       │   │
│  │   ┌─────────────────────────────────────────────────┐    │   │
│  │   │   RawExtraction + Codes ──▶ StructuredNote      │    │   │
│  │   └─────────────────────────────────────────────────┘    │   │
│  │                           │                               │   │
│  │                           ▼                               │   │
│  │   Step 5: VALIDATE                                        │   │
│  │   ┌─────────────────────────────────────────────────┐    │   │
│  │   │         ValidationTool (Pydantic)               │    │   │
│  │   │                                                  │    │   │
│  │   │   StructuredNote ──▶ Validation ──▶ Final Output    │   │
│  │   └─────────────────────────────────────────────────┘    │   │
│  └───────────────────────────────────────────────────────────┘   │
│                                                                   │
└──────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
                          StructuredNote
                    (FHIR-aligned Pydantic model)
```

## Tools

### EntityExtractionTool (LLM)
Uses structured output to extract all entity types from SOAP notes:

```python
# Example LLM output structure
{
  "patient": {"name": "John Doe", "identifier": "patient--001"},
  "conditions": [{"name": "Hyperlipidemia", "status": "active"}],
  "medications": [{"name": "atorvastatin", "dose": "20mg", "frequency": "daily"}],
  "vital_signs": [{"name": "BP", "value": "128/82", "unit": "mmHg"}],
  "lab_results": [{"name": "LDL", "value": 165, "unit": "mg/dL"}],
  "procedures": [{"name": "Annual physical exam"}],
  "care_plan": [{"description": "Follow-up in 3 months"}]
}
```

### ICD10LookupTool (NIH ClinicalTables API)
Looks up ICD-10-CM codes for conditions and diagnoses.

| Input | API | Output |
|-------|-----|--------|
| "Hyperlipidemia" | `clinicaltables.nlm.nih.gov` | `E78.5` |
| "Type 2 Diabetes" | | `E11.9` |
| "Essential Hypertension" | | `I10` |

### RxNormLookupTool (NIH RxNav API)
Looks up RxNorm codes (RxCUI) for medications.

| Input | API | Output |
|-------|-----|--------|
| "atorvastatin" | `rxnav.nlm.nih.gov` | `RxCUI 83367` |
| "lisinopril" | | `RxCUI 29046` |
| "metformin" | | `RxCUI 6809` |

**Lookup Strategy:**
1. Exact match (`/rxcui.json`)
2. Approximate match (`/approximateTerm.json`) - fallback
3. Drug name normalization (`/drugs.json`) - brand → generic

### ValidationTool (Pydantic)
Validates the assembled StructuredNote:
- Required fields present
- Enum values valid (clinical_status, medication_status, etc.)
- Code systems correct

## FHIR-Aligned Data Models

| Agent Model | FHIR Resource | Key Fields |
|-------------|---------------|------------|
| `PatientInfo` | Patient | identifier, name, birth_date, gender |
| `Condition` | Condition | code (ICD-10), clinical_status, verification_status |
| `Medication` | MedicationRequest | code (RxNorm), dosage, status, refills |
| `VitalSign` | Observation | code, value, unit, interpretation |
| `LabResult` | Observation | code, value, reference_range |
| `Procedure` | Procedure | code, status, body_site |
| `CarePlanActivity` | CarePlan | description, status, scheduled_string |

## Trajectory Logging

Every extraction includes a full execution audit trail:

```json
{
  "agent_name": "ExtractionAgent",
  "started_at": "2024-12-03T10:15:00Z",
  "completed_at": "2024-12-03T10:15:08Z",
  "success": true,
  "total_duration_ms": 8234,
  "steps": [
    {
      "step_number": 1,
      "step_name": "Extract Entities",
      "tool_name": "entity_extraction",
      "status": "success",
      "duration_ms": 3521,
      "input_summary": "SOAP note (1234 chars)",
      "output_summary": "Extracted 12 entities"
    },
    {
      "step_number": 2,
      "step_name": "Enrich Conditions",
      "tool_name": "icd10_lookup",
      "status": "success",
      "duration_ms": 1823,
      "input_summary": "3 conditions",
      "output_summary": "Found 3 ICD-10 codes"
    }
  ],
  "statistics": {
    "total_steps": 5,
    "successful_steps": 5,
    "failed_steps": 0
  }
}
```

## API Endpoint

### POST /extract_structured

Extract structured data from a SOAP note.

| Field | Type | Description |
|-------|------|-------------|
| `document_id` | int | ID of SOAP note document |
| `text` | string | Raw SOAP note (alternative to document_id) |
| `include_trajectory` | bool | Include execution trajectory (default: true) |
| `use_cache` | bool | Return cached if available (default: true) |

**Response:**

```json
{
  "success": true,
  "extracted_note_id": 1,
  "document_id": 2,
  "structured_data": {
    "patient": {"identifier": "patient--001", "name": "John Doe"},
    "conditions": [
      {
        "code": {"code": "E78.5", "system": "http://hl7.org/fhir/sid/icd-10-cm", "display": "Hyperlipidemia"},
        "clinical_status": "active",
        "verification_status": "confirmed"
      }
    ],
    "medications": [
      {
        "code": {"code": "83367", "system": "http://www.nlm.nih.gov/research/umls/rxnorm", "display": "atorvastatin"},
        "dosage": {"text": "20mg daily at bedtime"},
        "status": "active"
      }
    ]
  },
  "entity_counts": {
    "conditions": 2,
    "medications": 1,
    "vital_signs": 4,
    "lab_results": 3,
    "procedures": 0,
    "care_plan": 2
  },
  "cached": false
}
```

## Key Design Decisions

### 1. ReAct Pattern
The agent follows a Reasoning + Acting pattern:
- **Think**: Analyze SOAP note structure
- **Act**: Execute tools in sequence
- **Observe**: Log results and proceed

### 2. Parallel Code Lookups
ICD-10 and RxNorm lookups run concurrently using `asyncio.gather()` for better performance.

### 3. Graceful Degradation
Missing codes don't block extraction:
- If NIH API fails, the entity is still extracted (code = None)
- If validation fails on optional fields, they're set to defaults

### 4. Caching
Extractions are cached by `document_id` in the `extracted_notes` table to avoid redundant LLM calls and API lookups.

## Tests

```bash
make test-part4  # 36 tests
```

| Category | Tests | Description |
|----------|-------|-------------|
| Unit Tests | 27 | Mocked dependencies |
| NIH API Tests | 8 | Real API integration |
| Golden Set | 1 | End-to-end evaluation |

