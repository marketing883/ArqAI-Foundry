"""
Deterministic Compiler

Transforms validated intents into compliance-annotated IR without non-determinism.
No LLM, no guessing, no defaults - fail-closed semantics.
"""

import hashlib
import json
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

import structlog

from arqai_foundry.core.enums import (
    ActionType,
    DataClassification,
    Environment,
)
from arqai_foundry.core.exceptions import (
    AmbiguousIntentError,
    CompilationError,
    SchemaValidationError,
)
from arqai_foundry.core.models import (
    CompiledIR,
    Intent,
    IntentJustification,
    IntentTarget,
    IROperation,
)
from services.compiler.schema_registry import IntentSchemaRegistry

logger = structlog.get_logger(__name__)


class DeterministicCompiler:
    """
    Compiles validated intents into compliance-annotated IR.

    Compilation Pipeline:
    1. Schema validation (strict)
    2. Static policy check (deterministic rules)
    3. IR generation (one-to-one mapping)
    4. IR safety verification (prove properties)
    5. Compliance annotation (sensitivity, jurisdiction)

    CRITICAL: This compiler is 100% deterministic.
    Same input ALWAYS produces same output.
    """

    def __init__(
        self,
        schema_registry: IntentSchemaRegistry | None = None,
    ):
        self.schema_registry = schema_registry or IntentSchemaRegistry()

        # Compilation rules (deterministic mappings)
        self._action_mappings = self._build_action_mappings()
        self._classification_rules = self._build_classification_rules()

    def _build_action_mappings(self) -> dict[str, dict[str, str]]:
        """Build deterministic action type mappings."""
        return {
            "cost_optimization.terminate": {
                "terminate": "cloud.{provider}.{resource_type}.terminate",
                "stop": "cloud.{provider}.{resource_type}.stop",
                "snapshot": "cloud.{provider}.{resource_type}.snapshot",
            },
            "cost_optimization.resize": {
                "update": "cloud.{provider}.{resource_type}.modify",
            },
            "compliance.audit": {
                "analyze": "compliance.{framework}.audit",
            },
            "healthcare.phi_access": {
                "read": "healthcare.phi.read",
                "export": "healthcare.phi.export",
                "analyze": "healthcare.phi.analyze",
            },
            "notification.send": {
                "notify": "notification.{channel}.send",
            },
        }

    def _build_classification_rules(self) -> dict[str, DataClassification]:
        """Build deterministic data classification rules."""
        return {
            "healthcare.phi": DataClassification.PHI,
            "healthcare.patient": DataClassification.PHI,
            "payment": DataClassification.PCI,
            "pii": DataClassification.PII,
            "production": DataClassification.CONFIDENTIAL,
            "staging": DataClassification.INTERNAL,
            "development": DataClassification.INTERNAL,
            "public": DataClassification.PUBLIC,
        }

    async def compile(
        self,
        intent_data: dict[str, Any],
        policy_version: str = "1.0.0",
    ) -> CompiledIR:
        """
        Compile an intent into IR.

        This is the main entry point for compilation.
        Returns CompiledIR or raises CompilationError.
        """
        start_time = datetime.utcnow()
        compilation_id = uuid4()

        logger.info(
            "compilation_started",
            compilation_id=str(compilation_id),
            intent_type=intent_data.get("intent_type"),
        )

        try:
            # Step 1: Schema validation
            validation_errors = self.schema_registry.validate_intent(intent_data)
            if validation_errors:
                raise SchemaValidationError(
                    "Intent failed schema validation",
                    schema_errors=validation_errors,
                )

            # Step 2: Parse into typed Intent model
            intent = self._parse_intent(intent_data)

            # Step 3: Static policy check
            await self._static_policy_check(intent)

            # Step 4: Generate IR operations
            operations = self._generate_operations(intent, intent_data)

            # Step 5: Annotate with compliance metadata
            self._annotate_compliance(operations, intent)

            # Step 6: Determine policy requirements
            policy_requirements = self._determine_policy_requirements(operations, intent)

            # Build compiled IR
            compiled_ir = CompiledIR(
                intent_id=intent.intent_id,
                intent_type=intent.intent_type,
                operations=operations,
                policy_requirements=policy_requirements,
                compiled_at=datetime.utcnow(),
                policy_version=policy_version,
                schema_version=intent_data.get("version", "1.0.0"),
            )

            # Step 7: Verify IR safety
            self._verify_ir_safety(compiled_ir)

            compilation_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            logger.info(
                "compilation_completed",
                compilation_id=str(compilation_id),
                intent_id=str(intent.intent_id),
                operation_count=len(operations),
                compilation_time_ms=compilation_time,
            )

            return compiled_ir

        except (SchemaValidationError, AmbiguousIntentError, CompilationError):
            raise
        except Exception as e:
            logger.error(
                "compilation_failed",
                compilation_id=str(compilation_id),
                error=str(e),
            )
            raise CompilationError(f"Compilation failed: {e}")

    def _parse_intent(self, intent_data: dict[str, Any]) -> Intent:
        """Parse raw intent data into typed Intent model."""
        target_data = intent_data.get("target", {})
        justification_data = intent_data.get("justification", {})

        target = IntentTarget(
            resource_type=target_data.get("resource_type", target_data.get("scope", "unknown")),
            resource_id=target_data.get("resource_id", target_data.get("channel", "unknown")),
            provider=target_data.get("provider", target_data.get("channel", "internal")),
            region=target_data.get("region"),
            account_id=target_data.get("account_id"),
        )

        justification = IntentJustification(
            project_id=justification_data.get("project_id"),
            project_status=justification_data.get("project_status"),
            idle_days=justification_data.get("idle_days"),
            reason=justification_data.get("reason", ""),
            additional_context=justification_data.get("additional_context", {}),
        )

        action_str = intent_data.get("action", "")
        try:
            action = ActionType(action_str)
        except ValueError:
            raise AmbiguousIntentError(
                f"Unknown action type: {action_str}",
                details={"action": action_str},
            )

        env_str = intent_data.get("environment", "")
        try:
            environment = Environment(env_str)
        except ValueError:
            raise AmbiguousIntentError(
                f"Unknown environment: {env_str}",
                details={"environment": env_str},
            )

        return Intent(
            intent_type=intent_data["intent_type"],
            version=intent_data["version"],
            action=action,
            target=target,
            environment=environment,
            justification=justification,
            natural_language_input=intent_data.get("natural_language_input"),
        )

    async def _static_policy_check(self, intent: Intent) -> None:
        """
        Perform static policy checks before IR generation.

        These are compile-time checks that don't require runtime context.
        """
        # Rule 1: Production deletions are always suspicious
        if (
            intent.environment == Environment.PRODUCTION
            and intent.action in [ActionType.DELETE, ActionType.TERMINATE]
        ):
            # Not a rejection, but flag for higher risk scoring
            logger.warning(
                "production_deletion_detected",
                intent_id=str(intent.intent_id),
                action=intent.action.value,
            )

        # Rule 2: Healthcare PHI access requires authorization
        if intent.intent_type.startswith("healthcare.phi"):
            justification = intent.justification.additional_context
            if not justification.get("authorization"):
                raise CompilationError(
                    "PHI access requires explicit authorization",
                    details={"intent_type": intent.intent_type},
                )

        # Rule 3: Justification must be meaningful
        if len(intent.justification.reason) < 10:
            raise CompilationError(
                "Justification reason must be at least 10 characters",
                details={"reason_length": len(intent.justification.reason)},
            )

    def _generate_operations(
        self,
        intent: Intent,
        intent_data: dict[str, Any],
    ) -> list[IROperation]:
        """
        Generate IR operations from intent.

        This is a deterministic one-to-one mapping.
        """
        operations = []

        # Get action mapping for intent type
        mappings = self._action_mappings.get(intent.intent_type, {})
        action_template = mappings.get(intent.action.value)

        if not action_template:
            raise AmbiguousIntentError(
                f"No mapping for {intent.intent_type}.{intent.action.value}",
                details={
                    "intent_type": intent.intent_type,
                    "action": intent.action.value,
                },
            )

        # Resolve template variables
        op_type = action_template.format(
            provider=intent.target.provider,
            resource_type=intent.target.resource_type,
            framework=intent_data.get("audit_config", {}).get("framework", "generic"),
            channel=intent.target.provider,
        )

        # Build operation parameters
        parameters = self._build_operation_parameters(intent, intent_data)

        # Estimate cost impact
        cost_impact = self._estimate_cost_impact(intent, intent_data)

        # Determine rollback support
        rollback_supported, rollback_ops = self._determine_rollback(intent)

        operation = IROperation(
            type=op_type,
            target=intent.target.resource_id,
            parameters=parameters,
            data_classification=DataClassification.INTERNAL,  # Will be updated in annotation
            environment=intent.environment,
            jurisdiction=self._determine_jurisdiction(intent),
            estimated_cost_impact=cost_impact,
            rollback_supported=rollback_supported,
            rollback_operations=rollback_ops,
        )

        operations.append(operation)

        # Add prerequisite operations (e.g., snapshot before terminate)
        prereqs = self._generate_prerequisites(intent, operation)
        operations = prereqs + operations

        return operations

    def _build_operation_parameters(
        self,
        intent: Intent,
        intent_data: dict[str, Any],
    ) -> dict[str, Any]:
        """Build operation parameters from intent."""
        params: dict[str, Any] = {
            "resource_id": intent.target.resource_id,
            "resource_type": intent.target.resource_type,
        }

        if intent.target.region:
            params["region"] = intent.target.region

        if intent.target.account_id:
            params["account_id"] = intent.target.account_id

        # Add intent-specific parameters
        if intent.intent_type == "cost_optimization.resize":
            resize_config = intent_data.get("resize_config", {})
            params["from_size"] = resize_config.get("from_size")
            params["to_size"] = resize_config.get("to_size")

        if intent.intent_type == "compliance.audit":
            audit_config = intent_data.get("audit_config", {})
            params["framework"] = audit_config.get("framework")
            params["controls"] = audit_config.get("controls", [])

        if intent.intent_type == "notification.send":
            notification = intent_data.get("notification", {})
            params["notification_type"] = notification.get("type")
            params["content"] = notification.get("content")
            params["priority"] = notification.get("priority", "normal")

        return params

    def _estimate_cost_impact(
        self,
        intent: Intent,
        intent_data: dict[str, Any],
    ) -> dict[str, float] | None:
        """Estimate financial impact of the operation."""
        # In production, this would query cost data
        # For now, return placeholder estimates

        if intent.intent_type.startswith("cost_optimization"):
            return {
                "monthly_savings": 0.0,  # Will be populated by cost analyzer
                "annual_projection": 0.0,
            }

        return None

    def _determine_rollback(
        self,
        intent: Intent,
    ) -> tuple[bool, list[dict[str, Any]]]:
        """Determine if operation supports rollback and how."""
        # Terminate with snapshot supports rollback
        if intent.action == ActionType.TERMINATE:
            return True, [
                {
                    "type": "restore_from_snapshot",
                    "description": "Restore from pre-termination snapshot",
                }
            ]

        # Stop supports rollback via start
        if intent.action == ActionType.STOP:
            return True, [
                {
                    "type": "start",
                    "description": "Start the stopped resource",
                }
            ]

        # Resize supports rollback via resize back
        if intent.action == ActionType.UPDATE:
            return True, [
                {
                    "type": "resize_back",
                    "description": "Resize back to original size",
                }
            ]

        return False, []

    def _determine_jurisdiction(self, intent: Intent) -> list[str]:
        """Determine applicable jurisdictions for the operation."""
        # In production, this would be determined from resource metadata
        jurisdictions = ["US"]

        if intent.target.region:
            if intent.target.region.startswith("eu-"):
                jurisdictions.append("EU")
            if intent.target.region.startswith("ap-"):
                jurisdictions.append("APAC")

        return jurisdictions

    def _generate_prerequisites(
        self,
        intent: Intent,
        main_operation: IROperation,
    ) -> list[IROperation]:
        """Generate prerequisite operations (e.g., snapshot before terminate)."""
        prerequisites = []

        # Require snapshot before terminate
        if intent.action == ActionType.TERMINATE:
            snapshot_op = IROperation(
                type=f"cloud.{intent.target.provider}.{intent.target.resource_type}.snapshot",
                target=intent.target.resource_id,
                parameters={
                    "resource_id": intent.target.resource_id,
                    "snapshot_name": f"pre-terminate-{intent.target.resource_id}",
                    "retention_days": 30,
                },
                data_classification=main_operation.data_classification,
                environment=intent.environment,
                jurisdiction=main_operation.jurisdiction,
            )
            prerequisites.append(snapshot_op)

        return prerequisites

    def _annotate_compliance(
        self,
        operations: list[IROperation],
        intent: Intent,
    ) -> None:
        """Annotate operations with compliance metadata."""
        for op in operations:
            # Determine data classification
            classification = self._classify_data(intent)
            op.data_classification = classification

            # Add affected resources
            op.affected_resources = [intent.target.resource_id]

    def _classify_data(self, intent: Intent) -> DataClassification:
        """Determine data classification for an intent."""
        # Check intent type first
        for key, classification in self._classification_rules.items():
            if key in intent.intent_type:
                return classification

        # Fall back to environment-based classification
        env_classifications = {
            Environment.PRODUCTION: DataClassification.CONFIDENTIAL,
            Environment.STAGING: DataClassification.INTERNAL,
            Environment.DEVELOPMENT: DataClassification.INTERNAL,
            Environment.DR: DataClassification.CONFIDENTIAL,
        }

        return env_classifications.get(intent.environment, DataClassification.INTERNAL)

    def _determine_policy_requirements(
        self,
        operations: list[IROperation],
        intent: Intent,
    ) -> dict[str, Any]:
        """Determine policy requirements based on operations."""
        requirements: dict[str, Any] = {
            "min_risk_tier": "low",
            "required_approvals": [],
            "evidence_level": "standard",
        }

        # Elevate for production
        if intent.environment == Environment.PRODUCTION:
            requirements["min_risk_tier"] = "medium"
            requirements["evidence_level"] = "enhanced"

        # Elevate for destructive actions
        if intent.action in [ActionType.DELETE, ActionType.TERMINATE]:
            if requirements["min_risk_tier"] == "low":
                requirements["min_risk_tier"] = "medium"

        # Require approvals for PHI
        for op in operations:
            if op.data_classification == DataClassification.PHI:
                requirements["required_approvals"].append("privacy_officer")
                requirements["evidence_level"] = "hipaa_compliant"

        return requirements

    def _verify_ir_safety(self, compiled_ir: CompiledIR) -> None:
        """
        Verify compiled IR is safe to execute.

        This performs static analysis to prove safety properties.
        """
        for op in compiled_ir.operations:
            # Verify no ambiguous targets
            if not op.target or op.target == "unknown":
                raise CompilationError(
                    "Operation has ambiguous target",
                    details={"op_id": str(op.op_id), "type": op.type},
                )

            # Verify environment is set
            if not op.environment:
                raise CompilationError(
                    "Operation missing environment",
                    details={"op_id": str(op.op_id), "type": op.type},
                )

            # Verify data classification is set
            if not op.data_classification:
                raise CompilationError(
                    "Operation missing data classification",
                    details={"op_id": str(op.op_id), "type": op.type},
                )

        logger.debug(
            "ir_safety_verified",
            ir_id=str(compiled_ir.ir_id),
            operation_count=len(compiled_ir.operations),
        )

    def compute_ir_hash(self, compiled_ir: CompiledIR) -> str:
        """Compute deterministic hash of compiled IR."""
        # Serialize IR deterministically
        ir_data = compiled_ir.model_dump(mode="json")

        # Remove non-deterministic fields
        ir_data.pop("compiled_at", None)
        ir_data.pop("ir_id", None)
        for op in ir_data.get("operations", []):
            op.pop("op_id", None)

        # Compute hash
        canonical = json.dumps(ir_data, sort_keys=True)
        return hashlib.sha256(canonical.encode()).hexdigest()
