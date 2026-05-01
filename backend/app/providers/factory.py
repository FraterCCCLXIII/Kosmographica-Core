from app.config import get_settings
from app.providers.anthropic_provider import AnthropicLLMProvider
from app.providers.base import EmbeddingProvider, LLMProvider
from app.providers.local_provider import LocalEmbeddingProvider
from app.providers.openai_provider import OpenAIEmbeddingProvider, OpenAILLMProvider


def get_embedding_provider() -> EmbeddingProvider:
    settings = get_settings()
    if settings.embedding_provider == "local":
        return LocalEmbeddingProvider()
    if settings.embedding_provider == "openai":
        return OpenAIEmbeddingProvider(api_key=settings.openai_api_key)
    raise ValueError(f"Unsupported embedding provider: {settings.embedding_provider}")


def get_llm_provider() -> LLMProvider:
    settings = get_settings()
    if settings.llm_provider == "anthropic":
        return AnthropicLLMProvider(api_key=settings.anthropic_api_key)
    if settings.llm_provider == "openai":
        return OpenAILLMProvider(api_key=settings.openai_api_key)
    raise ValueError(f"Unsupported LLM provider: {settings.llm_provider}")
