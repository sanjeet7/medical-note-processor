from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, Dict, List

# Health check schema
class HealthResponse(BaseModel):
    """Health check response"""
    status: str

# Document schemas
class DocumentBase(BaseModel):
    """Base schema for document with validation"""
    title: str = Field(..., min_length=1, max_length=255)
    content: str = Field(..., min_length=1)
    doc_type: str = "general"
    doc_metadata: Dict = Field(default_factory=dict)

class DocumentCreate(DocumentBase):
    """Schema for creating a new document"""
    pass

class DocumentUpdate(BaseModel):
    """Schema for updating a document (all fields optional)"""
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    content: Optional[str] = Field(None, min_length=1)
    doc_type: Optional[str] = None
    doc_metadata: Optional[Dict] = None

class DocumentResponse(DocumentBase):
    """Schema for document response with all fields"""
    id: int
    created_at: datetime
    
    model_config = {"from_attributes": True}

# Summarization schemas (for Part 2)
class SummarizeRequest(BaseModel):
    """Request schema for note summarization"""
    document_id: Optional[int] = None
    text: Optional[str] = Field(None, min_length=1)
    
    @classmethod
    def validate_input(cls, values):
        if not values.get('document_id') and not values.get('text'):
            raise ValueError("Either document_id or text must be provided")
        return values

class SummarizeResponse(BaseModel):
    """Response schema for note summarization"""
    summary: str
    cached: bool
    provider: str
    model: str

# Query schemas
class QueryRequest(BaseModel):
    """Request schema for note querying"""
    document_id: Optional[int] = None
    text: Optional[str] = Field(None, min_length=1)
    query: str = Field(..., min_length=1)
    
    @classmethod
    def validate_input(cls, values):
        if not values.get('document_id') and not values.get('text'):
            raise ValueError("Either document_id or text must be provided")
        return values

class QueryResponse(BaseModel):
    """Response schema for note querying"""
    answer: str
    cached: bool
    provider: str
    model: str

class QueryNoteRequest(BaseModel):
    document_id: int = Field(..., description="ID of document to query")
    query: str = Field(..., min_length=1, max_length=1000, description="Question about the document")


class QueryNoteResponse(BaseModel):
    answer: str
    document_id: int
    document_title: str
    cached: bool
    provider: str
    model: str


# RAG Schemas (Part 3)
class AnswerQuestionRequest(BaseModel):
    """Request for answering questions using RAG over medical guidelines"""
    question: str = Field(..., min_length=1, max_length=2000, description="Medical question")


class SourceCitation(BaseModel):
    """Citation to source document chunk"""
    id: int = Field(..., description="Citation number")
    document: str = Field(..., description="Source document name")
    section: str = Field(..., description="Section title from document")
    text: str = Field(..., description="Relevant excerpt from document")


class AnswerQuestionResponse(BaseModel):
    """Response with answer, citations, and confidence"""
    answer: str = Field(..., description="Answer to question with inline citations")
    sources: List[SourceCitation] = Field(..., description="Source citations")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Overall confidence in answer")
    retrieved_count: int = Field(..., description="Number of chunks retrieved")


# ============================================================================
# Part 4: Structured Data Extraction Schemas
# ============================================================================

class ExtractStructuredRequest(BaseModel):
    """Request for structured data extraction from SOAP notes"""
    document_id: Optional[int] = Field(None, description="ID of document to extract from")
    text: Optional[str] = Field(None, min_length=1, description="Raw SOAP note text")
    include_trajectory: bool = Field(default=True, description="Include execution trajectory in response")
    use_cache: bool = Field(default=True, description="Return cached extraction if available for document_id")
    
    @classmethod
    def validate_input(cls, values):
        if not values.get('document_id') and not values.get('text'):
            raise ValueError("Either document_id or text must be provided")
        return values


class TrajectoryStepResponse(BaseModel):
    """A single step in the execution trajectory"""
    step_number: int
    step_name: str
    tool_name: str
    status: str
    duration_ms: Optional[float] = None
    input_summary: Optional[str] = None
    output_summary: Optional[str] = None
    error: Optional[str] = None


class TrajectoryResponse(BaseModel):
    """Execution trajectory for debugging and audit"""
    agent_name: str
    started_at: str
    completed_at: Optional[str] = None
    success: bool
    total_duration_ms: Optional[float] = None
    steps: List[TrajectoryStepResponse]
    statistics: Dict


class CodeableConceptResponse(BaseModel):
    """Coded medical concept (ICD-10, RxNorm, etc.)"""
    code: Optional[str] = Field(None, description="Standard code (ICD-10, RxNorm)")
    system: Optional[str] = Field(None, description="Code system URI")
    display: str = Field(..., description="Human-readable display text")


class PatientResponse(BaseModel):
    """Patient demographics"""
    identifier: Optional[str] = None
    name: Optional[str] = None
    birth_date: Optional[str] = None
    gender: Optional[str] = None


class ConditionResponse(BaseModel):
    """Medical condition/diagnosis with ICD-10 code"""
    code: CodeableConceptResponse
    clinical_status: str
    verification_status: str
    onset_date: Optional[str] = None
    note: Optional[str] = None


class DosageResponse(BaseModel):
    """Medication dosage information"""
    text: Optional[str] = None
    dose_value: Optional[float] = None
    dose_unit: Optional[str] = None
    route: Optional[str] = None
    frequency: Optional[str] = None


class MedicationResponse(BaseModel):
    """Medication with RxNorm code"""
    code: CodeableConceptResponse
    status: str
    dosage: Optional[DosageResponse] = None
    dispense_quantity: Optional[int] = None
    refills: Optional[int] = None
    as_needed: bool = False
    reason: Optional[str] = None


class VitalSignResponse(BaseModel):
    """Vital sign measurement"""
    code: CodeableConceptResponse
    value: float
    unit: str
    value_string: Optional[str] = None
    interpretation: Optional[str] = None


class LabResultResponse(BaseModel):
    """Laboratory test result"""
    code: CodeableConceptResponse
    value: Optional[float] = None
    value_string: Optional[str] = None
    unit: Optional[str] = None
    reference_range: Optional[str] = None
    interpretation: Optional[str] = None


class ProcedureResponse(BaseModel):
    """Medical procedure"""
    code: CodeableConceptResponse
    status: str
    body_site: Optional[str] = None
    note: Optional[str] = None


class CarePlanResponse(BaseModel):
    """Care plan activity"""
    description: str
    status: str
    category: Optional[str] = None
    scheduled_string: Optional[str] = None
    note: Optional[str] = None


class EncounterResponse(BaseModel):
    """Clinical encounter"""
    date: Optional[str] = None
    type: Optional[str] = None
    reason: Optional[str] = None


class ProviderResponse(BaseModel):
    """Healthcare provider"""
    name: Optional[str] = None
    specialty: Optional[str] = None
    credentials: Optional[str] = None


class StructuredNoteResponse(BaseModel):
    """Complete structured extraction from SOAP note"""
    patient: Optional[PatientResponse] = None
    encounter: Optional[EncounterResponse] = None
    provider: Optional[ProviderResponse] = None
    conditions: List[ConditionResponse] = Field(default_factory=list)
    medications: List[MedicationResponse] = Field(default_factory=list)
    vital_signs: List[VitalSignResponse] = Field(default_factory=list)
    lab_results: List[LabResultResponse] = Field(default_factory=list)
    procedures: List[ProcedureResponse] = Field(default_factory=list)
    care_plan: List[CarePlanResponse] = Field(default_factory=list)
    extraction_timestamp: Optional[str] = None


class ExtractStructuredResponse(BaseModel):
    """Response with structured data and optional trajectory"""
    success: bool = Field(..., description="Whether extraction succeeded")
    extracted_note_id: Optional[int] = Field(None, description="ID of stored extraction for FHIR conversion")
    document_id: Optional[int] = Field(None, description="Source document ID if extraction was from document")
    structured_data: Optional[StructuredNoteResponse] = Field(None, description="Extracted structured data")
    entity_counts: Optional[Dict[str, int]] = Field(None, description="Count of each entity type")
    trajectory: Optional[TrajectoryResponse] = Field(None, description="Execution trajectory for debugging")
    error: Optional[str] = Field(None, description="Error message if extraction failed")
    cached: bool = Field(default=False, description="True if result was returned from cache")


# ============================================================================
# Part 5: FHIR Conversion Schemas
# ============================================================================

class ToFHIRRequest(BaseModel):
    """Request for FHIR conversion"""
    extracted_note_id: Optional[int] = Field(None, description="ID of extracted note to convert")
    document_id: Optional[int] = Field(None, description="Document ID (uses latest extraction)")
    structured_data: Optional[StructuredNoteResponse] = Field(None, description="Raw structured data to convert")
    use_cache: bool = Field(default=True, description="Return cached FHIR bundle if available")
    
    @classmethod
    def validate_input(cls, values):
        if not values.get('extracted_note_id') and not values.get('document_id') and not values.get('structured_data'):
            raise ValueError("One of extracted_note_id, document_id, or structured_data must be provided")
        return values


class ToFHIRResponse(BaseModel):
    """FHIR Bundle response"""
    success: bool = Field(..., description="Whether conversion succeeded")
    bundle: Optional[Dict] = Field(None, description="FHIR Bundle containing all resources")
    resource_counts: Optional[Dict[str, int]] = Field(None, description="Count of each FHIR resource type")
    error: Optional[str] = Field(None, description="Error message if conversion failed")
    cached: bool = Field(default=False, description="True if result was returned from cache")
