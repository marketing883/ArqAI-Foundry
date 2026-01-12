"""
Natural Language Parser (Optional UX Layer)

Convenience layer to suggest structured intent from natural language.
IMPORTANT: This NEVER directly triggers execution.
- Extracts structured intent from NL
- Returns suggestion with confidence score
- Requires human confirmation before compilation
"""

import json
from datetime import datetime
from typing import Any
from uuid import uuid4

import structlog

from arqai_foundry.core.exceptions import CompilationError
from services.compiler.schema_registry import IntentSchemaRegistry

logger = structlog.get_logger(__name__)


class NLParseResult:
    """Result of natural language parsing."""

    def __init__(
        self,
        parse_id: str,
        natural_language_input: str,
        suggested_intent: dict[str, Any] | None,
        confidence: float,
        alternatives: list[dict[str, Any]],
        requires_clarification: bool,
        clarification_questions: list[str],
        warnings: list[str],
    ):
        self.parse_id = parse_id
        self.natural_language_input = natural_language_input
        self.suggested_intent = suggested_intent
        self.confidence = confidence
        self.alternatives = alternatives
        self.requires_clarification = requires_clarification
        self.clarification_questions = clarification_questions
        self.warnings = warnings
        self.created_at = datetime.utcnow()
        self.confirmed = False
        self.confirmed_at: datetime | None = None
        self.confirmed_by: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "parse_id": self.parse_id,
            "natural_language_input": self.natural_language_input,
            "suggested_intent": self.suggested_intent,
            "confidence": self.confidence,
            "alternatives": self.alternatives,
            "requires_clarification": self.requires_clarification,
            "clarification_questions": self.clarification_questions,
            "warnings": self.warnings,
            "created_at": self.created_at.isoformat(),
            "confirmed": self.confirmed,
            "confirmed_at": self.confirmed_at.isoformat() if self.confirmed_at else None,
            "confirmed_by": self.confirmed_by,
        }


class NaturalLanguageParser:
    """
    Parses natural language into structured intents.

    CRITICAL SAFETY PROPERTIES:
    1. This parser NEVER directly triggers execution
    2. All suggestions require explicit human confirmation
    3. Ambiguous input results in clarification requests, not guesses
    4. Audit trail shows: NL input → structured intent → user approval → compilation
    """

    def __init__(
        self,
        schema_registry: IntentSchemaRegistry | None = None,
        llm_client: Any = None,  # Will be typed properly when LLM layer is built
    ):
        self.schema_registry = schema_registry or IntentSchemaRegistry()
        self.llm_client = llm_client

        # Pending parse results awaiting confirmation
        self._pending_results: dict[str, NLParseResult] = {}

        # Pattern matchers for common intents (rule-based, no LLM)
        self._patterns = self._build_patterns()

    def _build_patterns(self) -> list[dict[str, Any]]:
        """Build rule-based patterns for common intents."""
        return [
            {
                "pattern_type": "terminate_resource",
                "keywords": ["terminate", "delete", "remove", "kill", "destroy", "shutdown"],
                "resource_keywords": ["ec2", "instance", "server", "vm", "rds", "database"],
                "intent_type": "cost_optimization.terminate",
                "action": "terminate",
            },
            {
                "pattern_type": "stop_resource",
                "keywords": ["stop", "pause", "halt", "suspend"],
                "resource_keywords": ["ec2", "instance", "server", "vm", "rds", "database"],
                "intent_type": "cost_optimization.terminate",
                "action": "stop",
            },
            {
                "pattern_type": "resize_resource",
                "keywords": ["resize", "scale", "change size", "modify"],
                "resource_keywords": ["ec2", "instance", "server", "rds", "database"],
                "intent_type": "cost_optimization.resize",
                "action": "update",
            },
            {
                "pattern_type": "audit",
                "keywords": ["audit", "compliance check", "review", "assess"],
                "framework_keywords": ["soc2", "soc 2", "hipaa", "pci", "gdpr", "iso"],
                "intent_type": "compliance.audit",
                "action": "analyze",
            },
            {
                "pattern_type": "notify",
                "keywords": ["notify", "send", "alert", "message", "tell"],
                "channel_keywords": ["slack", "teams", "email"],
                "intent_type": "notification.send",
                "action": "notify",
            },
        ]

    async def parse(
        self,
        natural_language: str,
        context: dict[str, Any] | None = None,
    ) -> NLParseResult:
        """
        Parse natural language into a suggested structured intent.

        Returns a suggestion that MUST be confirmed by a human before compilation.
        """
        parse_id = str(uuid4())

        logger.info(
            "nl_parse_started",
            parse_id=parse_id,
            input_length=len(natural_language),
        )

        # First, try rule-based parsing (deterministic)
        rule_result = self._rule_based_parse(natural_language, context)

        if rule_result["confidence"] >= 0.8:
            # High confidence rule match, use it
            result = NLParseResult(
                parse_id=parse_id,
                natural_language_input=natural_language,
                suggested_intent=rule_result["intent"],
                confidence=rule_result["confidence"],
                alternatives=rule_result.get("alternatives", []),
                requires_clarification=False,
                clarification_questions=[],
                warnings=rule_result.get("warnings", []),
            )
        elif self.llm_client:
            # Use LLM for ambiguous cases
            result = await self._llm_based_parse(
                parse_id, natural_language, context, rule_result
            )
        else:
            # No LLM available, return low-confidence rule result
            result = NLParseResult(
                parse_id=parse_id,
                natural_language_input=natural_language,
                suggested_intent=rule_result.get("intent"),
                confidence=rule_result["confidence"],
                alternatives=rule_result.get("alternatives", []),
                requires_clarification=rule_result["confidence"] < 0.5,
                clarification_questions=self._generate_clarification_questions(
                    natural_language, rule_result
                ),
                warnings=["LLM not available for enhanced parsing"],
            )

        # Store for later confirmation
        self._pending_results[parse_id] = result

        logger.info(
            "nl_parse_completed",
            parse_id=parse_id,
            confidence=result.confidence,
            requires_clarification=result.requires_clarification,
        )

        return result

    def _rule_based_parse(
        self,
        natural_language: str,
        context: dict[str, Any] | None,
    ) -> dict[str, Any]:
        """Rule-based parsing using keyword matching."""
        nl_lower = natural_language.lower()
        context = context or {}

        best_match: dict[str, Any] | None = None
        best_confidence = 0.0
        alternatives: list[dict[str, Any]] = []

        for pattern in self._patterns:
            confidence = self._calculate_pattern_confidence(nl_lower, pattern)

            if confidence > 0:
                intent = self._build_intent_from_pattern(
                    natural_language, pattern, context
                )

                if confidence > best_confidence:
                    if best_match:
                        alternatives.append({
                            "intent": best_match,
                            "confidence": best_confidence,
                        })
                    best_match = intent
                    best_confidence = confidence
                else:
                    alternatives.append({
                        "intent": intent,
                        "confidence": confidence,
                    })

        warnings = []
        if best_confidence < 0.5:
            warnings.append("Low confidence match - please verify carefully")

        return {
            "intent": best_match,
            "confidence": best_confidence,
            "alternatives": alternatives[:3],  # Top 3 alternatives
            "warnings": warnings,
        }

    def _calculate_pattern_confidence(
        self,
        nl_lower: str,
        pattern: dict[str, Any],
    ) -> float:
        """Calculate confidence score for a pattern match."""
        confidence = 0.0

        # Check action keywords
        action_matches = sum(
            1 for kw in pattern.get("keywords", [])
            if kw in nl_lower
        )
        if action_matches > 0:
            confidence += 0.4

        # Check resource keywords
        resource_keywords = pattern.get("resource_keywords", [])
        resource_matches = sum(1 for kw in resource_keywords if kw in nl_lower)
        if resource_matches > 0:
            confidence += 0.3

        # Check framework/channel keywords
        other_keywords = pattern.get("framework_keywords", []) or pattern.get("channel_keywords", [])
        other_matches = sum(1 for kw in other_keywords if kw in nl_lower)
        if other_matches > 0:
            confidence += 0.2

        # Check for resource IDs (like i-xxx for EC2)
        import re
        if re.search(r'i-[a-z0-9]{8,}', nl_lower):
            confidence += 0.1

        return min(confidence, 1.0)

    def _build_intent_from_pattern(
        self,
        natural_language: str,
        pattern: dict[str, Any],
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """Build structured intent from pattern match."""
        import re

        intent: dict[str, Any] = {
            "intent_type": pattern["intent_type"],
            "version": "1.0.0",
            "action": pattern["action"],
            "target": {},
            "environment": context.get("environment", "development"),
            "justification": {
                "reason": f"Parsed from: {natural_language[:100]}",
            },
        }

        # Extract resource IDs
        ec2_match = re.search(r'(i-[a-z0-9]{8,})', natural_language.lower())
        rds_match = re.search(r'(db-[a-z0-9-]+)', natural_language.lower())

        if ec2_match:
            intent["target"] = {
                "resource_type": "ec2",
                "resource_id": ec2_match.group(1),
                "provider": "aws",
            }
        elif rds_match:
            intent["target"] = {
                "resource_type": "rds",
                "resource_id": rds_match.group(1),
                "provider": "aws",
            }
        else:
            # Use context or placeholder
            intent["target"] = {
                "resource_type": context.get("resource_type", "unknown"),
                "resource_id": context.get("resource_id", "REQUIRES_INPUT"),
                "provider": context.get("provider", "aws"),
            }

        # Extract environment
        if "production" in natural_language.lower() or "prod" in natural_language.lower():
            intent["environment"] = "production"
        elif "staging" in natural_language.lower():
            intent["environment"] = "staging"

        # Add natural language for audit trail
        intent["natural_language_input"] = natural_language

        return intent

    async def _llm_based_parse(
        self,
        parse_id: str,
        natural_language: str,
        context: dict[str, Any] | None,
        rule_result: dict[str, Any],
    ) -> NLParseResult:
        """Use LLM for parsing when rules are insufficient."""
        # This will be implemented when LLM layer is built
        # For now, return the rule-based result with lower confidence

        return NLParseResult(
            parse_id=parse_id,
            natural_language_input=natural_language,
            suggested_intent=rule_result.get("intent"),
            confidence=rule_result["confidence"] * 0.8,  # Penalize without LLM
            alternatives=rule_result.get("alternatives", []),
            requires_clarification=True,
            clarification_questions=self._generate_clarification_questions(
                natural_language, rule_result
            ),
            warnings=["LLM parsing not yet implemented - using rule-based fallback"],
        )

    def _generate_clarification_questions(
        self,
        natural_language: str,
        rule_result: dict[str, Any],
    ) -> list[str]:
        """Generate questions to clarify ambiguous input."""
        questions = []
        intent = rule_result.get("intent", {})

        # Check for missing required fields
        target = intent.get("target", {})
        if target.get("resource_id") == "REQUIRES_INPUT":
            questions.append("What is the resource ID you want to act on?")

        if target.get("resource_type") == "unknown":
            questions.append("What type of resource is this? (e.g., EC2 instance, RDS database)")

        if not intent.get("intent_type"):
            questions.append("What action would you like to perform?")

        if rule_result["confidence"] < 0.5:
            questions.append(
                "I'm not confident about this interpretation. "
                "Could you rephrase or provide more details?"
            )

        return questions

    async def confirm(
        self,
        parse_id: str,
        confirmed_by: str,
        modifications: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Confirm a parsed intent for compilation.

        This is the ONLY way to proceed from NL parsing to compilation.
        """
        result = self._pending_results.get(parse_id)

        if not result:
            raise CompilationError(
                f"Parse result not found: {parse_id}",
                details={"parse_id": parse_id},
            )

        if result.confirmed:
            raise CompilationError(
                f"Parse result already confirmed: {parse_id}",
                details={"parse_id": parse_id},
            )

        # Apply modifications if provided
        confirmed_intent = result.suggested_intent.copy() if result.suggested_intent else {}
        if modifications:
            self._apply_modifications(confirmed_intent, modifications)

        # Validate against schema
        errors = self.schema_registry.validate_intent(confirmed_intent)
        if errors:
            raise CompilationError(
                "Confirmed intent fails schema validation",
                details={"errors": errors},
            )

        # Mark as confirmed
        result.confirmed = True
        result.confirmed_at = datetime.utcnow()
        result.confirmed_by = confirmed_by
        result.suggested_intent = confirmed_intent

        logger.info(
            "nl_parse_confirmed",
            parse_id=parse_id,
            confirmed_by=confirmed_by,
            intent_type=confirmed_intent.get("intent_type"),
        )

        return confirmed_intent

    def _apply_modifications(
        self,
        intent: dict[str, Any],
        modifications: dict[str, Any],
    ) -> None:
        """Apply user modifications to suggested intent."""
        for key, value in modifications.items():
            if "." in key:
                # Nested key like "target.resource_id"
                parts = key.split(".")
                current = intent
                for part in parts[:-1]:
                    if part not in current:
                        current[part] = {}
                    current = current[part]
                current[parts[-1]] = value
            else:
                intent[key] = value

    async def get_pending_result(self, parse_id: str) -> NLParseResult | None:
        """Get a pending parse result."""
        return self._pending_results.get(parse_id)

    async def discard(self, parse_id: str) -> None:
        """Discard a pending parse result."""
        if parse_id in self._pending_results:
            logger.info("nl_parse_discarded", parse_id=parse_id)
            del self._pending_results[parse_id]

    async def list_pending(self) -> list[dict[str, Any]]:
        """List all pending parse results."""
        return [
            {
                "parse_id": result.parse_id,
                "created_at": result.created_at.isoformat(),
                "confidence": result.confidence,
                "intent_type": result.suggested_intent.get("intent_type") if result.suggested_intent else None,
            }
            for result in self._pending_results.values()
            if not result.confirmed
        ]
