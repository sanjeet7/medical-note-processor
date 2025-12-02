from openai import AsyncOpenAI
from .base import LLMProvider
from tenacity import retry, stop_after_attempt, wait_exponential

class OpenAIProvider(LLMProvider):
    """OpenAI LLM provider with automatic retries"""
    
    def __init__(self, api_key: str, model: str = "gpt-5.1"):
        self.client = AsyncOpenAI(api_key=api_key)
        self.model = model
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    async def generate(self, prompt: str, **kwargs) -> str:
        """Generate completion with automatic retries"""
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            **kwargs
        )
        return response.choices[0].message.content
    
    def get_provider_name(self) -> str:
        return "openai"
    
    def get_model_name(self) -> str:
        return self.model
