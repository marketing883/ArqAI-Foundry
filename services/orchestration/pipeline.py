"""
Orchestration Pipeline

Coordinates the full execution flow:
compile → policy check → risk scoring → authorization → execution → evidence
"""

import time
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

import structlog

from arqai_foundry.core.enums import ExecutionStatus, PolicyEffect, RiskTier
from arqai_foundry.core.exceptions import (
    CompilationError,
    OrchestrationError,
    PolicyViolationError,
)
from arqai_foundry.core.models import (
    ApprovalRequest,
    CapabilityToken,
    CompiledIR,
    ExecutionContext,
    EvidencePacket,
    Intent,
    PolicyEvaluationResult,
    RiskAssessment,
)
from services.compiler import DeterministicCompiler
from services.evidence import EvidenceVault
from services.identity import CapabilityTokenService
from services.policy import PolicyEvaluator
from services.risk import RiskScoringEngine

logger = structlog.get_logger(__name__)


class OrchestrationPipeline:
    """
    Orchestrates the complete execution pipeline with governance checkpoints.

    Pipeline Stages:
    1. Compile: Intent → IR
    2. Static Check: IR → Policy evaluation
    3. Risk Scoring: IR + Context → Risk score
    4. Authorization: Risk score → Capability token (if allowed)
    5. Execution: IR + Token → Action execution
    6. Evidence: All above → Evidence packet

    State Machine:
    pending → compiling → checking → scoring → authorized → executing → completed
                     ↓          ↓         ↓          ↓
                   failed     denied   awaiting   failed
                                      _approval
    """

    def __init__(
        self,
        compiler: DeterministicCompiler | None = None,
        policy_evaluator: PolicyEvaluator | None = None,
        risk_scorer: RiskScoringEngine | None = None,
        token_service: CapabilityTokenService | None = None,
        evidence_vault: EvidenceVault | None = None,
    ):
        self.compiler = compiler or DeterministicCompiler()
        self.policy_evaluator = policy_evaluator or PolicyEvaluator()
        self.risk_scorer = risk_scorer or RiskScoringEngine()
        self.token_service = token_service or CapabilityTokenService()
        self.evidence_vault = evidence_vault or EvidenceVault()

        # Active executions
        self._executions: dict[UUID, ExecutionContext] = {}

    async def execute(
        self,
        intent_data: dict[str, Any],
        tenant_id: UUID,
        agent_id: UUID,
        context: dict[str, Any] | None = None,
        dry_run: bool = False,
    ) -> ExecutionContext:
        """
        Execute the full orchestration pipeline.

        Returns ExecutionContext with final status and all artifacts.
        """
        execution_id = uuid4()
        context = context or {}
        start_time = time.time()

        logger.info(
            "pipeline_started",
            execution_id=str(execution_id),
            tenant_id=str(tenant_id),
            agent_id=str(agent_id),
            intent_type=intent_data.get("intent_type"),
        )

        # Initialize execution context
        exec_ctx = ExecutionContext(
            execution_id=execution_id,
            tenant_id=tenant_id,
            agent_id=agent_id,
            status=ExecutionStatus.PENDING,
        )
        self._executions[execution_id] = exec_ctx

        try:
            # Stage 1: Compile
            exec_ctx = await self._stage_compile(exec_ctx, intent_data)
            if exec_ctx.status == ExecutionStatus.FAILED:
                return exec_ctx

            # Stage 2: Policy Check
            exec_ctx = await self._stage_policy_check(exec_ctx, context)
            if exec_ctx.status == ExecutionStatus.DENIED:
                return exec_ctx

            # Stage 3: Risk Scoring
            exec_ctx = await self._stage_risk_scoring(exec_ctx, context)

            # Stage 4: Authorization
            exec_ctx = await self._stage_authorization(exec_ctx, context)
            if exec_ctx.status == ExecutionStatus.AWAITING_APPROVAL:
                return exec_ctx
            if exec_ctx.status == ExecutionStatus.DENIED:
                return exec_ctx

            # Stage 5: Execution (skip if dry run)
            if not dry_run:
                exec_ctx = await self._stage_execution(exec_ctx, context)
            else:
                exec_ctx.status = ExecutionStatus.COMPLETED
                logger.info(
                    "pipeline_dry_run_completed",
                    execution_id=str(execution_id),
                )

            # Stage 6: Evidence
            exec_ctx = await self._stage_evidence(exec_ctx, context, dry_run)

            execution_time = (time.time() - start_time) * 1000
            logger.info(
                "pipeline_completed",
                execution_id=str(execution_id),
                status=exec_ctx.status.value,
                execution_time_ms=execution_time,
            )

            return exec_ctx

        except Exception as e:
            exec_ctx.status = ExecutionStatus.FAILED
            exec_ctx.error = str(e)
            logger.error(
                "pipeline_failed",
                execution_id=str(execution_id),
                error=str(e),
            )
            return exec_ctx

    async def _stage_compile(
        self,
        exec_ctx: ExecutionContext,
        intent_data: dict[str, Any],
    ) -> ExecutionContext:
        """Stage 1: Compile intent to IR."""
        exec_ctx.status = ExecutionStatus.COMPILING
        exec_ctx.current_stage = "compiling"

        logger.debug(
            "stage_compile_started",
            execution_id=str(exec_ctx.execution_id),
        )

        try:
            compiled_ir = await self.compiler.compile(intent_data)
            exec_ctx.compiled_ir = compiled_ir

            # Store original intent
            exec_ctx.intent = Intent(
                intent_type=intent_data["intent_type"],
                version=intent_data["version"],
                action=intent_data["action"],
                target=intent_data["target"],
                environment=intent_data["environment"],
                justification=intent_data["justification"],
            )

            logger.debug(
                "stage_compile_completed",
                execution_id=str(exec_ctx.execution_id),
                ir_id=str(compiled_ir.ir_id),
            )

            return exec_ctx

        except CompilationError as e:
            exec_ctx.status = ExecutionStatus.FAILED
            exec_ctx.error = str(e)
            exec_ctx.error_details = e.details
            return exec_ctx

    async def _stage_policy_check(
        self,
        exec_ctx: ExecutionContext,
        context: dict[str, Any],
    ) -> ExecutionContext:
        """Stage 2: Policy evaluation."""
        exec_ctx.status = ExecutionStatus.CHECKING
        exec_ctx.current_stage = "policy_check"

        logger.debug(
            "stage_policy_check_started",
            execution_id=str(exec_ctx.execution_id),
        )

        try:
            policy_result = await self.policy_evaluator.evaluate(
                compiled_ir=exec_ctx.compiled_ir,
                context=context,
                tenant_id=exec_ctx.tenant_id,
            )
            exec_ctx.policy_result = policy_result

            if policy_result.effect == PolicyEffect.DENY:
                exec_ctx.status = ExecutionStatus.DENIED
                exec_ctx.error = "Policy denied the action"
                exec_ctx.error_details = {
                    "matched_rules": policy_result.matched_rules,
                    "constraints": policy_result.constraints,
                }

            logger.debug(
                "stage_policy_check_completed",
                execution_id=str(exec_ctx.execution_id),
                effect=policy_result.effect.value,
            )

            return exec_ctx

        except Exception as e:
            exec_ctx.status = ExecutionStatus.FAILED
            exec_ctx.error = f"Policy evaluation failed: {e}"
            return exec_ctx

    async def _stage_risk_scoring(
        self,
        exec_ctx: ExecutionContext,
        context: dict[str, Any],
    ) -> ExecutionContext:
        """Stage 3: Risk scoring."""
        exec_ctx.status = ExecutionStatus.SCORING
        exec_ctx.current_stage = "risk_scoring"

        logger.debug(
            "stage_risk_scoring_started",
            execution_id=str(exec_ctx.execution_id),
        )

        try:
            risk_assessment = await self.risk_scorer.assess_risk(
                compiled_ir=exec_ctx.compiled_ir,
                context=context,
            )
            exec_ctx.risk_assessment = risk_assessment

            # Update policy result with risk score
            if exec_ctx.policy_result:
                exec_ctx.policy_result.risk_score = risk_assessment.risk_score
                exec_ctx.policy_result.risk_tier = risk_assessment.risk_tier

            logger.debug(
                "stage_risk_scoring_completed",
                execution_id=str(exec_ctx.execution_id),
                risk_score=risk_assessment.risk_score,
                risk_tier=risk_assessment.risk_tier.value,
            )

            return exec_ctx

        except Exception as e:
            exec_ctx.status = ExecutionStatus.FAILED
            exec_ctx.error = f"Risk scoring failed: {e}"
            return exec_ctx

    async def _stage_authorization(
        self,
        exec_ctx: ExecutionContext,
        context: dict[str, Any],
    ) -> ExecutionContext:
        """Stage 4: Authorization (token issuance or approval request)."""
        exec_ctx.current_stage = "authorization"

        logger.debug(
            "stage_authorization_started",
            execution_id=str(exec_ctx.execution_id),
        )

        policy_result = exec_ctx.policy_result

        # Check if approval is required
        if policy_result.effect == PolicyEffect.REQUIRE_APPROVAL:
            exec_ctx.status = ExecutionStatus.AWAITING_APPROVAL
            logger.info(
                "approval_required",
                execution_id=str(exec_ctx.execution_id),
                approvers=policy_result.required_approvals,
            )
            return exec_ctx

        # Check if auto-allowed
        if policy_result.effect in [PolicyEffect.ALLOW, PolicyEffect.ALLOW_AUTO]:
            try:
                # Issue capability token
                token = await self.token_service.issue_token(
                    agent_identity=str(exec_ctx.agent_id),  # Would use cert fingerprint
                    resource_id=exec_ctx.compiled_ir.operations[0].target,
                    action=exec_ctx.intent.action,
                    constraints=policy_result.constraints,
                )
                exec_ctx.capability_token = token
                exec_ctx.status = ExecutionStatus.AUTHORIZED

                logger.debug(
                    "stage_authorization_completed",
                    execution_id=str(exec_ctx.execution_id),
                    token_id=str(token.token_id),
                )

            except Exception as e:
                exec_ctx.status = ExecutionStatus.FAILED
                exec_ctx.error = f"Token issuance failed: {e}"

        return exec_ctx

    async def _stage_execution(
        self,
        exec_ctx: ExecutionContext,
        context: dict[str, Any],
    ) -> ExecutionContext:
        """Stage 5: Action execution."""
        exec_ctx.status = ExecutionStatus.EXECUTING
        exec_ctx.current_stage = "execution"

        logger.debug(
            "stage_execution_started",
            execution_id=str(exec_ctx.execution_id),
        )

        try:
            # Validate token before execution
            await self.token_service.consume_token(
                token=exec_ctx.capability_token,
                expected_resource_id=exec_ctx.compiled_ir.operations[0].target,
                expected_action=exec_ctx.intent.action,
            )

            # Execute action (would call ActionExecutor here)
            # For now, simulate successful execution
            execution_result = {
                "pre_action_state": {"status": "running"},
                "action_trace": [
                    {
                        "timestamp": datetime.utcnow().isoformat(),
                        "action": exec_ctx.intent.action.value,
                        "target": exec_ctx.compiled_ir.operations[0].target,
                        "result": "success",
                    }
                ],
                "post_action_state": {"status": "terminated"},
            }

            context["execution_result"] = execution_result
            exec_ctx.status = ExecutionStatus.COMPLETED
            exec_ctx.completed_at = datetime.utcnow()

            logger.debug(
                "stage_execution_completed",
                execution_id=str(exec_ctx.execution_id),
            )

        except Exception as e:
            exec_ctx.status = ExecutionStatus.FAILED
            exec_ctx.error = f"Execution failed: {e}"
            logger.error(
                "stage_execution_failed",
                execution_id=str(exec_ctx.execution_id),
                error=str(e),
            )

        return exec_ctx

    async def _stage_evidence(
        self,
        exec_ctx: ExecutionContext,
        context: dict[str, Any],
        dry_run: bool,
    ) -> ExecutionContext:
        """Stage 6: Evidence generation."""
        exec_ctx.current_stage = "evidence"

        logger.debug(
            "stage_evidence_started",
            execution_id=str(exec_ctx.execution_id),
        )

        try:
            evidence = await self.evidence_vault.create_evidence(
                tenant_id=exec_ctx.tenant_id,
                agent_id=exec_ctx.agent_id,
                request=exec_ctx.intent.model_dump() if exec_ctx.intent else {},
                compliance_ir=exec_ctx.compiled_ir.model_dump() if exec_ctx.compiled_ir else {},
                policy_validation=exec_ctx.policy_result.model_dump() if exec_ctx.policy_result else {},
                risk_assessment=exec_ctx.risk_assessment.model_dump() if exec_ctx.risk_assessment else {},
                capability_token=exec_ctx.capability_token.model_dump() if exec_ctx.capability_token else {},
                execution=context.get("execution_result", {"dry_run": dry_run}),
                financial_impact=exec_ctx.compiled_ir.operations[0].estimated_cost_impact if exec_ctx.compiled_ir else None,
            )

            exec_ctx.evidence_id = evidence.evidence_id

            logger.debug(
                "stage_evidence_completed",
                execution_id=str(exec_ctx.execution_id),
                evidence_id=str(evidence.evidence_id),
            )

        except Exception as e:
            logger.error(
                "stage_evidence_failed",
                execution_id=str(exec_ctx.execution_id),
                error=str(e),
            )
            # Don't fail the execution if evidence fails, but log it

        return exec_ctx

    async def get_execution(self, execution_id: UUID) -> ExecutionContext | None:
        """Get execution context by ID."""
        return self._executions.get(execution_id)

    async def resume_after_approval(
        self,
        execution_id: UUID,
        approved_by: str,
        context: dict[str, Any] | None = None,
    ) -> ExecutionContext:
        """Resume execution after approval."""
        exec_ctx = self._executions.get(execution_id)

        if not exec_ctx:
            raise OrchestrationError(f"Execution not found: {execution_id}")

        if exec_ctx.status != ExecutionStatus.AWAITING_APPROVAL:
            raise OrchestrationError(
                f"Execution not awaiting approval: {exec_ctx.status}"
            )

        context = context or {}
        context["approved_by"] = approved_by
        context["approved_at"] = datetime.utcnow().isoformat()

        # Issue token
        exec_ctx.policy_result.effect = PolicyEffect.ALLOW
        exec_ctx = await self._stage_authorization(exec_ctx, context)

        if exec_ctx.status == ExecutionStatus.AUTHORIZED:
            exec_ctx = await self._stage_execution(exec_ctx, context)
            exec_ctx = await self._stage_evidence(exec_ctx, context, dry_run=False)

        return exec_ctx

    async def cancel_execution(
        self,
        execution_id: UUID,
        reason: str,
    ) -> ExecutionContext:
        """Cancel a pending or awaiting execution."""
        exec_ctx = self._executions.get(execution_id)

        if not exec_ctx:
            raise OrchestrationError(f"Execution not found: {execution_id}")

        if exec_ctx.status in [ExecutionStatus.COMPLETED, ExecutionStatus.FAILED]:
            raise OrchestrationError(
                f"Cannot cancel completed execution: {exec_ctx.status}"
            )

        exec_ctx.status = ExecutionStatus.CANCELLED
        exec_ctx.error = f"Cancelled: {reason}"
        exec_ctx.completed_at = datetime.utcnow()

        logger.info(
            "execution_cancelled",
            execution_id=str(execution_id),
            reason=reason,
        )

        return exec_ctx
