"""
Medical Data Extraction Agent

A tool-based agent system for extracting structured medical data from SOAP notes.

Components:
- ExtractionAgent: Main orchestrator with ReAct-style pipeline
- Tools: Entity extraction, ICD-10 lookup, RxNorm lookup, validation
- Models: FHIR-aligned Pydantic schemas
- Trajectory: Execution audit trail logging

Usage:
    from src.agent import ExtractionAgent
    
    agent = ExtractionAgent()
    result = await agent.extract(soap_note_text)
    
    if result.success:
        structured_note = result.structured_note
        print(f"Extracted {sum(structured_note.entity_count().values())} entities")
"""
from src.agent.orchestrator import ExtractionAgent, ExtractionResult
from src.agent.models import (
    StructuredNote,
    PatientInfo,
    Condition,
    Medication,
    VitalSign,
    LabResult,
    Procedure,
    CarePlanActivity,
    Provider,
    Encounter,
    CodeableConcept,
    Dosage,
)
from src.agent.trajectory import Trajectory, TrajectoryStep, TrajectoryLogger

__all__ = [
    # Agent
    "ExtractionAgent",
    "ExtractionResult",
    
    # Models
    "StructuredNote",
    "PatientInfo",
    "Condition",
    "Medication",
    "VitalSign",
    "LabResult",
    "Procedure",
    "CarePlanActivity",
    "Provider",
    "Encounter",
    "CodeableConcept",
    "Dosage",
    
    # Trajectory
    "Trajectory",
    "TrajectoryStep",
    "TrajectoryLogger",
]

