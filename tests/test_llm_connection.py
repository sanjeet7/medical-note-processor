import pytest
import os
from src.providers.llm.openai import OpenAIProvider
from src.providers.llm.anthropic import AnthropicProvider
from src.config import settings

@pytest.mark.asyncio
async def test_openai_connection():
    """Test actual connection to OpenAI API"""
    if settings.llm_provider != "openai":
        pytest.skip("Skipping OpenAI test (provider not set to openai)")
    if not settings.llm_api_key:
        pytest.skip("LLM_API_KEY not set in settings")
        
    provider = OpenAIProvider(api_key=settings.llm_api_key, model="gpt-5.1") 
    try:
        response = await provider.generate("Say hello")
        assert len(response) > 0
        print(f"\nOpenAI Response: {response}")
    except Exception as e:
        pytest.fail(f"OpenAI connection failed: {str(e)}")

@pytest.mark.asyncio
async def test_anthropic_connection():
    """Test actual connection to Anthropic"""
    if settings.llm_provider != "anthropic":
        pytest.skip("Skipping Anthropic test (provider not set to anthropic)")
    if not settings.llm_api_key:
        pytest.skip("LLM_API_KEY not set in settings")

    # Use specific key if available, else fallback to generic
    api_key = settings.llm_api_key
    
    provider = AnthropicProvider(api_key=api_key, model="claude-sonnet-4-5")
    try:
        response = await provider.generate("Say hello")
        assert len(response) > 0
        print(f"\nAnthropic Response: {response}")
    except Exception as e:
        pytest.fail(f"Anthropic connection failed: {str(e)}")
