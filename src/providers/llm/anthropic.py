from anthropic import AsyncAnthropic
from .base import LLMProvider
from tenacity import retry, stop_after_attempt, wait_exponential

class AnthropicProvider(LLMProvider):
    """Anthropic LLM provider with automatic retries"""
    
    def __init__(self, api_key: str, model: str = "claude-3-opus-20240229"):
        self.client = AsyncAnthropic(api_key=api_key)
        self.model = model
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    async def generate(self, prompt: str, **kwargs) -> str:
        """Generate completion via Anthropic API"""
        response = await self.client.messages.create(
            model=self.model,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
            **kwargs
        )
        return response.content[0].text
    
    def get_provider_name(self) -> str:
        return "anthropic"
    
    def get_model_name(self) -> str:
        return self.model
