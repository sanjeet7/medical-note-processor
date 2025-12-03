"""Query reformulation for improved retrieval recall"""
from typing import List
from src.providers.llm.factory import LLMFactory
import json


class QueryReformulator:
    """Generates semantic variations of queries for better retrieval"""
    
    def __init__(self):
        """Initialize query reformulator with LLM"""
        self.llm = LLMFactory.create()
    
    async def reformulate(self, query: str, num_variations: int = 2) -> List[str]:
        """
        Generate semantic variations of the query.
        
        Args:
            query: Original user query
            num_variations: Number of reformulated queries to generate (default: 2)
            
        Returns:
            List containing original query + variations
        """
        prompt = f"""Generate {num_variations} semantic variations of this medical question.
Each variation should:
- Preserve the original intent and meaning
- Use different medical terminology or phrasing
- Help retrieve relevant information from medical guidelines

Original question: {query}

Return ONLY a JSON array of {num_variations} reformulated questions as strings.
Example format: ["variation 1", "variation 2"]

JSON array:"""
        
        try:
            response = await self.llm.generate(prompt)
            # Parse JSON array
            variations = json.loads(response.strip())
            
            # Return original + variations, deduplicated
            all_queries = [query] + variations
            # Simple deduplication
            unique_queries = []
            seen = set()
            for q in all_queries:
                q_lower = q.lower().strip()
                if q_lower not in seen:
                    unique_queries.append(q)
                    seen.add(q_lower)
            
            return unique_queries[:num_variations + 1]  # Original + num_variations
        
        except Exception as e:
            # Fallback: return original query if reformulation fails
            print(f"Query reformulation failed: {e}")
            return [query]
