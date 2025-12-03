"""
Part 4 Tests: Agent for Structured Data Extraction

Comprehensive tests for:
1. Tool unit tests (isolated with mocked dependencies)
2. Agent integration tests (with mocked APIs)
3. Golden set evaluation (with real API calls if available)
"""
import pytest
import asyncio
import json
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from datetime import datetime, date

# Import agent components
from src.agent.models import (
    StructuredNote, PatientInfo, Condition, Medication, VitalSign,
    LabResult, Procedure, CarePlanActivity, CodeableConcept, Dosage,
    RawExtraction, RawCondition, RawMedication, RawProcedure,
    Gender, ClinicalStatus, MedicationStatus
)
from src.agent.tools.base import Tool, ToolResult
from src.agent.tools.extractor import EntityExtractionTool
from src.agent.tools.icd_lookup import ICD10LookupTool, ICD10Code
from src.agent.tools.rxnorm_lookup import RxNormLookupTool, RxNormCode
from src.agent.tools.validator import ValidationTool
from src.agent.trajectory import Trajectory, TrajectoryStep, TrajectoryLogger, StepStatus
from src.agent.orchestrator import ExtractionAgent, ExtractionResult


# ============================================================================
# Sample SOAP Notes for Testing
# ============================================================================

SAMPLE_SOAP_NOTE = """
SOAP Note - Encounter Date: 2024-03-15 (Follow-Up Visit)
Patient: patient--001
S: Pt returns for follow-up on cholesterol. Labs drawn on previous encounter indicating elevated LDL (165 mg/dL).

O:
Vitals today:
BP: 134/84 mmHg
HR: 78 bpm
Weight stable at 192 lbs

A:
Hyperlipidemia
Overweight status

P:
Initiate atorvastatin 20 mg PO daily qHS
Return for follow-up in 3 months.

Signed:
Dr. Mark Reynolds, MD
Internal Medicine
"""

SAMPLE_EXTRACTION_JSON = {
    "patient_id": "patient--001",
    "patient_name": None,
    "patient_dob": None,
    "patient_gender": None,
    "encounter_date": "2024-03-15",
    "encounter_type": "follow-up",
    "encounter_reason": "cholesterol follow-up",
    "provider_name": "Dr. Mark Reynolds",
    "provider_specialty": "Internal Medicine",
    "conditions": [
        {"name": "Hyperlipidemia", "clinical_status": "active", "note": None},
        {"name": "Overweight status", "clinical_status": "active", "note": None}
    ],
    "medications": [
        {
            "name": "atorvastatin",
            "dose": "20 mg",
            "route": "oral",
            "frequency": "daily",
            "quantity": None,
            "refills": None,
            "as_needed": False,
            "reason": None
        }
    ],
    "procedures": [],
    "vital_signs": [
        {"name": "Blood Pressure", "value": 134, "unit": "mmHg", "value_string": "134/84 mmHg"},
        {"name": "Heart Rate", "value": 78, "unit": "bpm", "value_string": "78 bpm"},
        {"name": "Weight", "value": 192, "unit": "lbs", "value_string": "192 lbs"}
    ],
    "lab_results": [
        {"name": "LDL Cholesterol", "value": 165, "unit": "mg/dL", "reference_range": "<100 mg/dL", "interpretation": "elevated"}
    ],
    "care_plan": [
        {"description": "Return for follow-up", "category": "follow-up", "scheduled_string": "in 3 months", "status": "scheduled"}
    ]
}


# ============================================================================
# Tool Unit Tests
# ============================================================================

class TestToolBase:
    """Test base tool infrastructure."""
    
    def test_tool_result_ok(self):
        """Test ToolResult.ok() factory method."""
        result = ToolResult.ok(data={"key": "value"}, extra_meta="test")
        assert result.success is True
        assert result.data == {"key": "value"}
        assert result.error is None
        assert "timestamp" in result.metadata
        assert result.metadata.get("extra_meta") == "test"
    
    def test_tool_result_fail(self):
        """Test ToolResult.fail() factory method."""
        result = ToolResult.fail("Something went wrong", code=500)
        assert result.success is False
        assert result.data is None
        assert result.error == "Something went wrong"
        assert result.metadata.get("code") == 500


class TestEntityExtractionTool:
    """Test LLM entity extraction tool."""
    
    @pytest.mark.asyncio
    async def test_extraction_parses_soap_note(self):
        """Test that extraction tool correctly parses LLM output."""
        tool = EntityExtractionTool()
        
        # Mock LLM to return our sample extraction
        mock_llm = AsyncMock()
        mock_llm.generate.return_value = json.dumps(SAMPLE_EXTRACTION_JSON)
        mock_llm.get_provider_name.return_value = "openai"
        mock_llm.get_model_name.return_value = "gpt-4"
        tool._llm = mock_llm
        
        result = await tool.execute(SAMPLE_SOAP_NOTE)
        
        assert result.success is True
        assert isinstance(result.data, RawExtraction)
        assert result.data.patient_id == "patient--001"
        assert len(result.data.conditions) == 2
        assert result.data.conditions[0].name == "Hyperlipidemia"
        assert len(result.data.medications) == 1
        assert result.data.medications[0].name == "atorvastatin"
    
    @pytest.mark.asyncio
    async def test_extraction_handles_empty_note(self):
        """Test that extraction fails gracefully for empty notes."""
        tool = EntityExtractionTool()
        
        result = await tool.execute("")
        assert result.success is False
        assert "Empty" in result.error
        
        result = await tool.execute("   ")
        assert result.success is False
    
    @pytest.mark.asyncio
    async def test_extraction_handles_json_in_markdown(self):
        """Test that extraction handles JSON wrapped in markdown code blocks."""
        tool = EntityExtractionTool()
        
        mock_llm = AsyncMock()
        # LLM returns JSON in markdown code block
        mock_llm.generate.return_value = f"```json\n{json.dumps(SAMPLE_EXTRACTION_JSON)}\n```"
        mock_llm.get_provider_name.return_value = "openai"
        mock_llm.get_model_name.return_value = "gpt-4"
        tool._llm = mock_llm
        
        result = await tool.execute(SAMPLE_SOAP_NOTE)
        
        assert result.success is True
        assert isinstance(result.data, RawExtraction)
    
    @pytest.mark.asyncio
    async def test_extraction_handles_invalid_json(self):
        """Test that extraction fails gracefully for invalid JSON."""
        tool = EntityExtractionTool()
        
        mock_llm = AsyncMock()
        mock_llm.generate.return_value = "This is not valid JSON at all"
        mock_llm.get_provider_name.return_value = "openai"
        mock_llm.get_model_name.return_value = "gpt-4"
        tool._llm = mock_llm
        
        result = await tool.execute(SAMPLE_SOAP_NOTE)
        
        assert result.success is False
        assert "JSON" in result.error or "parse" in result.error.lower()


class TestICD10LookupTool:
    """Test ICD-10 code lookup tool."""
    
    @pytest.mark.asyncio
    async def test_icd_lookup_returns_code(self):
        """Test successful ICD-10 code lookup."""
        tool = ICD10LookupTool()
        
        # Mock the HTTP client
        mock_response = Mock()
        mock_response.json.return_value = [
            1,  # count
            ["E78.5"],  # codes
            None,
            [["E78.5", "Hyperlipidemia, unspecified"]]  # display data
        ]
        mock_response.raise_for_status = Mock()
        
        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.is_closed = False
        tool._client = mock_client
        
        result = await tool.execute("Hyperlipidemia")
        
        assert result.success is True
        assert isinstance(result.data, ICD10Code)
        assert result.data.code == "E78.5"
        assert "Hyperlipidemia" in result.data.display
    
    @pytest.mark.asyncio
    async def test_icd_lookup_handles_no_match(self):
        """Test ICD-10 lookup when no match found."""
        tool = ICD10LookupTool()
        
        mock_response = Mock()
        mock_response.json.return_value = [0, [], None, []]
        mock_response.raise_for_status = Mock()
        
        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.is_closed = False
        tool._client = mock_client
        
        result = await tool.execute("NonExistentCondition12345")
        
        assert result.success is False
        assert "No ICD-10 code found" in result.error
    
    @pytest.mark.asyncio
    async def test_icd_lookup_handles_empty_input(self):
        """Test ICD-10 lookup with empty input."""
        tool = ICD10LookupTool()
        
        result = await tool.execute("")
        assert result.success is False
        assert "Empty" in result.error
    
    @pytest.mark.asyncio
    async def test_icd_batch_lookup(self):
        """Test batch ICD-10 lookup for multiple conditions."""
        tool = ICD10LookupTool()
        
        # Mock successful responses
        mock_response = Mock()
        mock_response.json.return_value = [1, ["E78.5"], None, [["E78.5", "Hyperlipidemia"]]]
        mock_response.raise_for_status = Mock()
        
        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.is_closed = False
        tool._client = mock_client
        
        results = await tool.execute_batch(["Hyperlipidemia", "Hypertension"])
        
        assert len(results) == 2
        assert all(r.success for r in results)


class TestRxNormLookupTool:
    """Test RxNorm medication code lookup tool."""
    
    @pytest.mark.asyncio
    async def test_rxnorm_lookup_returns_rxcui(self):
        """Test successful RxNorm code lookup."""
        tool = RxNormLookupTool()
        
        # Mock exact match response
        mock_response = Mock()
        mock_response.json.return_value = {
            "idGroup": {
                "rxnormId": ["83367"]
            }
        }
        mock_response.raise_for_status = Mock()
        
        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.is_closed = False
        tool._client = mock_client
        
        result = await tool.execute("atorvastatin")
        
        assert result.success is True
        assert isinstance(result.data, RxNormCode)
        assert result.data.rxcui == "83367"
    
    @pytest.mark.asyncio
    async def test_rxnorm_fuzzy_match(self):
        """Test RxNorm fuzzy/approximate matching."""
        tool = RxNormLookupTool()
        
        # Mock exact match fails, approximate succeeds
        exact_response = Mock()
        exact_response.json.return_value = {"idGroup": {}}
        exact_response.raise_for_status = Mock()
        
        approx_response = Mock()
        approx_response.json.return_value = {
            "approximateGroup": {
                "candidate": [
                    {"rxcui": "83367", "name": "atorvastatin", "score": "100"}
                ]
            }
        }
        approx_response.raise_for_status = Mock()
        
        mock_client = AsyncMock()
        mock_client.get.side_effect = [exact_response, approx_response]
        mock_client.is_closed = False
        tool._client = mock_client
        
        result = await tool.execute("atorvastatin 20mg tablet")
        
        assert result.success is True
        assert result.data.rxcui == "83367"
        assert result.data.match_type == "approximate"
    
    @pytest.mark.asyncio
    async def test_rxnorm_handles_no_match(self):
        """Test RxNorm lookup when no match found."""
        tool = RxNormLookupTool()
        
        no_match_response = Mock()
        no_match_response.json.return_value = {"idGroup": {}}
        no_match_response.raise_for_status = Mock()
        
        approx_no_match = Mock()
        approx_no_match.json.return_value = {"approximateGroup": {}}
        approx_no_match.raise_for_status = Mock()
        
        mock_client = AsyncMock()
        mock_client.get.side_effect = [no_match_response, approx_no_match, approx_no_match]
        mock_client.is_closed = False
        tool._client = mock_client
        
        result = await tool.execute("nonexistentmedication12345")
        
        assert result.success is False
        assert "No RxNorm code found" in result.error
    
    def test_medication_name_normalization(self):
        """Test medication name normalization removes dosage info."""
        tool = RxNormLookupTool()
        
        assert tool._normalize_medication_name("atorvastatin 20 mg") == "atorvastatin"
        assert tool._normalize_medication_name("ibuprofen 400mg tablet") == "ibuprofen"
        assert tool._normalize_medication_name("Lisinopril 10mg oral") == "Lisinopril"


class TestValidationTool:
    """Test Pydantic validation tool."""
    
    @pytest.mark.asyncio
    async def test_validator_accepts_valid_data(self):
        """Test validator accepts well-formed data."""
        tool = ValidationTool()
        
        valid_data = {
            "patient": {
                "identifier": "patient-001",
                "name": "John Doe",
                "gender": "male"
            },
            "conditions": [
                {
                    "code": {"display": "Hypertension", "code": "I10"},
                    "clinical_status": "active",
                    "verification_status": "confirmed"
                }
            ],
            "medications": [],
            "vital_signs": [],
            "lab_results": [],
            "procedures": [],
            "care_plan": []
        }
        
        result = await tool.execute(valid_data)
        
        assert result.success is True
        assert isinstance(result.data, StructuredNote)
    
    @pytest.mark.asyncio
    async def test_validator_rejects_invalid_data(self):
        """Test validator rejects malformed data."""
        tool = ValidationTool()
        
        # Missing required 'display' in codeable concept
        invalid_data = {
            "conditions": [
                {
                    "code": {"code": "I10"},  # missing 'display'
                    "clinical_status": "active"
                }
            ]
        }
        
        result = await tool.execute(invalid_data)
        
        assert result.success is False
        assert "validation_errors" in result.metadata
    
    @pytest.mark.asyncio
    async def test_validator_handles_empty_data(self):
        """Test validator handles empty input."""
        tool = ValidationTool()
        
        # Empty dict creates valid StructuredNote with defaults
        result = await tool.execute({
            "conditions": [],
            "medications": [],
            "vital_signs": [],
            "lab_results": [],
            "procedures": [],
            "care_plan": []
        })
        assert result.success is True
        
        result = await tool.execute(None)
        assert result.success is False


# ============================================================================
# Trajectory Logger Tests
# ============================================================================

class TestTrajectoryLogger:
    """Test trajectory logging functionality."""
    
    def test_trajectory_step_timing(self):
        """Test step timing calculation."""
        step = TrajectoryStep(step_number=1, step_name="Test", tool_name="test_tool")
        
        step.start()
        assert step.status == StepStatus.RUNNING
        assert step.started_at is not None
        
        step.complete(output_data="result")
        assert step.status == StepStatus.SUCCESS
        assert step.completed_at is not None
        assert step.duration_ms is not None
        assert step.duration_ms >= 0
    
    def test_trajectory_logger_workflow(self):
        """Test complete trajectory logging workflow."""
        logger = TrajectoryLogger("TestAgent", "Test input")
        
        # Step 1
        step1 = logger.start_step("Step 1", "tool1", "Input for step 1")
        logger.complete_step(step1, output_summary="Step 1 done")
        
        # Step 2
        step2 = logger.start_step("Step 2", "tool2")
        logger.fail_step(step2, "Step 2 failed", "TestError")
        
        # Complete trajectory
        logger.complete(success=False, error="Pipeline failed")
        
        trajectory = logger.get_trajectory()
        
        assert trajectory.agent_name == "TestAgent"
        assert trajectory.success is False
        assert len(trajectory.steps) == 2
        assert trajectory.steps[0].status == StepStatus.SUCCESS
        assert trajectory.steps[1].status == StepStatus.FAILED
    
    def test_trajectory_to_dict(self):
        """Test trajectory serialization."""
        logger = TrajectoryLogger("TestAgent")
        step = logger.start_step("Test Step", "test_tool")
        logger.complete_step(step, output_summary="Done")
        logger.complete(success=True)
        
        trajectory = logger.get_trajectory()
        data = trajectory.to_dict()
        
        assert data["agent_name"] == "TestAgent"
        assert data["success"] is True
        assert len(data["steps"]) == 1
        assert "statistics" in data


# ============================================================================
# Agent Integration Tests
# ============================================================================

class TestExtractionAgent:
    """Test the complete extraction agent pipeline."""
    
    @pytest.mark.asyncio
    async def test_full_extraction_pipeline(self):
        """Test complete extraction pipeline with mocked tools."""
        agent = ExtractionAgent()
        
        # Mock the extractor tool
        mock_raw_extraction = RawExtraction(
            patient_id="patient--001",
            encounter_date="2024-03-15",
            provider_name="Dr. Test",
            provider_specialty="Internal Medicine",
            conditions=[RawCondition(name="Hyperlipidemia", clinical_status="active")],
            medications=[RawMedication(name="atorvastatin", dose="20 mg", frequency="daily")],
            vital_signs=[{"name": "Blood Pressure", "value": 134, "unit": "mmHg"}],
            lab_results=[],
            care_plan=[]
        )
        
        mock_extractor = AsyncMock()
        mock_extractor.execute.return_value = ToolResult.ok(mock_raw_extraction)
        agent.extractor = mock_extractor
        
        # Mock ICD-10 lookup
        mock_icd = AsyncMock()
        mock_icd.execute_batch.return_value = [
            ToolResult.ok(ICD10Code(code="E78.5", display="Hyperlipidemia"))
        ]
        mock_icd.close = AsyncMock()
        agent.icd_lookup = mock_icd
        
        # Mock RxNorm lookup
        mock_rxnorm = AsyncMock()
        mock_rxnorm.execute_batch.return_value = [
            ToolResult.ok(RxNormCode(rxcui="83367", display="atorvastatin"))
        ]
        mock_rxnorm.close = AsyncMock()
        agent.rxnorm_lookup = mock_rxnorm
        
        # Run extraction
        result = await agent.extract(SAMPLE_SOAP_NOTE)
        
        assert result.success is True
        assert result.structured_note is not None
        assert len(result.structured_note.conditions) == 1
        assert result.structured_note.conditions[0].code.code == "E78.5"
        assert len(result.structured_note.medications) == 1
        assert result.structured_note.medications[0].code.code == "83367"
    
    @pytest.mark.asyncio
    async def test_trajectory_logged_correctly(self):
        """Test that trajectory captures all pipeline steps."""
        agent = ExtractionAgent()
        
        # Mock successful extraction
        mock_raw = RawExtraction(
            conditions=[RawCondition(name="Test", clinical_status="active")],
            medications=[]
        )
        
        mock_extractor = AsyncMock()
        mock_extractor.execute.return_value = ToolResult.ok(mock_raw)
        agent.extractor = mock_extractor
        
        mock_icd = AsyncMock()
        mock_icd.execute_batch.return_value = [ToolResult.ok(ICD10Code(code="Z00", display="Test"))]
        mock_icd.close = AsyncMock()
        agent.icd_lookup = mock_icd
        
        mock_rxnorm = AsyncMock()
        mock_rxnorm.execute_batch.return_value = []
        mock_rxnorm.close = AsyncMock()
        agent.rxnorm_lookup = mock_rxnorm
        
        result = await agent.extract("Test SOAP note")
        
        assert result.trajectory is not None
        assert result.trajectory.agent_name == "ExtractionAgent"
        
        # Check that key steps are logged
        step_names = [s.step_name for s in result.trajectory.steps]
        assert "Extract Entities" in step_names
        assert "Enrich Conditions (ICD-10)" in step_names
        assert "Transform Entities" in step_names
        assert "Validate Output" in step_names
    
    @pytest.mark.asyncio
    async def test_handles_empty_note(self):
        """Test agent handles empty SOAP note gracefully."""
        agent = ExtractionAgent()
        
        mock_extractor = AsyncMock()
        mock_extractor.execute.return_value = ToolResult.fail("Empty note")
        agent.extractor = mock_extractor
        
        # Mock cleanup methods
        agent.icd_lookup.close = AsyncMock()
        agent.rxnorm_lookup.close = AsyncMock()
        
        result = await agent.extract("")
        
        assert result.success is False
        assert result.error is not None
    
    @pytest.mark.asyncio
    async def test_handles_missing_patient(self):
        """Test extraction works even without patient info."""
        agent = ExtractionAgent()
        
        # Extraction without patient info
        mock_raw = RawExtraction(
            patient_id=None,
            patient_name=None,
            conditions=[RawCondition(name="Fever", clinical_status="active")]
        )
        
        mock_extractor = AsyncMock()
        mock_extractor.execute.return_value = ToolResult.ok(mock_raw)
        agent.extractor = mock_extractor
        
        mock_icd = AsyncMock()
        mock_icd.execute_batch.return_value = [ToolResult.ok(ICD10Code(code="R50.9", display="Fever"))]
        mock_icd.close = AsyncMock()
        agent.icd_lookup = mock_icd
        
        mock_rxnorm = AsyncMock()
        mock_rxnorm.execute_batch.return_value = []
        mock_rxnorm.close = AsyncMock()
        agent.rxnorm_lookup = mock_rxnorm
        
        result = await agent.extract("Minimal SOAP note with fever")
        
        assert result.success is True
        assert result.structured_note.patient is None
        assert len(result.structured_note.conditions) == 1
    
    @pytest.mark.asyncio
    async def test_extracts_multiple_conditions(self):
        """Test extraction handles multiple conditions correctly."""
        agent = ExtractionAgent()
        
        mock_raw = RawExtraction(
            conditions=[
                RawCondition(name="Hypertension", clinical_status="active"),
                RawCondition(name="Type 2 Diabetes", clinical_status="active"),
                RawCondition(name="Obesity", clinical_status="active")
            ]
        )
        
        mock_extractor = AsyncMock()
        mock_extractor.execute.return_value = ToolResult.ok(mock_raw)
        agent.extractor = mock_extractor
        
        mock_icd = AsyncMock()
        mock_icd.execute_batch.return_value = [
            ToolResult.ok(ICD10Code(code="I10", display="Hypertension")),
            ToolResult.ok(ICD10Code(code="E11.9", display="Type 2 Diabetes")),
            ToolResult.ok(ICD10Code(code="E66.9", display="Obesity"))
        ]
        mock_icd.close = AsyncMock()
        agent.icd_lookup = mock_icd
        
        mock_rxnorm = AsyncMock()
        mock_rxnorm.execute_batch.return_value = []
        mock_rxnorm.close = AsyncMock()
        agent.rxnorm_lookup = mock_rxnorm
        
        result = await agent.extract("Note with multiple conditions")
        
        assert result.success is True
        assert len(result.structured_note.conditions) == 3
        
        # Verify all codes assigned
        codes = [c.code.code for c in result.structured_note.conditions]
        assert "I10" in codes
        assert "E11.9" in codes
        assert "E66.9" in codes


# ============================================================================
# API Endpoint Tests
# ============================================================================

class TestExtractStructuredEndpoint:
    """Test the /extract_structured API endpoint."""
    
    @pytest.fixture
    def client(self):
        """Create test client with mocked database."""
        from fastapi.testclient import TestClient
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from src.main import app
        from src.database import Base, get_db
        
        # Use SQLite in /tmp for container compatibility
        engine = create_engine("sqlite:////tmp/test_part4.db", connect_args={"check_same_thread": False})
        TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        Base.metadata.create_all(bind=engine)
        
        def override_get_db():
            try:
                db = TestingSessionLocal()
                yield db
            finally:
                db.close()
        
        app.dependency_overrides[get_db] = override_get_db
        return TestClient(app)
    
    def test_endpoint_requires_input(self, client):
        """Test that endpoint requires either document_id or text."""
        response = client.post("/extract_structured", json={})
        assert response.status_code == 400
        assert "document_id or text" in response.json()["detail"]
    
    def test_endpoint_document_not_found(self, client):
        """Test that endpoint returns 404 for non-existent document."""
        response = client.post("/extract_structured", json={"document_id": 99999})
        assert response.status_code == 404


# ============================================================================
# Golden Set Evaluation (Optional - requires API key)
# ============================================================================

GOLDEN_SOAP_NOTES = [
    {
        "note": """SOAP Note - Encounter Date: 2024-03-15
Patient: patient--001
S: Pt returns for follow-up on cholesterol.
O: BP: 134/84 mmHg, HR: 78 bpm
A: Hyperlipidemia
P: Initiate atorvastatin 20 mg PO daily
Signed: Dr. Mark Reynolds, MD, Internal Medicine""",
        "expected_conditions": ["Hyperlipidemia"],
        "expected_medications": ["atorvastatin"]
    },
    {
        "note": """SOAP Note - Encounter Date: 2023-12-28
Patient: Emily G. Williams. DOB 1996-12-02
S: Pt presents for post-surgical follow-up s/p arthroscopic surgery of left knee
O: BP: 118/74 mmHg, HR: 70 bpm, Temp: 98.4°F
A: Status-post left knee arthroscopic meniscal repair
P: Continue ibuprofen 400mg-600mg PO PRN
Signed: Dr. Sarah Martinez, MD, Orthopedic Surgery""",
        "expected_conditions": ["meniscal repair"],
        "expected_medications": ["ibuprofen"]
    }
]


# ============================================================================
# Real API Integration Tests (NIH APIs - no API key needed)
# ============================================================================

class TestRealNIHAPIs:
    """Integration tests that call the REAL NIH APIs (no mocking)."""
    
    @pytest.mark.asyncio
    async def test_real_icd10_lookup_hyperlipidemia(self):
        """Test real ICD-10 API call for Hyperlipidemia."""
        tool = ICD10LookupTool()
        
        result = await tool.execute("Hyperlipidemia")
        await tool.close()
        
        assert result.success is True, f"API call failed: {result.error}"
        assert result.data is not None
        assert result.data.code is not None
        # E78.5 is the ICD-10 code for Hyperlipidemia, unspecified
        assert result.data.code.startswith("E78"), f"Expected E78.x code, got {result.data.code}"
        print(f"✅ ICD-10 for 'Hyperlipidemia': {result.data.code} - {result.data.display}")
    
    @pytest.mark.asyncio
    async def test_real_icd10_lookup_hypertension(self):
        """Test real ICD-10 API call for Hypertension."""
        tool = ICD10LookupTool()
        
        result = await tool.execute("Essential Hypertension")
        await tool.close()
        
        assert result.success is True, f"API call failed: {result.error}"
        assert result.data.code is not None
        # I10 is the ICD-10 code for Essential hypertension
        assert result.data.code.startswith("I1"), f"Expected I1x code, got {result.data.code}"
        print(f"✅ ICD-10 for 'Essential Hypertension': {result.data.code} - {result.data.display}")
    
    @pytest.mark.asyncio
    async def test_real_icd10_lookup_diabetes(self):
        """Test real ICD-10 API call for Type 2 Diabetes."""
        tool = ICD10LookupTool()
        
        result = await tool.execute("Type 2 Diabetes Mellitus")
        await tool.close()
        
        assert result.success is True, f"API call failed: {result.error}"
        assert result.data.code is not None
        # E11.x is the ICD-10 code range for Type 2 diabetes
        assert result.data.code.startswith("E11"), f"Expected E11.x code, got {result.data.code}"
        print(f"✅ ICD-10 for 'Type 2 Diabetes Mellitus': {result.data.code} - {result.data.display}")
    
    @pytest.mark.asyncio
    async def test_real_rxnorm_lookup_atorvastatin(self):
        """Test real RxNorm API call for Atorvastatin."""
        tool = RxNormLookupTool()
        
        result = await tool.execute("atorvastatin")
        await tool.close()
        
        assert result.success is True, f"API call failed: {result.error}"
        assert result.data is not None
        assert result.data.rxcui is not None
        # 83367 is the RxCUI for atorvastatin
        print(f"✅ RxNorm for 'atorvastatin': RxCUI={result.data.rxcui} - {result.data.display}")
    
    @pytest.mark.asyncio
    async def test_real_rxnorm_lookup_ibuprofen(self):
        """Test real RxNorm API call for Ibuprofen."""
        tool = RxNormLookupTool()
        
        result = await tool.execute("ibuprofen")
        await tool.close()
        
        assert result.success is True, f"API call failed: {result.error}"
        assert result.data.rxcui is not None
        print(f"✅ RxNorm for 'ibuprofen': RxCUI={result.data.rxcui} - {result.data.display}")
    
    @pytest.mark.asyncio
    async def test_real_rxnorm_lookup_lisinopril(self):
        """Test real RxNorm API call for Lisinopril."""
        tool = RxNormLookupTool()
        
        result = await tool.execute("lisinopril")
        await tool.close()
        
        assert result.success is True, f"API call failed: {result.error}"
        assert result.data.rxcui is not None
        print(f"✅ RxNorm for 'lisinopril': RxCUI={result.data.rxcui} - {result.data.display}")
    
    @pytest.mark.asyncio
    async def test_real_batch_icd10_lookup(self):
        """Test real batch ICD-10 lookup for multiple conditions."""
        tool = ICD10LookupTool()
        
        conditions = ["Hyperlipidemia", "Hypertension", "Obesity"]
        results = await tool.execute_batch(conditions)
        await tool.close()
        
        print("\n📊 Batch ICD-10 Results:")
        for cond, result in zip(conditions, results):
            if result.success:
                print(f"  ✅ {cond}: {result.data.code} - {result.data.display}")
            else:
                print(f"  ❌ {cond}: {result.error}")
        
        # At least 2 out of 3 should succeed
        success_count = sum(1 for r in results if r.success)
        assert success_count >= 2, f"Only {success_count}/3 lookups succeeded"
    
    @pytest.mark.asyncio
    async def test_real_batch_rxnorm_lookup(self):
        """Test real batch RxNorm lookup for multiple medications."""
        tool = RxNormLookupTool()
        
        medications = ["atorvastatin", "metformin", "lisinopril"]
        results = await tool.execute_batch(medications)
        await tool.close()
        
        print("\n📊 Batch RxNorm Results:")
        for med, result in zip(medications, results):
            if result.success:
                print(f"  ✅ {med}: RxCUI={result.data.rxcui} - {result.data.display}")
            else:
                print(f"  ❌ {med}: {result.error}")
        
        # All 3 should succeed (these are common medications)
        success_count = sum(1 for r in results if r.success)
        assert success_count == 3, f"Only {success_count}/3 lookups succeeded"


class TestGoldenSetEvaluation:
    """Evaluate extraction against golden set (requires API key)."""
    
    @pytest.fixture
    def api_key_available(self):
        """Check if API key is available."""
        from src.config import settings
        return bool(settings.llm_api_key)
    
    @pytest.mark.asyncio
    async def test_golden_set_extraction(self, api_key_available):
        """Test extraction accuracy against golden set."""
        if not api_key_available:
            pytest.skip("API key not configured")
        
        agent = ExtractionAgent()
        
        results = []
        for item in GOLDEN_SOAP_NOTES:
            result = await agent.extract(item["note"])
            
            if result.success:
                # Check conditions extracted
                extracted_conditions = [c.code.display.lower() for c in result.structured_note.conditions]
                condition_matches = sum(
                    1 for exp in item["expected_conditions"]
                    if any(exp.lower() in ec for ec in extracted_conditions)
                )
                
                # Check medications extracted
                extracted_meds = [m.code.display.lower() for m in result.structured_note.medications]
                med_matches = sum(
                    1 for exp in item["expected_medications"]
                    if any(exp.lower() in em for em in extracted_meds)
                )
                
                results.append({
                    "success": True,
                    "condition_recall": condition_matches / len(item["expected_conditions"]),
                    "medication_recall": med_matches / len(item["expected_medications"])
                })
            else:
                results.append({"success": False})
        
        # Calculate aggregate metrics
        successful = [r for r in results if r["success"]]
        if successful:
            avg_condition_recall = sum(r["condition_recall"] for r in successful) / len(successful)
            avg_medication_recall = sum(r["medication_recall"] for r in successful) / len(successful)
            
            print(f"\n📊 Golden Set Evaluation Results:")
            print(f"Success Rate: {len(successful)}/{len(results)}")
            print(f"Avg Condition Recall: {avg_condition_recall:.2%}")
            print(f"Avg Medication Recall: {avg_medication_recall:.2%}")
            
            # Assert minimum thresholds
            assert avg_condition_recall >= 0.8, "Condition recall below 80%"
            assert avg_medication_recall >= 0.8, "Medication recall below 80%"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

