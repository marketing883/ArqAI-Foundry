"""
Intent Schema Registry

Defines and versions strict JSON schemas for all agent intents.
Every intent type has an explicit schema that is validated before compilation.
"""

from datetime import datetime
from typing import Any

import jsonschema
from jsonschema import Draft7Validator, ValidationError
import structlog

from arqai_foundry.core.exceptions import SchemaValidationError

logger = structlog.get_logger(__name__)


# =============================================================================
# Base Intent Schemas
# =============================================================================

BASE_INTENT_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "required": ["intent_type", "version", "action", "target", "environment", "justification"],
    "properties": {
        "intent_type": {"type": "string", "pattern": "^[a-z_]+\\.[a-z_]+$"},
        "version": {"type": "string", "pattern": "^\\d+\\.\\d+\\.\\d+$"},
        "action": {"type": "string"},
        "target": {"type": "object"},
        "environment": {"type": "string", "enum": ["development", "staging", "production", "disaster_recovery"]},
        "justification": {"type": "object"},
    },
    "additionalProperties": True,
}

# =============================================================================
# Cost Optimization Schemas
# =============================================================================

COST_OPTIMIZATION_TERMINATE_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "Cost Optimization Terminate Intent",
    "description": "Intent to terminate a cloud resource for cost optimization",
    "type": "object",
    "required": ["intent_type", "version", "action", "target", "environment", "justification"],
    "properties": {
        "intent_type": {
            "type": "string",
            "const": "cost_optimization.terminate",
        },
        "version": {
            "type": "string",
            "pattern": "^\\d+\\.\\d+\\.\\d+$",
        },
        "action": {
            "type": "string",
            "enum": ["terminate", "stop", "snapshot"],
        },
        "target": {
            "type": "object",
            "required": ["resource_type", "resource_id", "provider"],
            "properties": {
                "resource_type": {
                    "type": "string",
                    "enum": ["ec2", "rds", "s3", "ebs", "lambda", "elasticache"],
                },
                "resource_id": {
                    "type": "string",
                    "minLength": 1,
                },
                "provider": {
                    "type": "string",
                    "enum": ["aws", "azure", "gcp"],
                },
                "region": {
                    "type": "string",
                },
                "account_id": {
                    "type": "string",
                },
            },
            "additionalProperties": False,
        },
        "environment": {
            "type": "string",
            "enum": ["development", "staging", "production", "disaster_recovery"],
        },
        "justification": {
            "type": "object",
            "required": ["reason"],
            "properties": {
                "project_id": {"type": "string"},
                "project_status": {
                    "type": "string",
                    "enum": ["active", "completed", "cancelled", "on_hold"],
                },
                "idle_days": {
                    "type": "integer",
                    "minimum": 0,
                },
                "reason": {
                    "type": "string",
                    "minLength": 10,
                },
                "additional_context": {
                    "type": "object",
                },
            },
            "additionalProperties": False,
        },
    },
    "additionalProperties": False,
}

COST_OPTIMIZATION_RESIZE_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "Cost Optimization Resize Intent",
    "description": "Intent to resize a cloud resource for cost optimization",
    "type": "object",
    "required": ["intent_type", "version", "action", "target", "environment", "justification", "resize_config"],
    "properties": {
        "intent_type": {
            "type": "string",
            "const": "cost_optimization.resize",
        },
        "version": {
            "type": "string",
            "pattern": "^\\d+\\.\\d+\\.\\d+$",
        },
        "action": {
            "type": "string",
            "const": "update",
        },
        "target": {
            "type": "object",
            "required": ["resource_type", "resource_id", "provider"],
            "properties": {
                "resource_type": {"type": "string"},
                "resource_id": {"type": "string"},
                "provider": {"type": "string", "enum": ["aws", "azure", "gcp"]},
                "region": {"type": "string"},
            },
            "additionalProperties": False,
        },
        "environment": {
            "type": "string",
            "enum": ["development", "staging", "production", "disaster_recovery"],
        },
        "justification": {
            "type": "object",
            "required": ["reason"],
            "properties": {
                "reason": {"type": "string", "minLength": 10},
                "utilization_data": {"type": "object"},
            },
            "additionalProperties": False,
        },
        "resize_config": {
            "type": "object",
            "required": ["from_size", "to_size"],
            "properties": {
                "from_size": {"type": "string"},
                "to_size": {"type": "string"},
                "scheduled_time": {"type": "string", "format": "date-time"},
            },
            "additionalProperties": False,
        },
    },
    "additionalProperties": False,
}

# =============================================================================
# Compliance Schemas
# =============================================================================

COMPLIANCE_AUDIT_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "Compliance Audit Intent",
    "description": "Intent to perform a compliance audit",
    "type": "object",
    "required": ["intent_type", "version", "action", "target", "environment", "justification", "audit_config"],
    "properties": {
        "intent_type": {
            "type": "string",
            "const": "compliance.audit",
        },
        "version": {
            "type": "string",
            "pattern": "^\\d+\\.\\d+\\.\\d+$",
        },
        "action": {
            "type": "string",
            "const": "analyze",
        },
        "target": {
            "type": "object",
            "required": ["scope"],
            "properties": {
                "scope": {
                    "type": "string",
                    "enum": ["full", "incremental", "specific_controls"],
                },
                "resource_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                },
            },
            "additionalProperties": False,
        },
        "environment": {
            "type": "string",
            "enum": ["development", "staging", "production", "disaster_recovery"],
        },
        "justification": {
            "type": "object",
            "required": ["reason"],
            "properties": {
                "reason": {"type": "string"},
                "requested_by": {"type": "string"},
            },
            "additionalProperties": False,
        },
        "audit_config": {
            "type": "object",
            "required": ["framework"],
            "properties": {
                "framework": {
                    "type": "string",
                    "enum": ["soc2", "hipaa", "pci_dss", "gdpr", "iso27001", "nist"],
                },
                "controls": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "output_format": {
                    "type": "string",
                    "enum": ["json", "pdf", "csv"],
                },
            },
            "additionalProperties": False,
        },
    },
    "additionalProperties": False,
}

# =============================================================================
# Healthcare Schemas
# =============================================================================

HEALTHCARE_PHI_ACCESS_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "Healthcare PHI Access Intent",
    "description": "Intent to access protected health information",
    "type": "object",
    "required": ["intent_type", "version", "action", "target", "environment", "justification", "phi_config"],
    "properties": {
        "intent_type": {
            "type": "string",
            "const": "healthcare.phi_access",
        },
        "version": {
            "type": "string",
            "pattern": "^\\d+\\.\\d+\\.\\d+$",
        },
        "action": {
            "type": "string",
            "enum": ["read", "export", "analyze"],
        },
        "target": {
            "type": "object",
            "required": ["data_type"],
            "properties": {
                "data_type": {
                    "type": "string",
                    "enum": ["patient_records", "claims", "prescriptions", "lab_results"],
                },
                "patient_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "date_range": {
                    "type": "object",
                    "properties": {
                        "start": {"type": "string", "format": "date"},
                        "end": {"type": "string", "format": "date"},
                    },
                },
            },
            "additionalProperties": False,
        },
        "environment": {
            "type": "string",
            "enum": ["development", "staging", "production", "disaster_recovery"],
        },
        "justification": {
            "type": "object",
            "required": ["reason", "authorization"],
            "properties": {
                "reason": {"type": "string", "minLength": 20},
                "authorization": {
                    "type": "string",
                    "enum": ["treatment", "payment", "operations", "research", "legal"],
                },
                "authorized_by": {"type": "string"},
            },
            "additionalProperties": False,
        },
        "phi_config": {
            "type": "object",
            "properties": {
                "minimum_necessary": {"type": "boolean"},
                "de_identify": {"type": "boolean"},
                "audit_required": {"type": "boolean", "const": True},
            },
            "additionalProperties": False,
        },
    },
    "additionalProperties": False,
}

# =============================================================================
# Notification Schemas
# =============================================================================

NOTIFICATION_SEND_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "Notification Send Intent",
    "description": "Intent to send a notification",
    "type": "object",
    "required": ["intent_type", "version", "action", "target", "environment", "justification", "notification"],
    "properties": {
        "intent_type": {
            "type": "string",
            "const": "notification.send",
        },
        "version": {
            "type": "string",
            "pattern": "^\\d+\\.\\d+\\.\\d+$",
        },
        "action": {
            "type": "string",
            "const": "notify",
        },
        "target": {
            "type": "object",
            "required": ["channel"],
            "properties": {
                "channel": {
                    "type": "string",
                    "enum": ["slack", "msteams", "email", "webhook"],
                },
                "recipients": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "channel_id": {"type": "string"},
            },
            "additionalProperties": False,
        },
        "environment": {
            "type": "string",
            "enum": ["development", "staging", "production", "disaster_recovery"],
        },
        "justification": {
            "type": "object",
            "required": ["reason"],
            "properties": {
                "reason": {"type": "string"},
                "triggered_by": {"type": "string"},
            },
            "additionalProperties": False,
        },
        "notification": {
            "type": "object",
            "required": ["type", "content"],
            "properties": {
                "type": {
                    "type": "string",
                    "enum": ["info", "warning", "error", "approval_request", "action_complete"],
                },
                "content": {
                    "type": "object",
                    "required": ["title"],
                    "properties": {
                        "title": {"type": "string"},
                        "body": {"type": "string"},
                        "fields": {"type": "object"},
                        "actions": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "required": ["label", "action_id"],
                                "properties": {
                                    "label": {"type": "string"},
                                    "action_id": {"type": "string"},
                                    "style": {"type": "string", "enum": ["primary", "danger", "default"]},
                                },
                            },
                        },
                    },
                },
                "priority": {
                    "type": "string",
                    "enum": ["low", "normal", "high", "urgent"],
                },
            },
            "additionalProperties": False,
        },
    },
    "additionalProperties": False,
}


class IntentSchemaRegistry:
    """
    Registry of all intent schemas with versioning and validation.
    """

    def __init__(self):
        self._schemas: dict[str, dict[str, Any]] = {}
        self._validators: dict[str, Draft7Validator] = {}
        self._load_builtin_schemas()

    def _load_builtin_schemas(self) -> None:
        """Load all built-in schemas."""
        builtin_schemas = [
            ("cost_optimization.terminate", "1.0.0", COST_OPTIMIZATION_TERMINATE_SCHEMA),
            ("cost_optimization.resize", "1.0.0", COST_OPTIMIZATION_RESIZE_SCHEMA),
            ("compliance.audit", "1.0.0", COMPLIANCE_AUDIT_SCHEMA),
            ("healthcare.phi_access", "1.0.0", HEALTHCARE_PHI_ACCESS_SCHEMA),
            ("notification.send", "1.0.0", NOTIFICATION_SEND_SCHEMA),
        ]

        for intent_type, version, schema in builtin_schemas:
            self.register_schema(intent_type, version, schema)

    def register_schema(
        self,
        intent_type: str,
        version: str,
        schema: dict[str, Any],
    ) -> None:
        """Register a new schema version."""
        key = f"{intent_type}:{version}"

        # Validate the schema itself
        Draft7Validator.check_schema(schema)

        self._schemas[key] = {
            "intent_type": intent_type,
            "version": version,
            "schema": schema,
            "registered_at": datetime.utcnow().isoformat(),
        }
        self._validators[key] = Draft7Validator(schema)

        logger.info(
            "schema_registered",
            intent_type=intent_type,
            version=version,
        )

    def get_schema(
        self,
        intent_type: str,
        version: str | None = None,
    ) -> dict[str, Any]:
        """Get a schema by type and version."""
        if version:
            key = f"{intent_type}:{version}"
            if key not in self._schemas:
                raise SchemaValidationError(
                    f"Schema not found: {intent_type} v{version}",
                    schema_errors=[{"error": "schema_not_found"}],
                )
            return self._schemas[key]

        # Find latest version
        matching = [
            (k, v) for k, v in self._schemas.items()
            if k.startswith(f"{intent_type}:")
        ]
        if not matching:
            raise SchemaValidationError(
                f"No schema found for intent type: {intent_type}",
                schema_errors=[{"error": "schema_not_found"}],
            )

        # Sort by version and return latest
        matching.sort(key=lambda x: x[0], reverse=True)
        return matching[0][1]

    def validate_intent(
        self,
        intent_data: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """
        Validate intent data against its schema.

        Returns empty list if valid, list of errors otherwise.
        """
        intent_type = intent_data.get("intent_type")
        version = intent_data.get("version")

        if not intent_type:
            return [{"error": "missing_intent_type", "message": "intent_type is required"}]

        if not version:
            return [{"error": "missing_version", "message": "version is required"}]

        key = f"{intent_type}:{version}"
        validator = self._validators.get(key)

        if not validator:
            return [{
                "error": "unknown_schema",
                "message": f"No schema found for {intent_type} v{version}",
            }]

        errors = []
        for error in validator.iter_errors(intent_data):
            errors.append({
                "path": list(error.absolute_path),
                "message": error.message,
                "validator": error.validator,
                "value": error.instance if not isinstance(error.instance, dict) else "...",
            })

        if errors:
            logger.warning(
                "intent_validation_failed",
                intent_type=intent_type,
                error_count=len(errors),
            )
        else:
            logger.debug(
                "intent_validated",
                intent_type=intent_type,
                version=version,
            )

        return errors

    def list_schemas(self) -> list[dict[str, Any]]:
        """List all registered schemas."""
        return [
            {
                "intent_type": v["intent_type"],
                "version": v["version"],
                "registered_at": v["registered_at"],
            }
            for v in self._schemas.values()
        ]

    def list_intent_types(self) -> list[str]:
        """List all unique intent types."""
        return list(set(v["intent_type"] for v in self._schemas.values()))

    def get_schema_json(
        self,
        intent_type: str,
        version: str,
    ) -> dict[str, Any]:
        """Get the raw JSON schema for an intent type."""
        schema_entry = self.get_schema(intent_type, version)
        return schema_entry["schema"]
