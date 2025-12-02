from sqlalchemy.orm import Session
from src.providers.llm.factory import LLMFactory
from src.models import LLMCache
from src.config import settings

class LLMService:
    """Medical note LLM services (summarization, querying) with caching"""
    
    def __init__(self, db: Session):
        self.db = db
        self.llm = LLMFactory.create()
    
    async def summarize_note(self, note_text: str) -> dict:
        """Summarize medical note with automatic caching"""
        return await self._process_llm_request(
            prompt_template="""Summarize the following medical note concisely, highlighting:
- Patient information
- Key diagnoses/conditions
- Medications prescribed
- Important vitals or lab results
- Treatment plan

Medical Note:
{text}

Summary:""",
            input_text=note_text,
            task_type="summarization"
        )

    async def query_note(self, note_text: str, query: str) -> dict:
        """Query medical note with automatic caching"""
        return await self._process_llm_request(
            prompt_template=f"""Answer the following question based ONLY on the provided medical note.

Question: {query}

Medical Note:
{{text}}

Answer:""",
            input_text=note_text,
            task_type=f"query:{query}"
        )

    async def _process_llm_request(self, prompt_template: str, input_text: str, task_type: str) -> dict:
        """Generic LLM request processor with caching"""
        provider = self.llm.get_provider_name()
        model = self.llm.get_model_name()
        
        # Create a unique cache key based on task and input
        # For query, task_type includes the query itself
        cache_key = f"{task_type}:{input_text}"
        
        # Check cache first
        if settings.enable_llm_cache:
            prompt_hash = LLMCache.hash_prompt(cache_key, provider, model)
            cached = self.db.query(LLMCache).filter(
                LLMCache.prompt_hash == prompt_hash
            ).first()
            
            if cached:
                return {
                    "result": cached.response,
                    "cached": True,
                    "provider": provider,
                    "model": model
                }
        
        # Generate via LLM
        prompt = prompt_template.format(text=input_text)
        response = await self.llm.generate(prompt)
        
        # Cache response
        if settings.enable_llm_cache:
            cache_entry = LLMCache(
                prompt_hash=prompt_hash,
                prompt=cache_key, # Store the cache key as the prompt for reference
                response=response,
                provider=provider,
                model=model
            )
            self.db.add(cache_entry)
            self.db.commit()
        
        return {
            "result": response,
            "cached": False,
            "provider": provider,
            "model": model
        }
