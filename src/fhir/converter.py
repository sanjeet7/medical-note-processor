"""
FHIR Converter Service

Main service for converting structured medical data from Part 4
extraction into a complete FHIR Bundle.

Orchestrates:
1. Patient resource creation
2. Condition resources (with ICD-10 codes)
3. MedicationRequest resources (with RxNorm codes)
4. Observation resources (vitals and labs)
5. Procedure resources
6. CarePlan resource
7. Bundle assembly
"""
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

from fhir.resources.bundle import Bundle

from .mappers import (
    PatientMapper,
    ConditionMapper,
    MedicationRequestMapper,
    ObservationMapper,
    ProcedureMapper,
    CarePlanMapper,
    generate_id
)
from .bundler import FHIRBundler


@dataclass
class ConversionResult:
    """Result of FHIR conversion."""
    success: bool
    bundle: Optional[Bundle] = None
    bundle_dict: Optional[Dict[str, Any]] = None
    resource_counts: Optional[Dict[str, int]] = None
    error: Optional[str] = None


class FHIRConverter:
    """
    Converts structured medical data to FHIR Bundle.
    
    Usage:
        converter = FHIRConverter()
        result = converter.convert(structured_data)
        
        if result.success:
            fhir_bundle = result.bundle_dict
    """
    
    def __init__(self):
        """Initialize the converter."""
        self.bundler = FHIRBundler()
        self._patient_reference: Optional[str] = None
    
    def convert(self, structured_data: Dict[str, Any]) -> ConversionResult:
        """
        Convert structured medical data to FHIR Bundle.
        
        Args:
            structured_data: StructuredNote data as dictionary
            
        Returns:
            ConversionResult with Bundle and metadata
        """
        try:
            self.bundler.clear()
            resource_counts = {}
            
            # 1. Create Patient resource (required for references)
            patient_id = self._create_patient(structured_data.get("patient"))
            self._patient_reference = f"Patient/{patient_id}"
            resource_counts["Patient"] = 1 if structured_data.get("patient") else 0
            
            # 2. Create Condition resources
            conditions = structured_data.get("conditions", [])
            for condition in conditions:
                self._create_condition(condition)
            resource_counts["Condition"] = len(conditions)
            
            # 3. Create MedicationRequest resources
            medications = structured_data.get("medications", [])
            for medication in medications:
                self._create_medication_request(medication)
            resource_counts["MedicationRequest"] = len(medications)
            
            # 4. Create Observation resources for vital signs
            vital_signs = structured_data.get("vital_signs", [])
            for vital in vital_signs:
                self._create_vital_sign_observation(vital)
            resource_counts["Observation (vital-signs)"] = len(vital_signs)
            
            # 5. Create Observation resources for lab results
            lab_results = structured_data.get("lab_results", [])
            for lab in lab_results:
                self._create_lab_result_observation(lab)
            resource_counts["Observation (laboratory)"] = len(lab_results)
            
            # 6. Create Procedure resources
            procedures = structured_data.get("procedures", [])
            for procedure in procedures:
                self._create_procedure(procedure)
            resource_counts["Procedure"] = len(procedures)
            
            # 7. Create CarePlan resource (if activities exist)
            care_plan = structured_data.get("care_plan", [])
            if care_plan:
                self._create_care_plan(care_plan)
                resource_counts["CarePlan"] = 1
            else:
                resource_counts["CarePlan"] = 0
            
            # Build the bundle
            bundle = self.bundler.build()
            
            return ConversionResult(
                success=True,
                bundle=bundle,
                bundle_dict=bundle.dict(exclude_none=True),
                resource_counts=resource_counts
            )
            
        except Exception as e:
            return ConversionResult(
                success=False,
                error=f"FHIR conversion failed: {str(e)}"
            )
    
    def _create_patient(self, patient_data: Optional[Dict[str, Any]]) -> str:
        """Create Patient resource and add to bundle."""
        patient_id = generate_id()
        
        if patient_data:
            patient = PatientMapper.map(patient_data, patient_id)
        else:
            # Create minimal patient resource
            from fhir.resources.patient import Patient
            patient = Patient(
                id=patient_id,
                resourceType="Patient"
            )
        
        self.bundler.add_resource(patient)
        return patient_id
    
    def _create_condition(self, condition_data: Dict[str, Any]) -> None:
        """Create Condition resource and add to bundle."""
        condition = ConditionMapper.map(
            condition_data,
            self._patient_reference
        )
        self.bundler.add_resource(condition)
    
    def _create_medication_request(self, medication_data: Dict[str, Any]) -> None:
        """Create MedicationRequest resource and add to bundle."""
        med_request = MedicationRequestMapper.map(
            medication_data,
            self._patient_reference
        )
        self.bundler.add_resource(med_request)
    
    def _create_vital_sign_observation(self, vital_data: Dict[str, Any]) -> None:
        """Create Observation resource for vital sign and add to bundle."""
        observation = ObservationMapper.map_vital_sign(
            vital_data,
            self._patient_reference
        )
        self.bundler.add_resource(observation)
    
    def _create_lab_result_observation(self, lab_data: Dict[str, Any]) -> None:
        """Create Observation resource for lab result and add to bundle."""
        observation = ObservationMapper.map_lab_result(
            lab_data,
            self._patient_reference
        )
        self.bundler.add_resource(observation)
    
    def _create_procedure(self, procedure_data: Dict[str, Any]) -> None:
        """Create Procedure resource and add to bundle."""
        procedure = ProcedureMapper.map(
            procedure_data,
            self._patient_reference
        )
        self.bundler.add_resource(procedure)
    
    def _create_care_plan(self, activities: List[Dict[str, Any]]) -> None:
        """Create CarePlan resource and add to bundle."""
        care_plan = CarePlanMapper.map(
            activities,
            self._patient_reference
        )
        self.bundler.add_resource(care_plan)
