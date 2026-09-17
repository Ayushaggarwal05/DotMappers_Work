"""
xAI / Grok Provider module for SupportLens AI.
Re-exports the unified AIProvider and RuleBasedFallbackProvider.
"""
from backend.llm.ai_provider import (
    AIProvider,
    XAIProvider,
    GeminiProvider,
    RuleBasedFallbackProvider,
)

__all__ = [
    "AIProvider",
    "XAIProvider",
    "GeminiProvider",
    "RuleBasedFallbackProvider",
]
