"""
Entity Extraction Tool - LLM-based structured data extraction from SOAP notes.

This tool uses an LLM to extract medical entities from unstructured SOAP notes
into a structured intermediate format (RawExtraction) that can then be enriched
with ICD-10 and RxNorm codes.
"""
import json
import re
from typing import Optional
from .base import Tool, ToolResult
from src.providers.llm.factory import LLMFactory
from src.agent.models import RawExtraction, RawCondition, RawMedication, RawProcedure


# Comprehensive extraction prompt designed for medical SOAP notes
EXTRACTION_PROMPT = '''You are a medical data extraction specialist. Extract structured information from the following SOAP note.

SOAP Note:
{soap_note}

Extract the following entities and return as a JSON object. Be thorough but only extract information explicitly stated in the note.

Required JSON structure:
{{
  "patient_id": "patient identifier if present (e.g., 'patient--001')",
  "patient_name": "patient full name if present",
  "patient_dob": "date of birth in YYYY-MM-DD format if present",
  "patient_gender": "male, female, other, or unknown",
  
  "encounter_date": "encounter date in YYYY-MM-DD format",
  "encounter_type": "type of visit (e.g., 'annual physical', 'follow-up', 'post-surgical')",
  "encounter_reason": "chief complaint or reason for visit",
  
  "provider_name": "provider/physician name",
  "provider_specialty": "medical specialty (e.g., 'Internal Medicine', 'Family Medicine')",
  
  "conditions": [
    {{
      "name": "condition/diagnosis name exactly as clinically stated",
      "clinical_status": "active, resolved, or inactive",
      "note": "any additional clinical context"
    }}
  ],
  
  "medications": [
    {{
      "name": "medication name (generic preferred)",
      "dose": "dose with unit (e.g., '20 mg')",
      "route": "administration route (oral, IV, IM, topical, etc.)",
      "frequency": "how often (daily, BID, TID, PRN, etc.)",
      "quantity": "number of units dispensed (integer)",
      "refills": "number of refills (integer)",
      "as_needed": true/false for PRN medications,
      "reason": "indication/reason for medication"
    }}
  ],
  
  "procedures": [
    {{
      "name": "procedure name",
      "body_site": "body location",
      "date": "when performed in YYYY-MM-DD format",
      "status": "completed, scheduled, or in-progress",
      "note": "additional details"
    }}
  ],
  
  "vital_signs": [
    {{
      "name": "vital sign type (Blood Pressure, Heart Rate, Temperature, etc.)",
      "value": numeric_value,
      "unit": "unit of measurement",
      "value_string": "original string representation (e.g., '120/80 mmHg')"
    }}
  ],
  
  "lab_results": [
    {{
      "name": "lab test name",
      "value": numeric_value_or_null,
      "value_string": "string if non-numeric",
      "unit": "unit of measurement",
      "reference_range": "normal range",
      "interpretation": "normal, high, low, abnormal, etc."
    }}
  ],
  
  "care_plan": [
    {{
      "description": "planned activity or recommendation",
      "category": "follow-up, therapy, test, lifestyle, referral, etc.",
      "scheduled_string": "when scheduled (e.g., 'in 3 months', '2-4 weeks')",
      "status": "scheduled, not-started, in-progress, completed"
    }}
  ]
}}

IMPORTANT EXTRACTION RULES:
1. Only extract information explicitly present in the note
2. Use null for missing fields, not empty strings
3. For dates, convert to YYYY-MM-DD format when possible
4. For vital signs, extract both numeric value and string representation
5. For blood pressure, extract systolic as the primary value
6. Include ALL conditions mentioned in the Assessment section
7. Include ALL medications in the Plan section, including PRN
8. Include follow-up appointments, referrals, and lifestyle recommendations in care_plan
9. Extract procedures mentioned (past or scheduled)

Return ONLY the JSON object, no additional text.'''


class EntityExtractionTool(Tool):
    """
    Extracts structured medical entities from SOAP notes using LLM.
    
    This is the first step in the extraction pipeline, producing a RawExtraction
    that can then be enriched with medical codes (ICD-10, RxNorm).
    """
    
    def __init__(self, llm=None):
        """
        Initialize the extraction tool.
        
        Args:
            llm: Optional LLM provider. If not provided, uses factory default.
        """
        self._llm = llm
    
    @property
    def name(self) -> str:
        return "entity_extraction"
    
    @property
    def description(self) -> str:
        return (
            "Extracts structured medical entities from SOAP notes including "
            "patient info, conditions, medications, vital signs, lab results, "
            "procedures, and care plan activities."
        )
    
    @property
    def llm(self):
        """Lazy-load LLM provider."""
        if self._llm is None:
            self._llm = LLMFactory.create()
        return self._llm
    
    async def execute(self, soap_note: str) -> ToolResult:
        """
        Extract entities from a SOAP note.
        
        Args:
            soap_note: Raw SOAP note text
            
        Returns:
            ToolResult with RawExtraction data or error
        """
        if not soap_note or not soap_note.strip():
            return ToolResult.fail("Empty or whitespace-only SOAP note provided")
        
        try:
            # Generate extraction using LLM
            prompt = EXTRACTION_PROMPT.format(soap_note=soap_note)
            response = await self.llm.generate(prompt)
            
            # Parse JSON from response
            extraction_data = self._parse_llm_response(response)
            
            # Convert to RawExtraction model
            raw_extraction = self._build_raw_extraction(extraction_data)
            
            return ToolResult.ok(
                data=raw_extraction,
                llm_provider=self.llm.get_provider_name(),
                llm_model=self.llm.get_model_name(),
                raw_response_length=len(response)
            )
            
        except json.JSONDecodeError as e:
            return ToolResult.fail(
                f"Failed to parse LLM response as JSON: {str(e)}",
                raw_response=response[:500] if 'response' in dir() else None
            )
        except Exception as e:
            return ToolResult.fail(f"Extraction failed: {str(e)}")
    
    def _parse_llm_response(self, response: str) -> dict:
        """
        Parse JSON from LLM response, handling markdown code blocks.
        
        Args:
            response: Raw LLM response text
            
        Returns:
            Parsed JSON dictionary
        """
        # Clean up response - remove markdown code blocks if present
        cleaned = response.strip()
        
        # Handle ```json ... ``` blocks
        if cleaned.startswith("```"):
            # Find the end of the code block
            lines = cleaned.split("\n")
            json_lines = []
            in_block = False
            for line in lines:
                if line.startswith("```") and not in_block:
                    in_block = True
                    continue
                elif line.startswith("```") and in_block:
                    break
                elif in_block:
                    json_lines.append(line)
            cleaned = "\n".join(json_lines)
        
        # Try to find JSON object in response
        # Look for { ... } pattern
        match = re.search(r'\{[\s\S]*\}', cleaned)
        if match:
            cleaned = match.group(0)
        
        return json.loads(cleaned)
    
    def _build_raw_extraction(self, data: dict) -> RawExtraction:
        """
        Build RawExtraction model from parsed JSON.
        
        Args:
            data: Parsed extraction dictionary
            
        Returns:
            RawExtraction model
        """
        # Build conditions
        conditions = []
        for cond in data.get("conditions", []) or []:
            if cond and cond.get("name"):
                conditions.append(RawCondition(
                    name=cond["name"],
                    clinical_status=cond.get("clinical_status"),
                    note=cond.get("note")
                ))
        
        # Build medications
        medications = []
        for med in data.get("medications", []) or []:
            if med and med.get("name"):
                medications.append(RawMedication(
                    name=med["name"],
                    dose=med.get("dose"),
                    route=med.get("route"),
                    frequency=med.get("frequency"),
                    quantity=self._safe_int(med.get("quantity")),
                    refills=self._safe_int(med.get("refills")),
                    as_needed=bool(med.get("as_needed", False)),
                    reason=med.get("reason")
                ))
        
        # Build procedures
        procedures = []
        for proc in data.get("procedures", []) or []:
            if proc and proc.get("name"):
                procedures.append(RawProcedure(
                    name=proc["name"],
                    body_site=proc.get("body_site"),
                    date=proc.get("date"),
                    status=proc.get("status"),
                    note=proc.get("note")
                ))
        
        return RawExtraction(
            patient_id=data.get("patient_id"),
            patient_name=data.get("patient_name"),
            patient_dob=data.get("patient_dob"),
            patient_gender=data.get("patient_gender"),
            encounter_date=data.get("encounter_date"),
            encounter_type=data.get("encounter_type"),
            encounter_reason=data.get("encounter_reason"),
            provider_name=data.get("provider_name"),
            provider_specialty=data.get("provider_specialty"),
            conditions=conditions,
            medications=medications,
            procedures=procedures,
            vital_signs=data.get("vital_signs", []) or [],
            lab_results=data.get("lab_results", []) or [],
            care_plan=data.get("care_plan", []) or []
        )
    
    def _safe_int(self, value) -> Optional[int]:
        """Safely convert value to int."""
        if value is None:
            return None
        try:
            return int(value)
        except (ValueError, TypeError):
            return None

