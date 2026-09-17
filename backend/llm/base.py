from abc import ABC, abstractmethod
from backend.query_engine.intent_schema import StructuredIntent


class BaseLLMProvider(ABC):
    """Abstract interface for natural language query intent translation."""

    @abstractmethod
    async def generate_intent(self, question: str) -> StructuredIntent:
        """
        Translate a natural language question into a strict Pydantic StructuredIntent.
        
        Must NEVER output raw SQL or executable code.
        """
        pass
