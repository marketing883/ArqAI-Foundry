"""
Healthcare Vertical Templates

Templates for healthcare industry:
1. PHI Access Controller - HIPAA-compliant PHI access management
2. Clinical Workflow Agent - Clinical process automation
3. Compliance Auditor - Healthcare compliance monitoring
4. Resource Optimizer - Healthcare infrastructure optimization
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


def get_healthcare_templates() -> list[AgentTemplate]:
    """Get all healthcare vertical templates."""
    return [
        _create_phi_access_template(),
        _create_clinical_workflow_template(),
        _create_compliance_auditor_template(),
        _create_resource_optimizer_template(),
    ]


def _create_phi_access_template() -> AgentTemplate:
    """PHI Access Controller - HIPAA compliant."""
    return AgentTemplate(
        template_id="hc-phi-access-v1",
        name="PHI Access Controller",
        description=(
            "HIPAA-compliant Protected Health Information (PHI) access management. "
            "Controls access to patient data, logs all access events, enforces minimum necessary, "
            "and supports break-glass emergency access with full audit trails."
        ),
        category=TemplateCategory.COMPLIANCE,
        vertical=TemplateVertical.HEALTHCARE,
        version=TemplateVersion(major=1, minor=0, patch=0),
        capabilities=[
            TemplateCapability(
                name="access_request_processing",
                description="Process PHI access requests",
                action_types=["phi.request", "phi.authorize"],
                required_permissions=["phi:read_request"],
                risk_tier=RiskTier.LOW,
                data_classification=DataClassification.PHI,
            ),
            TemplateCapability(
                name="minimum_necessary_enforcement",
                description="Enforce minimum necessary principle",
                action_types=["phi.filter", "phi.mask"],
                required_permissions=["phi:filter"],
                risk_tier=RiskTier.LOW,
                data_classification=DataClassification.PHI,
            ),
            TemplateCapability(
                name="access_logging",
                description="Log all PHI access events",
                action_types=["audit.log", "hipaa.log"],
                required_permissions=["audit:write"],
                risk_tier=RiskTier.LOW,
            ),
            TemplateCapability(
                name="break_glass_access",
                description="Emergency break-glass PHI access",
                action_types=["phi.break_glass", "emergency.authorize"],
                required_permissions=["phi:emergency_access"],
                risk_tier=RiskTier.CRITICAL,
                enabled_by_default=True,
            ),
            TemplateCapability(
                name="access_revocation",
                description="Revoke PHI access permissions",
                action_types=["phi.revoke", "access.terminate"],
                required_permissions=["phi:revoke"],
                risk_tier=RiskTier.MEDIUM,
            ),
            TemplateCapability(
                name="consent_management",
                description="Manage patient consent for data sharing",
                action_types=["consent.check", "consent.update"],
                required_permissions=["consent:read", "consent:write"],
                risk_tier=RiskTier.LOW,
                data_classification=DataClassification.PHI,
            ),
        ],
        parameters=[
            TemplateParameter(
                name="minimum_necessary_rules",
                description="Rules for minimum necessary data exposure",
                param_type="object",
                default_value={
                    "billing": ["name", "dob", "insurance_id", "diagnosis_codes"],
                    "clinical": ["name", "dob", "medical_history", "medications"],
                    "research": ["anonymized_id", "age_range", "diagnosis_codes"],
                },
            ),
            TemplateParameter(
                name="break_glass_notification_list",
                description="Users to notify on break-glass access",
                param_type="list",
                default_value=["privacy-officer", "compliance-team"],
            ),
            TemplateParameter(
                name="access_log_retention_years",
                description="Years to retain access logs (HIPAA minimum 6)",
                param_type="number",
                default_value=6,
                validation_rules={"min": 6, "max": 25},
            ),
            TemplateParameter(
                name="auto_expire_hours",
                description="Hours before access automatically expires",
                param_type="number",
                default_value=8,
                validation_rules={"min": 1, "max": 72},
            ),
        ],
        default_policies=[
            TemplatePolicy(
                policy_id="hc-hipaa-audit-trail",
                name="HIPAA Audit Trail",
                description="Complete audit trail for HIPAA compliance",
                default_enabled=True,
                customizable=False,
                policy_definition={
                    "effect": "require",
                    "condition": {"data_type": "PHI"},
                    "action": "log_access",
                    "log_fields": [
                        "user_id", "patient_id", "access_type", "data_accessed",
                        "timestamp", "purpose", "ip_address"
                    ],
                    "retention_years": 6,
                },
            ),
            TemplatePolicy(
                policy_id="hc-break-glass-protocol",
                name="Break Glass Protocol",
                description="Emergency access protocol with accountability",
                default_enabled=True,
                customizable=False,
                policy_definition={
                    "effect": "allow_with_audit",
                    "condition": {"access_type": "break_glass"},
                    "requirements": [
                        "justification_required",
                        "immediate_notification",
                        "post_access_review",
                    ],
                },
            ),
            TemplatePolicy(
                policy_id="hc-minimum-necessary",
                name="Minimum Necessary",
                description="Enforce minimum necessary principle",
                default_enabled=True,
                customizable=True,
                policy_definition={
                    "effect": "filter",
                    "action": "apply_data_filter",
                    "filter_by": "role_and_purpose",
                },
            ),
        ],
        integrations=[
            TemplateIntegration(
                integration_type="ehr_system",
                required=True,
                configuration_schema={
                    "type": "object",
                    "properties": {
                        "ehr_type": {
                            "type": "string",
                            "enum": ["epic", "cerner", "allscripts", "meditech", "custom"],
                        },
                        "api_endpoint": {"type": "string"},
                    },
                },
            ),
            TemplateIntegration(
                integration_type="identity_provider",
                required=True,
            ),
            TemplateIntegration(
                integration_type="slack",
                required=False,
            ),
        ],
        customization_level=CustomizationLevel.PARTIAL,
        tags=["hipaa", "phi", "access-control", "healthcare", "compliance"],
        author="ArqAI",
    )


def _create_clinical_workflow_template() -> AgentTemplate:
    """Clinical Workflow Agent - Process automation."""
    return AgentTemplate(
        template_id="hc-clinical-workflow-v1",
        name="Clinical Workflow Automator",
        description=(
            "Automates clinical workflows with full HIPAA compliance. "
            "Handles patient intake, appointment scheduling, lab result routing, "
            "and clinical alerts while maintaining complete audit trails."
        ),
        category=TemplateCategory.WORKFLOW,
        vertical=TemplateVertical.HEALTHCARE,
        version=TemplateVersion(major=1, minor=0, patch=0),
        capabilities=[
            TemplateCapability(
                name="patient_intake",
                description="Automated patient intake processing",
                action_types=["intake.process", "demographics.verify"],
                required_permissions=["patient:read", "patient:write"],
                risk_tier=RiskTier.LOW,
                data_classification=DataClassification.PHI,
            ),
            TemplateCapability(
                name="appointment_management",
                description="Schedule and manage appointments",
                action_types=["appointment.schedule", "appointment.modify", "appointment.cancel"],
                required_permissions=["schedule:read", "schedule:write"],
                risk_tier=RiskTier.LOW,
            ),
            TemplateCapability(
                name="lab_result_routing",
                description="Route lab results to appropriate providers",
                action_types=["lab.route", "lab.notify"],
                required_permissions=["lab:read", "notification:send"],
                risk_tier=RiskTier.MEDIUM,
                data_classification=DataClassification.PHI,
            ),
            TemplateCapability(
                name="clinical_alerts",
                description="Generate clinical alerts and reminders",
                action_types=["alert.create", "reminder.schedule"],
                required_permissions=["alert:write"],
                risk_tier=RiskTier.MEDIUM,
            ),
            TemplateCapability(
                name="referral_processing",
                description="Process and track referrals",
                action_types=["referral.create", "referral.track"],
                required_permissions=["referral:write"],
                risk_tier=RiskTier.LOW,
            ),
            TemplateCapability(
                name="prescription_management",
                description="Manage prescription workflows",
                action_types=["rx.request", "rx.renew", "rx.route"],
                required_permissions=["rx:read", "rx:write"],
                risk_tier=RiskTier.HIGH,
                data_classification=DataClassification.PHI,
                enabled_by_default=False,
            ),
        ],
        parameters=[
            TemplateParameter(
                name="appointment_buffer_minutes",
                description="Buffer time between appointments",
                param_type="number",
                default_value=15,
                validation_rules={"min": 0, "max": 60},
            ),
            TemplateParameter(
                name="lab_critical_values",
                description="Lab values requiring immediate notification",
                param_type="object",
                default_value={
                    "potassium": {"low": 2.5, "high": 6.5},
                    "glucose": {"low": 50, "high": 500},
                    "hemoglobin": {"low": 7.0, "high": 20.0},
                },
            ),
            TemplateParameter(
                name="alert_escalation_minutes",
                description="Minutes before unacknowledged alerts escalate",
                param_type="number",
                default_value=30,
            ),
            TemplateParameter(
                name="working_hours",
                description="Clinic working hours",
                param_type="object",
                default_value={
                    "start": "08:00",
                    "end": "17:00",
                    "timezone": "America/New_York",
                },
            ),
        ],
        default_policies=[
            TemplatePolicy(
                policy_id="hc-workflow-audit",
                name="Workflow Audit",
                description="Audit all workflow actions",
                default_enabled=True,
                customizable=False,
                policy_definition={
                    "effect": "require",
                    "action": "log_workflow_action",
                    "retention_years": 6,
                },
            ),
            TemplatePolicy(
                policy_id="hc-critical-alert-policy",
                name="Critical Alert Policy",
                description="Handle critical alerts with urgency",
                default_enabled=True,
                customizable=True,
                policy_definition={
                    "effect": "escalate",
                    "condition": {"alert_type": "critical"},
                    "escalation": {
                        "immediate": ["attending_physician"],
                        "5_minutes": ["department_head"],
                        "15_minutes": ["medical_director"],
                    },
                },
            ),
        ],
        integrations=[
            TemplateIntegration(
                integration_type="ehr_system",
                required=True,
            ),
            TemplateIntegration(
                integration_type="scheduling_system",
                required=True,
            ),
            TemplateIntegration(
                integration_type="lab_system",
                required=False,
            ),
            TemplateIntegration(
                integration_type="teams",
                required=False,
            ),
        ],
        customization_level=CustomizationLevel.PARTIAL,
        tags=["clinical", "workflow", "automation", "healthcare", "ehr"],
        author="ArqAI",
    )


def _create_compliance_auditor_template() -> AgentTemplate:
    """Healthcare Compliance Auditor - HIPAA, HITECH."""
    return AgentTemplate(
        template_id="hc-compliance-auditor-v1",
        name="Healthcare Compliance Auditor",
        description=(
            "Continuous compliance monitoring for HIPAA, HITECH, and state regulations. "
            "Scans for policy violations, monitors access patterns, generates compliance reports, "
            "and provides remediation recommendations."
        ),
        category=TemplateCategory.COMPLIANCE,
        vertical=TemplateVertical.HEALTHCARE,
        version=TemplateVersion(major=1, minor=0, patch=0),
        capabilities=[
            TemplateCapability(
                name="policy_scanning",
                description="Scan for policy compliance",
                action_types=["scan.policy", "violation.detect"],
                required_permissions=["policy:read", "config:read"],
                risk_tier=RiskTier.LOW,
            ),
            TemplateCapability(
                name="access_pattern_analysis",
                description="Analyze PHI access patterns for anomalies",
                action_types=["analysis.access_pattern", "anomaly.detect"],
                required_permissions=["audit:read"],
                risk_tier=RiskTier.LOW,
                data_classification=DataClassification.INTERNAL,
            ),
            TemplateCapability(
                name="risk_assessment",
                description="Perform security risk assessments",
                action_types=["risk.assess", "vulnerability.scan"],
                required_permissions=["security:read"],
                risk_tier=RiskTier.LOW,
            ),
            TemplateCapability(
                name="report_generation",
                description="Generate compliance reports",
                action_types=["report.generate", "report.schedule"],
                required_permissions=["report:write"],
                risk_tier=RiskTier.LOW,
            ),
            TemplateCapability(
                name="remediation_tracking",
                description="Track remediation of compliance issues",
                action_types=["remediation.create", "remediation.track"],
                required_permissions=["remediation:write"],
                risk_tier=RiskTier.LOW,
            ),
            TemplateCapability(
                name="alert_on_violation",
                description="Alert on compliance violations",
                action_types=["alert.compliance", "notification.urgent"],
                required_permissions=["alert:write"],
                risk_tier=RiskTier.MEDIUM,
            ),
        ],
        parameters=[
            TemplateParameter(
                name="scan_frequency",
                description="How often to run compliance scans",
                param_type="string",
                default_value="daily",
                allowed_values=["hourly", "daily", "weekly"],
            ),
            TemplateParameter(
                name="compliance_frameworks",
                description="Applicable compliance frameworks",
                param_type="list",
                default_value=["HIPAA", "HITECH"],
                allowed_values=["HIPAA", "HITECH", "STATE_PRIVACY", "GDPR", "CCPA"],
            ),
            TemplateParameter(
                name="anomaly_sensitivity",
                description="Sensitivity for access pattern anomalies (1-10)",
                param_type="number",
                default_value=7,
                validation_rules={"min": 1, "max": 10},
            ),
            TemplateParameter(
                name="report_recipients",
                description="Recipients for compliance reports",
                param_type="list",
                default_value=["privacy-officer", "ciso", "compliance-committee"],
            ),
        ],
        default_policies=[
            TemplatePolicy(
                policy_id="hc-violation-response",
                name="Violation Response",
                description="Response policy for compliance violations",
                default_enabled=True,
                customizable=True,
                policy_definition={
                    "effect": "require",
                    "on_violation": {
                        "low": {"action": "log", "notify": ["compliance-team"]},
                        "medium": {"action": "alert", "notify": ["privacy-officer"]},
                        "high": {"action": "escalate", "notify": ["ciso", "legal"]},
                        "critical": {"action": "immediate_response", "notify": ["executive-team"]},
                    },
                },
            ),
        ],
        integrations=[
            TemplateIntegration(
                integration_type="audit_log_system",
                required=True,
            ),
            TemplateIntegration(
                integration_type="ehr_system",
                required=True,
            ),
            TemplateIntegration(
                integration_type="jira",
                required=False,
            ),
            TemplateIntegration(
                integration_type="slack",
                required=False,
            ),
        ],
        customization_level=CustomizationLevel.PARTIAL,
        tags=["hipaa", "hitech", "compliance", "audit", "healthcare"],
        author="ArqAI",
    )


def _create_resource_optimizer_template() -> AgentTemplate:
    """Healthcare Resource Optimizer - HIPAA-aware cost optimization."""
    return AgentTemplate(
        template_id="hc-resource-optimizer-v1",
        name="Healthcare Resource Optimizer",
        description=(
            "Cloud and infrastructure optimization for healthcare organizations. "
            "HIPAA-aware resource management, ensures data residency compliance, "
            "and maintains required redundancy for critical systems."
        ),
        category=TemplateCategory.COST_OPTIMIZATION,
        vertical=TemplateVertical.HEALTHCARE,
        version=TemplateVersion(major=1, minor=0, patch=0),
        capabilities=[
            TemplateCapability(
                name="resource_discovery",
                description="Discover healthcare infrastructure resources",
                action_types=["resource.discover", "resource.classify"],
                required_permissions=["infrastructure:read"],
                risk_tier=RiskTier.LOW,
            ),
            TemplateCapability(
                name="phi_data_classification",
                description="Classify resources containing PHI",
                action_types=["data.classify", "phi.detect"],
                required_permissions=["data:read"],
                risk_tier=RiskTier.LOW,
                data_classification=DataClassification.PHI,
            ),
            TemplateCapability(
                name="cost_analysis",
                description="Analyze infrastructure costs",
                action_types=["cost.analyze", "savings.identify"],
                required_permissions=["billing:read"],
                risk_tier=RiskTier.LOW,
            ),
            TemplateCapability(
                name="rightsizing",
                description="Rightsize non-PHI resources",
                action_types=["resource.resize"],
                required_permissions=["resource:modify"],
                risk_tier=RiskTier.MEDIUM,
            ),
            TemplateCapability(
                name="stop_non_critical",
                description="Stop non-critical non-PHI resources",
                action_types=["resource.stop"],
                required_permissions=["resource:stop"],
                risk_tier=RiskTier.MEDIUM,
            ),
            TemplateCapability(
                name="backup_verification",
                description="Verify backup compliance for PHI systems",
                action_types=["backup.verify", "dr.test"],
                required_permissions=["backup:read"],
                risk_tier=RiskTier.LOW,
            ),
        ],
        parameters=[
            TemplateParameter(
                name="phi_resource_tags",
                description="Tags identifying PHI-containing resources",
                param_type="list",
                default_value=["PHI", "HIPAA", "ePHI", "PatientData"],
            ),
            TemplateParameter(
                name="required_redundancy",
                description="Required redundancy for PHI systems",
                param_type="string",
                default_value="multi-az",
                allowed_values=["single-az", "multi-az", "multi-region"],
            ),
            TemplateParameter(
                name="allowed_regions",
                description="Allowed regions for PHI data (data residency)",
                param_type="list",
                default_value=["us-east-1", "us-west-2"],
            ),
            TemplateParameter(
                name="backup_retention_days",
                description="Minimum backup retention days",
                param_type="number",
                default_value=90,
                validation_rules={"min": 30, "max": 365},
            ),
        ],
        default_policies=[
            TemplatePolicy(
                policy_id="hc-phi-protection",
                name="PHI Resource Protection",
                description="Protect PHI-containing resources from optimization",
                default_enabled=True,
                customizable=False,
                policy_definition={
                    "effect": "deny",
                    "condition": {"contains_phi": True},
                    "actions": ["terminate", "stop", "resize_down"],
                    "exceptions": ["approved_maintenance_window"],
                },
            ),
            TemplatePolicy(
                policy_id="hc-data-residency",
                name="Data Residency",
                description="Enforce data residency requirements",
                default_enabled=True,
                customizable=True,
                policy_definition={
                    "effect": "deny",
                    "condition": {
                        "contains_phi": True,
                        "region": {"not_in": ["us-east-1", "us-west-2"]},
                    },
                    "action": "prevent_and_alert",
                },
            ),
        ],
        integrations=[
            TemplateIntegration(
                integration_type="aws",
                required=True,
            ),
            TemplateIntegration(
                integration_type="backup_system",
                required=True,
            ),
            TemplateIntegration(
                integration_type="jira",
                required=False,
            ),
        ],
        customization_level=CustomizationLevel.PARTIAL,
        tags=["hipaa", "cost-optimization", "healthcare", "infrastructure"],
        author="ArqAI",
    )
