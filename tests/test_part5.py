"""
Part 5 Tests: FHIR Conversion

Comprehensive tests for:
1. Resource mapper unit tests
2. Bundle assembly tests
3. Converter integration tests
4. API endpoint tests
"""
import pytest
from unittest.mock import Mock, patch
from typing import Dict, Any

from fhir.resources.patient import Patient
from fhir.resources.condition import Condition
from fhir.resources.medicationrequest import MedicationRequest
from fhir.resources.observation import Observation
from fhir.resources.procedure import Procedure
from fhir.resources.careplan import CarePlan
from fhir.resources.bundle import Bundle

from src.fhir.mappers import (
    PatientMapper,
    ConditionMapper,
    MedicationRequestMapper,
    ObservationMapper,
    ProcedureMapper,
    CarePlanMapper
)
from src.fhir.bundler import FHIRBundler
from src.fhir.converter import FHIRConverter, ConversionResult


# ============================================================================
# Sample Data for Testing
# ============================================================================

SAMPLE_PATIENT = {
    "identifier": "patient--001",
    "name": "John Doe",
    "birth_date": "1980-05-15",
    "gender": "male"
}

SAMPLE_CONDITION = {
    "code": {
        "code": "E78.5",
        "system": "http://hl7.org/fhir/sid/icd-10-cm",
        "display": "Hyperlipidemia, unspecified"
    },
    "clinical_status": "active",
    "verification_status": "confirmed",
    "note": "Patient has family history"
}

SAMPLE_MEDICATION = {
    "code": {
        "code": "83367",
        "system": "http://www.nlm.nih.gov/research/umls/rxnorm",
        "display": "atorvastatin"
    },
    "status": "active",
    "dosage": {
        "text": "20 mg oral daily",
        "dose_value": 20,
        "dose_unit": "mg",
        "route": "oral",
        "frequency": "daily"
    },
    "dispense_quantity": 90,
    "refills": 3,
    "as_needed": False
}

SAMPLE_VITAL_SIGN = {
    "code": {"display": "Blood Pressure"},
    "value": 134,
    "unit": "mmHg",
    "value_string": "134/84 mmHg",
    "interpretation": "elevated"
}

SAMPLE_LAB_RESULT = {
    "code": {"display": "LDL Cholesterol"},
    "value": 165,
    "unit": "mg/dL",
    "reference_range": "<100 mg/dL",
    "interpretation": "high"
}

SAMPLE_PROCEDURE = {
    "code": {"display": "Arthroscopic meniscal repair"},
    "status": "completed",
    "body_site": "left knee",
    "note": "Successful repair"
}

SAMPLE_CARE_PLAN = [
    {
        "description": "Follow-up appointment in 3 months",
        "status": "scheduled",
        "category": "follow-up",
        "scheduled_string": "in 3 months"
    },
    {
        "description": "Continue physical therapy",
        "status": "in-progress",
        "category": "therapy"
    }
]

SAMPLE_STRUCTURED_NOTE = {
    "patient": SAMPLE_PATIENT,
    "conditions": [SAMPLE_CONDITION],
    "medications": [SAMPLE_MEDICATION],
    "vital_signs": [SAMPLE_VITAL_SIGN],
    "lab_results": [SAMPLE_LAB_RESULT],
    "procedures": [SAMPLE_PROCEDURE],
    "care_plan": SAMPLE_CARE_PLAN
}


# ============================================================================
# Mapper Unit Tests
# ============================================================================

class TestPatientMapper:
    """Test Patient resource mapping."""
    
    def test_map_full_patient(self):
        """Test mapping complete patient data."""
        patient = PatientMapper.map(SAMPLE_PATIENT)
        
        assert patient.resource_type == "Patient"
        assert patient.id is not None
        assert len(patient.identifier) == 1
        assert patient.identifier[0].value == "patient--001"
        assert len(patient.name) == 1
        assert patient.name[0].text == "John Doe"
        assert str(patient.birthDate) == "1980-05-15"
        assert patient.gender == "male"
    
    def test_map_minimal_patient(self):
        """Test mapping patient with minimal data."""
        patient = PatientMapper.map({"identifier": "test-id"})
        
        assert patient.resource_type == "Patient"
        assert patient.identifier[0].value == "test-id"
        assert patient.name is None
    
    def test_map_empty_patient(self):
        """Test mapping empty patient data."""
        patient = PatientMapper.map({})
        
        assert patient.resource_type == "Patient"
        assert patient.id is not None


class TestConditionMapper:
    """Test Condition resource mapping."""
    
    def test_map_condition_with_icd10(self):
        """Test mapping condition with ICD-10 code."""
        condition = ConditionMapper.map(SAMPLE_CONDITION, "Patient/123")
        
        assert condition.resource_type == "Condition"
        assert condition.subject.reference == "Patient/123"
        assert condition.code.coding[0].code == "E78.5"
        assert condition.code.coding[0].system == "http://hl7.org/fhir/sid/icd-10-cm"
        assert condition.clinicalStatus.coding[0].code == "active"
        assert condition.verificationStatus.coding[0].code == "confirmed"
    
    def test_map_condition_without_code(self):
        """Test mapping condition without ICD-10 code (display only)."""
        condition_data = {
            "code": {"display": "Obesity"},
            "clinical_status": "active"
        }
        condition = ConditionMapper.map(condition_data, "Patient/123")
        
        assert condition.code.text == "Obesity"


class TestMedicationRequestMapper:
    """Test MedicationRequest resource mapping."""
    
    def test_map_medication_with_rxnorm(self):
        """Test mapping medication with RxNorm code."""
        med = MedicationRequestMapper.map(SAMPLE_MEDICATION, "Patient/123")
        
        assert med.resource_type == "MedicationRequest"
        assert med.subject.reference == "Patient/123"
        assert med.status == "active"
        assert med.intent == "order"
        # FHIR R5 uses medication.concept instead of medicationCodeableConcept
        assert med.medication.concept.coding[0].code == "83367"
        assert "atorvastatin" in med.medication.concept.text
    
    def test_map_medication_with_dosage(self):
        """Test medication dosage instruction mapping."""
        med = MedicationRequestMapper.map(SAMPLE_MEDICATION, "Patient/123")
        
        assert len(med.dosageInstruction) == 1
        dosage = med.dosageInstruction[0]
        assert dosage.text == "20 mg oral daily"
        assert dosage.route.text == "oral"
        assert dosage.doseAndRate[0].doseQuantity.value == 20
        assert dosage.doseAndRate[0].doseQuantity.unit == "mg"
    
    def test_map_prn_medication(self):
        """Test PRN (as needed) medication flag."""
        prn_med = {
            "code": {"display": "ibuprofen"},
            "as_needed": True
        }
        med = MedicationRequestMapper.map(prn_med, "Patient/123")
        
        # Check asNeeded is set
        assert med.dosageInstruction[0].asNeeded is True


class TestObservationMapper:
    """Test Observation resource mapping for vitals and labs."""
    
    def test_map_vital_sign(self):
        """Test vital sign observation mapping."""
        obs = ObservationMapper.map_vital_sign(SAMPLE_VITAL_SIGN, "Patient/123")
        
        assert obs.resource_type == "Observation"
        assert obs.status == "final"
        assert obs.subject.reference == "Patient/123"
        assert obs.category[0].coding[0].code == "vital-signs"
        assert obs.code.text == "Blood Pressure"
        assert obs.valueQuantity.value == 134
        assert obs.valueQuantity.unit == "mmHg"
    
    def test_map_lab_result(self):
        """Test lab result observation mapping."""
        obs = ObservationMapper.map_lab_result(SAMPLE_LAB_RESULT, "Patient/123")
        
        assert obs.resource_type == "Observation"
        assert obs.category[0].coding[0].code == "laboratory"
        assert obs.code.text == "LDL Cholesterol"
        assert obs.valueQuantity.value == 165
        assert obs.referenceRange[0].text == "<100 mg/dL"
        assert obs.interpretation[0].text == "high"


class TestProcedureMapper:
    """Test Procedure resource mapping."""
    
    def test_map_procedure(self):
        """Test procedure mapping."""
        proc = ProcedureMapper.map(SAMPLE_PROCEDURE, "Patient/123")
        
        assert proc.resource_type == "Procedure"
        assert proc.status == "completed"
        assert proc.subject.reference == "Patient/123"
        assert proc.code.text == "Arthroscopic meniscal repair"
        assert proc.bodySite[0].text == "left knee"
        assert proc.note[0].text == "Successful repair"


class TestCarePlanMapper:
    """Test CarePlan resource mapping."""
    
    def test_map_care_plan(self):
        """Test care plan with activities mapping (FHIR R5 structure)."""
        care_plan = CarePlanMapper.map(SAMPLE_CARE_PLAN, "Patient/123")
        
        assert care_plan.resource_type == "CarePlan"
        assert care_plan.status == "active"
        assert care_plan.intent == "plan"
        assert care_plan.subject.reference == "Patient/123"
        assert len(care_plan.activity) == 2
        # FHIR R5 uses performedActivity with CodeableReference
        assert care_plan.activity[0].performedActivity[0].concept.text == "Follow-up appointment in 3 months"
        # Check progress annotation contains status
        assert "scheduled" in care_plan.activity[0].progress[0].text.lower()
        # Check notes summary
        assert "Care Plan Activities" in care_plan.note[0].text


# ============================================================================
# Bundler Tests
# ============================================================================

class TestFHIRBundler:
    """Test FHIR Bundle assembly."""
    
    def test_create_empty_bundle(self):
        """Test creating empty bundle."""
        bundler = FHIRBundler()
        bundle = bundler.build()
        
        assert bundle.type == "collection"
        assert bundle.id is not None
        assert bundler.resource_count == 0
    
    def test_add_resources(self):
        """Test adding resources to bundle."""
        bundler = FHIRBundler()
        
        patient = PatientMapper.map(SAMPLE_PATIENT)
        condition = ConditionMapper.map(SAMPLE_CONDITION, f"Patient/{patient.id}")
        
        bundler.add_resource(patient)
        bundler.add_resource(condition)
        
        assert bundler.resource_count == 2
        assert "Patient" in bundler.get_resource_types()
        assert "Condition" in bundler.get_resource_types()
    
    def test_bundle_to_dict(self):
        """Test converting bundle to dictionary."""
        bundler = FHIRBundler()
        patient = PatientMapper.map(SAMPLE_PATIENT)
        bundler.add_resource(patient)
        
        bundle_dict = bundler.to_dict()
        
        assert bundle_dict["resourceType"] == "Bundle"
        assert bundle_dict["type"] == "collection"
        assert len(bundle_dict["entry"]) == 1
        assert bundle_dict["entry"][0]["resource"]["resourceType"] == "Patient"


# ============================================================================
# Converter Integration Tests
# ============================================================================

class TestFHIRConverter:
    """Test complete FHIR conversion."""
    
    def test_convert_full_structured_note(self):
        """Test converting complete structured note."""
        converter = FHIRConverter()
        result = converter.convert(SAMPLE_STRUCTURED_NOTE)
        
        assert result.success is True
        assert result.bundle is not None
        assert result.bundle_dict is not None
        assert result.error is None
        
        # Check resource counts
        assert result.resource_counts["Patient"] == 1
        assert result.resource_counts["Condition"] == 1
        assert result.resource_counts["MedicationRequest"] == 1
        assert result.resource_counts["Observation (vital-signs)"] == 1
        assert result.resource_counts["Observation (laboratory)"] == 1
        assert result.resource_counts["Procedure"] == 1
        assert result.resource_counts["CarePlan"] == 1
    
    def test_convert_minimal_note(self):
        """Test converting note with minimal data."""
        minimal_data = {
            "conditions": [{"code": {"display": "Test Condition"}, "clinical_status": "active"}]
        }
        converter = FHIRConverter()
        result = converter.convert(minimal_data)
        
        assert result.success is True
        assert result.resource_counts["Patient"] == 0  # No patient data
        assert result.resource_counts["Condition"] == 1
    
    def test_bundle_structure(self):
        """Test the structure of the generated bundle."""
        converter = FHIRConverter()
        result = converter.convert(SAMPLE_STRUCTURED_NOTE)
        
        bundle = result.bundle_dict
        
        assert bundle["resourceType"] == "Bundle"
        assert bundle["type"] == "collection"
        assert "timestamp" in bundle
        assert len(bundle["entry"]) > 0
        
        # Verify all entries have fullUrl and resource
        for entry in bundle["entry"]:
            assert "fullUrl" in entry
            assert "resource" in entry
            assert "resourceType" in entry["resource"]
    
    def test_patient_reference_in_resources(self):
        """Test that resources correctly reference the patient."""
        converter = FHIRConverter()
        result = converter.convert(SAMPLE_STRUCTURED_NOTE)
        
        # Find patient ID from bundle
        patient_id = None
        for entry in result.bundle_dict["entry"]:
            if entry["resource"]["resourceType"] == "Patient":
                patient_id = entry["resource"]["id"]
                break
        
        assert patient_id is not None
        
        # Check that condition references patient
        for entry in result.bundle_dict["entry"]:
            if entry["resource"]["resourceType"] == "Condition":
                assert f"Patient/{patient_id}" == entry["resource"]["subject"]["reference"]


# ============================================================================
# API Endpoint Tests
# ============================================================================

class TestToFHIREndpoint:
    """Test /to_fhir API endpoint."""
    
    @pytest.fixture
    def client_and_db(self):
        """Create test client and database session."""
        from fastapi.testclient import TestClient
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from src.main import app
        from src.database import Base, get_db
        
        engine = create_engine("sqlite:///./test_part5.db", connect_args={"check_same_thread": False})
        TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        Base.metadata.create_all(bind=engine)
        
        def override_get_db():
            try:
                db = TestingSessionLocal()
                yield db
            finally:
                db.close()
        
        app.dependency_overrides[get_db] = override_get_db
        client = TestClient(app)
        db = TestingSessionLocal()
        return client, db
    
    @pytest.fixture
    def client(self, client_and_db):
        """Create test client."""
        return client_and_db[0]
    
    def test_endpoint_requires_input(self, client):
        """Test that endpoint requires one of the input options."""
        response = client.post("/to_fhir", json={})
        assert response.status_code == 400
    
    def test_endpoint_with_structured_data(self, client):
        """Test conversion with raw structured data."""
        response = client.post("/to_fhir", json={
            "structured_data": {
                "patient": {"name": "Test Patient"},
                "conditions": [{
                    "code": {"display": "Test"},
                    "clinical_status": "active",
                    "verification_status": "confirmed"
                }],
                "medications": [],
                "vital_signs": [],
                "lab_results": [],
                "procedures": [],
                "care_plan": []
            }
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["bundle"]["resourceType"] == "Bundle"
        assert data["resource_counts"]["Condition"] == 1
    
    def test_endpoint_extracted_note_not_found(self, client):
        """Test 404 for non-existent extracted note."""
        response = client.post("/to_fhir", json={"extracted_note_id": 99999})
        assert response.status_code == 404
    
    def test_endpoint_document_not_extracted(self, client):
        """Test 404 when document has no extraction."""
        response = client.post("/to_fhir", json={"document_id": 99999})
        assert response.status_code == 404


# ============================================================================
# FHIR Compliance Tests
# ============================================================================

class TestFHIRCompliance:
    """Test FHIR R4 spec compliance."""
    
    def test_patient_resource_valid(self):
        """Test Patient resource is FHIR-compliant."""
        patient = PatientMapper.map(SAMPLE_PATIENT)
        
        # Should not raise validation error
        assert patient.resource_type == "Patient"
        
        # Test serialization
        json_str = patient.json()
        assert "Patient" in json_str
    
    def test_condition_resource_valid(self):
        """Test Condition resource is FHIR-compliant."""
        condition = ConditionMapper.map(SAMPLE_CONDITION, "Patient/123")
        
        assert condition.resource_type == "Condition"
        json_str = condition.json()
        assert "Condition" in json_str
    
    def test_medication_request_resource_valid(self):
        """Test MedicationRequest resource is FHIR-compliant."""
        med = MedicationRequestMapper.map(SAMPLE_MEDICATION, "Patient/123")
        
        assert med.resource_type == "MedicationRequest"
        json_str = med.json()
        assert "MedicationRequest" in json_str
    
    def test_observation_resource_valid(self):
        """Test Observation resource is FHIR-compliant."""
        obs = ObservationMapper.map_vital_sign(SAMPLE_VITAL_SIGN, "Patient/123")
        
        assert obs.resource_type == "Observation"
        json_str = obs.json()
        assert "Observation" in json_str
    
    def test_bundle_resource_valid(self):
        """Test Bundle resource is FHIR-compliant."""
        converter = FHIRConverter()
        result = converter.convert(SAMPLE_STRUCTURED_NOTE)
        
        assert result.bundle.resource_type == "Bundle"
        json_str = result.bundle.json()
        assert "Bundle" in json_str


class TestCaching:
    """Test caching behavior for /extract_structured and /to_fhir endpoints."""
    
    @pytest.fixture
    def client_and_db(self):
        """Create test client and database session."""
        from fastapi.testclient import TestClient
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from src.main import app
        from src.database import Base, get_db
        from src import models
        
        engine = create_engine("sqlite:///./test_caching.db", connect_args={"check_same_thread": False})
        TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        Base.metadata.create_all(bind=engine)
        
        def override_get_db():
            try:
                db = TestingSessionLocal()
                yield db
            finally:
                db.close()
        
        app.dependency_overrides[get_db] = override_get_db
        client = TestClient(app)
        db = TestingSessionLocal()
        
        # Create a test document
        doc = models.Document(
            title="Test SOAP Note",
            content="Patient presents with headache. Assessment: Tension headache. Plan: Rest.",
            doc_type="soap_note"
        )
        db.add(doc)
        db.commit()
        db.refresh(doc)
        
        yield client, db, doc.id
        
        # Cleanup
        db.close()
    
    def test_extract_structured_uses_cache(self, client_and_db):
        """Test that /extract_structured returns cached result on second call."""
        client, db, doc_id = client_and_db
        from src import models
        
        # Create a cached extraction for the document
        cached_data = {
            "patient": {"identifier": "cached-patient"},
            "conditions": [{"code": {"display": "Cached Condition"}, "clinical_status": "active", "verification_status": "confirmed"}],
            "medications": [],
            "vital_signs": [],
            "lab_results": [],
            "procedures": [],
            "care_plan": []
        }
        cached_extraction = models.ExtractedNote(
            document_id=doc_id,
            structured_data=cached_data,
            entity_counts={"conditions": 1}
        )
        db.add(cached_extraction)
        db.commit()
        db.refresh(cached_extraction)
        
        # Call with use_cache=True (default)
        response = client.post("/extract_structured", json={
            "document_id": doc_id,
            "include_trajectory": False
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["cached"] is True  # Should be from cache
        assert data["extracted_note_id"] == cached_extraction.id
        assert data["structured_data"]["patient"]["identifier"] == "cached-patient"
    
    def test_extract_structured_bypass_cache(self, client_and_db):
        """Test that use_cache=False forces re-extraction."""
        client, db, doc_id = client_and_db
        from src import models
        
        # Create a cached extraction
        cached_extraction = models.ExtractedNote(
            document_id=doc_id,
            structured_data={"patient": {"identifier": "old-cache"}},
            entity_counts={}
        )
        db.add(cached_extraction)
        db.commit()
        
        # Call with use_cache=False - this will try to run the agent
        # which may fail without proper setup, but we're testing the bypass logic
        response = client.post("/extract_structured", json={
            "document_id": doc_id,
            "use_cache": False,
            "include_trajectory": False
        })
        
        # Even if extraction fails, it should NOT return the cached result
        # The response will either be a new extraction or an error, but not cached
        if response.status_code == 200:
            data = response.json()
            assert data.get("cached", False) is False
    
    def test_to_fhir_uses_cache(self, client_and_db):
        """Test that /to_fhir returns cached FHIR bundle on second call."""
        client, db, doc_id = client_and_db
        from src import models
        
        # Create an extraction with cached FHIR bundle
        cached_bundle = {
            "resourceType": "Bundle",
            "type": "collection",
            "entry": [{"resource": {"resourceType": "Patient", "id": "cached-patient"}}]
        }
        extraction = models.ExtractedNote(
            document_id=doc_id,
            structured_data={"patient": {"identifier": "test"}},
            entity_counts={},
            fhir_bundle=cached_bundle
        )
        db.add(extraction)
        db.commit()
        db.refresh(extraction)
        
        # Call with use_cache=True (default)
        response = client.post("/to_fhir", json={
            "extracted_note_id": extraction.id
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["cached"] is True
        assert data["bundle"]["entry"][0]["resource"]["id"] == "cached-patient"
    
    def test_to_fhir_bypass_cache(self, client_and_db):
        """Test that use_cache=False forces re-conversion."""
        client, db, doc_id = client_and_db
        from src import models
        
        # Create an extraction with cached FHIR bundle
        extraction = models.ExtractedNote(
            document_id=doc_id,
            structured_data={
                "patient": {"identifier": "fresh-patient"},
                "conditions": [],
                "medications": [],
                "vital_signs": [],
                "lab_results": [],
                "procedures": [],
                "care_plan": []
            },
            entity_counts={},
            fhir_bundle={"resourceType": "Bundle", "entry": [{"resource": {"resourceType": "Patient", "id": "old-cached"}}]}
        )
        db.add(extraction)
        db.commit()
        db.refresh(extraction)
        
        # Call with use_cache=False
        response = client.post("/to_fhir", json={
            "extracted_note_id": extraction.id,
            "use_cache": False
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["cached"] is False
        # The bundle should be freshly converted, not the cached one
        assert data["bundle"]["entry"][0]["resource"]["id"] != "old-cached"
    
    def test_to_fhir_caches_result(self, client_and_db):
        """Test that /to_fhir stores the result in cache."""
        client, db, doc_id = client_and_db
        from src import models
        
        # Create an extraction WITHOUT cached FHIR bundle
        extraction = models.ExtractedNote(
            document_id=doc_id,
            structured_data={
                "patient": {"identifier": "test-patient"},
                "conditions": [],
                "medications": [],
                "vital_signs": [],
                "lab_results": [],
                "procedures": [],
                "care_plan": []
            },
            entity_counts={},
            fhir_bundle=None  # No cache
        )
        db.add(extraction)
        db.commit()
        db.refresh(extraction)
        
        # First call - should convert and cache
        response1 = client.post("/to_fhir", json={
            "extracted_note_id": extraction.id
        })
        
        assert response1.status_code == 200
        data1 = response1.json()
        assert data1["cached"] is False  # First call, not cached
        
        # Refresh from DB to see cached value
        db.refresh(extraction)
        assert extraction.fhir_bundle is not None  # Should be cached now
        
        # Second call - should return cached
        response2 = client.post("/to_fhir", json={
            "extracted_note_id": extraction.id
        })
        
        assert response2.status_code == 200
        data2 = response2.json()
        assert data2["cached"] is True  # Second call, from cache


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

