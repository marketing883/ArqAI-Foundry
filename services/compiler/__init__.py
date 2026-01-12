"""
Typed Intent & Deterministic Compiler

Provides deterministic, type-safe compilation from strict schemas to executable IR:
- Intent Schema Registry (JSON Schema validation)
- Deterministic Compiler (no LLM, no guessing)
- Optional NL Parser (suggestion only, requires human confirmation)
"""

from services.compiler.schema_registry import IntentSchemaRegistry
from services.compiler.compiler import DeterministicCompiler
from services.compiler.nl_parser import NaturalLanguageParser

__all__ = [
    "IntentSchemaRegistry",
    "DeterministicCompiler",
    "NaturalLanguageParser",
]
