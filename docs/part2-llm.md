# Part 2: LLM Integration

Model-agnostic LLM integration with provider abstraction, response caching, and medical note processing.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         LLM Service                              │
│                    (src/services/llm_service.py)                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   summarize_note()  ─────┐                                      │
│                          ▼                                       │
│   query_note()     ─────▶ _process_llm_request()                │
│                          │                                       │
│                          ▼                                       │
│              ┌───────────────────────┐                          │
│              │    LLMCache Check     │◀─── SHA-256 hash         │
│              │ (prompt + provider +  │     of prompt            │
│              │      model)           │                          │
│              └───────────┬───────────┘                          │
│                          │                                       │
│           Cache Hit?     │                                       │
│           ┌──────────────┴──────────────┐                       │
│           ▼ YES                    NO ▼                         │
│    Return cached              Call LLM Provider                  │
│    response                   Store in cache                     │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                       LLM Factory                                │
│                  (src/providers/llm/factory.py)                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   Settings.llm_provider ───▶ Provider Selection                  │
│                                                                  │
│              ┌──────────────────────────────────┐               │
│              │                                   │               │
│              ▼                                   ▼               │
│   ┌─────────────────────┐         ┌─────────────────────┐       │
│   │   OpenAIProvider    │         │  AnthropicProvider  │       │
│   │                     │         │                     │       │
│   │  • gpt-5.1          │         │  • claude-sonnet-4-5│       │
│   │  • gpt-5-mini       │         │  • claude-haiku     │       │
│   │  • gpt-4o           │         │                     │       │
│   └─────────────────────┘         └─────────────────────┘       │
│              │                                   │               │
│              └───────────────┬───────────────────┘               │
│                              ▼                                   │
│                    LLMProvider (Abstract)                        │
│                    • generate(prompt)                            │
│                    • get_provider_name()                         │
│                    • get_model_name()                            │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Provider Abstraction

The Factory Pattern enables easy provider switching via environment variables:

```python
# Abstract interface all providers implement
class LLMProvider(ABC):
    async def generate(self, prompt: str, **kwargs) -> str
    def get_provider_name(self) -> str
    def get_model_name(self) -> str

# Factory creates the right provider from config
class LLMFactory:
    @staticmethod
    def create(model: str = None) -> LLMProvider:
        if settings.llm_provider == "openai":
            return OpenAIProvider(api_key, model)
        elif settings.llm_provider == "anthropic":
            return AnthropicProvider(api_key, model)
```

## Configuration

```env
# OpenAI (default)
LLM_PROVIDER=openai
LLM_MODEL=gpt-5.1
LLM_API_KEY=sk-...

# Anthropic (alternative)
LLM_PROVIDER=anthropic
LLM_MODEL=claude-sonnet-4-5
LLM_API_KEY=sk-ant-...
```

## API Endpoints

### POST /summarize_note

Generates a clinical summary highlighting key medical information.

| Field | Type | Description |
|-------|------|-------------|
| `document_id` | int | ID of SOAP note to summarize |

**Response includes:**
- `summary`: Concise clinical summary
- `cached`: Whether response was from cache
- `provider`: LLM provider used
- `model`: Model used

### POST /query_note

Ask natural language questions about a specific medical note.

| Field | Type | Description |
|-------|------|-------------|
| `document_id` | int | ID of SOAP note to query |
| `query` | string | Question about the note |

## Caching Strategy

Responses are cached using a SHA-256 hash of:
- Prompt/input text
- Provider name
- Model name

This means:
- Same note + same model = cache hit
- Same note + different model = cache miss (different output expected)
- Switching providers invalidates relevant cache entries

```
Cache Key = SHA256(prompt + ":" + provider + ":" + model)
```

## Key Design Decisions

### 1. Model Agnostic
The abstract `LLMProvider` interface ensures no business logic depends on a specific provider. Switching from OpenAI to Anthropic requires only changing environment variables.

### 2. Automatic Retries
OpenAI provider uses exponential backoff for transient failures:
```python
@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
async def generate(self, prompt: str, **kwargs) -> str:
```

### 3. Cost Optimization
LLM responses are cached in PostgreSQL to avoid repeat API calls for identical requests. The `ENABLE_LLM_CACHE=true` setting (default) enables this.

## Tests

```bash
make test-part2  # 8 tests
```

| Test | Description |
|------|-------------|
| `test_openai_provider_creation` | Factory creates OpenAI provider |
| `test_anthropic_provider_creation` | Factory creates Anthropic provider |
| `test_factory_invalid_provider` | Unsupported provider raises error |
| `test_summarize_endpoint` | `/summarize_note` returns summary |
| `test_summarize_cache_miss` | First call not cached |
| `test_summarize_cache_hit` | Second identical call is cached |
| `test_query_note_endpoint` | `/query_note` answers questions |
| `test_llm_error_handling` | API failures return 500 with detail |

