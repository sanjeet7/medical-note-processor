"""
RxNorm Lookup Tool - NIH RxNav API integration for medication codes.

Uses the NIH RxNav API to look up RxNorm codes (RxCUI) for medications
extracted from medical notes.

API Documentation: https://lhncbc.nlm.nih.gov/RxNav/APIs/api-RxNorm.findRxcuiByString.html
"""
import asyncio
from typing import Optional, List
from dataclasses import dataclass
import httpx
from .base import Tool, ToolResult, BatchTool


# NIH RxNav API endpoints
RXNORM_API_BASE = "https://rxnav.nlm.nih.gov/REST"
RXCUI_ENDPOINT = f"{RXNORM_API_BASE}/rxcui.json"
APPROX_ENDPOINT = f"{RXNORM_API_BASE}/approximateTerm.json"
DRUGS_ENDPOINT = f"{RXNORM_API_BASE}/drugs.json"


@dataclass
class RxNormCode:
    """Represents an RxNorm code lookup result."""
    rxcui: str
    display: str
    system: str = "http://www.nlm.nih.gov/research/umls/rxnorm"
    match_type: str = "exact"  # exact, approximate, or normalized


class RxNormLookupTool(BatchTool):
    """
    Looks up RxNorm codes (RxCUI) for medications using NIH RxNav API.
    
    Features:
    - Exact name matching (primary)
    - Approximate term matching (fallback)
    - Drug name normalization
    - Handles brand vs generic names
    - Batch lookup support for multiple medications
    """
    
    def __init__(self, timeout: float = 10.0, max_results: int = 5):
        """
        Initialize the RxNorm lookup tool.
        
        Args:
            timeout: HTTP request timeout in seconds
            max_results: Maximum results for approximate matching
        """
        self.timeout = timeout
        self.max_results = max_results
        self._client: Optional[httpx.AsyncClient] = None
    
    @property
    def name(self) -> str:
        return "rxnorm_lookup"
    
    @property
    def description(self) -> str:
        return (
            "Looks up RxNorm codes (RxCUI) for medications from the NIH RxNav API. "
            "Input a medication name and receive the corresponding RxCUI code."
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
    
    async def execute(self, medication_name: str) -> ToolResult:
        """
        Look up RxNorm code for a medication.
        
        Strategy:
        1. Try exact name match
        2. Fall back to approximate term search
        3. Try drug name normalization
        
        Args:
            medication_name: Medication name (brand or generic)
            
        Returns:
            ToolResult with RxNormCode data or error
        """
        if not medication_name or not medication_name.strip():
            return ToolResult.fail("Empty medication name provided")
        
        # Normalize medication name (remove dosage info for lookup)
        clean_name = self._normalize_medication_name(medication_name)
        
        try:
            client = await self._get_client()
            
            # Strategy 1: Exact match
            result = await self._exact_lookup(client, clean_name)
            if result.success:
                return result
            
            # Strategy 2: Approximate term search
            result = await self._approximate_lookup(client, clean_name)
            if result.success:
                return result
            
            # Strategy 3: Try with original name if different
            if clean_name != medication_name.strip():
                result = await self._approximate_lookup(client, medication_name.strip())
                if result.success:
                    return result
            
            return ToolResult.fail(
                f"No RxNorm code found for: {medication_name}",
                search_term=medication_name,
                normalized_term=clean_name
            )
            
        except httpx.TimeoutException:
            return ToolResult.fail(
                f"API timeout looking up: {medication_name}",
                search_term=medication_name
            )
        except httpx.HTTPStatusError as e:
            return ToolResult.fail(
                f"API error ({e.response.status_code}): {str(e)}",
                search_term=medication_name
            )
        except Exception as e:
            return ToolResult.fail(
                f"RxNorm lookup failed: {str(e)}",
                search_term=medication_name
            )
    
    async def _exact_lookup(self, client: httpx.AsyncClient, name: str) -> ToolResult:
        """
        Attempt exact match lookup via rxcui endpoint.
        
        API: /rxcui.json?name={name}
        """
        params = {"name": name}
        response = await client.get(RXCUI_ENDPOINT, params=params)
        response.raise_for_status()
        
        data = response.json()
        
        # Response structure: {"idGroup": {"rxnormId": ["123"]}}
        id_group = data.get("idGroup", {})
        rxnorm_ids = id_group.get("rxnormId", [])
        
        if rxnorm_ids:
            rxcui = rxnorm_ids[0]
            return ToolResult.ok(
                data=RxNormCode(
                    rxcui=rxcui,
                    display=name,
                    match_type="exact"
                ),
                search_term=name,
                api_endpoint=RXCUI_ENDPOINT
            )
        
        return ToolResult.fail(f"No exact match for: {name}")
    
    async def _approximate_lookup(self, client: httpx.AsyncClient, name: str) -> ToolResult:
        """
        Attempt approximate term search (fuzzy matching).
        
        API: /approximateTerm.json?term={term}&maxEntries={max}
        """
        params = {
            "term": name,
            "maxEntries": self.max_results
        }
        response = await client.get(APPROX_ENDPOINT, params=params)
        response.raise_for_status()
        
        data = response.json()
        
        # Response structure: {"approximateGroup": {"candidate": [{"rxcui": "123", "name": "..."}]}}
        approx_group = data.get("approximateGroup", {})
        candidates = approx_group.get("candidate", [])
        
        if candidates:
            best = candidates[0]
            rxcui = best.get("rxcui")
            display = best.get("name", name)
            score = best.get("score", "0")
            
            if rxcui:
                return ToolResult.ok(
                    data=RxNormCode(
                        rxcui=rxcui,
                        display=display,
                        match_type="approximate"
                    ),
                    search_term=name,
                    match_score=score,
                    total_candidates=len(candidates),
                    api_endpoint=APPROX_ENDPOINT
                )
        
        return ToolResult.fail(f"No approximate match for: {name}")
    
    def _normalize_medication_name(self, name: str) -> str:
        """
        Normalize medication name for better matching.
        
        Removes:
        - Dosage information (mg, mL, etc.)
        - Route information (oral, IV, etc.)
        - Common suffixes (tablet, capsule, etc.)
        
        Args:
            name: Raw medication name
            
        Returns:
            Normalized medication name
        """
        import re
        
        normalized = name.strip()
        
        # Remove dosage patterns like "20mg", "20 mg", "500mg/5ml"
        normalized = re.sub(r'\s*\d+\.?\d*\s*(mg|mcg|g|ml|meq|units?|iu)\b/?(\d*\s*(mg|mcg|g|ml))?', '', normalized, flags=re.IGNORECASE)
        
        # Remove form/route words
        forms = ['tablet', 'tab', 'capsule', 'cap', 'solution', 'suspension', 
                 'injection', 'inj', 'cream', 'ointment', 'patch', 'spray',
                 'oral', 'iv', 'im', 'po', 'nasal', 'topical', 'ophthalmic']
        for form in forms:
            normalized = re.sub(rf'\b{form}s?\b', '', normalized, flags=re.IGNORECASE)
        
        # Remove extra whitespace
        normalized = ' '.join(normalized.split())
        
        return normalized.strip()
    
    async def execute_batch(self, medications: List[str]) -> List[ToolResult]:
        """
        Look up RxNorm codes for multiple medications in parallel.
        
        Args:
            medications: List of medication names
            
        Returns:
            List of ToolResults, one per medication
        """
        if not medications:
            return []
        
        # Execute all lookups in parallel
        tasks = [self.execute(med) for med in medications]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Convert any exceptions to failed results
        processed = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed.append(ToolResult.fail(
                    f"Batch lookup failed: {str(result)}",
                    search_term=medications[i]
                ))
            else:
                processed.append(result)
        
        return processed
    
    async def lookup_with_fallback(self, medication_name: str) -> Optional[RxNormCode]:
        """
        Convenience method that returns RxNormCode or None.
        
        Args:
            medication_name: Medication name
            
        Returns:
            RxNormCode if found, None otherwise
        """
        result = await self.execute(medication_name)
        return result.data if result.success else None

