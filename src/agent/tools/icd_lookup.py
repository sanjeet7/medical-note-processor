"""
ICD-10 Lookup Tool - NIH ClinicalTables API integration for diagnosis codes.

Uses the NIH ClinicalTables API to look up ICD-10-CM codes for conditions
and diagnoses extracted from medical notes.

API Documentation: https://clinicaltables.nlm.nih.gov/apidoc/icd10cm/v3/doc.html
"""
import asyncio
from typing import Optional, List
from dataclasses import dataclass
import httpx
from .base import Tool, ToolResult, BatchTool


# NIH ClinicalTables API for ICD-10-CM
ICD10_API_BASE = "https://clinicaltables.nlm.nih.gov/api/icd10cm/v3/search"


@dataclass
class ICD10Code:
    """Represents an ICD-10-CM code lookup result."""
    code: str
    display: str
    system: str = "http://hl7.org/fhir/sid/icd-10-cm"
    match_score: float = 1.0


class ICD10LookupTool(BatchTool):
    """
    Looks up ICD-10-CM codes for medical conditions using NIH ClinicalTables API.
    
    Features:
    - Single and batch lookup support
    - Handles ambiguous terms (returns best match)
    - Graceful degradation when no match found
    - Rate limiting respect (built into httpx)
    """
    
    def __init__(self, timeout: float = 10.0, max_results: int = 5):
        """
        Initialize the ICD-10 lookup tool.
        
        Args:
            timeout: HTTP request timeout in seconds
            max_results: Maximum results to request from API
        """
        self.timeout = timeout
        self.max_results = max_results
        self._client: Optional[httpx.AsyncClient] = None
    
    @property
    def name(self) -> str:
        return "icd10_lookup"
    
    @property
    def description(self) -> str:
        return (
            "Looks up ICD-10-CM diagnosis codes from the NIH ClinicalTables API. "
            "Input a condition/diagnosis name and receive the corresponding code."
        )
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=self.timeout)
        return self._client
    
    async def close(self):
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
    
    async def execute(self, condition_name: str) -> ToolResult:
        """
        Look up ICD-10-CM code for a condition.
        
        Args:
            condition_name: Medical condition/diagnosis name
            
        Returns:
            ToolResult with ICD10Code data or error
        """
        if not condition_name or not condition_name.strip():
            return ToolResult.fail("Empty condition name provided")
        
        try:
            client = await self._get_client()
            
            # Query the NIH API
            # API returns: [total_count, codes_array, null, display_strings_array]
            params = {
                "terms": condition_name.strip(),
                "maxList": self.max_results,
                "sf": "code,name"  # Search fields
            }
            
            response = await client.get(ICD10_API_BASE, params=params)
            response.raise_for_status()
            
            data = response.json()
            
            # Parse API response: [count, [codes], null, [[code, name], ...]]
            if not data or len(data) < 4:
                return ToolResult.fail(
                    f"No ICD-10 code found for: {condition_name}",
                    search_term=condition_name
                )
            
            count = data[0]
            codes = data[1]
            display_data = data[3]
            
            if count == 0 or not codes:
                return ToolResult.fail(
                    f"No ICD-10 code found for: {condition_name}",
                    search_term=condition_name
                )
            
            # Get best match (first result)
            best_code = codes[0]
            best_display = display_data[0] if display_data else [best_code, condition_name]
            
            # Display is [code, description] or just description
            if isinstance(best_display, list):
                display_text = best_display[1] if len(best_display) > 1 else best_display[0]
            else:
                display_text = best_display
            
            icd_code = ICD10Code(
                code=best_code,
                display=display_text,
                match_score=1.0 if count == 1 else 0.9  # Lower score if ambiguous
            )
            
            return ToolResult.ok(
                data=icd_code,
                search_term=condition_name,
                total_matches=count,
                api_endpoint=ICD10_API_BASE
            )
            
        except httpx.TimeoutException:
            return ToolResult.fail(
                f"API timeout looking up: {condition_name}",
                search_term=condition_name
            )
        except httpx.HTTPStatusError as e:
            return ToolResult.fail(
                f"API error ({e.response.status_code}): {str(e)}",
                search_term=condition_name
            )
        except Exception as e:
            return ToolResult.fail(
                f"ICD-10 lookup failed: {str(e)}",
                search_term=condition_name
            )
    
    async def execute_batch(self, conditions: List[str]) -> List[ToolResult]:
        """
        Look up ICD-10 codes for multiple conditions in parallel.
        
        Args:
            conditions: List of condition names
            
        Returns:
            List of ToolResults, one per condition
        """
        if not conditions:
            return []
        
        # Execute all lookups in parallel
        tasks = [self.execute(cond) for cond in conditions]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Convert any exceptions to failed results
        processed = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed.append(ToolResult.fail(
                    f"Batch lookup failed: {str(result)}",
                    search_term=conditions[i]
                ))
            else:
                processed.append(result)
        
        return processed
    
    async def lookup_with_fallback(self, condition_name: str) -> Optional[ICD10Code]:
        """
        Convenience method that returns ICD10Code or None.
        
        Useful when you want simple access without handling ToolResult.
        
        Args:
            condition_name: Medical condition name
            
        Returns:
            ICD10Code if found, None otherwise
        """
        result = await self.execute(condition_name)
        return result.data if result.success else None

