"""
Policy Evaluation Engine

Evaluates policy rules against intents/IR deterministically.
Same inputs ALWAYS produce same outputs.
"""

import time
from datetime import datetime
from typing import Any
from uuid import UUID

import structlog

from arqai_foundry.core.enums import Environment, PolicyEffect, RiskTier
from arqai_foundry.core.exceptions import PolicyEvaluationError
from arqai_foundry.core.models import (
    CompiledIR,
    Policy,
    PolicyEvaluationResult,
    PolicyRule,
)
from services.policy.policy_store import PolicyStore

logger = structlog.get_logger(__name__)


class PolicyEvaluator:
    """
    Evaluates policies deterministically.

    Key Properties:
    - Deterministic: same inputs → same result
    - Short-circuit: first deny/require_approval wins
    - Priority-based: higher priority rules evaluated first
    - Fail-closed: ambiguity results in denial
    """

    def __init__(
        self,
        policy_store: PolicyStore | None = None,
    ):
        self.policy_store = policy_store or PolicyStore()

        # Evaluation cache (would use Redis in production)
        self._cache: dict[str, PolicyEvaluationResult] = {}
        self._cache_ttl_seconds = 3600

    async def evaluate(
        self,
        compiled_ir: CompiledIR,
        context: dict[str, Any],
        tenant_id: UUID,
    ) -> PolicyEvaluationResult:
        """
        Evaluate policies against compiled IR.

        Returns PolicyEvaluationResult with allow/deny decision,
        matched rules, risk score, and required approvals.
        """
        start_time = time.time()

        # Check cache
        cache_key = self._compute_cache_key(compiled_ir, context, tenant_id)
        cached = self._cache.get(cache_key)
        if cached:
            logger.debug("policy_evaluation_cache_hit", cache_key=cache_key[:16])
            return cached

        logger.info(
            "policy_evaluation_started",
            ir_id=str(compiled_ir.ir_id),
            tenant_id=str(tenant_id),
        )

        try:
            # Get applicable policies
            environment = self._get_environment(compiled_ir)
            policies = await self.policy_store.get_applicable_policies(
                tenant_id=tenant_id,
                environment=environment,
                intent_type=compiled_ir.intent_type,
            )

            if not policies:
                # No policies = default deny (fail-closed)
                logger.warning(
                    "no_policies_found",
                    tenant_id=str(tenant_id),
                    intent_type=compiled_ir.intent_type,
                )
                return self._create_deny_result(
                    "No applicable policies found",
                    start_time,
                )

            # Evaluate each policy
            results = []
            for policy in policies:
                result = await self._evaluate_policy(policy, compiled_ir, context)
                results.append((policy, result))

            # Merge results (most restrictive wins)
            final_result = self._merge_results(results, start_time)

            # Cache result
            self._cache[cache_key] = final_result

            evaluation_time = (time.time() - start_time) * 1000
            logger.info(
                "policy_evaluation_completed",
                ir_id=str(compiled_ir.ir_id),
                allowed=final_result.allowed,
                effect=final_result.effect.value,
                matched_rules=final_result.matched_rules,
                evaluation_time_ms=evaluation_time,
            )

            return final_result

        except Exception as e:
            logger.error(
                "policy_evaluation_failed",
                ir_id=str(compiled_ir.ir_id),
                error=str(e),
            )
            # Fail-closed: evaluation error = deny
            return self._create_deny_result(f"Evaluation error: {e}", start_time)

    async def _evaluate_policy(
        self,
        policy: Policy,
        compiled_ir: CompiledIR,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """Evaluate a single policy against IR."""
        # Sort rules by priority (descending)
        sorted_rules = sorted(policy.rules, key=lambda r: r.priority, reverse=True)

        matched_rules: list[str] = []
        final_effect = PolicyEffect.ALLOW  # Default if no rules match
        required_approvals: list[dict[str, str]] = []
        constraints: dict[str, Any] = {}

        # Enrich context with IR data
        enriched_context = self._enrich_context(context, compiled_ir, policy)

        for rule in sorted_rules:
            if self._evaluate_condition(rule.condition, enriched_context):
                matched_rules.append(rule.rule_id)

                # Short-circuit on deny
                if rule.effect == PolicyEffect.DENY:
                    return {
                        "effect": PolicyEffect.DENY,
                        "matched_rules": matched_rules,
                        "required_approvals": [],
                        "constraints": {"deny_reason": rule.name},
                    }

                # Collect approvals
                if rule.effect == PolicyEffect.REQUIRE_APPROVAL:
                    required_approvals.extend(rule.approvers)
                    final_effect = PolicyEffect.REQUIRE_APPROVAL
                    constraints["timeout_hours"] = max(
                        constraints.get("timeout_hours", 0),
                        rule.timeout_hours,
                    )

                # Allow auto takes precedence if no approval required
                if rule.effect == PolicyEffect.ALLOW_AUTO and final_effect == PolicyEffect.ALLOW:
                    final_effect = PolicyEffect.ALLOW_AUTO

        return {
            "effect": final_effect,
            "matched_rules": matched_rules,
            "required_approvals": required_approvals,
            "constraints": constraints,
        }

    def _evaluate_condition(
        self,
        condition: dict[str, Any],
        context: dict[str, Any],
    ) -> bool:
        """Evaluate a rule condition against context."""
        # Handle logical operators
        if "and" in condition:
            return all(
                self._evaluate_condition(c, context)
                for c in condition["and"]
            )

        if "or" in condition:
            return any(
                self._evaluate_condition(c, context)
                for c in condition["or"]
            )

        if "not" in condition:
            return not self._evaluate_condition(condition["not"], context)

        # Handle field comparison
        field = condition.get("field")
        operator = condition.get("operator")
        value = condition.get("value")

        if not field or not operator:
            logger.warning("invalid_condition", condition=condition)
            return False

        # Get field value from context
        field_value = self._get_field_value(field, context)

        return self._compare(field_value, operator, value)

    def _get_field_value(
        self,
        field: str,
        context: dict[str, Any],
    ) -> Any:
        """Get a field value from context, supporting nested fields."""
        parts = field.split(".")
        value = context

        for part in parts:
            if isinstance(value, dict):
                value = value.get(part)
            else:
                return None

        return value

    def _compare(
        self,
        field_value: Any,
        operator: str,
        value: Any,
    ) -> bool:
        """Compare field value against target value."""
        if field_value is None:
            return operator == "is_null"

        comparisons = {
            "equals": lambda f, v: f == v,
            "not_equals": lambda f, v: f != v,
            "greater_than": lambda f, v: f > v,
            "greater_than_or_equals": lambda f, v: f >= v,
            "less_than": lambda f, v: f < v,
            "less_than_or_equals": lambda f, v: f <= v,
            "in": lambda f, v: f in v,
            "not_in": lambda f, v: f not in v,
            "contains": lambda f, v: v in f,
            "starts_with": lambda f, v: str(f).startswith(str(v)),
            "ends_with": lambda f, v: str(f).endswith(str(v)),
            "is_null": lambda f, v: f is None,
            "is_not_null": lambda f, v: f is not None,
            "matches": lambda f, v: self._regex_match(f, v),
        }

        compare_fn = comparisons.get(operator)
        if not compare_fn:
            logger.warning("unknown_operator", operator=operator)
            return False

        try:
            return compare_fn(field_value, value)
        except (TypeError, ValueError) as e:
            logger.warning(
                "comparison_error",
                field_value=field_value,
                operator=operator,
                value=value,
                error=str(e),
            )
            return False

    def _regex_match(self, field_value: Any, pattern: str) -> bool:
        """Perform regex match."""
        import re

        try:
            return bool(re.match(pattern, str(field_value)))
        except re.error:
            return False

    def _enrich_context(
        self,
        context: dict[str, Any],
        compiled_ir: CompiledIR,
        policy: Policy,
    ) -> dict[str, Any]:
        """Enrich context with data from IR and policy."""
        enriched = dict(context)

        # Add IR data
        for op in compiled_ir.operations:
            enriched["environment"] = op.environment.value
            enriched["data_classification"] = op.data_classification.value
            enriched["jurisdiction"] = op.jurisdiction

            if op.estimated_cost_impact:
                enriched["monthly_cost_impact"] = op.estimated_cost_impact.get("monthly_savings", 0)

        # Add from intent justification if in context
        if "justification" in context:
            justification = context["justification"]
            enriched["project_status"] = justification.get("project_status")
            enriched["idle_days"] = justification.get("idle_days", 0)

        # Add action type
        enriched["action"] = context.get("action", compiled_ir.intent_type.split(".")[-1])

        return enriched

    def _merge_results(
        self,
        results: list[tuple[Policy, dict[str, Any]]],
        start_time: float,
    ) -> PolicyEvaluationResult:
        """Merge results from multiple policies."""
        if not results:
            return self._create_deny_result("No policy results", start_time)

        # Find most restrictive effect
        final_effect = PolicyEffect.ALLOW
        all_matched_rules: list[str] = []
        all_approvers: list[dict[str, str]] = []
        all_constraints: dict[str, Any] = {}
        policy_id = ""
        policy_version = ""
        policy_hash = ""

        for policy, result in results:
            policy_id = policy.policy_id
            policy_version = policy.version
            policy_hash = self.policy_store.compute_policy_hash(policy)

            effect = result["effect"]
            all_matched_rules.extend(result["matched_rules"])

            # Deny is most restrictive
            if effect == PolicyEffect.DENY:
                final_effect = PolicyEffect.DENY
                all_constraints.update(result["constraints"])
                break

            # Require approval is next
            if effect == PolicyEffect.REQUIRE_APPROVAL:
                final_effect = PolicyEffect.REQUIRE_APPROVAL
                all_approvers.extend(result["required_approvals"])
                all_constraints.update(result["constraints"])

            # Allow auto only if nothing else
            if effect == PolicyEffect.ALLOW_AUTO and final_effect == PolicyEffect.ALLOW:
                final_effect = PolicyEffect.ALLOW_AUTO

        # Determine risk tier from context/constraints
        risk_score = all_constraints.get("risk_score", 0)
        risk_tier = self._score_to_tier(risk_score)

        evaluation_time = (time.time() - start_time) * 1000

        return PolicyEvaluationResult(
            policy_id=policy_id,
            policy_version=policy_version,
            policy_hash=policy_hash,
            allowed=final_effect not in [PolicyEffect.DENY],
            effect=final_effect,
            matched_rules=list(set(all_matched_rules)),
            risk_score=risk_score,
            risk_tier=risk_tier,
            required_approvals=self._dedupe_approvers(all_approvers),
            constraints=all_constraints,
            evaluation_time_ms=evaluation_time,
        )

    def _create_deny_result(
        self,
        reason: str,
        start_time: float,
    ) -> PolicyEvaluationResult:
        """Create a deny result."""
        evaluation_time = (time.time() - start_time) * 1000

        return PolicyEvaluationResult(
            policy_id="system",
            policy_version="1.0.0",
            policy_hash="",
            allowed=False,
            effect=PolicyEffect.DENY,
            matched_rules=["system_deny"],
            risk_score=100,
            risk_tier=RiskTier.CRITICAL,
            required_approvals=[],
            constraints={"deny_reason": reason},
            evaluation_time_ms=evaluation_time,
        )

    def _score_to_tier(self, score: int) -> RiskTier:
        """Convert risk score to tier."""
        if score < 30:
            return RiskTier.LOW
        if score < 60:
            return RiskTier.MEDIUM
        if score < 80:
            return RiskTier.HIGH
        return RiskTier.CRITICAL

    def _dedupe_approvers(
        self,
        approvers: list[dict[str, str]],
    ) -> list[dict[str, str]]:
        """Deduplicate approvers list."""
        seen = set()
        deduped = []

        for approver in approvers:
            key = (approver.get("role"), approver.get("user_id"))
            if key not in seen:
                seen.add(key)
                deduped.append(approver)

        return deduped

    def _get_environment(self, compiled_ir: CompiledIR) -> Environment:
        """Extract environment from compiled IR."""
        for op in compiled_ir.operations:
            return op.environment
        return Environment.DEVELOPMENT

    def _compute_cache_key(
        self,
        compiled_ir: CompiledIR,
        context: dict[str, Any],
        tenant_id: UUID,
    ) -> str:
        """Compute cache key for evaluation."""
        import hashlib
        import json

        key_data = {
            "ir_hash": str(compiled_ir.ir_id),
            "context": context,
            "tenant_id": str(tenant_id),
        }
        canonical = json.dumps(key_data, sort_keys=True)
        return hashlib.sha256(canonical.encode()).hexdigest()

    def invalidate_cache(self, tenant_id: UUID | None = None) -> None:
        """Invalidate evaluation cache."""
        if tenant_id:
            # Invalidate tenant-specific cache
            keys_to_remove = [
                k for k in self._cache.keys()
                if str(tenant_id) in k
            ]
            for key in keys_to_remove:
                del self._cache[key]
        else:
            self._cache.clear()

        logger.info(
            "policy_cache_invalidated",
            tenant_id=str(tenant_id) if tenant_id else "all",
        )
