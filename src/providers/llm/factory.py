from .base import LLMProvider
from .openai import OpenAIProvider
from .anthropic import AnthropicProvider
from src.config import settings

class LLMFactory:
    """Factory for creating LLM providers from configuration"""
    
    @staticmethod
    def create() -> LLMProvider:
        """Create LLM provider based on settings"""
        provider = settings.llm_provider.lower()
        
        if provider == "openai":
            return OpenAIProvider(
                api_key=settings.llm_api_key,
                model=settings.llm_model
            )
        elif provider == "anthropic":
            return AnthropicProvider(
                api_key=settings.llm_api_key,
                model=settings.llm_model
            )
        else:
            raise ValueError(f"Unsupported LLM provider: {provider}")
