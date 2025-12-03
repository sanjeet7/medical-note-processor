from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List
from . import models, schemas, database
from .config import settings

from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database tables on startup"""
    models.Base.metadata.create_all(bind=database.engine)
    print("✅ Database tables created")
    yield

# Create FastAPI application
app = FastAPI(
    title=settings.app_name,
    description="Medical Note Processing System - AI Engineer Take Home",
    version="1.0.0",
    lifespan=lifespan
)

# ============================================================================
# PART 1 ENDPOINTS
# ============================================================================

@app.get("/health", response_model=schemas.HealthResponse)
def health_check():
    """
    Health check endpoint - returns {"status": "ok"}
    
    This endpoint verifies the server is running properly.
    """
    return {"status": "ok"}

@app.get("/documents", response_model=List[int])
def get_documents(db: Session = Depends(database.get_db)):
    """
    Fetch all document IDs from database
    
    Returns a list of all document IDs for retrieval or processing.
    """
    documents = db.query(models.Document.id).all()
    return [doc.id for doc in documents]

@app.post("/documents", response_model=schemas.DocumentResponse, status_code=status.HTTP_201_CREATED)
def create_document(
    document: schemas.DocumentCreate,
    db: Session = Depends(database.get_db)
):
    """
    Create a new document with validation
    
    Accepts:
    - title: Document title (1-255 characters)
    - content: Document content (minimum 1 character)
    - doc_type: Type of document (e.g., 'soap_note', 'guideline')
    - doc_metadata: Additional metadata as JSON
    
    Returns the created document with ID and timestamp.
    """
    db_document = models.Document(**document.model_dump())
    db.add(db_document)
    db.commit()
    db.refresh(db_document)
    return db_document

@app.get("/documents/{document_id}", response_model=schemas.DocumentResponse)
def get_document(document_id: int, db: Session = Depends(database.get_db)):
    """
    Fetch a specific document by ID
    
    Returns:
    - Document with all fields if found
    - 404 error if document doesn't exist
    """
    document = db.query(models.Document).filter(models.Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    return document

@app.put("/documents/{document_id}", response_model=schemas.DocumentResponse)
def update_document(
    document_id: int,
    document: schemas.DocumentUpdate,
    db: Session = Depends(database.get_db)
):
    """
    Update an existing document (partial update supported)
    
    Updates only the provided fields of the document.
    Returns 404 if document doesn't exist.
    """
    db_document = db.query(models.Document).filter(models.Document.id == document_id).first()
    if not db_document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Only update fields that are provided (not None)
    update_data = document.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_document, key, value)
    
    db.commit()
    db.refresh(db_document)
    return db_document

@app.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(document_id: int, db: Session = Depends(database.get_db)):
    """
    Delete a document by ID
    
    Returns:
    - 204 No Content if successful
    - 404 error if document doesn't exist
    """
    db_document = db.query(models.Document).filter(models.Document.id == document_id).first()
    if not db_document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    db.delete(db_document)
    db.commit()
    return None

from .services.llm_service import LLMService
from .schemas import SummarizeRequest, SummarizeResponse, QueryRequest, QueryResponse

@app.post("/summarize_note", response_model=SummarizeResponse)
async def summarize_note(
    request: SummarizeRequest,
    db: Session = Depends(database.get_db)
):
    """Summarize a medical note using LLM with caching"""
    try:
        # Get text from document_id or use provided text
        if request.document_id:
            document = db.query(models.Document).filter(
                models.Document.id == request.document_id
            ).first()
            if not document:
                raise HTTPException(status_code=404, detail="Document not found")
            note_text = document.content
        elif request.text:
            note_text = request.text
        else:
            raise HTTPException(status_code=400, detail="Either document_id or text must be provided")
        
        service = LLMService(db)
        result = await service.summarize_note(note_text)
        # Map generic result to specific response schema
        return {
            "summary": result["result"],
            "cached": result["cached"],
            "provider": result["provider"],
            "model": result["model"]
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"LLM summarization failed: {str(e)}"
        )

@app.post("/query_note", response_model=QueryResponse)
async def query_note(
    request: QueryRequest,
    db: Session = Depends(database.get_db)
):
    """Query a medical note using LLM with caching"""
    try:
        # Get text from document_id or use provided text
        if request.document_id:
            document = db.query(models.Document).filter(
                models.Document.id == request.document_id
            ).first()
            if not document:
                raise HTTPException(status_code=404, detail="Document not found")
            note_text = document.content
        elif request.text:
            note_text = request.text
        else:
            raise HTTPException(status_code=400, detail="Either document_id or text must be provided")
        
        service = LLMService(db)
        result = await service.query_note(note_text, request.query)
        return {
            "answer": result["result"],
            "cached": result["cached"],
            "provider": result["provider"],
            "model": result["model"]
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"LLM query failed: {str(e)}"
        )

# ============================================================================
# PART 3 ENDPOINT - RAG Pipeline
# ============================================================================

from .rag.service import RAGService
from .schemas import AnswerQuestionRequest, AnswerQuestionResponse, SourceCitation

@app.post("/answer_question", response_model=AnswerQuestionResponse)
async def answer_question(request: AnswerQuestionRequest):
    """
    Answer medical questions using RAG over medical guidelines.
    
    Pipeline:
    1. Query reformulation for better recall
    2. Hybrid retrieval (vector search + LLM reranking)
    3. Dynamic filtering by relevance threshold (>= 0.7)
    4. Answer generation with inline citations
    5. Confidence assessment
    
    Returns:
    - Answer with inline citation markers [1], [2], etc.
    - List of source citations with document, section, and relevance scores
    - Overall confidence score (0.0-1.0)
    - Number of chunks retrieved
    """
    try:
        rag_service = RAGService()
        rag_answer = await rag_service.answer_question(request.question)
        
        # Convert to response schema
        return AnswerQuestionResponse(
            answer=rag_answer.answer,
            sources=[
                SourceCitation(
                    id=source.id,
                    document=source.document,
                    section=source.section,
                    text=source.text
                )
                for source in rag_answer.sources
            ],
            confidence=rag_answer.confidence,
            retrieved_count=rag_answer.retrieved_count
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"RAG question answering failed: {str(e)}"
        )


# ============================================================================
# PART 4 ENDPOINT - Structured Data Extraction Agent
# ============================================================================

from .agent import ExtractionAgent
from .schemas import (
    ExtractStructuredRequest,
    ExtractStructuredResponse,
    StructuredNoteResponse,
    TrajectoryResponse,
    TrajectoryStepResponse,
    PatientResponse,
    ConditionResponse,
    MedicationResponse,
    VitalSignResponse,
    LabResultResponse,
    ProcedureResponse,
    CarePlanResponse,
    EncounterResponse,
    ProviderResponse,
    CodeableConceptResponse,
    DosageResponse,
)


def _convert_structured_note(note) -> StructuredNoteResponse:
    """Convert StructuredNote model to response schema."""
    
    def convert_codeable(code) -> CodeableConceptResponse:
        return CodeableConceptResponse(
            code=code.code,
            system=code.system,
            display=code.display
        )
    
    def convert_dosage(dosage) -> DosageResponse:
        if not dosage:
            return None
        return DosageResponse(
            text=dosage.text,
            dose_value=dosage.dose_value,
            dose_unit=dosage.dose_unit,
            route=dosage.route,
            frequency=dosage.frequency
        )
    
    return StructuredNoteResponse(
        patient=PatientResponse(
            identifier=note.patient.identifier,
            name=note.patient.name,
            birth_date=str(note.patient.birth_date) if note.patient.birth_date else None,
            gender=note.patient.gender.value if note.patient.gender else None
        ) if note.patient else None,
        
        encounter=EncounterResponse(
            date=str(note.encounter.encounter_date) if note.encounter and note.encounter.encounter_date else None,
            type=note.encounter.encounter_type if note.encounter else None,
            reason=note.encounter.reason if note.encounter else None
        ) if note.encounter else None,
        
        provider=ProviderResponse(
            name=note.provider.name if note.provider else None,
            specialty=note.provider.specialty if note.provider else None,
            credentials=note.provider.credentials if note.provider else None
        ) if note.provider else None,
        
        conditions=[
            ConditionResponse(
                code=convert_codeable(c.code),
                clinical_status=c.clinical_status.value,
                verification_status=c.verification_status.value,
                onset_date=str(c.onset_date) if c.onset_date else None,
                note=c.note
            )
            for c in note.conditions
        ],
        
        medications=[
            MedicationResponse(
                code=convert_codeable(m.code),
                status=m.status.value,
                dosage=convert_dosage(m.dosage),
                dispense_quantity=m.dispense_quantity,
                refills=m.refills,
                as_needed=m.as_needed,
                reason=m.reason
            )
            for m in note.medications
        ],
        
        vital_signs=[
            VitalSignResponse(
                code=convert_codeable(v.code),
                value=v.value,
                unit=v.unit,
                value_string=v.value_string,
                interpretation=v.interpretation
            )
            for v in note.vital_signs
        ],
        
        lab_results=[
            LabResultResponse(
                code=convert_codeable(l.code),
                value=l.value,
                value_string=l.value_string,
                unit=l.unit,
                reference_range=l.reference_range,
                interpretation=l.interpretation
            )
            for l in note.lab_results
        ],
        
        procedures=[
            ProcedureResponse(
                code=convert_codeable(p.code),
                status=p.status.value,
                body_site=p.body_site,
                note=p.note
            )
            for p in note.procedures
        ],
        
        care_plan=[
            CarePlanResponse(
                description=c.description,
                status=c.status.value,
                category=c.category,
                scheduled_string=c.scheduled_string,
                note=c.note
            )
            for c in note.care_plan
        ],
        
        extraction_timestamp=note.extraction_timestamp.isoformat() if note.extraction_timestamp else None
    )


def _convert_trajectory(trajectory) -> TrajectoryResponse:
    """Convert Trajectory model to response schema."""
    return TrajectoryResponse(
        agent_name=trajectory.agent_name,
        started_at=trajectory.started_at.isoformat(),
        completed_at=trajectory.completed_at.isoformat() if trajectory.completed_at else None,
        success=trajectory.success,
        total_duration_ms=trajectory.total_duration_ms,
        steps=[
            TrajectoryStepResponse(
                step_number=s.step_number,
                step_name=s.step_name,
                tool_name=s.tool_name,
                status=s.status.value,
                duration_ms=s.duration_ms,
                input_summary=s.input_summary,
                output_summary=s.output_summary,
                error=s.error
            )
            for s in trajectory.steps
        ],
        statistics=trajectory.get_statistics()
    )


def _count_fhir_resources(bundle_dict: dict) -> dict:
    """Count resources in a FHIR Bundle by type."""
    counts = {}
    entries = bundle_dict.get("entry", [])
    for entry in entries:
        resource = entry.get("resource", {})
        resource_type = resource.get("resourceType", "Unknown")
        
        # Differentiate Observation types by category
        if resource_type == "Observation":
            categories = resource.get("category", [])
            for cat in categories:
                codings = cat.get("coding", [])
                for coding in codings:
                    code = coding.get("code", "")
                    if code == "vital-signs":
                        resource_type = "Observation (vital-signs)"
                        break
                    elif code == "laboratory":
                        resource_type = "Observation (laboratory)"
                        break
        
        counts[resource_type] = counts.get(resource_type, 0) + 1
    
    return counts


@app.post("/extract_structured", response_model=ExtractStructuredResponse)
async def extract_structured(
    request: ExtractStructuredRequest,
    db: Session = Depends(database.get_db)
):
    """
    Extract structured medical data from a SOAP note using an agent pipeline.
    
    Pipeline Steps:
    1. Entity Extraction (LLM) - Extract raw entities from SOAP note
    2. ICD-10 Enrichment (NIH API) - Look up diagnosis codes
    3. RxNorm Enrichment (NIH API) - Look up medication codes
    4. Validation (Pydantic) - Validate and assemble final output
    
    Caching:
    - If use_cache=True (default) and document_id is provided, returns cached
      extraction if one exists for that document
    - Set use_cache=False to force re-extraction
    
    Returns:
    - extracted_note_id: ID of stored extraction (for use with /to_fhir)
    - document_id: Source document ID (if extraction was from document)
    - Structured data with patient info, conditions (with ICD-10), medications (with RxNorm),
      vital signs, lab results, procedures, and care plan activities
    - Optional execution trajectory for debugging
    - Entity counts for quick summary
    - cached: True if result was returned from cache
    
    The output is FHIR-aligned and stored in database for FHIR conversion.
    """
    try:
        # Get text from document_id or use provided text
        document_id = None
        if request.document_id:
            document = db.query(models.Document).filter(
                models.Document.id == request.document_id
            ).first()
            if not document:
                raise HTTPException(status_code=404, detail="Document not found")
            note_text = document.content
            document_id = request.document_id
            
            # Check cache if enabled
            if request.use_cache:
                cached_extraction = db.query(models.ExtractedNote).filter(
                    models.ExtractedNote.document_id == document_id
                ).order_by(models.ExtractedNote.created_at.desc()).first()
                
                if cached_extraction:
                    # Return cached extraction
                    return ExtractStructuredResponse(
                        success=True,
                        extracted_note_id=cached_extraction.id,
                        document_id=document_id,
                        structured_data=StructuredNoteResponse(**cached_extraction.structured_data),
                        entity_counts=cached_extraction.entity_counts,
                        cached=True
                    )
        elif request.text:
            note_text = request.text
        else:
            raise HTTPException(
                status_code=400,
                detail="Either document_id or text must be provided"
            )
        
        # Run extraction agent
        agent = ExtractionAgent()
        result = await agent.extract(note_text)
        
        # Build response
        response = ExtractStructuredResponse(
            success=result.success,
            document_id=document_id,
            error=result.error,
            cached=False
        )
        
        if result.success and result.structured_note:
            response.structured_data = _convert_structured_note(result.structured_note)
            response.entity_counts = result.structured_note.entity_count()
            
            # Store extraction in database for FHIR conversion
            extracted_note = models.ExtractedNote(
                document_id=document_id,
                structured_data=response.structured_data.model_dump(),
                entity_counts=response.entity_counts
            )
            db.add(extracted_note)
            db.commit()
            db.refresh(extracted_note)
            response.extracted_note_id = extracted_note.id
        
        if request.include_trajectory and result.trajectory:
            response.trajectory = _convert_trajectory(result.trajectory)
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Structured extraction failed: {str(e)}"
        )


# ============================================================================
# PART 5 ENDPOINT - FHIR Conversion
# ============================================================================

from .fhir import FHIRConverter
from .schemas import ToFHIRRequest, ToFHIRResponse


@app.post("/to_fhir", response_model=ToFHIRResponse)
async def convert_to_fhir(
    request: ToFHIRRequest,
    db: Session = Depends(database.get_db)
):
    """
    Convert structured medical data to FHIR R5 Bundle.
    
    Accepts one of:
    - extracted_note_id: ID of a previously extracted note
    - document_id: ID of source document (uses latest extraction)
    - structured_data: Raw structured data to convert directly
    
    Caching:
    - If use_cache=True (default) and using extracted_note_id or document_id,
      returns cached FHIR bundle if one exists
    - Set use_cache=False to force re-conversion
    
    Returns:
    - FHIR Bundle (collection type) containing:
      - Patient resource
      - Condition resources (with ICD-10 codes)
      - MedicationRequest resources (with RxNorm codes)
      - Observation resources (vital signs and lab results)
      - Procedure resources
      - CarePlan resource
    - Resource counts for each type
    - cached: True if result was returned from cache
    
    The output is FHIR R5 spec-compliant using the fhir.resources library.
    """
    try:
        structured_data = None
        extracted_note = None
        
        # Get structured data from one of the sources
        if request.extracted_note_id:
            # Look up by extracted_note_id
            extracted_note = db.query(models.ExtractedNote).filter(
                models.ExtractedNote.id == request.extracted_note_id
            ).first()
            if not extracted_note:
                raise HTTPException(
                    status_code=404,
                    detail=f"Extracted note with ID {request.extracted_note_id} not found"
                )
            
            # Check for cached FHIR bundle
            if request.use_cache and extracted_note.fhir_bundle:
                return ToFHIRResponse(
                    success=True,
                    bundle=extracted_note.fhir_bundle,
                    resource_counts=_count_fhir_resources(extracted_note.fhir_bundle),
                    cached=True
                )
            
            structured_data = extracted_note.structured_data
            
        elif request.document_id:
            # Look up latest extraction for document
            extracted_note = db.query(models.ExtractedNote).filter(
                models.ExtractedNote.document_id == request.document_id
            ).order_by(models.ExtractedNote.created_at.desc()).first()
            if not extracted_note:
                raise HTTPException(
                    status_code=404,
                    detail=f"No extraction found for document ID {request.document_id}. "
                           f"Run /extract_structured first."
                )
            
            # Check for cached FHIR bundle
            if request.use_cache and extracted_note.fhir_bundle:
                return ToFHIRResponse(
                    success=True,
                    bundle=extracted_note.fhir_bundle,
                    resource_counts=_count_fhir_resources(extracted_note.fhir_bundle),
                    cached=True
                )
            
            structured_data = extracted_note.structured_data
            
        elif request.structured_data:
            # Use provided structured data directly (no caching possible)
            structured_data = request.structured_data.model_dump()
        else:
            raise HTTPException(
                status_code=400,
                detail="One of extracted_note_id, document_id, or structured_data must be provided"
            )
        
        # Convert to FHIR
        converter = FHIRConverter()
        result = converter.convert(structured_data)
        
        if result.success:
            # Convert bundle to JSON-serializable dict (handles datetime, etc.)
            import json
            bundle_json = json.loads(result.bundle.json(exclude_none=True))
            
            # Cache the FHIR bundle if we have an extracted_note
            if extracted_note:
                extracted_note.fhir_bundle = bundle_json
                db.commit()
            
            return ToFHIRResponse(
                success=True,
                bundle=bundle_json,
                resource_counts=result.resource_counts,
                cached=False
            )
        else:
            return ToFHIRResponse(
                success=False,
                error=result.error,
                cached=False
            )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"FHIR conversion failed: {str(e)}"
        )
