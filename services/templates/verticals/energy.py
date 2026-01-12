"""
Energy Vertical Templates

Templates for energy and utilities industry:
1. Grid Operations Agent - NERC CIP compliant grid management
2. Asset Maintenance Agent - Predictive maintenance automation
3. Regulatory Compliance Agent - Energy regulatory compliance
4. Energy Trading Agent - Energy market trading compliance
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


def get_energy_templates() -> list[AgentTemplate]:
    """Get all energy vertical templates."""
    return [
        _create_grid_operations_template(),
        _create_asset_maintenance_template(),
        _create_regulatory_compliance_template(),
        _create_energy_trading_template(),
    ]


def _create_grid_operations_template() -> AgentTemplate:
    """Grid Operations Agent - NERC CIP compliant."""
    return AgentTemplate(
        template_id="energy-grid-ops-v1",
        name="Grid Operations Manager",
        description=(
            "NERC CIP compliant grid operations management. "
            "Monitors grid stability, manages load balancing, handles outage response, "
            "and ensures critical infrastructure protection requirements are met."
        ),
        category=TemplateCategory.OPERATIONS,
        vertical=TemplateVertical.ENERGY,
        version=TemplateVersion(major=1, minor=0, patch=0),
        capabilities=[
            TemplateCapability(
                name="grid_monitoring",
                description="Real-time grid status monitoring",
                action_types=["grid.monitor", "metrics.collect"],
                required_permissions=["scada:read", "ems:read"],
                risk_tier=RiskTier.LOW,
                data_classification=DataClassification.CONFIDENTIAL,
            ),
            TemplateCapability(
                name="load_analysis",
                description="Analyze grid load and capacity",
                action_types=["load.analyze", "capacity.forecast"],
                required_permissions=["load:read"],
                risk_tier=RiskTier.LOW,
            ),
            TemplateCapability(
                name="alert_management",
                description="Manage grid alerts and notifications",
                action_types=["alert.create", "alert.escalate"],
                required_permissions=["alert:write"],
                risk_tier=RiskTier.MEDIUM,
            ),
            TemplateCapability(
                name="outage_response",
                description="Coordinate outage response",
                action_types=["outage.detect", "crew.dispatch", "restoration.track"],
                required_permissions=["outage:write", "dispatch:write"],
                risk_tier=RiskTier.HIGH,
            ),
            TemplateCapability(
                name="load_shedding",
                description="Execute controlled load shedding",
                action_types=["load.shed", "feeder.disconnect"],
                required_permissions=["grid:control"],
                risk_tier=RiskTier.CRITICAL,
                enabled_by_default=False,
            ),
            TemplateCapability(
                name="generation_dispatch",
                description="Coordinate generation dispatch",
                action_types=["generation.dispatch", "unit.commit"],
                required_permissions=["generation:control"],
                risk_tier=RiskTier.HIGH,
                enabled_by_default=False,
            ),
        ],
        parameters=[
            TemplateParameter(
                name="frequency_threshold_hz",
                description="Grid frequency deviation threshold",
                param_type="number",
                default_value=0.5,
                validation_rules={"min": 0.1, "max": 1.0},
            ),
            TemplateParameter(
                name="voltage_tolerance_percent",
                description="Voltage deviation tolerance percentage",
                param_type="number",
                default_value=5,
                validation_rules={"min": 1, "max": 10},
            ),
            TemplateParameter(
                name="load_shed_stages",
                description="Load shedding stages configuration",
                param_type="list",
                default_value=[
                    {"stage": 1, "mw": 100, "feeders": "non_critical"},
                    {"stage": 2, "mw": 250, "feeders": "commercial"},
                    {"stage": 3, "mw": 500, "feeders": "residential"},
                ],
            ),
            TemplateParameter(
                name="nerc_region",
                description="NERC reliability region",
                param_type="string",
                default_value="RFC",
                allowed_values=["RFC", "SERC", "WECC", "TRE", "NPCC", "MRO", "SPP"],
            ),
            TemplateParameter(
                name="critical_assets",
                description="List of critical cyber assets",
                param_type="list",
                default_value=[],
            ),
        ],
        default_policies=[
            TemplatePolicy(
                policy_id="energy-nerc-cip-audit",
                name="NERC CIP Audit Trail",
                description="Complete audit trail for NERC CIP compliance",
                default_enabled=True,
                customizable=False,
                policy_definition={
                    "effect": "require",
                    "action": "log_all_actions",
                    "cip_controls": ["CIP-007", "CIP-008", "CIP-009"],
                    "retention_years": 3,
                },
            ),
            TemplatePolicy(
                policy_id="energy-critical-asset-protection",
                name="Critical Asset Protection",
                description="Protect critical cyber assets",
                default_enabled=True,
                customizable=False,
                policy_definition={
                    "effect": "require",
                    "condition": {"asset_type": "critical_cyber_asset"},
                    "requirements": [
                        "multi_factor_auth",
                        "change_approval",
                        "security_review",
                    ],
                },
            ),
            TemplatePolicy(
                policy_id="energy-grid-control-approval",
                name="Grid Control Approval",
                description="Require approval for grid control actions",
                default_enabled=True,
                customizable=True,
                policy_definition={
                    "effect": "require_approval",
                    "condition": {"action_type": ["load_shed", "generation_dispatch"]},
                    "approvers": ["grid-operator", "reliability-coordinator"],
                },
            ),
        ],
        integrations=[
            TemplateIntegration(
                integration_type="scada",
                required=True,
                configuration_schema={
                    "type": "object",
                    "properties": {
                        "scada_type": {"type": "string"},
                        "connection_protocol": {"type": "string"},
                    },
                },
            ),
            TemplateIntegration(
                integration_type="ems",
                required=True,
            ),
            TemplateIntegration(
                integration_type="oms",
                required=False,
            ),
            TemplateIntegration(
                integration_type="teams",
                required=False,
            ),
        ],
        customization_level=CustomizationLevel.PARTIAL,
        tags=["nerc-cip", "grid", "scada", "energy", "utilities", "critical-infrastructure"],
        author="ArqAI",
    )


def _create_asset_maintenance_template() -> AgentTemplate:
    """Asset Maintenance Agent - Predictive maintenance."""
    return AgentTemplate(
        template_id="energy-asset-maintenance-v1",
        name="Asset Maintenance Optimizer",
        description=(
            "Predictive maintenance for energy infrastructure assets. "
            "Monitors equipment health, predicts failures, schedules maintenance, "
            "and optimizes spare parts inventory while ensuring safety compliance."
        ),
        category=TemplateCategory.OPERATIONS,
        vertical=TemplateVertical.ENERGY,
        version=TemplateVersion(major=1, minor=0, patch=0),
        capabilities=[
            TemplateCapability(
                name="asset_monitoring",
                description="Monitor asset health metrics",
                action_types=["asset.monitor", "sensor.collect"],
                required_permissions=["asset:read", "sensor:read"],
                risk_tier=RiskTier.LOW,
            ),
            TemplateCapability(
                name="failure_prediction",
                description="Predict equipment failures using ML",
                action_types=["ml.predict", "failure.forecast"],
                required_permissions=["ml:execute"],
                risk_tier=RiskTier.LOW,
            ),
            TemplateCapability(
                name="work_order_creation",
                description="Create maintenance work orders",
                action_types=["workorder.create", "maintenance.schedule"],
                required_permissions=["workorder:write"],
                risk_tier=RiskTier.LOW,
            ),
            TemplateCapability(
                name="parts_management",
                description="Manage spare parts inventory",
                action_types=["inventory.check", "parts.order"],
                required_permissions=["inventory:read", "procurement:write"],
                risk_tier=RiskTier.LOW,
            ),
            TemplateCapability(
                name="crew_scheduling",
                description="Schedule maintenance crews",
                action_types=["crew.schedule", "resource.allocate"],
                required_permissions=["schedule:write"],
                risk_tier=RiskTier.LOW,
            ),
            TemplateCapability(
                name="safety_lockout",
                description="Initiate safety lockout procedures",
                action_types=["safety.lockout", "clearance.request"],
                required_permissions=["safety:write"],
                risk_tier=RiskTier.HIGH,
                enabled_by_default=False,
            ),
        ],
        parameters=[
            TemplateParameter(
                name="prediction_horizon_days",
                description="Days ahead for failure prediction",
                param_type="number",
                default_value=30,
                validation_rules={"min": 7, "max": 90},
            ),
            TemplateParameter(
                name="failure_probability_threshold",
                description="Probability threshold for maintenance alert",
                param_type="number",
                default_value=0.7,
                validation_rules={"min": 0.5, "max": 0.95},
            ),
            TemplateParameter(
                name="critical_asset_types",
                description="Asset types considered critical",
                param_type="list",
                default_value=["transformer", "breaker", "generator", "turbine"],
            ),
            TemplateParameter(
                name="maintenance_window_hours",
                description="Preferred maintenance window",
                param_type="object",
                default_value={
                    "start": "02:00",
                    "end": "06:00",
                    "days": ["saturday", "sunday"],
                },
            ),
        ],
        default_policies=[
            TemplatePolicy(
                policy_id="energy-safety-first",
                name="Safety First Policy",
                description="Safety requirements for all maintenance",
                default_enabled=True,
                customizable=False,
                policy_definition={
                    "effect": "require",
                    "condition": {"action_category": "maintenance"},
                    "requirements": [
                        "safety_briefing_completed",
                        "ppe_verified",
                        "lockout_tagout_confirmed",
                    ],
                },
            ),
            TemplatePolicy(
                policy_id="energy-critical-asset-approval",
                name="Critical Asset Approval",
                description="Approval for critical asset maintenance",
                default_enabled=True,
                customizable=True,
                policy_definition={
                    "effect": "require_approval",
                    "condition": {"asset_criticality": "high"},
                    "approvers": ["maintenance-manager", "operations-supervisor"],
                },
            ),
        ],
        integrations=[
            TemplateIntegration(
                integration_type="eam",  # Enterprise Asset Management
                required=True,
            ),
            TemplateIntegration(
                integration_type="scada",
                required=True,
            ),
            TemplateIntegration(
                integration_type="inventory_system",
                required=False,
            ),
            TemplateIntegration(
                integration_type="jira",
                required=False,
            ),
        ],
        customization_level=CustomizationLevel.PARTIAL,
        tags=["maintenance", "predictive", "assets", "energy", "iot"],
        author="ArqAI",
    )


def _create_regulatory_compliance_template() -> AgentTemplate:
    """Energy Regulatory Compliance Agent."""
    return AgentTemplate(
        template_id="energy-regulatory-compliance-v1",
        name="Energy Regulatory Compliance Monitor",
        description=(
            "Monitors compliance with energy regulations including NERC CIP, FERC, "
            "state PUC requirements, and environmental regulations. "
            "Tracks compliance status, manages evidence collection, and generates regulatory reports."
        ),
        category=TemplateCategory.COMPLIANCE,
        vertical=TemplateVertical.ENERGY,
        version=TemplateVersion(major=1, minor=0, patch=0),
        capabilities=[
            TemplateCapability(
                name="compliance_scanning",
                description="Scan systems for compliance status",
                action_types=["scan.compliance", "control.verify"],
                required_permissions=["compliance:read", "system:read"],
                risk_tier=RiskTier.LOW,
            ),
            TemplateCapability(
                name="evidence_collection",
                description="Collect and organize compliance evidence",
                action_types=["evidence.collect", "evidence.organize"],
                required_permissions=["evidence:write"],
                risk_tier=RiskTier.LOW,
            ),
            TemplateCapability(
                name="gap_analysis",
                description="Identify compliance gaps",
                action_types=["gap.analyze", "risk.assess"],
                required_permissions=["compliance:read"],
                risk_tier=RiskTier.LOW,
            ),
            TemplateCapability(
                name="report_generation",
                description="Generate regulatory reports",
                action_types=["report.generate", "report.submit"],
                required_permissions=["report:write"],
                risk_tier=RiskTier.MEDIUM,
            ),
            TemplateCapability(
                name="remediation_tracking",
                description="Track remediation of compliance issues",
                action_types=["remediation.create", "remediation.track"],
                required_permissions=["remediation:write"],
                risk_tier=RiskTier.LOW,
            ),
            TemplateCapability(
                name="audit_support",
                description="Support regulatory audits",
                action_types=["audit.prepare", "evidence.present"],
                required_permissions=["audit:read"],
                risk_tier=RiskTier.LOW,
            ),
        ],
        parameters=[
            TemplateParameter(
                name="regulatory_frameworks",
                description="Applicable regulatory frameworks",
                param_type="list",
                default_value=["NERC_CIP", "FERC", "EPA"],
                allowed_values=["NERC_CIP", "FERC", "EPA", "OSHA", "STATE_PUC", "NRC"],
            ),
            TemplateParameter(
                name="cip_standards",
                description="Applicable NERC CIP standards",
                param_type="list",
                default_value=["CIP-002", "CIP-003", "CIP-004", "CIP-005", "CIP-006", "CIP-007"],
            ),
            TemplateParameter(
                name="scan_schedule",
                description="Compliance scan schedule",
                param_type="string",
                default_value="weekly",
                allowed_values=["daily", "weekly", "monthly"],
            ),
            TemplateParameter(
                name="evidence_retention_years",
                description="Years to retain compliance evidence",
                param_type="number",
                default_value=7,
                validation_rules={"min": 3, "max": 10},
            ),
        ],
        default_policies=[
            TemplatePolicy(
                policy_id="energy-evidence-integrity",
                name="Evidence Integrity",
                description="Ensure compliance evidence integrity",
                default_enabled=True,
                customizable=False,
                policy_definition={
                    "effect": "require",
                    "action": "hash_and_sign_evidence",
                    "verification": "tamper_evident",
                },
            ),
            TemplatePolicy(
                policy_id="energy-finding-escalation",
                name="Finding Escalation",
                description="Escalation for compliance findings",
                default_enabled=True,
                customizable=True,
                policy_definition={
                    "effect": "escalate",
                    "condition": {"finding_severity": {"gte": "high"}},
                    "escalation_path": ["compliance-manager", "ciso", "general-counsel"],
                },
            ),
        ],
        integrations=[
            TemplateIntegration(
                integration_type="grc_system",  # Governance Risk Compliance
                required=True,
            ),
            TemplateIntegration(
                integration_type="document_management",
                required=True,
            ),
            TemplateIntegration(
                integration_type="jira",
                required=False,
            ),
        ],
        customization_level=CustomizationLevel.PARTIAL,
        tags=["nerc-cip", "ferc", "compliance", "regulatory", "energy"],
        author="ArqAI",
    )


def _create_energy_trading_template() -> AgentTemplate:
    """Energy Trading Compliance Agent."""
    return AgentTemplate(
        template_id="energy-trading-v1",
        name="Energy Trading Compliance Agent",
        description=(
            "Monitors energy trading activities for regulatory compliance. "
            "Supports FERC market manipulation rules, position limits, "
            "and reporting requirements for wholesale electricity and natural gas markets."
        ),
        category=TemplateCategory.COMPLIANCE,
        vertical=TemplateVertical.ENERGY,
        version=TemplateVersion(major=1, minor=0, patch=0),
        capabilities=[
            TemplateCapability(
                name="trade_monitoring",
                description="Monitor energy trades in real-time",
                action_types=["trade.monitor", "position.track"],
                required_permissions=["trade:read", "market:read"],
                risk_tier=RiskTier.LOW,
                data_classification=DataClassification.CONFIDENTIAL,
            ),
            TemplateCapability(
                name="manipulation_detection",
                description="Detect potential market manipulation",
                action_types=["pattern.detect", "anomaly.analyze"],
                required_permissions=["trade:read"],
                risk_tier=RiskTier.LOW,
            ),
            TemplateCapability(
                name="position_limit_monitoring",
                description="Monitor position limits",
                action_types=["position.check", "limit.alert"],
                required_permissions=["position:read"],
                risk_tier=RiskTier.MEDIUM,
            ),
            TemplateCapability(
                name="eqr_reporting",
                description="Generate Electric Quarterly Reports",
                action_types=["report.eqr", "report.submit"],
                required_permissions=["report:write"],
                risk_tier=RiskTier.MEDIUM,
            ),
            TemplateCapability(
                name="trade_halt",
                description="Halt trading on compliance violation",
                action_types=["trade.halt", "position.freeze"],
                required_permissions=["trade:control"],
                risk_tier=RiskTier.CRITICAL,
                enabled_by_default=False,
            ),
        ],
        parameters=[
            TemplateParameter(
                name="markets",
                description="Energy markets to monitor",
                param_type="list",
                default_value=["PJM", "ERCOT", "CAISO"],
                allowed_values=["PJM", "ERCOT", "CAISO", "MISO", "NYISO", "ISO-NE", "SPP"],
            ),
            TemplateParameter(
                name="position_limit_mw",
                description="Position limit in MW",
                param_type="number",
                default_value=1000,
            ),
            TemplateParameter(
                name="manipulation_patterns",
                description="Market manipulation patterns to detect",
                param_type="list",
                default_value=["wash_trading", "spoofing", "round_trip", "parking"],
            ),
            TemplateParameter(
                name="reporting_schedule",
                description="Regulatory reporting schedule",
                param_type="object",
                default_value={
                    "eqr": "quarterly",
                    "form_552": "annually",
                },
            ),
        ],
        default_policies=[
            TemplatePolicy(
                policy_id="energy-trade-audit",
                name="Trade Audit Trail",
                description="Complete audit trail for all trades",
                default_enabled=True,
                customizable=False,
                policy_definition={
                    "effect": "require",
                    "action": "log_trade",
                    "retention_years": 5,
                },
            ),
            TemplatePolicy(
                policy_id="energy-manipulation-response",
                name="Manipulation Response",
                description="Response to potential manipulation",
                default_enabled=True,
                customizable=True,
                policy_definition={
                    "effect": "escalate",
                    "condition": {"detection_confidence": {"gte": 0.8}},
                    "actions": ["alert", "preserve_evidence", "notify_compliance"],
                },
            ),
        ],
        integrations=[
            TemplateIntegration(
                integration_type="etrm",  # Energy Trading Risk Management
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
        tags=["ferc", "trading", "energy", "markets", "compliance"],
        author="ArqAI",
    )
