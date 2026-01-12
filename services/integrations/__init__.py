"""
Integration Layer

Connects to external systems with evidence-first design:
- Framework for all integrations
- AWS Connector (EC2, RDS, S3, Cost Explorer)
- Jira Connector
- Slack Connector
- MS Teams Connector
"""

from services.integrations.aws.connector import AWSConnector
from services.integrations.framework.base import IntegrationConnector
from services.integrations.framework.registry import IntegrationRegistry
from services.integrations.jira.connector import JiraConnector
from services.integrations.msteams.connector import MSTeamsConnector
from services.integrations.slack.connector import SlackConnector

__all__ = [
    "IntegrationConnector",
    "IntegrationRegistry",
    "AWSConnector",
    "JiraConnector",
    "SlackConnector",
    "MSTeamsConnector",
]
