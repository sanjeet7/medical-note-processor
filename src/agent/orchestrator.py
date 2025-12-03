"""
Extraction Agent Orchestrator - ReAct-style pipeline for medical data extraction.

This is the main agent that orchestrates the extraction pipeline:
1. Entity Extraction (LLM) - Extract raw entities from SOAP note
2. Code Enrichment (NIH APIs) - Look up ICD-10 and RxNorm codes
3. Validation (Pydantic) - Validate and assemble final output

The agent follows a ReAct (Reasoning + Acting) pattern with full trajectory logging.
"""
import asyncio
from datetime import datetime, date
from typing import Optional, List, Dict, Any
from dataclasses import dataclass

from src.agent.models import (
    StructuredNote, PatientInfo, Condition, Medication, VitalSign,
    LabResult, Procedure, CarePlanActivity, Provider, Encounter,
    CodeableConcept, Dosage, Gender, ClinicalStatus, VerificationStatus,
    MedicationStatus, CarePlanStatus, ProcedureStatus,
    RawExtraction, RawCondition, RawMedication, RawProcedure
)
from src.agent.trajectory import TrajectoryLogger, Trajectory
from src.agent.tools.extractor import EntityExtractionTool
from src.agent.tools.icd_lookup import ICD10LookupTool, ICD10Code
from src.agent.tools.rxnorm_lookup import RxNormLookupTool, RxNormCode
from src.agent.tools.validator import ValidationTool


@dataclass
class ExtractionResult:
    """Result of the extraction pipeline."""
    structured_note: Optional[StructuredNote]
    trajectory: Trajectory
    success: bool
    error: Optional[str] = None


class ExtractionAgent:
    """
    Medical data extraction agent using ReAct-style tool orchestration.
    
    Pipeline Steps:
    1. THINK: Analyze SOAP note structure
    2. ACT: Extract entities using LLM
    3. ACT: Enrich conditions with ICD-10 codes (parallel)
    4. ACT: Enrich medications with RxNorm codes (parallel)
    5. ACT: Transform raw data to structured models
    6. ACT: Validate final output
    7. OBSERVE: Return structured note with trajectory
    
    Features:
    - Parallel code lookups for performance
    - Graceful degradation (missing codes don't block extraction)
    - Full trajectory logging for debugging
    - FHIR-aligned output
    """
    
    def __init__(self):
        """Initialize the extraction agent with all tools."""
        self.extractor = EntityExtractionTool()
        self.icd_lookup = ICD10LookupTool()
        self.rxnorm_lookup = RxNormLookupTool()
        self.validator = ValidationTool()
        
        self._trajectory_logger: Optional[TrajectoryLogger] = None
    
    async def extract(self, soap_note: str) -> ExtractionResult:
        """
        Extract structured data from a SOAP note.
        
        This is the main entry point for the extraction pipeline.
        
        Args:
            soap_note: Raw SOAP note text
            
        Returns:
            ExtractionResult with structured note and trajectory
        """
        # Initialize trajectory logging
        note_preview = soap_note[:100] + "..." if len(soap_note) > 100 else soap_note
        self._trajectory_logger = TrajectoryLogger(
            agent_name="ExtractionAgent",
            input_summary=f"SOAP note ({len(soap_note)} chars): {note_preview}"
        )
        
        try:
            # Step 1: Extract raw entities from SOAP note
            raw_extraction = await self._step_extract_entities(soap_note)
            if raw_extraction is None:
                return self._create_error_result("Entity extraction failed")
            
            # Step 2: Enrich conditions with ICD-10 codes (parallel)
            conditions = await self._step_enrich_conditions(raw_extraction.conditions)
            
            # Step 3: Enrich medications with RxNorm codes (parallel)
            medications = await self._step_enrich_medications(raw_extraction.medications)
            
            # Step 4: Transform remaining entities
            structured_data = await self._step_transform_entities(raw_extraction, conditions, medications)
            
            # Step 5: Validate final output
            validated_note = await self._step_validate(structured_data, soap_note)
            if validated_note is None:
                return self._create_error_result("Validation failed")
            
            # Complete trajectory
            entity_counts = validated_note.entity_count()
            self._trajectory_logger.complete(
                success=True,
                output_summary=f"Extracted {sum(entity_counts.values())} entities"
            )
            
            return ExtractionResult(
                structured_note=validated_note,
                trajectory=self._trajectory_logger.get_trajectory(),
                success=True
            )
            
        except Exception as e:
            self._trajectory_logger.complete(
                success=False,
                error=str(e)
            )
            return ExtractionResult(
                structured_note=None,
                trajectory=self._trajectory_logger.get_trajectory(),
                success=False,
                error=str(e)
            )
        finally:
            # Clean up HTTP clients
            await self._cleanup()
    
    async def _step_extract_entities(self, soap_note: str) -> Optional[RawExtraction]:
        """
        Step 1: Extract raw entities from SOAP note using LLM.
        
        Args:
            soap_note: Raw SOAP note text
            
        Returns:
            RawExtraction or None if failed
        """
        step = self._trajectory_logger.start_step(
            step_name="Extract Entities",
            tool_name="entity_extraction",
            input_summary=f"SOAP note ({len(soap_note)} chars)"
        )
        
        result = await self.extractor.execute(soap_note)
        
        if result.success:
            raw = result.data
            summary = (
                f"Extracted: {len(raw.conditions)} conditions, "
                f"{len(raw.medications)} medications, "
                f"{len(raw.vital_signs)} vitals, "
                f"{len(raw.lab_results)} labs, "
                f"{len(raw.procedures)} procedures, "
                f"{len(raw.care_plan)} care plan items"
            )
            self._trajectory_logger.complete_step(step, output_summary=summary)
            return raw
        else:
            self._trajectory_logger.fail_step(step, result.error or "Unknown extraction error")
            return None
    
    async def _step_enrich_conditions(self, raw_conditions: List[RawCondition]) -> List[Condition]:
        """
        Step 2: Enrich conditions with ICD-10 codes.
        
        Performs parallel lookups for all conditions.
        
        Args:
            raw_conditions: List of raw extracted conditions
            
        Returns:
            List of enriched Condition objects
        """
        if not raw_conditions:
            self._trajectory_logger.skip_step(
                "Enrich Conditions (ICD-10)",
                "icd10_lookup",
                "No conditions to enrich"
            )
            return []
        
        step = self._trajectory_logger.start_step(
            step_name="Enrich Conditions (ICD-10)",
            tool_name="icd10_lookup",
            input_summary=f"{len(raw_conditions)} condition(s) to look up"
        )
        
        # Parallel ICD-10 lookups
        condition_names = [c.name for c in raw_conditions]
        results = await self.icd_lookup.execute_batch(condition_names)
        
        # Build enriched conditions
        conditions = []
        successful_lookups = 0
        
        for raw_cond, result in zip(raw_conditions, results):
            if result.success and result.data:
                icd_code: ICD10Code = result.data
                code = CodeableConcept(
                    code=icd_code.code,
                    system=icd_code.system,
                    display=icd_code.display
                )
                successful_lookups += 1
            else:
                # No code found - use display name only
                code = CodeableConcept(display=raw_cond.name)
            
            # Map clinical status
            clinical_status = self._map_clinical_status(raw_cond.clinical_status)
            
            conditions.append(Condition(
                code=code,
                clinical_status=clinical_status,
                verification_status=VerificationStatus.CONFIRMED,
                note=raw_cond.note
            ))
        
        self._trajectory_logger.complete_step(
            step,
            output_summary=f"Enriched {successful_lookups}/{len(raw_conditions)} with ICD-10 codes"
        )
        
        return conditions
    
    async def _step_enrich_medications(self, raw_medications: List[RawMedication]) -> List[Medication]:
        """
        Step 3: Enrich medications with RxNorm codes.
        
        Performs parallel lookups for all medications.
        
        Args:
            raw_medications: List of raw extracted medications
            
        Returns:
            List of enriched Medication objects
        """
        if not raw_medications:
            self._trajectory_logger.skip_step(
                "Enrich Medications (RxNorm)",
                "rxnorm_lookup",
                "No medications to enrich"
            )
            return []
        
        step = self._trajectory_logger.start_step(
            step_name="Enrich Medications (RxNorm)",
            tool_name="rxnorm_lookup",
            input_summary=f"{len(raw_medications)} medication(s) to look up"
        )
        
        # Parallel RxNorm lookups
        medication_names = [m.name for m in raw_medications]
        results = await self.rxnorm_lookup.execute_batch(medication_names)
        
        # Build enriched medications
        medications = []
        successful_lookups = 0
        
        for raw_med, result in zip(raw_medications, results):
            if result.success and result.data:
                rxnorm_code: RxNormCode = result.data
                code = CodeableConcept(
                    code=rxnorm_code.rxcui,
                    system=rxnorm_code.system,
                    display=rxnorm_code.display
                )
                successful_lookups += 1
            else:
                # No code found - use original name
                code = CodeableConcept(display=raw_med.name)
            
            # Build dosage
            dosage = None
            if raw_med.dose or raw_med.route or raw_med.frequency:
                dosage = Dosage(
                    text=self._build_dosage_text(raw_med),
                    dose_value=self._parse_dose_value(raw_med.dose),
                    dose_unit=self._parse_dose_unit(raw_med.dose),
                    route=raw_med.route,
                    frequency=raw_med.frequency
                )
            
            medications.append(Medication(
                code=code,
                status=MedicationStatus.ACTIVE,
                dosage=dosage,
                dispense_quantity=raw_med.quantity,
                refills=raw_med.refills,
                as_needed=raw_med.as_needed,
                reason=raw_med.reason
            ))
        
        self._trajectory_logger.complete_step(
            step,
            output_summary=f"Enriched {successful_lookups}/{len(raw_medications)} with RxNorm codes"
        )
        
        return medications
    
    async def _step_transform_entities(
        self,
        raw: RawExtraction,
        conditions: List[Condition],
        medications: List[Medication]
    ) -> Dict[str, Any]:
        """
        Step 4: Transform remaining raw entities to structured models.
        
        Args:
            raw: Raw extraction data
            conditions: Enriched conditions
            medications: Enriched medications
            
        Returns:
            Dictionary ready for StructuredNote validation
        """
        step = self._trajectory_logger.start_step(
            step_name="Transform Entities",
            tool_name="transformer",
            input_summary="Building structured models"
        )
        
        try:
            # Build patient info
            patient = None
            if raw.patient_id or raw.patient_name or raw.patient_dob:
                patient = PatientInfo(
                    identifier=raw.patient_id,
                    name=raw.patient_name,
                    birth_date=self._parse_date(raw.patient_dob),
                    gender=self._map_gender(raw.patient_gender)
                )
            
            # Build encounter
            encounter = None
            if raw.encounter_date or raw.encounter_type:
                encounter = Encounter(
                    encounter_date=self._parse_date(raw.encounter_date),
                    encounter_type=raw.encounter_type,
                    reason=raw.encounter_reason
                )
            
            # Build provider
            provider = None
            if raw.provider_name:
                provider = Provider(
                    name=raw.provider_name,
                    specialty=raw.provider_specialty
                )
            
            # Transform vital signs
            vital_signs = [self._transform_vital(v) for v in raw.vital_signs if v]
            
            # Transform lab results
            lab_results = [self._transform_lab(l) for l in raw.lab_results if l]
            
            # Transform procedures
            procedures = [self._transform_procedure(p) for p in raw.procedures if p]
            
            # Transform care plan
            care_plan = [self._transform_care_plan(c) for c in raw.care_plan if c]
            
            structured_data = {
                "patient": patient,
                "encounter": encounter,
                "provider": provider,
                "conditions": conditions,
                "medications": medications,
                "vital_signs": [v for v in vital_signs if v],
                "lab_results": [l for l in lab_results if l],
                "procedures": [p for p in procedures if p],
                "care_plan": [c for c in care_plan if c],
                "extraction_timestamp": datetime.utcnow()
            }
            
            self._trajectory_logger.complete_step(
                step,
                output_summary="Transformed all entity types"
            )
            
            return structured_data
            
        except Exception as e:
            self._trajectory_logger.fail_step(step, str(e))
            raise
    
    async def _step_validate(
        self,
        structured_data: Dict[str, Any],
        source_text: str
    ) -> Optional[StructuredNote]:
        """
        Step 5: Validate and finalize the structured note.
        
        Args:
            structured_data: Dictionary of structured entities
            source_text: Original SOAP note text
            
        Returns:
            Validated StructuredNote or None if validation fails
        """
        step = self._trajectory_logger.start_step(
            step_name="Validate Output",
            tool_name="validator",
            input_summary="Validating structured note"
        )
        
        # Add source text
        structured_data["source_text"] = source_text
        
        result = await self.validator.execute(structured_data)
        
        if result.success:
            validated_note: StructuredNote = result.data
            warnings = result.metadata.get("warnings", [])
            summary = f"Validation passed"
            if warnings:
                summary += f" with {len(warnings)} warning(s)"
            self._trajectory_logger.complete_step(step, output_summary=summary)
            return validated_note
        else:
            errors = result.metadata.get("validation_errors", [])
            self._trajectory_logger.fail_step(
                step,
                f"Validation failed: {result.error}",
                error_type="ValidationError"
            )
            return None
    
    def _create_error_result(self, error: str) -> ExtractionResult:
        """Create an error result with trajectory."""
        self._trajectory_logger.complete(success=False, error=error)
        return ExtractionResult(
            structured_note=None,
            trajectory=self._trajectory_logger.get_trajectory(),
            success=False,
            error=error
        )
    
    async def _cleanup(self):
        """Clean up resources."""
        await self.icd_lookup.close()
        await self.rxnorm_lookup.close()
    
    # =========================================================================
    # Helper Methods for Data Transformation
    # =========================================================================
    
    def _map_gender(self, gender_str: Optional[str]) -> Optional[Gender]:
        """Map gender string to Gender enum."""
        if not gender_str:
            return None
        gender_lower = gender_str.lower().strip()
        mapping = {
            "male": Gender.MALE,
            "m": Gender.MALE,
            "female": Gender.FEMALE,
            "f": Gender.FEMALE,
            "other": Gender.OTHER,
            "unknown": Gender.UNKNOWN,
        }
        return mapping.get(gender_lower, Gender.UNKNOWN)
    
    def _map_clinical_status(self, status_str: Optional[str]) -> ClinicalStatus:
        """Map clinical status string to ClinicalStatus enum."""
        if not status_str:
            return ClinicalStatus.ACTIVE
        status_lower = status_str.lower().strip()
        mapping = {
            "active": ClinicalStatus.ACTIVE,
            "resolved": ClinicalStatus.RESOLVED,
            "inactive": ClinicalStatus.INACTIVE,
            "remission": ClinicalStatus.REMISSION,
            "recurrence": ClinicalStatus.RECURRENCE,
            "relapse": ClinicalStatus.RELAPSE,
        }
        return mapping.get(status_lower, ClinicalStatus.ACTIVE)
    
    def _map_care_plan_status(self, status_str: Optional[str]) -> CarePlanStatus:
        """Map care plan status string to CarePlanStatus enum."""
        if not status_str:
            return CarePlanStatus.SCHEDULED
        status_lower = status_str.lower().strip()
        mapping = {
            "scheduled": CarePlanStatus.SCHEDULED,
            "not-started": CarePlanStatus.NOT_STARTED,
            "not started": CarePlanStatus.NOT_STARTED,
            "in-progress": CarePlanStatus.IN_PROGRESS,
            "in progress": CarePlanStatus.IN_PROGRESS,
            "completed": CarePlanStatus.COMPLETED,
            "cancelled": CarePlanStatus.CANCELLED,
            "canceled": CarePlanStatus.CANCELLED,
            "on-hold": CarePlanStatus.ON_HOLD,
            "on hold": CarePlanStatus.ON_HOLD,
        }
        return mapping.get(status_lower, CarePlanStatus.SCHEDULED)
    
    def _map_procedure_status(self, status_str: Optional[str]) -> ProcedureStatus:
        """Map procedure status string to ProcedureStatus enum."""
        if not status_str:
            return ProcedureStatus.COMPLETED
        status_lower = status_str.lower().strip()
        mapping = {
            "completed": ProcedureStatus.COMPLETED,
            "in-progress": ProcedureStatus.IN_PROGRESS,
            "in progress": ProcedureStatus.IN_PROGRESS,
            "scheduled": ProcedureStatus.PREPARATION,
            "preparation": ProcedureStatus.PREPARATION,
            "not-done": ProcedureStatus.NOT_DONE,
            "not done": ProcedureStatus.NOT_DONE,
            "stopped": ProcedureStatus.STOPPED,
        }
        return mapping.get(status_lower, ProcedureStatus.COMPLETED)
    
    def _parse_date(self, date_str: Optional[str]) -> Optional[date]:
        """Parse date string to date object."""
        if not date_str:
            return None
        try:
            # Try common formats
            for fmt in ["%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%Y/%m/%d"]:
                try:
                    return datetime.strptime(date_str, fmt).date()
                except ValueError:
                    continue
            return None
        except Exception:
            return None
    
    def _parse_dose_value(self, dose_str: Optional[str]) -> Optional[float]:
        """Extract numeric dose value from dose string."""
        if not dose_str:
            return None
        import re
        match = re.search(r'(\d+\.?\d*)', dose_str)
        if match:
            try:
                return float(match.group(1))
            except ValueError:
                return None
        return None
    
    def _parse_dose_unit(self, dose_str: Optional[str]) -> Optional[str]:
        """Extract dose unit from dose string."""
        if not dose_str:
            return None
        import re
        # Common units
        match = re.search(r'\d+\.?\d*\s*(mg|mcg|g|ml|meq|units?|iu|%)', dose_str, re.IGNORECASE)
        if match:
            return match.group(1).lower()
        return None
    
    def _build_dosage_text(self, raw_med: RawMedication) -> str:
        """Build human-readable dosage text."""
        parts = []
        if raw_med.dose:
            parts.append(raw_med.dose)
        if raw_med.route:
            parts.append(raw_med.route)
        if raw_med.frequency:
            parts.append(raw_med.frequency)
        return " ".join(parts) if parts else ""
    
    def _transform_vital(self, vital_dict: dict) -> Optional[VitalSign]:
        """Transform vital sign dictionary to VitalSign model."""
        try:
            name = vital_dict.get("name", "")
            value = vital_dict.get("value")
            unit = vital_dict.get("unit", "")
            
            if not name:
                return None
            
            # Handle missing value
            if value is None:
                # Try to parse from value_string
                value_string = vital_dict.get("value_string", "")
                if value_string:
                    import re
                    match = re.search(r'(\d+\.?\d*)', value_string)
                    if match:
                        value = float(match.group(1))
                    else:
                        value = 0.0
                else:
                    value = 0.0
            
            return VitalSign(
                code=CodeableConcept(display=name),
                value=float(value),
                unit=unit,
                value_string=vital_dict.get("value_string"),
                interpretation=vital_dict.get("interpretation")
            )
        except Exception:
            return None
    
    def _transform_lab(self, lab_dict: dict) -> Optional[LabResult]:
        """Transform lab result dictionary to LabResult model."""
        try:
            name = lab_dict.get("name", "")
            if not name:
                return None
            
            return LabResult(
                code=CodeableConcept(display=name),
                value=lab_dict.get("value"),
                value_string=lab_dict.get("value_string"),
                unit=lab_dict.get("unit"),
                reference_range=lab_dict.get("reference_range"),
                interpretation=lab_dict.get("interpretation")
            )
        except Exception:
            return None
    
    def _transform_procedure(self, proc: RawProcedure) -> Optional[Procedure]:
        """Transform RawProcedure to Procedure model."""
        try:
            return Procedure(
                code=CodeableConcept(display=proc.name),
                status=self._map_procedure_status(proc.status),
                body_site=proc.body_site,
                note=proc.note
            )
        except Exception:
            return None
    
    def _transform_care_plan(self, plan_dict: dict) -> Optional[CarePlanActivity]:
        """Transform care plan dictionary to CarePlanActivity model."""
        try:
            description = plan_dict.get("description", "")
            if not description:
                return None
            
            return CarePlanActivity(
                description=description,
                status=self._map_care_plan_status(plan_dict.get("status")),
                category=plan_dict.get("category"),
                scheduled_string=plan_dict.get("scheduled_string"),
                note=plan_dict.get("note")
            )
        except Exception:
            return None
    
    def get_trajectory(self) -> Optional[Trajectory]:
        """Get the current trajectory (if available)."""
        if self._trajectory_logger:
            return self._trajectory_logger.get_trajectory()
        return None

