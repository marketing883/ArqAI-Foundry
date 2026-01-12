"""
Finance Vertical Templates

Templates for financial services industry:
1. Cost Optimization Agent - Cloud cost management with SOX compliance
2. Trade Compliance Agent - Trade surveillance and compliance
3. Risk Assessment Agent - Financial risk analysis and reporting
4. Fraud Detection Agent - Transaction fraud monitoring
"""

from arqai_foundry.core.enums import DataClassification, RiskTier
from services.templates.base import (
    AgentTemplate,
    CustomizationLevel,
    TemplateCapability,
    TemplateCategory,
    TemplateIntegration,
    TemplateParameter,
    TemplatePolicy,
    TemplateVersion,
    TemplateVertical,
)


def get_finance_templates() -> list[AgentTemplate]:
    """Get all finance vertical templates."""
    return [
        _create_cost_optimization_template(),
        _create_trade_compliance_template(),
        _create_risk_assessment_template(),
        _create_fraud_detection_template(),
    ]


def _create_cost_optimization_template() -> AgentTemplate:
    """Finance Cost Optimization Agent - SOX compliant."""
    return AgentTemplate(
        template_id="fin-cost-optimization-v1",
        name="Financial Services Cost Optimizer",
        description=(
            "Automated cloud cost optimization for financial institutions. "
            "Includes SOX compliance controls, audit trails, and multi-level approvals. "
            "Identifies idle resources, rightsizing opportunities, and reserved instance savings."
        ),
        category=TemplateCategory.COST_OPTIMIZATION,
        vertical=TemplateVertical.FINANCE,
        version=TemplateVersion(major=1, minor=0, patch=0),
        capabilities=[
            TemplateCapability(
                name="resource_discovery",
                description="Discover and inventory cloud resources",
                action_types=["aws.ec2.describe", "aws.rds.describe", "aws.s3.list"],
                required_permissions=["ec2:Describe*", "rds:Describe*", "s3:List*"],
                risk_tier=RiskTier.LOW,
                data_classification=DataClassification.INTERNAL,
            ),
            TemplateCapability(
                name="cost_analysis",
                description="Analyze costs and identify optimization opportunities",
                action_types=["aws.ce.query", "cost_analysis.generate"],
                required_permissions=["ce:GetCostAndUsage"],
                risk_tier=RiskTier.LOW,
                data_classification=DataClassification.INTERNAL,
            ),
            TemplateCapability(
                name="idle_resource_detection",
                description="Detect idle and underutilized resources",
                action_types=["analysis.idle_detection"],
                required_permissions=["cloudwatch:GetMetricData"],
                risk_tier=RiskTier.LOW,
            ),
            TemplateCapability(
                name="stop_resources",
                description="Stop non-production resources",
                action_types=["aws.ec2.stop", "aws.rds.stop"],
                required_permissions=["ec2:StopInstances", "rds:StopDBInstance"],
                risk_tier=RiskTier.MEDIUM,
                enabled_by_default=True,
            ),
            TemplateCapability(
                name="terminate_resources",
                description="Terminate resources (requires approval)",
                action_types=["aws.ec2.terminate"],
                required_permissions=["ec2:TerminateInstances"],
                risk_tier=RiskTier.HIGH,
                enabled_by_default=False,  # Must be explicitly enabled
            ),
            TemplateCapability(
                name="create_tickets",
                description="Create Jira tickets for recommendations",
                action_types=["jira.create_issue", "jira.update_status"],
                required_permissions=["jira:write"],
                risk_tier=RiskTier.LOW,
            ),
        ],
        parameters=[
            TemplateParameter(
                name="idle_threshold_days",
                description="Days of inactivity before resource is considered idle",
                param_type="number",
                default_value=14,
                validation_rules={"min": 1, "max": 90},
            ),
            TemplateParameter(
                name="cpu_threshold_percent",
                description="CPU utilization threshold for underutilization",
                param_type="number",
                default_value=10,
                validation_rules={"min": 1, "max": 50},
            ),
            TemplateParameter(
                name="excluded_tags",
                description="Resource tags to exclude from optimization",
                param_type="list",
                default_value=["DoNotOptimize", "Production-Critical"],
            ),
            TemplateParameter(
                name="approval_threshold_usd",
                description="Cost threshold requiring executive approval",
                param_type="number",
                default_value=10000,
            ),
            TemplateParameter(
                name="sox_control_ids",
                description="SOX control IDs for audit mapping",
                param_type="list",
                default_value=["SOX-IT-001", "SOX-IT-002"],
            ),
        ],
        default_policies=[
            TemplatePolicy(
                policy_id="fin-sox-audit-trail",
                name="SOX Audit Trail",
                description="Ensure all actions are logged for SOX compliance",
                default_enabled=True,
                customizable=False,
                policy_definition={
                    "effect": "require",
                    "condition": "always",
                    "action": "log_to_audit_trail",
                    "retention_days": 2555,  # 7 years
                },
            ),
            TemplatePolicy(
                policy_id="fin-prod-protection",
                name="Production Protection",
                description="Prevent changes to production resources",
                default_enabled=True,
                customizable=True,
                policy_definition={
                    "effect": "deny",
                    "condition": {
                        "resource_tag": {"Environment": "Production"},
                    },
                    "actions": ["terminate", "stop"],
                },
            ),
            TemplatePolicy(
                policy_id="fin-approval-required",
                name="Multi-Level Approval",
                description="Require approval for high-value changes",
                default_enabled=True,
                customizable=True,
                policy_definition={
                    "effect": "require_approval",
                    "condition": {
                        "estimated_impact_usd": {"gt": 5000},
                    },
                    "approvers": ["finance-manager", "it-director"],
                },
            ),
        ],
        integrations=[
            TemplateIntegration(
                integration_type="aws",
                required=True,
                configuration_schema={
                    "type": "object",
                    "properties": {
                        "role_arn": {"type": "string"},
                        "regions": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["role_arn"],
                },
            ),
            TemplateIntegration(
                integration_type="jira",
                required=False,
                configuration_schema={
                    "type": "object",
                    "properties": {
                        "project_key": {"type": "string"},
                        "issue_type": {"type": "string", "default": "Task"},
                    },
                },
            ),
            TemplateIntegration(
                integration_type="slack",
                required=False,
            ),
        ],
        customization_level=CustomizationLevel.PARTIAL,
        tags=["cost-optimization", "sox", "cloud", "aws", "finance"],
        author="ArqAI",
    )


def _create_trade_compliance_template() -> AgentTemplate:
    """Trade Compliance Agent - MiFID II, Dodd-Frank compliant."""
    return AgentTemplate(
        template_id="fin-trade-compliance-v1",
        name="Trade Compliance Monitor",
        description=(
            "Monitors trading activities for regulatory compliance. "
            "Supports MiFID II, Dodd-Frank, and MAR requirements. "
            "Detects suspicious patterns, monitors position limits, and generates regulatory reports."
        ),
        category=TemplateCategory.COMPLIANCE,
        vertical=TemplateVertical.FINANCE,
        version=TemplateVersion(major=1, minor=0, patch=0),
        capabilities=[
            TemplateCapability(
                name="trade_surveillance",
                description="Monitor trades for suspicious patterns",
                action_types=["trade.monitor", "pattern.detect"],
                required_permissions=["trade:read", "market:read"],
                risk_tier=RiskTier.LOW,
                data_classification=DataClassification.CONFIDENTIAL,
            ),
            TemplateCapability(
                name="position_monitoring",
                description="Monitor position limits and concentration",
                action_types=["position.check", "limit.validate"],
                required_permissions=["position:read"],
                risk_tier=RiskTier.LOW,
            ),
            TemplateCapability(
                name="alert_generation",
                description="Generate compliance alerts",
                action_types=["alert.create", "notification.send"],
                required_permissions=["alert:write"],
                risk_tier=RiskTier.MEDIUM,
            ),
            TemplateCapability(
                name="report_generation",
                description="Generate regulatory reports",
                action_types=["report.generate", "report.submit"],
                required_permissions=["report:write"],
                risk_tier=RiskTier.MEDIUM,
                data_classification=DataClassification.CONFIDENTIAL,
            ),
            TemplateCapability(
                name="trade_halt",
                description="Halt trading for compliance violations",
                action_types=["trade.halt", "account.restrict"],
                required_permissions=["trade:write", "account:restrict"],
                risk_tier=RiskTier.CRITICAL,
                enabled_by_default=False,
            ),
        ],
        parameters=[
            TemplateParameter(
                name="surveillance_patterns",
                description="Patterns to monitor (wash_trading, spoofing, layering)",
                param_type="list",
                default_value=["wash_trading", "spoofing", "layering", "front_running"],
            ),
            TemplateParameter(
                name="position_limit_percent",
                description="Position limit as percentage of market cap",
                param_type="number",
                default_value=5,
                validation_rules={"min": 0.1, "max": 25},
            ),
            TemplateParameter(
                name="alert_threshold",
                description="Sensitivity threshold for alerts (1-10)",
                param_type="number",
                default_value=7,
                validation_rules={"min": 1, "max": 10},
            ),
            TemplateParameter(
                name="regulatory_frameworks",
                description="Applicable regulatory frameworks",
                param_type="list",
                default_value=["MiFID_II", "Dodd_Frank", "MAR"],
                allowed_values=["MiFID_II", "Dodd_Frank", "MAR", "SEC_Rule_15c3_5", "EMIR"],
            ),
        ],
        default_policies=[
            TemplatePolicy(
                policy_id="fin-trade-audit",
                name="Trade Audit Trail",
                description="Complete audit trail for all trade surveillance",
                default_enabled=True,
                customizable=False,
                policy_definition={
                    "effect": "require",
                    "action": "log_trade_surveillance",
                    "retention_days": 2555,
                },
            ),
            TemplatePolicy(
                policy_id="fin-alert-escalation",
                name="Alert Escalation",
                description="Escalation rules for compliance alerts",
                default_enabled=True,
                customizable=True,
                policy_definition={
                    "effect": "escalate",
                    "condition": {"severity": {"gte": "high"}},
                    "escalation_path": ["compliance-officer", "chief-compliance-officer"],
                },
            ),
        ],
        integrations=[
            TemplateIntegration(
                integration_type="trading_system",
                required=True,
            ),
            TemplateIntegration(
                integration_type="market_data",
                required=True,
            ),
            TemplateIntegration(
                integration_type="slack",
                required=False,
            ),
        ],
        customization_level=CustomizationLevel.PARTIAL,
        tags=["compliance", "trading", "mifid", "dodd-frank", "surveillance"],
        author="ArqAI",
    )


def _create_risk_assessment_template() -> AgentTemplate:
    """Risk Assessment Agent - Basel III/IV compliant."""
    return AgentTemplate(
        template_id="fin-risk-assessment-v1",
        name="Financial Risk Assessor",
        description=(
            "Automated financial risk assessment and reporting. "
            "Supports Basel III/IV capital requirements, stress testing, and VaR calculations. "
            "Generates risk reports and monitors risk limits."
        ),
        category=TemplateCategory.ANALYTICS,
        vertical=TemplateVertical.FINANCE,
        version=TemplateVersion(major=1, minor=0, patch=0),
        capabilities=[
            TemplateCapability(
                name="var_calculation",
                description="Calculate Value at Risk metrics",
                action_types=["risk.var_calculate", "risk.historical_simulation"],
                required_permissions=["risk:read", "portfolio:read"],
                risk_tier=RiskTier.LOW,
                data_classification=DataClassification.CONFIDENTIAL,
            ),
            TemplateCapability(
                name="stress_testing",
                description="Run stress test scenarios",
                action_types=["risk.stress_test", "scenario.run"],
                required_permissions=["risk:execute"],
                risk_tier=RiskTier.LOW,
            ),
            TemplateCapability(
                name="capital_calculation",
                description="Calculate regulatory capital requirements",
                action_types=["capital.calculate", "rwa.calculate"],
                required_permissions=["capital:read"],
                risk_tier=RiskTier.LOW,
            ),
            TemplateCapability(
                name="limit_monitoring",
                description="Monitor risk limits and breaches",
                action_types=["limit.monitor", "breach.alert"],
                required_permissions=["limit:read", "alert:write"],
                risk_tier=RiskTier.MEDIUM,
            ),
            TemplateCapability(
                name="report_generation",
                description="Generate regulatory risk reports",
                action_types=["report.generate"],
                required_permissions=["report:write"],
                risk_tier=RiskTier.LOW,
            ),
        ],
        parameters=[
            TemplateParameter(
                name="var_confidence_level",
                description="Confidence level for VaR calculation",
                param_type="number",
                default_value=0.99,
                allowed_values=[0.95, 0.99, 0.995],
            ),
            TemplateParameter(
                name="var_horizon_days",
                description="Time horizon for VaR in days",
                param_type="number",
                default_value=10,
                allowed_values=[1, 10, 20],
            ),
            TemplateParameter(
                name="stress_scenarios",
                description="Stress test scenarios to run",
                param_type="list",
                default_value=["2008_financial_crisis", "covid_march_2020", "custom_scenario_1"],
            ),
            TemplateParameter(
                name="reporting_frequency",
                description="Frequency of risk reports",
                param_type="string",
                default_value="daily",
                allowed_values=["realtime", "daily", "weekly", "monthly"],
            ),
        ],
        default_policies=[
            TemplatePolicy(
                policy_id="fin-risk-data-protection",
                name="Risk Data Protection",
                description="Protect sensitive risk data",
                default_enabled=True,
                customizable=False,
                policy_definition={
                    "effect": "require",
                    "condition": {"data_classification": "confidential"},
                    "action": "encrypt_at_rest",
                },
            ),
        ],
        integrations=[
            TemplateIntegration(
                integration_type="risk_system",
                required=True,
            ),
            TemplateIntegration(
                integration_type="portfolio_system",
                required=True,
            ),
        ],
        customization_level=CustomizationLevel.PARTIAL,
        tags=["risk", "basel", "var", "stress-testing", "capital"],
        author="ArqAI",
    )


def _create_fraud_detection_template() -> AgentTemplate:
    """Fraud Detection Agent - Real-time transaction monitoring."""
    return AgentTemplate(
        template_id="fin-fraud-detection-v1",
        name="Transaction Fraud Detector",
        description=(
            "Real-time fraud detection for financial transactions. "
            "Uses ML-based anomaly detection, rule-based screening, and velocity checks. "
            "Integrates with case management for investigation workflow."
        ),
        category=TemplateCategory.SECURITY,
        vertical=TemplateVertical.FINANCE,
        version=TemplateVersion(major=1, minor=0, patch=0),
        capabilities=[
            TemplateCapability(
                name="transaction_screening",
                description="Screen transactions against rules",
                action_types=["txn.screen", "rule.evaluate"],
                required_permissions=["transaction:read"],
                risk_tier=RiskTier.LOW,
                data_classification=DataClassification.PII,
            ),
            TemplateCapability(
                name="anomaly_detection",
                description="ML-based anomaly detection",
                action_types=["ml.score", "anomaly.detect"],
                required_permissions=["ml:execute"],
                risk_tier=RiskTier.LOW,
            ),
            TemplateCapability(
                name="velocity_check",
                description="Check transaction velocity patterns",
                action_types=["velocity.check"],
                required_permissions=["transaction:read"],
                risk_tier=RiskTier.LOW,
            ),
            TemplateCapability(
                name="alert_generation",
                description="Generate fraud alerts",
                action_types=["alert.create"],
                required_permissions=["alert:write"],
                risk_tier=RiskTier.LOW,
            ),
            TemplateCapability(
                name="transaction_block",
                description="Block suspicious transactions",
                action_types=["txn.block", "account.freeze"],
                required_permissions=["transaction:write", "account:restrict"],
                risk_tier=RiskTier.HIGH,
                enabled_by_default=False,
            ),
            TemplateCapability(
                name="case_management",
                description="Create and manage investigation cases",
                action_types=["case.create", "case.update"],
                required_permissions=["case:write"],
                risk_tier=RiskTier.LOW,
            ),
        ],
        parameters=[
            TemplateParameter(
                name="ml_threshold",
                description="ML model score threshold for alerts",
                param_type="number",
                default_value=0.85,
                validation_rules={"min": 0.5, "max": 0.99},
            ),
            TemplateParameter(
                name="velocity_window_minutes",
                description="Time window for velocity checks",
                param_type="number",
                default_value=60,
            ),
            TemplateParameter(
                name="max_transactions_per_window",
                description="Max transactions in velocity window",
                param_type="number",
                default_value=10,
            ),
            TemplateParameter(
                name="high_risk_countries",
                description="Countries flagged as high risk",
                param_type="list",
                default_value=[],
            ),
            TemplateParameter(
                name="auto_block_threshold",
                description="Score threshold for automatic blocking",
                param_type="number",
                default_value=0.95,
            ),
        ],
        default_policies=[
            TemplatePolicy(
                policy_id="fin-fraud-pii-protection",
                name="PII Protection",
                description="Protect PII in fraud investigations",
                default_enabled=True,
                customizable=False,
                policy_definition={
                    "effect": "require",
                    "action": "mask_pii",
                    "fields": ["ssn", "account_number", "card_number"],
                },
            ),
            TemplatePolicy(
                policy_id="fin-fraud-escalation",
                name="Fraud Escalation",
                description="Escalation rules for high-value fraud",
                default_enabled=True,
                customizable=True,
                policy_definition={
                    "effect": "escalate",
                    "condition": {"amount_usd": {"gt": 50000}},
                    "escalation_path": ["fraud-analyst", "fraud-manager"],
                },
            ),
        ],
        integrations=[
            TemplateIntegration(
                integration_type="transaction_system",
                required=True,
            ),
            TemplateIntegration(
                integration_type="case_management",
                required=False,
            ),
            TemplateIntegration(
                integration_type="slack",
                required=False,
            ),
        ],
        customization_level=CustomizationLevel.PARTIAL,
        tags=["fraud", "aml", "kyc", "transactions", "security"],
        author="ArqAI",
    )
