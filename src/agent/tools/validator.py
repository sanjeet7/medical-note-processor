"""
Validation Tool - Pydantic-based structured data validation.

Validates extracted and enriched medical data against the FHIR-aligned
Pydantic models, ensuring data quality before final output.
"""
from typing import Any, Dict, List, Optional
from pydantic import ValidationError
from .base import Tool, ToolResult
from src.agent.models import StructuredNote, PatientInfo, Condition, Medication


class ValidationTool(Tool):
    """
    Validates structured medical data against Pydantic models.
    
    Performs:
    - Schema validation (required fields, types)
    - Business rule validation (logical consistency)
    - Data quality checks
    """
    
    @property
    def name(self) -> str:
        return "validator"
    
    @property
    def description(self) -> str:
        return (
            "Validates extracted medical data against FHIR-aligned schemas. "
            "Ensures data quality and schema compliance before output."
        )
    
    async def execute(self, structured_data: Dict[str, Any]) -> ToolResult:
        """
        Validate structured data and return StructuredNote.
        
        Args:
            structured_data: Dictionary of extracted/enriched data
            
        Returns:
            ToolResult with validated StructuredNote or validation errors
        """
        if not structured_data:
            return ToolResult.fail("No data provided for validation")
        
        errors = []
        warnings = []
        
        try:
            # Validate the complete structure
            validated = StructuredNote(**structured_data)
            
            # Additional business rule validations
            warnings.extend(self._check_business_rules(validated))
            
            return ToolResult.ok(
                data=validated,
                entity_counts=validated.entity_count(),
                warnings=warnings if warnings else None
            )
            
        except ValidationError as e:
            # Collect all validation errors
            for error in e.errors():
                field = ".".join(str(loc) for loc in error["loc"])
                errors.append({
                    "field": field,
                    "message": error["msg"],
                    "type": error["type"]
                })
            
            return ToolResult.fail(
                f"Validation failed with {len(errors)} error(s)",
                validation_errors=errors
            )
        except Exception as e:
            return ToolResult.fail(f"Validation error: {str(e)}")
    
    def _check_business_rules(self, data: StructuredNote) -> List[str]:
        """
        Check business rules and return warnings.
        
        Args:
            data: Validated StructuredNote
            
        Returns:
            List of warning messages
        """
        warnings = []
        
        # Check for missing patient info
        if not data.patient or (not data.patient.name and not data.patient.identifier):
            warnings.append("Patient identification is incomplete")
        
        # Check for conditions without codes
        for i, cond in enumerate(data.conditions):
            if not cond.code.code:
                warnings.append(f"Condition '{cond.code.display}' has no ICD-10 code")
        
        # Check for medications without codes
        for i, med in enumerate(data.medications):
            if not med.code.code:
                warnings.append(f"Medication '{med.code.display}' has no RxNorm code")
        
        # Check for medications without dosage
        for med in data.medications:
            if not med.dosage or not med.dosage.text:
                warnings.append(f"Medication '{med.code.display}' has no dosage information")
        
        return warnings
    
    async def validate_partial(self, data: Dict[str, Any], model_name: str) -> ToolResult:
        """
        Validate a partial structure against a specific model.
        
        Useful for validating individual components before assembly.
        
        Args:
            data: Data to validate
            model_name: Name of the model to validate against
            
        Returns:
            ToolResult with validated data or errors
        """
        models = {
            "patient": PatientInfo,
            "condition": Condition,
            "medication": Medication,
            "structured_note": StructuredNote,
        }
        
        model = models.get(model_name.lower())
        if not model:
            return ToolResult.fail(f"Unknown model: {model_name}")
        
        try:
            validated = model(**data)
            return ToolResult.ok(data=validated)
        except ValidationError as e:
            errors = [
                {"field": ".".join(str(loc) for loc in err["loc"]), "message": err["msg"]}
                for err in e.errors()
            ]
            return ToolResult.fail(
                f"Validation failed for {model_name}",
                validation_errors=errors
            )

