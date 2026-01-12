"""
Policy Testing Framework

Tests policies before deployment with simulation and verification.
Ensures policies work as expected before going live.
"""

import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

import structlog

from arqai_foundry.core.enums import Environment, PolicyEffect
from arqai_foundry.core.models import CompiledIR, IROperation, Policy
from services.policy.evaluator import PolicyEvaluator
from services.policy.policy_store import PolicyStore

logger = structlog.get_logger(__name__)


@dataclass
class PolicyTestCase:
    """A single policy test case."""

    name: str
    description: str | None
    intent: dict[str, Any]
    context: dict[str, Any]
    expected_effect: PolicyEffect
    expected_matched_rules: list[str] | None = None
    expected_approvers: list[str] | None = None
    expected_risk_tier: str | None = None


@dataclass
class PolicyTestResult:
    """Result of a single test case."""

    test_case: PolicyTestCase
    passed: bool
    actual_effect: PolicyEffect
    actual_matched_rules: list[str]
    actual_approvers: list[dict[str, str]]
    actual_risk_tier: str
    evaluation_time_ms: float
    error: str | None = None
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class PolicyTestSuiteResult:
    """Result of running a test suite."""

    suite_name: str
    policy_id: str
    policy_version: str
    total_tests: int
    passed_tests: int
    failed_tests: int
    results: list[PolicyTestResult]
    coverage: dict[str, Any]
    total_time_ms: float
    run_at: datetime = field(default_factory=datetime.utcnow)

    @property
    def pass_rate(self) -> float:
        if self.total_tests == 0:
            return 0.0
        return self.passed_tests / self.total_tests * 100


class PolicyTestFramework:
    """
    Framework for testing policies before deployment.

    Features:
    - Test case execution
    - Coverage analysis
    - Regression testing
    - Performance testing
    """

    def __init__(
        self,
        policy_store: PolicyStore | None = None,
        evaluator: PolicyEvaluator | None = None,
    ):
        self.policy_store = policy_store or PolicyStore()
        self.evaluator = evaluator or PolicyEvaluator(self.policy_store)

    async def run_test_suite(
        self,
        policy_id: str,
        test_cases: list[PolicyTestCase],
        tenant_id: UUID,
        suite_name: str = "default",
    ) -> PolicyTestSuiteResult:
        """Run a suite of test cases against a policy."""
        start_time = time.time()

        logger.info(
            "policy_test_suite_started",
            policy_id=policy_id,
            suite_name=suite_name,
            test_count=len(test_cases),
        )

        policy = await self.policy_store.get_policy(policy_id)
        results: list[PolicyTestResult] = []
        passed = 0
        failed = 0

        for test_case in test_cases:
            result = await self._run_test_case(test_case, policy, tenant_id)
            results.append(result)

            if result.passed:
                passed += 1
            else:
                failed += 1

        # Calculate coverage
        coverage = self._calculate_coverage(policy, results)

        total_time = (time.time() - start_time) * 1000

        suite_result = PolicyTestSuiteResult(
            suite_name=suite_name,
            policy_id=policy_id,
            policy_version=policy.version,
            total_tests=len(test_cases),
            passed_tests=passed,
            failed_tests=failed,
            results=results,
            coverage=coverage,
            total_time_ms=total_time,
        )

        logger.info(
            "policy_test_suite_completed",
            policy_id=policy_id,
            suite_name=suite_name,
            passed=passed,
            failed=failed,
            pass_rate=suite_result.pass_rate,
            total_time_ms=total_time,
        )

        return suite_result

    async def _run_test_case(
        self,
        test_case: PolicyTestCase,
        policy: Policy,
        tenant_id: UUID,
    ) -> PolicyTestResult:
        """Run a single test case."""
        start_time = time.time()

        try:
            # Build mock compiled IR from intent
            compiled_ir = self._build_mock_ir(test_case.intent)

            # Run evaluation
            eval_result = await self.evaluator.evaluate(
                compiled_ir=compiled_ir,
                context=test_case.context,
                tenant_id=tenant_id,
            )

            # Check expectations
            passed = True
            details: dict[str, Any] = {}

            # Check effect
            if eval_result.effect != test_case.expected_effect:
                passed = False
                details["effect_mismatch"] = {
                    "expected": test_case.expected_effect.value,
                    "actual": eval_result.effect.value,
                }

            # Check matched rules (if specified)
            if test_case.expected_matched_rules is not None:
                expected_set = set(test_case.expected_matched_rules)
                actual_set = set(eval_result.matched_rules)
                if expected_set != actual_set:
                    passed = False
                    details["rules_mismatch"] = {
                        "expected": list(expected_set),
                        "actual": list(actual_set),
                        "missing": list(expected_set - actual_set),
                        "unexpected": list(actual_set - expected_set),
                    }

            # Check approvers (if specified)
            if test_case.expected_approvers is not None:
                actual_roles = [a.get("role") for a in eval_result.required_approvals]
                if set(test_case.expected_approvers) != set(actual_roles):
                    passed = False
                    details["approvers_mismatch"] = {
                        "expected": test_case.expected_approvers,
                        "actual": actual_roles,
                    }

            # Check risk tier (if specified)
            if test_case.expected_risk_tier is not None:
                if eval_result.risk_tier.value != test_case.expected_risk_tier:
                    passed = False
                    details["risk_tier_mismatch"] = {
                        "expected": test_case.expected_risk_tier,
                        "actual": eval_result.risk_tier.value,
                    }

            evaluation_time = (time.time() - start_time) * 1000

            return PolicyTestResult(
                test_case=test_case,
                passed=passed,
                actual_effect=eval_result.effect,
                actual_matched_rules=eval_result.matched_rules,
                actual_approvers=eval_result.required_approvals,
                actual_risk_tier=eval_result.risk_tier.value,
                evaluation_time_ms=evaluation_time,
                details=details,
            )

        except Exception as e:
            evaluation_time = (time.time() - start_time) * 1000

            return PolicyTestResult(
                test_case=test_case,
                passed=False,
                actual_effect=PolicyEffect.DENY,
                actual_matched_rules=[],
                actual_approvers=[],
                actual_risk_tier="critical",
                evaluation_time_ms=evaluation_time,
                error=str(e),
            )

    def _build_mock_ir(self, intent: dict[str, Any]) -> CompiledIR:
        """Build a mock CompiledIR from test intent data."""
        target = intent.get("target", {})
        environment_str = intent.get("environment", "development")

        try:
            environment = Environment(environment_str)
        except ValueError:
            environment = Environment.DEVELOPMENT

        from arqai_foundry.core.enums import DataClassification

        operation = IROperation(
            type=f"test.{intent.get('action', 'unknown')}",
            target=target.get("resource_id", "test-resource"),
            parameters=intent,
            data_classification=DataClassification.INTERNAL,
            environment=environment,
            jurisdiction=["US"],
        )

        return CompiledIR(
            intent_id=uuid4(),
            intent_type=intent.get("intent_type", "test.intent"),
            operations=[operation],
            policy_version="1.0.0",
            schema_version="1.0.0",
        )

    def _calculate_coverage(
        self,
        policy: Policy,
        results: list[PolicyTestResult],
    ) -> dict[str, Any]:
        """Calculate test coverage for policy rules."""
        all_rules = {rule.rule_id for rule in policy.rules}
        tested_rules: set[str] = set()

        for result in results:
            tested_rules.update(result.actual_matched_rules)

        untested_rules = all_rules - tested_rules
        coverage_percent = (
            len(tested_rules) / len(all_rules) * 100
            if all_rules else 100
        )

        return {
            "total_rules": len(all_rules),
            "tested_rules": len(tested_rules),
            "untested_rules": list(untested_rules),
            "coverage_percent": round(coverage_percent, 2),
        }

    async def run_regression_tests(
        self,
        policy_id: str,
        old_version: str,
        new_version: str,
        test_cases: list[PolicyTestCase],
        tenant_id: UUID,
    ) -> dict[str, Any]:
        """Run regression tests comparing two policy versions."""
        logger.info(
            "regression_test_started",
            policy_id=policy_id,
            old_version=old_version,
            new_version=new_version,
        )

        # Run tests against old version
        old_policy = await self.policy_store.get_policy(policy_id, old_version)
        old_results = await self.run_test_suite(
            policy_id=policy_id,
            test_cases=test_cases,
            tenant_id=tenant_id,
            suite_name=f"regression-{old_version}",
        )

        # Temporarily activate new version and run tests
        await self.policy_store.set_active_version(policy_id, new_version)
        new_results = await self.run_test_suite(
            policy_id=policy_id,
            test_cases=test_cases,
            tenant_id=tenant_id,
            suite_name=f"regression-{new_version}",
        )

        # Restore old version
        await self.policy_store.set_active_version(policy_id, old_version)

        # Compare results
        regressions = []
        improvements = []

        for old_result, new_result in zip(old_results.results, new_results.results):
            if old_result.passed and not new_result.passed:
                regressions.append({
                    "test_name": old_result.test_case.name,
                    "old_effect": old_result.actual_effect.value,
                    "new_effect": new_result.actual_effect.value,
                })
            elif not old_result.passed and new_result.passed:
                improvements.append({
                    "test_name": old_result.test_case.name,
                    "old_effect": old_result.actual_effect.value,
                    "new_effect": new_result.actual_effect.value,
                })

        return {
            "policy_id": policy_id,
            "old_version": old_version,
            "new_version": new_version,
            "old_pass_rate": old_results.pass_rate,
            "new_pass_rate": new_results.pass_rate,
            "regressions": regressions,
            "improvements": improvements,
            "regression_count": len(regressions),
            "improvement_count": len(improvements),
            "safe_to_deploy": len(regressions) == 0,
        }

    async def run_performance_test(
        self,
        policy_id: str,
        test_cases: list[PolicyTestCase],
        tenant_id: UUID,
        iterations: int = 100,
    ) -> dict[str, Any]:
        """Run performance tests on policy evaluation."""
        logger.info(
            "performance_test_started",
            policy_id=policy_id,
            iterations=iterations,
        )

        times: list[float] = []

        for _ in range(iterations):
            for test_case in test_cases:
                compiled_ir = self._build_mock_ir(test_case.intent)

                start = time.time()
                await self.evaluator.evaluate(
                    compiled_ir=compiled_ir,
                    context=test_case.context,
                    tenant_id=tenant_id,
                )
                times.append((time.time() - start) * 1000)

        # Calculate statistics
        times.sort()
        total_evaluations = len(times)

        return {
            "policy_id": policy_id,
            "total_evaluations": total_evaluations,
            "min_ms": round(min(times), 3),
            "max_ms": round(max(times), 3),
            "avg_ms": round(sum(times) / len(times), 3),
            "p50_ms": round(times[int(len(times) * 0.50)], 3),
            "p95_ms": round(times[int(len(times) * 0.95)], 3),
            "p99_ms": round(times[int(len(times) * 0.99)], 3),
            "evaluations_per_second": round(total_evaluations / (sum(times) / 1000), 2),
        }

    def create_test_case(
        self,
        name: str,
        intent: dict[str, Any],
        expected_effect: PolicyEffect,
        context: dict[str, Any] | None = None,
        description: str | None = None,
        expected_matched_rules: list[str] | None = None,
        expected_approvers: list[str] | None = None,
        expected_risk_tier: str | None = None,
    ) -> PolicyTestCase:
        """Helper to create a test case."""
        return PolicyTestCase(
            name=name,
            description=description,
            intent=intent,
            context=context or {},
            expected_effect=expected_effect,
            expected_matched_rules=expected_matched_rules,
            expected_approvers=expected_approvers,
            expected_risk_tier=expected_risk_tier,
        )


# =============================================================================
# Pre-built Test Suites
# =============================================================================

def get_cost_optimization_test_suite() -> list[PolicyTestCase]:
    """Get pre-built test suite for cost optimization policy."""
    return [
        PolicyTestCase(
            name="production_terminate_requires_approval",
            description="Terminating production resources should require approval",
            intent={
                "intent_type": "cost_optimization.terminate",
                "action": "terminate",
                "target": {"resource_type": "ec2", "resource_id": "i-prod-123"},
                "environment": "production",
            },
            context={"monthly_cost_impact": 500},
            expected_effect=PolicyEffect.REQUIRE_APPROVAL,
        ),
        PolicyTestCase(
            name="dev_low_risk_auto_allowed",
            description="Low-risk dev cleanup should auto-allow",
            intent={
                "intent_type": "cost_optimization.terminate",
                "action": "terminate",
                "target": {"resource_type": "ec2", "resource_id": "i-dev-123"},
                "environment": "development",
            },
            context={
                "risk_score": 20,
                "justification": {
                    "project_status": "completed",
                    "idle_days": 100,
                },
            },
            expected_effect=PolicyEffect.ALLOW_AUTO,
        ),
        PolicyTestCase(
            name="high_cost_requires_approval",
            description="High-cost actions should require approval",
            intent={
                "intent_type": "cost_optimization.terminate",
                "action": "terminate",
                "target": {"resource_type": "ec2", "resource_id": "i-dev-456"},
                "environment": "development",
            },
            context={"monthly_cost_impact": 10000},
            expected_effect=PolicyEffect.REQUIRE_APPROVAL,
        ),
        PolicyTestCase(
            name="staging_terminate_requires_approval",
            description="Staging terminations should require team lead approval",
            intent={
                "intent_type": "cost_optimization.terminate",
                "action": "terminate",
                "target": {"resource_type": "rds", "resource_id": "db-staging-123"},
                "environment": "staging",
            },
            context={},
            expected_effect=PolicyEffect.REQUIRE_APPROVAL,
            expected_approvers=["team_lead"],
        ),
    ]


def get_healthcare_test_suite() -> list[PolicyTestCase]:
    """Get pre-built test suite for healthcare HIPAA policy."""
    return [
        PolicyTestCase(
            name="phi_access_requires_approval",
            description="PHI access should always require approval",
            intent={
                "intent_type": "healthcare.phi_access",
                "action": "read",
                "target": {"data_type": "patient_records"},
                "environment": "production",
            },
            context={"data_classification": "phi"},
            expected_effect=PolicyEffect.REQUIRE_APPROVAL,
        ),
        PolicyTestCase(
            name="phi_export_without_authorization_denied",
            description="PHI export without proper authorization should be denied",
            intent={
                "intent_type": "healthcare.phi_access",
                "action": "export",
                "target": {"data_type": "patient_records"},
                "environment": "production",
            },
            context={
                "data_classification": "phi",
                "authorization": "personal_use",
            },
            expected_effect=PolicyEffect.DENY,
        ),
        PolicyTestCase(
            name="phi_minimum_necessary_enforced",
            description="PHI access without minimum necessary should be denied",
            intent={
                "intent_type": "healthcare.phi_access",
                "action": "read",
                "target": {"data_type": "patient_records"},
                "environment": "production",
            },
            context={
                "data_classification": "phi",
                "minimum_necessary": False,
            },
            expected_effect=PolicyEffect.DENY,
        ),
    ]
