"""Compatibility provider facade for the mission execution layer."""

from .gemini_connector import generate_text
from .ai_connectors import generate_claude, generate_perplexity

__all__ = ["generate_text", "generate_claude", "generate_perplexity"]
