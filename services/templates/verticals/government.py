"""
Government Vertical Templates

Templates for government and public sector:
1. FedRAMP Compliance Agent - Cloud compliance for government
2. Citizen Data Protection Agent - PII protection for citizen data
3. Procurement Automation Agent - Government procurement compliance
4. Security Operations Agent - Government security monitoring
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


def get_government_templates() -> list[AgentTemplate]:
    """Get all government vertical templates."""
    return [
        _create_fedramp_compliance_template(),
        _create_citizen_data_protection_template(),
        _create_procurement_automation_template(),
        _create_security_operations_template(),
    ]


def _create_fedramp_compliance_template() -> AgentTemplate:
    """FedRAMP Compliance Agent."""
    return AgentTemplate(
        template_id="gov-fedramp-compliance-v1",
        name="FedRAMP Compliance Manager",
        description=(
            "Manages FedRAMP compliance for government cloud environments. "
            "Monitors security controls, tracks POA&Ms, generates compliance artifacts, "
            "and supports continuous monitoring requirements."
        ),
        category=TemplateCategory.COMPLIANCE,
        vertical=TemplateVertical.GOVERNMENT,
        version=TemplateVersion(major=1, minor=0, patch=0),
        capabilities=[
            TemplateCapability(
                name="control_assessment",
                description="Assess FedRAMP security controls",
                action_types=["control.assess", "nist.evaluate"],
                required_permissions=["compliance:read", "security:read"],
                risk_tier=RiskTier.LOW,
            ),
            TemplateCapability(
                name="vulnerability_scanning",
                description="Continuous vulnerability scanning",
                action_types=["scan.vulnerability", "scan.configuration"],
                required_permissions=["scan:execute"],
                risk_tier=RiskTier.LOW,
            ),
            TemplateCapability(
                name="poam_management",
                description="Manage Plan of Action and Milestones",
                action_types=["poam.create", "poam.update", "poam.track"],
                required_permissions=["poam:write"],
                risk_tier=RiskTier.LOW,
            ),
            TemplateCapability(
                name="conmon_reporting",
                description="Generate continuous monitoring reports",
                action_types=["report.conmon", "metrics.collect"],
                required_permissions=["report:write"],
                risk_tier=RiskTier.LOW,
            ),
            TemplateCapability(
                name="ssp_management",
                description="System Security Plan management",
                action_types=["ssp.update", "ssp.version"],
                required_permissions=["ssp:write"],
                risk_tier=RiskTier.MEDIUM,
            ),
            TemplateCapability(
                name="incident_response",
                description="FedRAMP incident response",
                action_types=["incident.detect", "incident.report"],
                required_permissions=["incident:write"],
                risk_tier=RiskTier.HIGH,
            ),
        ],
        parameters=[
            TemplateParameter(
                name="fedramp_level",
                description="FedRAMP authorization level",
                param_type="string",
                default_value="Moderate",
                allowed_values=["Low", "Moderate", "High"],
            ),
            TemplateParameter(
                name="nist_revision",
                description="NIST 800-53 revision",
                param_type="string",
                default_value="Rev5",
                allowed_values=["Rev4", "Rev5"],
            ),
            TemplateParameter(
                name="scan_frequency_days",
                description="Vulnerability scan frequency in days",
                param_type="number",
                default_value=30,
                validation_rules={"min": 1, "max": 30},
            ),
            TemplateParameter(
                name="conmon_report_frequency",
                description="Continuous monitoring report frequency",
                param_type="string",
                default_value="monthly",
                allowed_values=["weekly", "monthly", "quarterly"],
            ),
            TemplateParameter(
                name="3pao_contact",
                description="3PAO assessor contact information",
                param_type="object",
                default_value={},
            ),
        ],
        default_policies=[
            TemplatePolicy(
                policy_id="gov-fedramp-audit-trail",
                name="FedRAMP Audit Trail",
                description="AU-2 compliant audit trail",
                default_enabled=True,
                customizable=False,
                policy_definition={
                    "effect": "require",
                    "nist_control": "AU-2",
                    "action": "log_all_security_events",
                    "retention_years": 3,
                },
            ),
            TemplatePolicy(
                policy_id="gov-vulnerability-response",
                name="Vulnerability Response",
                description="RA-5 vulnerability response timeline",
                default_enabled=True,
                customizable=True,
                policy_definition={
                    "effect": "require",
                    "nist_control": "RA-5",
                    "response_timeline": {
                        "critical": "24_hours",
                        "high": "30_days",
                        "moderate": "90_days",
                        "low": "180_days",
                    },
                },
            ),
            TemplatePolicy(
                policy_id="gov-incident-reporting",
                name="Incident Reporting",
                description="IR-6 incident reporting requirements",
                default_enabled=True,
                customizable=False,
                policy_definition={
                    "effect": "require",
                    "nist_control": "IR-6",
                    "us_cert_notification": "1_hour",
                    "agency_notification": "24_hours",
                },
            ),
        ],
        integrations=[
            TemplateIntegration(
                integration_type="aws_govcloud",
                required=True,
                configuration_schema={
                    "type": "object",
                    "properties": {
                        "govcloud_region": {
                            "type": "string",
                            "enum": ["us-gov-west-1", "us-gov-east-1"],
                        },
                    },
                },
            ),
            TemplateIntegration(
                integration_type="vulnerability_scanner",
                required=True,
            ),
            TemplateIntegration(
                integration_type="grc_system",
                required=True,
            ),
            TemplateIntegration(
                integration_type="teams",
                required=False,
            ),
        ],
        customization_level=CustomizationLevel.PARTIAL,
        tags=["fedramp", "nist", "government", "compliance", "cloud"],
        author="ArqAI",
    )


def _create_citizen_data_protection_template() -> AgentTemplate:
    """Citizen Data Protection Agent - Privacy Act compliant."""
    return AgentTemplate(
        template_id="gov-citizen-data-v1",
        name="Citizen Data Protection Agent",
        description=(
            "Protects citizen PII in compliance with Privacy Act, E-Government Act, "
            "and state privacy laws. Manages consent, access requests, data minimization, "
            "and breach notification requirements."
        ),
        category=TemplateCategory.DATA_MANAGEMENT,
        vertical=TemplateVertical.GOVERNMENT,
        version=TemplateVersion(major=1, minor=0, patch=0),
        capabilities=[
            TemplateCapability(
                name="pii_discovery",
                description="Discover and classify citizen PII",
                action_types=["pii.discover", "data.classify"],
                required_permissions=["data:read"],
                risk_tier=RiskTier.LOW,
                data_classification=DataClassification.PII,
            ),
            TemplateCapability(
                name="access_control",
                description="Control access to citizen data",
                action_types=["access.authorize", "access.revoke"],
                required_permissions=["access:write"],
                risk_tier=RiskTier.MEDIUM,
                data_classification=DataClassification.PII,
            ),
            TemplateCapability(
                name="foia_processing",
                description="Process FOIA requests",
                action_types=["foia.process", "redaction.apply"],
                required_permissions=["foia:process"],
                risk_tier=RiskTier.MEDIUM,
            ),
            TemplateCapability(
                name="consent_management",
                description="Manage citizen consent for data use",
                action_types=["consent.record", "consent.verify"],
                required_permissions=["consent:write"],
                risk_tier=RiskTier.LOW,
            ),
            TemplateCapability(
                name="breach_detection",
                description="Detect potential data breaches",
                action_types=["breach.detect", "anomaly.analyze"],
                required_permissions=["security:read"],
                risk_tier=RiskTier.MEDIUM,
            ),
            TemplateCapability(
                name="breach_notification",
                description="Manage breach notification process",
                action_types=["breach.notify", "report.generate"],
                required_permissions=["notification:send"],
                risk_tier=RiskTier.HIGH,
            ),
        ],
        parameters=[
            TemplateParameter(
                name="pii_categories",
                description="Categories of PII to protect",
                param_type="list",
                default_value=[
                    "ssn", "name", "dob", "address", "phone", "email",
                    "financial", "health", "biometric"
                ],
            ),
            TemplateParameter(
                name="retention_schedule",
                description="Data retention schedule by category",
                param_type="object",
                default_value={
                    "tax_records": "7_years",
                    "benefits": "6_years",
                    "general": "3_years",
                },
            ),
            TemplateParameter(
                name="foia_response_days",
                description="FOIA response deadline in days",
                param_type="number",
                default_value=20,
                validation_rules={"min": 1, "max": 30},
            ),
            TemplateParameter(
                name="breach_notification_hours",
                description="Hours to notify affected citizens",
                param_type="number",
                default_value=72,
            ),
            TemplateParameter(
                name="state_privacy_laws",
                description="Applicable state privacy laws",
                param_type="list",
                default_value=[],
                allowed_values=["CCPA", "CPRA", "VCDPA", "CPA", "CTDPA"],
            ),
        ],
        default_policies=[
            TemplatePolicy(
                policy_id="gov-privacy-act-compliance",
                name="Privacy Act Compliance",
                description="Privacy Act of 1974 requirements",
                default_enabled=True,
                customizable=False,
                policy_definition={
                    "effect": "require",
                    "requirements": [
                        "collection_notice",
                        "purpose_limitation",
                        "access_rights",
                        "correction_rights",
                    ],
                },
            ),
            TemplatePolicy(
                policy_id="gov-data-minimization",
                name="Data Minimization",
                description="Collect only necessary citizen data",
                default_enabled=True,
                customizable=True,
                policy_definition={
                    "effect": "require",
                    "principle": "minimum_necessary",
                    "retention": "purpose_based",
                },
            ),
            TemplatePolicy(
                policy_id="gov-breach-response",
                name="Breach Response",
                description="OMB M-17-12 breach response",
                default_enabled=True,
                customizable=False,
                policy_definition={
                    "effect": "require",
                    "notification_timeline": {
                        "us_cert": "1_hour",
                        "agency_head": "24_hours",
                        "affected_citizens": "72_hours",
                    },
                },
            ),
        ],
        integrations=[
            TemplateIntegration(
                integration_type="identity_system",
                required=True,
            ),
            TemplateIntegration(
                integration_type="case_management",
                required=True,
            ),
            TemplateIntegration(
                integration_type="notification_system",
                required=True,
            ),
        ],
        customization_level=CustomizationLevel.PARTIAL,
        tags=["privacy-act", "pii", "foia", "government", "data-protection"],
        author="ArqAI",
    )


def _create_procurement_automation_template() -> AgentTemplate:
    """Government Procurement Automation Agent - FAR compliant."""
    return AgentTemplate(
        template_id="gov-procurement-v1",
        name="Government Procurement Automator",
        description=(
            "Automates government procurement processes in compliance with FAR. "
            "Manages requisitions, vendor evaluation, contract compliance, "
            "and small business set-aside requirements."
        ),
        category=TemplateCategory.WORKFLOW,
        vertical=TemplateVertical.GOVERNMENT,
        version=TemplateVersion(major=1, minor=0, patch=0),
        capabilities=[
            TemplateCapability(
                name="requisition_processing",
                description="Process procurement requisitions",
                action_types=["requisition.process", "requisition.validate"],
                required_permissions=["procurement:read"],
                risk_tier=RiskTier.LOW,
            ),
            TemplateCapability(
                name="vendor_screening",
                description="Screen vendors against SAM.gov",
                action_types=["vendor.screen", "sam.check", "debarment.verify"],
                required_permissions=["vendor:read"],
                risk_tier=RiskTier.LOW,
            ),
            TemplateCapability(
                name="small_business_analysis",
                description="Analyze small business set-aside eligibility",
                action_types=["setaside.analyze", "goal.track"],
                required_permissions=["procurement:read"],
                risk_tier=RiskTier.LOW,
            ),
            TemplateCapability(
                name="contract_generation",
                description="Generate contract documents",
                action_types=["contract.generate", "clause.insert"],
                required_permissions=["contract:write"],
                risk_tier=RiskTier.MEDIUM,
            ),
            TemplateCapability(
                name="approval_routing",
                description="Route for required approvals",
                action_types=["approval.route", "approval.track"],
                required_permissions=["approval:write"],
                risk_tier=RiskTier.LOW,
            ),
            TemplateCapability(
                name="award_processing",
                description="Process contract awards",
                action_types=["award.process", "fpds.report"],
                required_permissions=["contract:write"],
                risk_tier=RiskTier.HIGH,
            ),
        ],
        parameters=[
            TemplateParameter(
                name="simplified_acquisition_threshold",
                description="Simplified acquisition threshold",
                param_type="number",
                default_value=250000,
            ),
            TemplateParameter(
                name="small_business_goals",
                description="Small business contracting goals (%)",
                param_type="object",
                default_value={
                    "small_business": 23,
                    "sdb": 5,
                    "wosb": 5,
                    "hubzone": 3,
                    "sdvosb": 3,
                },
            ),
            TemplateParameter(
                name="approval_thresholds",
                description="Dollar thresholds for approval levels",
                param_type="object",
                default_value={
                    "contracting_officer": 25000,
                    "supervisor": 100000,
                    "director": 500000,
                    "agency_head": 1000000,
                },
            ),
            TemplateParameter(
                name="far_supplements",
                description="Applicable FAR supplements",
                param_type="list",
                default_value=["DFARS"],
                allowed_values=["DFARS", "GSAFAR", "DOSAR", "AIDAR", "VAAR"],
            ),
        ],
        default_policies=[
            TemplatePolicy(
                policy_id="gov-far-compliance",
                name="FAR Compliance",
                description="Federal Acquisition Regulation compliance",
                default_enabled=True,
                customizable=False,
                policy_definition={
                    "effect": "require",
                    "requirements": [
                        "competition_requirement",
                        "fair_opportunity",
                        "best_value",
                        "documentation",
                    ],
                },
            ),
            TemplatePolicy(
                policy_id="gov-sam-verification",
                name="SAM.gov Verification",
                description="Verify vendors in SAM.gov",
                default_enabled=True,
                customizable=False,
                policy_definition={
                    "effect": "require",
                    "action": "verify_sam_status",
                    "checks": ["active_registration", "no_exclusions", "cage_code"],
                },
            ),
            TemplatePolicy(
                policy_id="gov-competition-requirements",
                name="Competition Requirements",
                description="Full and open competition requirements",
                default_enabled=True,
                customizable=True,
                policy_definition={
                    "effect": "require",
                    "condition": {"value": {"gt": 10000}},
                    "exceptions": [
                        "only_one_source",
                        "unusual_urgency",
                        "national_security",
                    ],
                    "documentation_required": True,
                },
            ),
        ],
        integrations=[
            TemplateIntegration(
                integration_type="sam_gov",
                required=True,
            ),
            TemplateIntegration(
                integration_type="fpds",
                required=True,
            ),
            TemplateIntegration(
                integration_type="financial_system",
                required=True,
            ),
            TemplateIntegration(
                integration_type="jira",
                required=False,
            ),
        ],
        customization_level=CustomizationLevel.PARTIAL,
        tags=["far", "procurement", "government", "contracts", "acquisition"],
        author="ArqAI",
    )


def _create_security_operations_template() -> AgentTemplate:
    """Government Security Operations Agent - FISMA compliant."""
    return AgentTemplate(
        template_id="gov-secops-v1",
        name="Government Security Operations Agent",
        description=(
            "FISMA-compliant security operations for government systems. "
            "Monitors security events, manages incidents, tracks vulnerabilities, "
            "and ensures compliance with NIST Cybersecurity Framework."
        ),
        category=TemplateCategory.SECURITY,
        vertical=TemplateVertical.GOVERNMENT,
        version=TemplateVersion(major=1, minor=0, patch=0),
        capabilities=[
            TemplateCapability(
                name="security_monitoring",
                description="Continuous security monitoring",
                action_types=["monitor.security", "event.collect"],
                required_permissions=["siem:read"],
                risk_tier=RiskTier.LOW,
            ),
            TemplateCapability(
                name="threat_detection",
                description="Detect security threats",
                action_types=["threat.detect", "ioc.match"],
                required_permissions=["threat:read"],
                risk_tier=RiskTier.LOW,
            ),
            TemplateCapability(
                name="incident_triage",
                description="Triage security incidents",
                action_types=["incident.triage", "severity.assign"],
                required_permissions=["incident:write"],
                risk_tier=RiskTier.MEDIUM,
            ),
            TemplateCapability(
                name="incident_response",
                description="Execute incident response procedures",
                action_types=["incident.respond", "containment.execute"],
                required_permissions=["incident:execute"],
                risk_tier=RiskTier.HIGH,
            ),
            TemplateCapability(
                name="threat_intel_integration",
                description="Integrate threat intelligence",
                action_types=["intel.ingest", "intel.correlate"],
                required_permissions=["intel:read"],
                risk_tier=RiskTier.LOW,
            ),
            TemplateCapability(
                name="automated_containment",
                description="Automated threat containment",
                action_types=["host.isolate", "account.disable", "traffic.block"],
                required_permissions=["security:control"],
                risk_tier=RiskTier.CRITICAL,
                enabled_by_default=False,
            ),
        ],
        parameters=[
            TemplateParameter(
                name="fisma_level",
                description="FISMA impact level",
                param_type="string",
                default_value="Moderate",
                allowed_values=["Low", "Moderate", "High"],
            ),
            TemplateParameter(
                name="incident_severity_mapping",
                description="Map events to incident severity",
                param_type="object",
                default_value={
                    "malware_detected": "high",
                    "unauthorized_access": "high",
                    "data_exfiltration": "critical",
                    "policy_violation": "medium",
                    "suspicious_activity": "low",
                },
            ),
            TemplateParameter(
                name="uscert_reporting",
                description="US-CERT reporting enabled",
                param_type="boolean",
                default_value=True,
            ),
            TemplateParameter(
                name="threat_feeds",
                description="Threat intelligence feeds",
                param_type="list",
                default_value=["cisa_known_exploited", "stix_taxii"],
            ),
            TemplateParameter(
                name="containment_auto_threshold",
                description="Severity threshold for auto-containment",
                param_type="string",
                default_value="critical",
                allowed_values=["high", "critical", "disabled"],
            ),
        ],
        default_policies=[
            TemplatePolicy(
                policy_id="gov-fisma-audit",
                name="FISMA Audit Requirements",
                description="FISMA audit and accountability",
                default_enabled=True,
                customizable=False,
                policy_definition={
                    "effect": "require",
                    "nist_family": "AU",
                    "controls": ["AU-2", "AU-3", "AU-6", "AU-12"],
                    "retention_years": 3,
                },
            ),
            TemplatePolicy(
                policy_id="gov-incident-response",
                name="Incident Response Policy",
                description="NIST IR controls implementation",
                default_enabled=True,
                customizable=True,
                policy_definition={
                    "effect": "require",
                    "nist_family": "IR",
                    "response_timeline": {
                        "critical": "15_minutes",
                        "high": "1_hour",
                        "medium": "4_hours",
                        "low": "24_hours",
                    },
                },
            ),
            TemplatePolicy(
                policy_id="gov-uscert-notification",
                name="US-CERT Notification",
                description="Notify US-CERT per BOD requirements",
                default_enabled=True,
                customizable=False,
                policy_definition={
                    "effect": "require",
                    "condition": {"severity": {"in": ["high", "critical"]}},
                    "action": "notify_uscert",
                    "timeline": "1_hour",
                },
            ),
        ],
        integrations=[
            TemplateIntegration(
                integration_type="siem",
                required=True,
            ),
            TemplateIntegration(
                integration_type="soar",
                required=False,
            ),
            TemplateIntegration(
                integration_type="edr",
                required=True,
            ),
            TemplateIntegration(
                integration_type="threat_intel",
                required=False,
            ),
            TemplateIntegration(
                integration_type="teams",
                required=False,
            ),
        ],
        customization_level=CustomizationLevel.PARTIAL,
        tags=["fisma", "nist", "secops", "government", "cybersecurity"],
        author="ArqAI",
    )
