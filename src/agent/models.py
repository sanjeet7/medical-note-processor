"""
FHIR-aligned Pydantic models for structured medical data extraction.

These models are designed to map directly to FHIR R4 resources:
- PatientInfo → FHIR Patient
- Condition → FHIR Condition
- Medication → FHIR MedicationRequest
- VitalSign → FHIR Observation (vital-signs)
- LabResult → FHIR Observation (laboratory)
- Procedure → FHIR Procedure
- CarePlanActivity → FHIR CarePlan
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import date, datetime
from enum import Enum


class Gender(str, Enum):
    """Patient gender aligned with FHIR administrative-gender"""
    MALE = "male"
    FEMALE = "female"
    OTHER = "other"
    UNKNOWN = "unknown"


class ClinicalStatus(str, Enum):
    """Condition clinical status aligned with FHIR condition-clinical"""
    ACTIVE = "active"
    RECURRENCE = "recurrence"
    RELAPSE = "relapse"
    INACTIVE = "inactive"
    REMISSION = "remission"
    RESOLVED = "resolved"


class VerificationStatus(str, Enum):
    """Condition verification status aligned with FHIR condition-ver-status"""
    UNCONFIRMED = "unconfirmed"
    PROVISIONAL = "provisional"
    DIFFERENTIAL = "differential"
    CONFIRMED = "confirmed"
    REFUTED = "refuted"
    ENTERED_IN_ERROR = "entered-in-error"


class MedicationStatus(str, Enum):
    """Medication request status aligned with FHIR medicationrequest-status"""
    ACTIVE = "active"
    ON_HOLD = "on-hold"
    CANCELLED = "cancelled"
    COMPLETED = "completed"
    STOPPED = "stopped"
    DRAFT = "draft"
    UNKNOWN = "unknown"


class CarePlanStatus(str, Enum):
    """Care plan activity status aligned with FHIR care-plan-activity-status"""
    NOT_STARTED = "not-started"
    SCHEDULED = "scheduled"
    IN_PROGRESS = "in-progress"
    ON_HOLD = "on-hold"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    STOPPED = "stopped"
    UNKNOWN = "unknown"


class ProcedureStatus(str, Enum):
    """Procedure status aligned with FHIR event-status"""
    PREPARATION = "preparation"
    IN_PROGRESS = "in-progress"
    NOT_DONE = "not-done"
    ON_HOLD = "on-hold"
    STOPPED = "stopped"
    COMPLETED = "completed"
    ENTERED_IN_ERROR = "entered-in-error"
    UNKNOWN = "unknown"


# ============================================================================
# Core Entity Models (FHIR-Aligned)
# ============================================================================

class CodeableConcept(BaseModel):
    """
    Represents a coded concept with optional code system.
    Maps to FHIR CodeableConcept.
    """
    code: Optional[str] = Field(None, description="The code value (e.g., ICD-10, RxNorm)")
    system: Optional[str] = Field(None, description="Code system URI (e.g., http://hl7.org/fhir/sid/icd-10-cm)")
    display: str = Field(..., description="Human-readable display text")
    
    model_config = {"extra": "forbid"}


class PatientInfo(BaseModel):
    """
    Patient demographics - maps to FHIR Patient resource.
    
    FHIR mapping:
    - identifier → Patient.identifier
    - name → Patient.name
    - birth_date → Patient.birthDate
    - gender → Patient.gender
    """
    identifier: Optional[str] = Field(None, description="Patient ID (e.g., 'patient--001')")
    name: Optional[str] = Field(None, description="Patient full name")
    birth_date: Optional[date] = Field(None, description="Date of birth (YYYY-MM-DD)")
    gender: Optional[Gender] = Field(None, description="Administrative gender")
    
    model_config = {"extra": "forbid"}


class Condition(BaseModel):
    """
    Medical condition/diagnosis - maps to FHIR Condition resource.
    
    FHIR mapping:
    - code → Condition.code (CodeableConcept with ICD-10)
    - clinical_status → Condition.clinicalStatus
    - verification_status → Condition.verificationStatus
    - onset_date → Condition.onsetDateTime
    - note → Condition.note
    """
    code: CodeableConcept = Field(..., description="Condition code with ICD-10 if available")
    clinical_status: ClinicalStatus = Field(
        default=ClinicalStatus.ACTIVE,
        description="Clinical status of the condition"
    )
    verification_status: VerificationStatus = Field(
        default=VerificationStatus.CONFIRMED,
        description="Verification status"
    )
    onset_date: Optional[date] = Field(None, description="When condition started")
    note: Optional[str] = Field(None, description="Additional clinical notes")
    
    model_config = {"extra": "forbid"}


class Dosage(BaseModel):
    """
    Medication dosage instructions - maps to FHIR Dosage.
    """
    text: Optional[str] = Field(None, description="Free text dosage instructions")
    dose_value: Optional[float] = Field(None, description="Dose amount")
    dose_unit: Optional[str] = Field(None, description="Dose unit (mg, mL, etc.)")
    route: Optional[str] = Field(None, description="Route of administration (oral, IV, etc.)")
    frequency: Optional[str] = Field(None, description="Frequency (daily, BID, TID, PRN, etc.)")
    
    model_config = {"extra": "forbid"}


class Medication(BaseModel):
    """
    Medication prescription - maps to FHIR MedicationRequest resource.
    
    FHIR mapping:
    - code → MedicationRequest.medicationCodeableConcept (with RxNorm)
    - status → MedicationRequest.status
    - dosage → MedicationRequest.dosageInstruction
    - dispense_quantity → MedicationRequest.dispenseRequest.quantity
    - refills → MedicationRequest.dispenseRequest.numberOfRepeatsAllowed
    """
    code: CodeableConcept = Field(..., description="Medication code with RxNorm if available")
    status: MedicationStatus = Field(
        default=MedicationStatus.ACTIVE,
        description="Status of the medication request"
    )
    dosage: Optional[Dosage] = Field(None, description="Dosage instructions")
    dispense_quantity: Optional[int] = Field(None, description="Number of units to dispense")
    refills: Optional[int] = Field(None, description="Number of refills allowed")
    as_needed: bool = Field(default=False, description="PRN medication flag")
    reason: Optional[str] = Field(None, description="Reason for medication")
    
    model_config = {"extra": "forbid"}


class VitalSign(BaseModel):
    """
    Vital sign measurement - maps to FHIR Observation (vital-signs category).
    
    FHIR mapping:
    - code → Observation.code
    - value/unit → Observation.valueQuantity
    - effective_datetime → Observation.effectiveDateTime
    """
    code: CodeableConcept = Field(..., description="Vital sign type (BP, HR, Temp, etc.)")
    value: float = Field(..., description="Measured value")
    unit: str = Field(..., description="Unit of measurement")
    value_string: Optional[str] = Field(None, description="String representation (e.g., '120/80')")
    effective_datetime: Optional[datetime] = Field(None, description="When measured")
    interpretation: Optional[str] = Field(None, description="Normal, high, low, etc.")
    
    model_config = {"extra": "forbid"}


class LabResult(BaseModel):
    """
    Laboratory test result - maps to FHIR Observation (laboratory category).
    
    FHIR mapping:
    - code → Observation.code
    - value/unit → Observation.valueQuantity
    - reference_range → Observation.referenceRange
    """
    code: CodeableConcept = Field(..., description="Lab test name/code")
    value: Optional[float] = Field(None, description="Numeric result value")
    value_string: Optional[str] = Field(None, description="String result if not numeric")
    unit: Optional[str] = Field(None, description="Unit of measurement")
    reference_range: Optional[str] = Field(None, description="Normal reference range")
    interpretation: Optional[str] = Field(None, description="Normal, abnormal, critical, etc.")
    effective_datetime: Optional[datetime] = Field(None, description="When collected/resulted")
    
    model_config = {"extra": "forbid"}


class Procedure(BaseModel):
    """
    Medical procedure - maps to FHIR Procedure resource.
    
    FHIR mapping:
    - code → Procedure.code (with ICD-10-PCS if available)
    - status → Procedure.status
    - performed_datetime → Procedure.performedDateTime
    - body_site → Procedure.bodySite
    """
    code: CodeableConcept = Field(..., description="Procedure code")
    status: ProcedureStatus = Field(
        default=ProcedureStatus.COMPLETED,
        description="Status of the procedure"
    )
    performed_datetime: Optional[datetime] = Field(None, description="When performed")
    body_site: Optional[str] = Field(None, description="Body site of procedure")
    note: Optional[str] = Field(None, description="Additional notes")
    
    model_config = {"extra": "forbid"}


class CarePlanActivity(BaseModel):
    """
    Care plan activity/recommendation - maps to FHIR CarePlan resource.
    
    FHIR mapping:
    - description → CarePlan.activity.detail.description
    - status → CarePlan.activity.detail.status
    - scheduled_date → CarePlan.activity.detail.scheduledTiming
    - category → CarePlan.category
    """
    description: str = Field(..., description="Activity description")
    status: CarePlanStatus = Field(
        default=CarePlanStatus.SCHEDULED,
        description="Activity status"
    )
    category: Optional[str] = Field(None, description="Category (follow-up, therapy, test, etc.)")
    scheduled_date: Optional[date] = Field(None, description="When scheduled")
    scheduled_string: Optional[str] = Field(None, description="Free text timing (e.g., 'in 3 months')")
    note: Optional[str] = Field(None, description="Additional instructions")
    
    model_config = {"extra": "forbid"}


class Provider(BaseModel):
    """
    Healthcare provider information - maps to FHIR Practitioner.
    """
    name: Optional[str] = Field(None, description="Provider name")
    specialty: Optional[str] = Field(None, description="Medical specialty")
    credentials: Optional[str] = Field(None, description="Credentials (MD, DO, NP, etc.)")
    
    model_config = {"extra": "forbid"}


class Encounter(BaseModel):
    """
    Clinical encounter information - maps to FHIR Encounter.
    """
    encounter_date: Optional[date] = Field(None, description="Encounter date")
    encounter_type: Optional[str] = Field(None, description="Type of encounter (follow-up, annual physical, etc.)")
    reason: Optional[str] = Field(None, description="Reason for visit")
    
    model_config = {"extra": "forbid"}


# ============================================================================
# Aggregate Model - Complete Structured Note
# ============================================================================

class StructuredNote(BaseModel):
    """
    Complete structured representation of a medical note.
    This is the primary output of the extraction agent.
    
    Contains all extracted entities ready for FHIR Bundle conversion in Part 5.
    """
    # Patient and encounter context
    patient: Optional[PatientInfo] = Field(None, description="Patient demographics")
    encounter: Optional[Encounter] = Field(None, description="Encounter information")
    provider: Optional[Provider] = Field(None, description="Attending provider")
    
    # Clinical entities
    conditions: List[Condition] = Field(default_factory=list, description="Diagnoses and conditions")
    medications: List[Medication] = Field(default_factory=list, description="Medications prescribed")
    vital_signs: List[VitalSign] = Field(default_factory=list, description="Vital sign measurements")
    lab_results: List[LabResult] = Field(default_factory=list, description="Laboratory results")
    procedures: List[Procedure] = Field(default_factory=list, description="Procedures performed")
    care_plan: List[CarePlanActivity] = Field(default_factory=list, description="Care plan activities")
    
    # Metadata
    source_text: Optional[str] = Field(None, description="Original SOAP note text")
    extraction_timestamp: Optional[datetime] = Field(None, description="When extraction was performed")
    
    model_config = {"extra": "forbid"}
    
    def entity_count(self) -> dict:
        """Return count of each entity type extracted."""
        return {
            "patient": 1 if self.patient else 0,
            "encounter": 1 if self.encounter else 0,
            "provider": 1 if self.provider else 0,
            "conditions": len(self.conditions),
            "medications": len(self.medications),
            "vital_signs": len(self.vital_signs),
            "lab_results": len(self.lab_results),
            "procedures": len(self.procedures),
            "care_plan": len(self.care_plan),
        }


# ============================================================================
# Raw Extraction Models (Pre-enrichment)
# ============================================================================

class RawCondition(BaseModel):
    """Condition before ICD-10 enrichment."""
    name: str = Field(..., description="Condition name as extracted")
    clinical_status: Optional[str] = Field(None, description="Raw status text")
    note: Optional[str] = Field(None)


class RawMedication(BaseModel):
    """Medication before RxNorm enrichment."""
    name: str = Field(..., description="Medication name as extracted")
    dose: Optional[str] = Field(None, description="Dose as written")
    route: Optional[str] = Field(None)
    frequency: Optional[str] = Field(None)
    quantity: Optional[int] = Field(None)
    refills: Optional[int] = Field(None)
    as_needed: bool = Field(default=False)
    reason: Optional[str] = Field(None)


class RawProcedure(BaseModel):
    """Procedure before code enrichment."""
    name: str = Field(..., description="Procedure name as extracted")
    body_site: Optional[str] = Field(None)
    date: Optional[str] = Field(None)
    status: Optional[str] = Field(None)
    note: Optional[str] = Field(None)


class RawExtraction(BaseModel):
    """
    Raw extraction output from LLM before code enrichment.
    This is the intermediate format before ICD-10/RxNorm lookup.
    """
    # Patient and context
    patient_id: Optional[str] = None
    patient_name: Optional[str] = None
    patient_dob: Optional[str] = None
    patient_gender: Optional[str] = None
    
    # Encounter
    encounter_date: Optional[str] = None
    encounter_type: Optional[str] = None
    encounter_reason: Optional[str] = None
    
    # Provider
    provider_name: Optional[str] = None
    provider_specialty: Optional[str] = None
    
    # Clinical entities (raw - to be enriched)
    conditions: List[RawCondition] = Field(default_factory=list)
    medications: List[RawMedication] = Field(default_factory=list)
    procedures: List[RawProcedure] = Field(default_factory=list)
    
    # Already structured (no enrichment needed)
    vital_signs: List[dict] = Field(default_factory=list)
    lab_results: List[dict] = Field(default_factory=list)
    care_plan: List[dict] = Field(default_factory=list)

