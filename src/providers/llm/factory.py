from .base import LLMProvider
from .openai import OpenAIProvider
from .anthropic import AnthropicProvider
from src.config import settings

class LLMFactory:
    """Factory for creating LLM providers from configuration"""
    
    @staticmethod
    def create(model: str = None) -> LLMProvider:
        """
        Create LLM provider based on settings.
        
        Args:
            model: Optional model override. If None, uses settings.llm_model
            
        Raises:
            ValueError: If provider not supported or model not configured
        """
        provider = settings.llm_provider.lower()
        model_name = model or settings.llm_model
        
        if not model_name:
            raise ValueError("LLM_MODEL not configured. Set it in .env (e.g., 'gpt-4' for OpenAI)")
        
        if not settings.llm_api_key:
            raise ValueError("LLM_API_KEY not configured. Set it in .env")
        
        if provider == "openai":
            return OpenAIProvider(
                api_key=settings.llm_api_key,
                model=model_name
            )
        elif provider == "anthropic":
            return AnthropicProvider(
                api_key=settings.llm_api_key,
                model=model_name
            )
        else:
            raise ValueError(f"Unsupported LLM provider: {provider}")
