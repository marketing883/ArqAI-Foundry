-- ArqAI Foundry - Database Initialization Script
-- Creates necessary schemas and tables

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create schemas
CREATE SCHEMA IF NOT EXISTS identity;
CREATE SCHEMA IF NOT EXISTS evidence;
CREATE SCHEMA IF NOT EXISTS policy;
CREATE SCHEMA IF NOT EXISTS orchestration;

-- ===========================================================================
-- Identity Schema
-- ===========================================================================

-- Tenants
CREATE TABLE IF NOT EXISTS identity.tenants (
    tenant_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'active',
    settings JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Agents
CREATE TABLE IF NOT EXISTS identity.agents (
    agent_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES identity.tenants(tenant_id),
    name VARCHAR(255) NOT NULL,
    template_id VARCHAR(255),
    status VARCHAR(50) NOT NULL DEFAULT 'active',
    capabilities TEXT[] DEFAULT '{}',
    max_risk_tier VARCHAR(50) DEFAULT 'low',
    config JSONB DEFAULT '{}',
    certificate_fingerprint VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_agents_tenant ON identity.agents(tenant_id);
CREATE INDEX idx_agents_template ON identity.agents(template_id);

-- ===========================================================================
-- Evidence Schema
-- ===========================================================================

-- Evidence Packets
CREATE TABLE IF NOT EXISTS evidence.packets (
    evidence_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL,
    execution_id UUID NOT NULL,
    agent_id UUID NOT NULL,
    action_type VARCHAR(255) NOT NULL,
    target VARCHAR(255),
    pre_state JSONB,
    post_state JSONB,
    policy_evaluation JSONB,
    risk_assessment JSONB,
    authorization JSONB,
    execution_trace JSONB,
    hash VARCHAR(64) NOT NULL,
    previous_hash VARCHAR(64),
    signature TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_evidence_tenant ON evidence.packets(tenant_id);
CREATE INDEX idx_evidence_agent ON evidence.packets(agent_id);
CREATE INDEX idx_evidence_execution ON evidence.packets(execution_id);
CREATE INDEX idx_evidence_created ON evidence.packets(created_at);

-- ===========================================================================
-- Policy Schema
-- ===========================================================================

-- Policies
CREATE TABLE IF NOT EXISTS policy.policies (
    policy_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    priority INTEGER DEFAULT 100,
    effect VARCHAR(50) NOT NULL,
    conditions JSONB NOT NULL DEFAULT '{}',
    actions TEXT[] DEFAULT '{}',
    enabled BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_policies_tenant ON policy.policies(tenant_id);
CREATE INDEX idx_policies_enabled ON policy.policies(enabled);

-- ===========================================================================
-- Orchestration Schema
-- ===========================================================================

-- Executions
CREATE TABLE IF NOT EXISTS orchestration.executions (
    execution_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL,
    agent_id UUID NOT NULL,
    intent JSONB NOT NULL,
    compiled_ir JSONB,
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    risk_score INTEGER,
    risk_tier VARCHAR(50),
    approval_id UUID,
    result JSONB,
    error TEXT,
    started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX idx_executions_tenant ON orchestration.executions(tenant_id);
CREATE INDEX idx_executions_agent ON orchestration.executions(agent_id);
CREATE INDEX idx_executions_status ON orchestration.executions(status);

-- Approvals
CREATE TABLE IF NOT EXISTS orchestration.approvals (
    approval_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    execution_id UUID NOT NULL REFERENCES orchestration.executions(execution_id),
    tenant_id UUID NOT NULL,
    action_summary TEXT NOT NULL,
    risk_score INTEGER NOT NULL,
    risk_tier VARCHAR(50) NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    required_approvers JSONB NOT NULL DEFAULT '[]',
    approved_by VARCHAR(255),
    rejected_by VARCHAR(255),
    rejection_reason TEXT,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    resolved_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_approvals_execution ON orchestration.approvals(execution_id);
CREATE INDEX idx_approvals_status ON orchestration.approvals(status);
CREATE INDEX idx_approvals_expires ON orchestration.approvals(expires_at);

-- ===========================================================================
-- Functions
-- ===========================================================================

-- Update timestamp trigger
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply to relevant tables
CREATE TRIGGER update_tenants_updated_at
    BEFORE UPDATE ON identity.tenants
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER update_agents_updated_at
    BEFORE UPDATE ON identity.agents
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER update_policies_updated_at
    BEFORE UPDATE ON policy.policies
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();
