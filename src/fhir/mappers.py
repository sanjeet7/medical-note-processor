"""
FHIR Resource Mappers

Maps structured data from Part 4 extraction to FHIR R4 resources
using the fhir.resources library for spec compliance.

Mappings:
- PatientInfo → Patient
- Condition → Condition
- Medication → MedicationRequest
- VitalSign → Observation (vital-signs)
- LabResult → Observation (laboratory)
- Procedure → Procedure
- CarePlanActivity → CarePlan
"""
from typing import Optional, List, Dict, Any
from datetime import datetime
import uuid

from fhir.resources.patient import Patient
from fhir.resources.condition import Condition
from fhir.resources.medicationrequest import MedicationRequest
from fhir.resources.observation import Observation
from fhir.resources.procedure import Procedure
from fhir.resources.careplan import CarePlan
from fhir.resources.codeableconcept import CodeableConcept
from fhir.resources.coding import Coding
from fhir.resources.humanname import HumanName
from fhir.resources.identifier import Identifier
from fhir.resources.reference import Reference
from fhir.resources.quantity import Quantity
from fhir.resources.dosage import Dosage
from fhir.resources.period import Period


def generate_id() -> str:
    """Generate a unique resource ID."""
    return str(uuid.uuid4())


class PatientMapper:
    """Maps PatientInfo to FHIR Patient resource."""
    
    @staticmethod
    def map(patient_data: Dict[str, Any], resource_id: str = None) -> Patient:
        """
        Convert patient data to FHIR Patient resource.
        
        Args:
            patient_data: Dictionary with patient info
            resource_id: Optional resource ID (generated if not provided)
            
        Returns:
            FHIR Patient resource
        """
        resource_id = resource_id or generate_id()
        
        patient_dict = {
            "resourceType": "Patient",
            "id": resource_id,
        }
        
        # Add identifier if present
        if patient_data.get("identifier"):
            patient_dict["identifier"] = [{
                "system": "urn:medical-note-processor",
                "value": patient_data["identifier"]
            }]
        
        # Add name if present
        if patient_data.get("name"):
            patient_dict["name"] = [{
                "text": patient_data["name"],
                "use": "official"
            }]
        
        # Add birth date if present
        if patient_data.get("birth_date"):
            birth_date = patient_data["birth_date"]
            if isinstance(birth_date, str) and birth_date != "None":
                patient_dict["birthDate"] = birth_date
        
        # Add gender if present
        if patient_data.get("gender"):
            gender = patient_data["gender"]
            if gender and gender != "None":
                patient_dict["gender"] = gender.lower()
        
        return Patient(**patient_dict)


class ConditionMapper:
    """Maps Condition data to FHIR Condition resource."""
    
    @staticmethod
    def map(
        condition_data: Dict[str, Any],
        patient_reference: str,
        resource_id: str = None
    ) -> Condition:
        """
        Convert condition data to FHIR Condition resource.
        
        Args:
            condition_data: Dictionary with condition info (including ICD-10 code)
            patient_reference: Reference to Patient resource
            resource_id: Optional resource ID
            
        Returns:
            FHIR Condition resource
        """
        resource_id = resource_id or generate_id()
        
        condition_dict = {
            "resourceType": "Condition",
            "id": resource_id,
            "subject": {"reference": patient_reference},
        }
        
        # Build CodeableConcept for condition
        code_data = condition_data.get("code", {})
        codings = []
        
        # Add ICD-10 coding if present
        if code_data.get("code"):
            codings.append({
                "system": code_data.get("system", "http://hl7.org/fhir/sid/icd-10-cm"),
                "code": code_data["code"],
                "display": code_data.get("display", "")
            })
        elif code_data.get("display"):
            # No code, just display text
            codings.append({
                "display": code_data["display"]
            })
        
        if codings:
            condition_dict["code"] = {
                "coding": codings,
                "text": code_data.get("display", "")
            }
        
        # Clinical status
        clinical_status = condition_data.get("clinical_status", "active")
        condition_dict["clinicalStatus"] = {
            "coding": [{
                "system": "http://terminology.hl7.org/CodeSystem/condition-clinical",
                "code": clinical_status
            }]
        }
        
        # Verification status
        verification_status = condition_data.get("verification_status", "confirmed")
        condition_dict["verificationStatus"] = {
            "coding": [{
                "system": "http://terminology.hl7.org/CodeSystem/condition-ver-status",
                "code": verification_status
            }]
        }
        
        # Add note if present
        if condition_data.get("note"):
            condition_dict["note"] = [{"text": condition_data["note"]}]
        
        return Condition(**condition_dict)


class MedicationRequestMapper:
    """Maps Medication data to FHIR MedicationRequest resource."""
    
    @staticmethod
    def map(
        medication_data: Dict[str, Any],
        patient_reference: str,
        resource_id: str = None
    ) -> MedicationRequest:
        """
        Convert medication data to FHIR MedicationRequest resource.
        
        Args:
            medication_data: Dictionary with medication info (including RxNorm code)
            patient_reference: Reference to Patient resource
            resource_id: Optional resource ID
            
        Returns:
            FHIR MedicationRequest resource
        """
        from fhir.resources.codeablereference import CodeableReference
        from fhir.resources.codeableconcept import CodeableConcept as FHIRCodeableConcept
        
        resource_id = resource_id or generate_id()
        
        # Build medication CodeableConcept with RxNorm
        code_data = medication_data.get("code", {})
        codings = []
        
        if code_data.get("code"):
            codings.append({
                "system": code_data.get("system", "http://www.nlm.nih.gov/research/umls/rxnorm"),
                "code": code_data["code"],
                "display": code_data.get("display", "")
            })
        elif code_data.get("display"):
            codings.append({
                "display": code_data["display"]
            })
        
        # Create medication CodeableReference (FHIR R5 structure)
        if codings:
            medication_ref = CodeableReference(
                concept=FHIRCodeableConcept(
                    coding=codings,
                    text=code_data.get("display", "")
                )
            )
        else:
            medication_ref = CodeableReference(
                concept=FHIRCodeableConcept(text="Unknown medication")
            )
        
        med_dict = {
            "resourceType": "MedicationRequest",
            "id": resource_id,
            "status": medication_data.get("status", "active"),
            "intent": "order",
            "subject": {"reference": patient_reference},
            "medication": medication_ref,
        }
        
        # Add dosage instruction if present
        dosage_data = medication_data.get("dosage")
        if dosage_data:
            dosage_instruction = {}
            
            if dosage_data.get("text"):
                dosage_instruction["text"] = dosage_data["text"]
            
            if dosage_data.get("route"):
                dosage_instruction["route"] = {
                    "text": dosage_data["route"]
                }
            
            if dosage_data.get("frequency"):
                dosage_instruction["timing"] = {
                    "code": {"text": dosage_data["frequency"]}
                }
            
            if dosage_data.get("dose_value") and dosage_data.get("dose_unit"):
                dosage_instruction["doseAndRate"] = [{
                    "doseQuantity": {
                        "value": dosage_data["dose_value"],
                        "unit": dosage_data["dose_unit"]
                    }
                }]
            
            # PRN flag - use asNeeded (not asNeededBoolean)
            if medication_data.get("as_needed"):
                dosage_instruction["asNeeded"] = True
            
            if dosage_instruction:
                med_dict["dosageInstruction"] = [dosage_instruction]
        elif medication_data.get("as_needed"):
            # PRN flag without other dosage info
            med_dict["dosageInstruction"] = [{"asNeeded": True}]
        
        # Add dispense request if quantity or refills present
        dispense_request = {}
        if medication_data.get("dispense_quantity"):
            dispense_request["quantity"] = {
                "value": medication_data["dispense_quantity"]
            }
        if medication_data.get("refills") is not None:
            dispense_request["numberOfRepeatsAllowed"] = medication_data["refills"]
        
        if dispense_request:
            med_dict["dispenseRequest"] = dispense_request
        
        return MedicationRequest(**med_dict)


class ObservationMapper:
    """Maps VitalSign and LabResult to FHIR Observation resources."""
    
    @staticmethod
    def map_vital_sign(
        vital_data: Dict[str, Any],
        patient_reference: str,
        resource_id: str = None
    ) -> Observation:
        """
        Convert vital sign data to FHIR Observation resource.
        
        Args:
            vital_data: Dictionary with vital sign info
            patient_reference: Reference to Patient resource
            resource_id: Optional resource ID
            
        Returns:
            FHIR Observation resource (vital-signs category)
        """
        resource_id = resource_id or generate_id()
        
        obs_dict = {
            "resourceType": "Observation",
            "id": resource_id,
            "status": "final",
            "subject": {"reference": patient_reference},
            "category": [{
                "coding": [{
                    "system": "http://terminology.hl7.org/CodeSystem/observation-category",
                    "code": "vital-signs",
                    "display": "Vital Signs"
                }]
            }],
        }
        
        # Code
        code_data = vital_data.get("code", {})
        display_text = code_data.get("display", "Unknown Vital Sign")
        obs_dict["code"] = {
            "text": display_text
        }
        
        # Value
        if vital_data.get("value") is not None:
            obs_dict["valueQuantity"] = {
                "value": vital_data["value"],
                "unit": vital_data.get("unit", "")
            }
        elif vital_data.get("value_string"):
            obs_dict["valueString"] = vital_data["value_string"]
        
        # Interpretation
        if vital_data.get("interpretation"):
            obs_dict["interpretation"] = [{
                "text": vital_data["interpretation"]
            }]
        
        return Observation(**obs_dict)
    
    @staticmethod
    def map_lab_result(
        lab_data: Dict[str, Any],
        patient_reference: str,
        resource_id: str = None
    ) -> Observation:
        """
        Convert lab result data to FHIR Observation resource.
        
        Args:
            lab_data: Dictionary with lab result info
            patient_reference: Reference to Patient resource
            resource_id: Optional resource ID
            
        Returns:
            FHIR Observation resource (laboratory category)
        """
        resource_id = resource_id or generate_id()
        
        obs_dict = {
            "resourceType": "Observation",
            "id": resource_id,
            "status": "final",
            "subject": {"reference": patient_reference},
            "category": [{
                "coding": [{
                    "system": "http://terminology.hl7.org/CodeSystem/observation-category",
                    "code": "laboratory",
                    "display": "Laboratory"
                }]
            }],
        }
        
        # Code
        code_data = lab_data.get("code", {})
        display_text = code_data.get("display", "Unknown Lab Test")
        obs_dict["code"] = {
            "text": display_text
        }
        
        # Value
        if lab_data.get("value") is not None:
            obs_dict["valueQuantity"] = {
                "value": lab_data["value"],
                "unit": lab_data.get("unit", "")
            }
        elif lab_data.get("value_string"):
            obs_dict["valueString"] = lab_data["value_string"]
        
        # Reference range
        if lab_data.get("reference_range"):
            obs_dict["referenceRange"] = [{
                "text": lab_data["reference_range"]
            }]
        
        # Interpretation
        if lab_data.get("interpretation"):
            obs_dict["interpretation"] = [{
                "text": lab_data["interpretation"]
            }]
        
        return Observation(**obs_dict)


class ProcedureMapper:
    """Maps Procedure data to FHIR Procedure resource."""
    
    @staticmethod
    def map(
        procedure_data: Dict[str, Any],
        patient_reference: str,
        resource_id: str = None
    ) -> Procedure:
        """
        Convert procedure data to FHIR Procedure resource.
        
        Args:
            procedure_data: Dictionary with procedure info
            patient_reference: Reference to Patient resource
            resource_id: Optional resource ID
            
        Returns:
            FHIR Procedure resource
        """
        resource_id = resource_id or generate_id()
        
        # Map status
        status_map = {
            "completed": "completed",
            "in-progress": "in-progress",
            "preparation": "preparation",
            "not-done": "not-done",
            "stopped": "stopped",
            "unknown": "unknown"
        }
        status = procedure_data.get("status", "completed")
        fhir_status = status_map.get(status, "completed")
        
        proc_dict = {
            "resourceType": "Procedure",
            "id": resource_id,
            "status": fhir_status,
            "subject": {"reference": patient_reference},
        }
        
        # Code
        code_data = procedure_data.get("code", {})
        if code_data.get("display"):
            proc_dict["code"] = {
                "text": code_data["display"]
            }
            if code_data.get("code"):
                proc_dict["code"]["coding"] = [{
                    "code": code_data["code"],
                    "display": code_data["display"]
                }]
        
        # Body site
        if procedure_data.get("body_site"):
            proc_dict["bodySite"] = [{
                "text": procedure_data["body_site"]
            }]
        
        # Note
        if procedure_data.get("note"):
            proc_dict["note"] = [{"text": procedure_data["note"]}]
        
        return Procedure(**proc_dict)


class CarePlanMapper:
    """Maps CarePlanActivity data to FHIR CarePlan resource."""
    
    @staticmethod
    def map(
        activities: List[Dict[str, Any]],
        patient_reference: str,
        resource_id: str = None
    ) -> CarePlan:
        """
        Convert care plan activities to FHIR CarePlan resource.
        
        FHIR R5 uses a simplified CarePlan.activity structure with:
        - performedActivity (CodeableReference) for completed activities
        - plannedActivityReference for planned activities referencing other resources
        
        Since our activities are simple descriptions, we store them in notes
        and use progress annotations for detailed information.
        
        Args:
            activities: List of care plan activity dictionaries
            patient_reference: Reference to Patient resource
            resource_id: Optional resource ID
            
        Returns:
            FHIR CarePlan resource containing all activities
        """
        from fhir.resources.codeablereference import CodeableReference
        from fhir.resources.codeableconcept import CodeableConcept as FHIRCodeableConcept
        
        resource_id = resource_id or generate_id()
        
        careplan_dict = {
            "resourceType": "CarePlan",
            "id": resource_id,
            "status": "active",
            "intent": "plan",
            "subject": {"reference": patient_reference},
        }
        
        # Build activities using FHIR R5 structure
        # Use performedActivity with CodeableReference to store activity descriptions
        fhir_activities = []
        notes = []
        
        for idx, activity in enumerate(activities):
            description = activity.get("description", "Activity")
            status = activity.get("status", "scheduled")
            
            # Create activity with performedActivity
            fhir_activity = {
                "performedActivity": [
                    CodeableReference(
                        concept=FHIRCodeableConcept(text=description)
                    )
                ]
            }
            
            # Add progress annotation with status and timing info
            progress_text = f"Status: {status}"
            if activity.get("scheduled_string"):
                progress_text += f"; Scheduled: {activity['scheduled_string']}"
            if activity.get("category"):
                progress_text += f"; Category: {activity['category']}"
            
            fhir_activity["progress"] = [{"text": progress_text}]
            
            fhir_activities.append(fhir_activity)
            
            # Also add to notes for easier human reading
            note_text = f"{idx + 1}. {description}"
            if activity.get("scheduled_string"):
                note_text += f" - {activity['scheduled_string']}"
            notes.append(note_text)
        
        if fhir_activities:
            careplan_dict["activity"] = fhir_activities
        
        # Add summary notes
        if notes:
            careplan_dict["note"] = [{"text": "Care Plan Activities:\n" + "\n".join(notes)}]
        
        return CarePlan(**careplan_dict)
