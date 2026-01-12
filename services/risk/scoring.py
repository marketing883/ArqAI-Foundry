"""
Risk Scoring Engine

Computes contextual risk scores using:
- Weighted factor evaluation
- Deterministic algorithms
- Caching for performance
"""

import hashlib
import json
import time
from datetime import datetime
from typing import Any
from uuid import UUID

import structlog

from arqai_foundry.core.enums import DataClassification, Environment, RiskTier
from arqai_foundry.core.exceptions import RiskScoringError, RiskThresholdExceededError
from arqai_foundry.core.models import CompiledIR, RiskAssessment, RiskFactor

logger = structlog.get_logger(__name__)


# =============================================================================
# Default Risk Factors
# =============================================================================

DEFAULT_RISK_FACTORS = [
    {
        "name": "data_sensitivity",
        "weight": 0.35,
        "type": "mapping",
        "description": "Risk based on data classification",
        "mapping": {
            "public": 0,
            "internal": 10,
            "confidential": 25,
            "pii": 40,
            "phi": 50,
            "pci": 45,
            "restricted": 60,
        },
    },
    {
        "name": "environment",
        "weight": 0.25,
        "type": "mapping",
        "description": "Risk based on deployment environment",
        "mapping": {
            "development": -15,
            "staging": 0,
            "production": 25,
            "disaster_recovery": 20,
        },
    },
    {
        "name": "financial_impact",
        "weight": 0.20,
        "type": "threshold",
        "description": "Risk based on monthly cost impact",
        "field": "monthly_cost",
        "thresholds": [
            {"max": 100, "score": 0},
            {"max": 1000, "score": 5},
            {"max": 5000, "score": 15},
            {"max": 10000, "score": 25},
            {"max": float("inf"), "score": 35},
        ],
    },
    {
        "name": "idle_duration",
        "weight": 0.10,
        "type": "threshold",
        "description": "Risk reduction based on resource idle time",
        "field": "idle_days",
        "thresholds": [
            {"min": 180, "score": -40},
            {"min": 90, "score": -25},
            {"min": 30, "score": -10},
            {"min": 0, "score": 0},
        ],
        "reverse": True,  # Higher idle days = lower risk
    },
    {
        "name": "has_dependencies",
        "weight": 0.05,
        "type": "boolean",
        "description": "Risk increase if resource has dependencies",
        "field": "has_dependencies",
        "true_score": 25,
        "false_score": 0,
    },
    {
        "name": "action_destructiveness",
        "weight": 0.05,
        "type": "mapping",
        "description": "Risk based on action type",
        "field": "action",
        "mapping": {
            "read": -10,
            "analyze": -5,
            "notify": 0,
            "stop": 5,
            "update": 10,
            "terminate": 20,
            "delete": 30,
        },
    },
]


class RiskScoringEngine:
    """
    Computes contextual risk scores deterministically.

    Key Properties:
    - Deterministic: same inputs → same score
    - Transparent: reasoning explains each factor
    - Configurable: factors can be customized per tenant
    - Cached: results cached for performance
    """

    def __init__(
        self,
        factors: list[dict[str, Any]] | None = None,
    ):
        self.factors = factors or DEFAULT_RISK_FACTORS

        # Cache (would use Redis in production)
        self._cache: dict[str, RiskAssessment] = {}
        self._cache_ttl_seconds = 300  # 5 minutes

    async def assess_risk(
        self,
        compiled_ir: CompiledIR,
        context: dict[str, Any],
    ) -> RiskAssessment:
        """
        Assess risk for a compiled IR.

        Returns RiskAssessment with:
        - Risk score (0-100)
        - Risk tier (low/medium/high/critical)
        - Factor breakdown
        - Human-readable reasoning
        """
        start_time = time.time()

        # Check cache
        cache_key = self._compute_cache_key(compiled_ir, context)
        cached = self._cache.get(cache_key)
        if cached:
            logger.debug("risk_score_cache_hit", cache_key=cache_key[:16])
            return cached

        logger.info(
            "risk_assessment_started",
            ir_id=str(compiled_ir.ir_id),
        )

        try:
            # Enrich context with IR data
            enriched_context = self._enrich_context(context, compiled_ir)

            # Evaluate each factor
            factor_results: list[RiskFactor] = []
            total_weighted_score = 0.0

            for factor_config in self.factors:
                factor_result = self._evaluate_factor(factor_config, enriched_context)
                factor_results.append(factor_result)
                total_weighted_score += factor_result.score * factor_config["weight"]

            # Clamp to 0-100
            risk_score = max(0, min(100, int(total_weighted_score)))

            # Determine tier
            risk_tier = self._score_to_tier(risk_score)

            # Generate reasoning
            reasoning = self._generate_reasoning(factor_results, risk_score)

            assessment_time = (time.time() - start_time) * 1000

            assessment = RiskAssessment(
                risk_score=risk_score,
                risk_tier=risk_tier,
                factors=factor_results,
                reasoning=reasoning,
                assessment_time_ms=assessment_time,
            )

            # Cache result
            self._cache[cache_key] = assessment

            logger.info(
                "risk_assessment_completed",
                ir_id=str(compiled_ir.ir_id),
                risk_score=risk_score,
                risk_tier=risk_tier.value,
                assessment_time_ms=assessment_time,
            )

            return assessment

        except Exception as e:
            logger.error(
                "risk_assessment_failed",
                ir_id=str(compiled_ir.ir_id),
                error=str(e),
            )
            raise RiskScoringError(f"Risk assessment failed: {e}")

    def _enrich_context(
        self,
        context: dict[str, Any],
        compiled_ir: CompiledIR,
    ) -> dict[str, Any]:
        """Enrich context with data from compiled IR."""
        enriched = dict(context)

        # Extract from operations
        for op in compiled_ir.operations:
            enriched["environment"] = op.environment.value
            enriched["data_classification"] = op.data_classification.value
            enriched["jurisdiction"] = op.jurisdiction

            if op.estimated_cost_impact:
                enriched["monthly_cost"] = op.estimated_cost_impact.get("monthly_savings", 0)

            enriched["has_dependencies"] = len(op.dependencies) > 0

        # Extract action from intent type
        parts = compiled_ir.intent_type.split(".")
        if len(parts) > 1:
            enriched["action"] = parts[-1]

        # Extract from justification if present
        if "justification" in context:
            justification = context["justification"]
            enriched["project_status"] = justification.get("project_status")
            enriched["idle_days"] = justification.get("idle_days", 0)

        return enriched

    def _evaluate_factor(
        self,
        factor_config: dict[str, Any],
        context: dict[str, Any],
    ) -> RiskFactor:
        """Evaluate a single risk factor."""
        name = factor_config["name"]
        factor_type = factor_config["type"]
        field = factor_config.get("field", name)

        # Get raw value from context
        raw_value = context.get(field)

        # Handle missing values
        if raw_value is None:
            return RiskFactor(
                name=name,
                weight=factor_config["weight"],
                raw_value=None,
                score=0,
                explanation=f"{name}: no data available (score: 0)",
            )

        # Evaluate based on type
        if factor_type == "mapping":
            score = self._evaluate_mapping(factor_config, raw_value)
        elif factor_type == "threshold":
            score = self._evaluate_threshold(factor_config, raw_value)
        elif factor_type == "boolean":
            score = self._evaluate_boolean(factor_config, raw_value)
        elif factor_type == "formula":
            score = self._evaluate_formula(factor_config, raw_value, context)
        else:
            score = 0

        explanation = (
            f"{name}={raw_value} "
            f"(+{score} points, {factor_config['weight']*100:.0f}% weight)"
        )

        return RiskFactor(
            name=name,
            weight=factor_config["weight"],
            raw_value=raw_value,
            score=score,
            explanation=explanation,
        )

    def _evaluate_mapping(
        self,
        factor_config: dict[str, Any],
        raw_value: Any,
    ) -> int:
        """Evaluate mapping-type factor."""
        mapping = factor_config.get("mapping", {})
        return mapping.get(str(raw_value).lower(), 0)

    def _evaluate_threshold(
        self,
        factor_config: dict[str, Any],
        raw_value: Any,
    ) -> int:
        """Evaluate threshold-type factor."""
        try:
            value = float(raw_value)
        except (TypeError, ValueError):
            return 0

        thresholds = factor_config.get("thresholds", [])
        reverse = factor_config.get("reverse", False)

        if reverse:
            # For reverse thresholds (like idle_days), check min values
            for threshold in thresholds:
                if "min" in threshold and value >= threshold["min"]:
                    return threshold["score"]
        else:
            # For normal thresholds, check max values
            for threshold in thresholds:
                if "max" in threshold and value <= threshold["max"]:
                    return threshold["score"]

        return 0

    def _evaluate_boolean(
        self,
        factor_config: dict[str, Any],
        raw_value: Any,
    ) -> int:
        """Evaluate boolean-type factor."""
        is_true = bool(raw_value)
        if is_true:
            return factor_config.get("true_score", 0)
        return factor_config.get("false_score", 0)

    def _evaluate_formula(
        self,
        factor_config: dict[str, Any],
        raw_value: Any,
        context: dict[str, Any],
    ) -> int:
        """
        Evaluate formula-type factor.

        NOTE: Formula evaluation is sandboxed and limited.
        """
        # For security, we don't execute arbitrary code
        # Instead, we use predefined formulas
        formula_name = factor_config.get("formula_name")

        if formula_name == "financial_impact":
            try:
                value = float(raw_value)
                if value > 10000:
                    return 30
                elif value > 5000:
                    return 20
                elif value > 1000:
                    return 10
                return 0
            except (TypeError, ValueError):
                return 0

        return 0

    def _score_to_tier(self, score: int) -> RiskTier:
        """Convert risk score to tier."""
        if score < 30:
            return RiskTier.LOW
        if score < 60:
            return RiskTier.MEDIUM
        if score < 80:
            return RiskTier.HIGH
        return RiskTier.CRITICAL

    def _generate_reasoning(
        self,
        factors: list[RiskFactor],
        final_score: int,
    ) -> list[str]:
        """Generate human-readable reasoning."""
        reasoning = []

        for factor in factors:
            if factor.score != 0:
                reasoning.append(factor.explanation)

        # Add calculation summary
        calculation_parts = []
        for factor in factors:
            if factor.score != 0:
                contribution = factor.score * factor.weight
                calculation_parts.append(f"{factor.score}*{factor.weight:.2f}")

        if calculation_parts:
            reasoning.append(
                f"Final: {' + '.join(calculation_parts)} = {final_score}"
            )

        return reasoning

    def _compute_cache_key(
        self,
        compiled_ir: CompiledIR,
        context: dict[str, Any],
    ) -> str:
        """Compute cache key for risk assessment."""
        key_data = {
            "ir_id": str(compiled_ir.ir_id),
            "intent_type": compiled_ir.intent_type,
            "context": context,
        }
        canonical = json.dumps(key_data, sort_keys=True, default=str)
        return hashlib.sha256(canonical.encode()).hexdigest()

    def invalidate_cache(self) -> None:
        """Invalidate the risk score cache."""
        self._cache.clear()
        logger.info("risk_cache_invalidated")

    async def check_threshold(
        self,
        assessment: RiskAssessment,
        max_tier: RiskTier = RiskTier.MEDIUM,
    ) -> bool:
        """
        Check if risk assessment is within acceptable threshold.

        Returns True if acceptable, raises exception if not.
        """
        tier_order = {
            RiskTier.LOW: 0,
            RiskTier.MEDIUM: 1,
            RiskTier.HIGH: 2,
            RiskTier.CRITICAL: 3,
        }

        if tier_order[assessment.risk_tier] > tier_order[max_tier]:
            raise RiskThresholdExceededError(
                f"Risk tier {assessment.risk_tier.value} exceeds maximum {max_tier.value}",
                risk_score=assessment.risk_score,
                threshold=tier_order[max_tier],
            )

        return True

    def get_factor_config(self, factor_name: str) -> dict[str, Any] | None:
        """Get configuration for a specific factor."""
        for factor in self.factors:
            if factor["name"] == factor_name:
                return factor
        return None

    def update_factor_config(
        self,
        factor_name: str,
        updates: dict[str, Any],
    ) -> None:
        """Update configuration for a specific factor."""
        for i, factor in enumerate(self.factors):
            if factor["name"] == factor_name:
                self.factors[i] = {**factor, **updates}
                self.invalidate_cache()
                logger.info(
                    "risk_factor_updated",
                    factor_name=factor_name,
                )
                return

        logger.warning(
            "risk_factor_not_found",
            factor_name=factor_name,
        )

    def get_all_factors(self) -> list[dict[str, Any]]:
        """Get all factor configurations."""
        return self.factors.copy()
