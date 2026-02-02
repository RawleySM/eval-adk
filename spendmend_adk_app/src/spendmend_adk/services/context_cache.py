"""Context cache configuration for optimizing LLM context usage.

ADK Docs:
- https://google.github.io/adk-docs/context/caching/#context-caching-with-gemini
"""

from google.adk.apps import ContextCacheConfig


def create_context_cache_config(
    enabled: bool = True,
    ttl_seconds: int = 3600,
    max_entries: int = 256,
) -> ContextCacheConfig:
    """
    Create a ContextCacheConfig instance.

    Args:
        enabled: Enable context caching (default: True)
        ttl_seconds: Cache time-to-live in seconds (default: 3600 = 1 hour)
        max_entries: Maximum number of cache entries (default: 256)

    Returns:
        Configured ContextCacheConfig instance

    Note:
        Context caching can significantly reduce API costs and latency by
        caching common context between agent invocations. This is particularly
        useful when:
        - Repeatedly using the same prompts/instructions
        - Processing multiple similar tasks in sequence
        - Sharing context across workflow stages

        Tuning considerations:
        - Increase ttl_seconds for longer sessions
        - Increase max_entries if processing many different contexts
        - Disable if context is highly variable and caching provides no benefit
    """
    return ContextCacheConfig(
        enabled=enabled,
        ttl_seconds=ttl_seconds,
        max_entries=max_entries,
    )
