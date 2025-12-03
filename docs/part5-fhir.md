# Part 5: FHIR Conversion

Converts structured medical data from Part 4 into spec-compliant FHIR R5 resources using the `fhir.resources` library, assembled into a FHIR Bundle.

## Architecture

```
                      Structured Data (Part 4)
                               │
                               ▼
┌──────────────────────────────────────────────────────────────────┐
│                       FHIRConverter                               │
│                   (src/fhir/converter.py)                         │
├──────────────────────────────────────────────────────────────────┤
│                                                                   │
│   ┌─────────────────────────────────────────────────────────────┐│
│   │  Input: StructuredNote                                      ││
│   │  ├── patient: PatientInfo                                   ││
│   │  ├── conditions: List[Condition]     ─┐                     ││
│   │  ├── medications: List[Medication]    │ with ICD-10/RxNorm  ││
│   │  ├── vital_signs: List[VitalSign]     │                     ││
│   │  ├── lab_results: List[LabResult]    ─┘                     ││
│   │  ├── procedures: List[Procedure]                            ││
│   │  └── care_plan: List[CarePlanActivity]                      ││
│   └─────────────────────────────────────────────────────────────┘│
│                               │                                   │
│   ┌───────────────────────────┼───────────────────────────────┐  │
│   │                           ▼                               │  │
│   │   ┌─────────────────┐  ┌─────────────────┐               │  │
│   │   │  PatientMapper  │  │ ConditionMapper │               │  │
│   │   │                 │  │                 │               │  │
│   │   │ PatientInfo ───▶│  │ Condition ─────▶│               │  │
│   │   │ FHIR Patient    │  │ FHIR Condition  │               │  │
│   │   │                 │  │ (with ICD-10)   │               │  │
│   │   └─────────────────┘  └─────────────────┘               │  │
│   │                                                           │  │
│   │   ┌─────────────────────────┐  ┌─────────────────────┐   │  │
│   │   │ MedicationRequestMapper │  │  ObservationMapper  │   │  │
│   │   │                         │  │                     │   │  │
│   │   │ Medication ────────────▶│  │ VitalSign ─────────▶│   │  │
│   │   │ FHIR MedicationRequest  │  │ FHIR Observation    │   │  │
│   │   │ (with RxNorm)           │  │ (vital-signs)       │   │  │
│   │   └─────────────────────────┘  │                     │   │  │
│   │                                │ LabResult ─────────▶│   │  │
│   │   ┌─────────────────┐         │ FHIR Observation    │   │  │
│   │   │ ProcedureMapper │         │ (laboratory)        │   │  │
│   │   │                 │         └─────────────────────┘   │  │
│   │   │ Procedure ─────▶│                                   │  │
│   │   │ FHIR Procedure  │  ┌─────────────────┐              │  │
│   │   └─────────────────┘  │ CarePlanMapper  │              │  │
│   │                        │                 │              │  │
│   │                        │ Activities ────▶│              │  │
│   │                        │ FHIR CarePlan   │              │  │
│   │                        └─────────────────┘              │  │
│   └─────────────────────────────────────────────────────────┘  │
│                               │                                   │
│                               ▼                                   │
│   ┌─────────────────────────────────────────────────────────────┐│
│   │                      FHIRBundler                            ││
│   │                  (src/fhir/bundler.py)                      ││
│   │                                                              ││
│   │   add_resource(Patient)                                     ││
│   │   add_resource(Condition)                                   ││
│   │   add_resource(MedicationRequest)                           ││
│   │   add_resource(Observation) × N                             ││
│   │   add_resource(Procedure)                                   ││
│   │   add_resource(CarePlan)                                    ││
│   │                    │                                        ││
│   │                    ▼                                        ││
│   │   build() ──▶ Bundle(type="collection", entry=[...])       ││
│   └─────────────────────────────────────────────────────────────┘│
│                                                                   │
└──────────────────────────────────────────────────────────────────┘
                               │
                               ▼
                      FHIR Bundle (JSON)
```

## Resource Mappings

| Part 4 Model | FHIR R5 Resource | Key Mappings |
|--------------|------------------|--------------|
| `PatientInfo` | `Patient` | identifier, name, birthDate, gender |
| `Condition` | `Condition` | code.coding (ICD-10), clinicalStatus, subject |
| `Medication` | `MedicationRequest` | medication.concept (RxNorm), dosageInstruction |
| `VitalSign` | `Observation` | code, valueQuantity, category=vital-signs |
| `LabResult` | `Observation` | code, valueQuantity, category=laboratory |
| `Procedure` | `Procedure` | code, status, bodySite |
| `CarePlanActivity` | `CarePlan` | activity.performedActivity, status |

## Medical Code Preservation

Codes from Part 4's NIH API lookups flow through to FHIR resources:

### ICD-10 in Condition

```json
{
  "resourceType": "Condition",
  "code": {
    "coding": [{
      "system": "http://hl7.org/fhir/sid/icd-10-cm",
      "code": "E78.5",
      "display": "Hyperlipidemia, unspecified"
    }],
    "text": "Hyperlipidemia"
  },
  "clinicalStatus": {
    "coding": [{
      "system": "http://terminology.hl7.org/CodeSystem/condition-clinical",
      "code": "active"
    }]
  },
  "subject": {"reference": "Patient/abc123"}
}
```

### RxNorm in MedicationRequest

```json
{
  "resourceType": "MedicationRequest",
  "medication": {
    "concept": {
      "coding": [{
        "system": "http://www.nlm.nih.gov/research/umls/rxnorm",
        "code": "83367",
        "display": "atorvastatin"
      }]
    }
  },
  "dosageInstruction": [{
    "text": "20mg daily at bedtime",
    "route": {"text": "oral"}
  }],
  "subject": {"reference": "Patient/abc123"},
  "status": "active",
  "intent": "order"
}
```

## API Endpoint

### POST /to_fhir

Convert structured data to FHIR Bundle.

**Input Options:**

| Field | Type | Description |
|-------|------|-------------|
| `extracted_note_id` | int | ID from `/extract_structured` response |
| `document_id` | int | Uses latest extraction for document |
| `structured_data` | object | Direct StructuredNote JSON |
| `use_cache` | bool | Return cached bundle (default: true) |

**Response:**

```json
{
  "success": true,
  "bundle": {
    "resourceType": "Bundle",
    "id": "uuid-here",
    "type": "collection",
    "timestamp": "2024-12-03T10:30:00Z",
    "entry": [
      {"fullUrl": "urn:uuid:abc", "resource": {"resourceType": "Patient", ...}},
      {"fullUrl": "urn:uuid:def", "resource": {"resourceType": "Condition", ...}},
      {"fullUrl": "urn:uuid:ghi", "resource": {"resourceType": "MedicationRequest", ...}}
    ]
  },
  "resource_counts": {
    "Patient": 1,
    "Condition": 2,
    "MedicationRequest": 1,
    "Observation (vital-signs)": 4,
    "Observation (laboratory)": 3,
    "Procedure": 0,
    "CarePlan": 1
  },
  "cached": false
}
```

## FHIR R5 Specifics

This implementation uses FHIR R5 via `fhir.resources` 7.1.0:

| FHIR R4 | FHIR R5 |
|---------|---------|
| `medicationCodeableConcept` | `medication.concept` (CodeableReference) |
| `CarePlan.activity.detail` | `CarePlan.activity.performedActivity` |

## Caching

FHIR bundles are cached in the `extracted_notes.fhir_bundle` column:

```
┌─────────────────────────────────────────────────────────────┐
│                     extracted_notes                          │
├─────────────────────────────────────────────────────────────┤
│  id              │ Primary key                               │
│  document_id     │ Source document                           │
│  structured_data │ Part 4 extraction (JSON)                  │
│  fhir_bundle     │ Cached FHIR Bundle (JSON) ◀── /to_fhir   │
│  created_at      │ Timestamp                                 │
└─────────────────────────────────────────────────────────────┘
```

## Key Design Decisions

### 1. Library-Based Validation
Using `fhir.resources` library ensures spec-compliant output:
- Automatic field validation
- Proper data types
- Required fields enforced

### 2. Reference Linking
All resources reference the Patient via `subject`:
```python
{"reference": f"Patient/{patient_id}"}
```

### 3. Bundle Type
Uses `collection` type (not `transaction`) since this is read-only output, not intended for FHIR server submission.

### 4. Observation Categories
Vitals and labs are distinguished by category:
- `vital-signs`: BP, HR, Temp, etc.
- `laboratory`: LDL, A1C, etc.

## Tests

```bash
make test-part5  # 33 tests
```

| Category | Tests | Description |
|----------|-------|-------------|
| Mapper Unit Tests | 11 | Individual resource mapping |
| Bundler Tests | 3 | Bundle assembly |
| Converter Tests | 4 | End-to-end conversion |
| Endpoint Tests | 4 | API functionality |
| FHIR Compliance | 5 | Spec validation |
| Caching Tests | 5 | Cache behavior |

