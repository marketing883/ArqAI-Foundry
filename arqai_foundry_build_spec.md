# ArqAI Foundry: Complete Build Specification
## Optimized for Claude Code Execution

---

# ARCHITECTURE OVERVIEW

## System Boundaries

**Control Plane** (ArqAI-hosted SaaS):
- Policy evaluation engine
- Risk scoring service
- Capability token issuance
- Evidence ledger (append-only)
- Management UI/API
- NO customer data processing

**Data Plane** (Customer VPC - optional deployment):
- Agent execution runtime
- Cloud API interactions
- Customer data access
- Evidence hash generation (data stays local)

**Trust Model**:
- Cryptographic identity for every component
- Capability tokens for every action
- Immutable evidence for every execution
- Public verification without metadata leakage

---

# PHASE 0: TRUST CORE (Months 1-6)

## BUILD 1: Identity & Key Management System

### Objective
Establish cryptographic trust foundation with HSM-backed identities, hierarchical key management, and automated rotation.

### Components to Build

**1.1 Key Management Service**

Purpose: Generate, store, rotate, and revoke cryptographic keys across the platform

Requirements:
- Integrate with HashiCorp Vault
- Three key hierarchies:
  - Root CA (platform-level, HSM-backed)
  - Intermediate CA per tenant
  - Leaf certificates for agents, tokens, evidence
- Automated rotation schedule:
  - Agent keys: 90 days
  - Token signing keys: 7 days
  - Evidence signing keys: 365 days
- Revocation list distribution (sub-second propagation)
- Key compromise containment (tenant isolation)

Acceptance Criteria:
- Keys never leave Vault except as signed certificates
- Rotation happens automatically without downtime
- Revocation propagates to all services within 1 second
- Audit log of all key operations
- Tenant keys are cryptographically isolated

**1.2 Agent Identity Service**

Purpose: Issue and manage cryptographic identities for agent instances

Requirements:
- Generate unique keypair per agent deployment
- Bind identity to agent_id, tenant_id, template_id
- Attestation: agent must prove runtime integrity
- Identity lifecycle:
  - Issue: on agent deployment
  - Rotate: every 90 days automatically
  - Revoke: on agent deletion or compromise
  - Suspend: for policy violations
- Identity certificate format:
  ```
  Subject: agent_id
  Extension: tenant_id (non-transferable)
  Extension: template_id
  Extension: deployment_environment
  Issuer: Tenant Intermediate CA
  Validity: 90 days
  ```

Acceptance Criteria:
- Agent cannot execute without valid identity
- Identity validates in <10ms
- Compromised identity can be revoked instantly
- Audit trail links every action to agent identity

**1.3 Capability Token Service**

Purpose: Issue single-use, time-bound, scoped authorization tokens

Requirements:
- Token structure:
  ```
  token_id: UUID
  agent_identity: certificate_fingerprint
  scope:
    resource_id: exact resource identifier
    action: single action (e.g., "terminate")
    constraints: field-level restrictions
  issued_at: timestamp
  expires_at: timestamp (5 min max)
  one_time_nonce: ensures single use
  signature: signed by token service key
  ```
- Token validation rules:
  - Signature must be valid
  - Not expired (TTL check)
  - Not already used (nonce check)
  - Agent identity matches token
  - Action within scope
- Token revocation:
  - Immediate on anomaly detection
  - Immediate on policy change
  - Cascading revocation (if parent workflow cancelled)

Acceptance Criteria:
- Token issuance in <20ms
- Token validation in <10ms
- Tokens cannot be reused (even within TTL)
- Revoked tokens fail immediately
- Zero false positives in validation

**1.4 Trust Anchor Registry**

Purpose: Maintain root of trust and public key infrastructure

Requirements:
- Publish platform root CA certificate (public)
- Maintain intermediate CA registry per tenant
- Provide public key lookup service:
  - By tenant_id (requires auth)
  - By evidence_id (public, for verification)
- Key pinning for critical services
- Certificate transparency log (all issued certificates)

Acceptance Criteria:
- Public root CA accessible via HTTPS
- Certificate transparency log queryable
- Key lookup <5ms
- No private keys ever exposed

---

## BUILD 2: Typed Intent & Deterministic Compiler

### Objective
Replace LLM-based intent parsing with deterministic, type-safe compilation from strict schemas to executable IR.

### Components to Build

**2.1 Intent Schema Registry**

Purpose: Define and version strict JSON schemas for all agent intents

Requirements:
- Schema format (JSON Schema Draft 7):
  ```json
  {
    "intent_type": "cost_optimization.terminate",
    "version": "1.0.0",
    "schema": {
      "type": "object",
      "required": ["action", "target", "environment", "justification"],
      "properties": {
        "action": {
          "type": "string",
          "enum": ["terminate", "stop", "snapshot"]
        },
        "target": {
          "type": "object",
          "required": ["resource_type", "resource_id"],
          "properties": {
            "resource_type": {"enum": ["ec2", "rds"]},
            "resource_id": {"pattern": "^i-[a-z0-9]{8,}$"}
          }
        },
        "environment": {"enum": ["dev", "staging", "production"]},
        "justification": {
          "type": "object",
          "required": ["project_id", "project_status", "idle_days"],
          "properties": {
            "project_id": {"type": "string"},
            "project_status": {"enum": ["completed", "cancelled"]},
            "idle_days": {"type": "integer", "minimum": 0}
          }
        }
      },
      "additionalProperties": false
    }
  }
  ```
- Schema versioning (semantic versioning)
- Schema validation library integration
- Schema evolution rules (backward compatibility)

Acceptance Criteria:
- Every intent type has explicit schema
- Validation rejects malformed intents immediately
- Schemas are versioned and immutable
- Schema registry is queryable via API

**2.2 Deterministic Compiler**

Purpose: Transform validated intents into compliance-annotated IR without non-determinism

Requirements:
- Compilation pipeline:
  1. Schema validation (strict)
  2. Static policy check (deterministic rules)
  3. IR generation (one-to-one mapping)
  4. IR safety verification (prove properties)
  5. Compliance annotation (sensitivity, jurisdiction)
- IR format:
  ```json
  {
    "ir_version": "1.0.0",
    "operations": [{
      "op_id": "uuid",
      "type": "cloud.ec2.terminate",
      "target": "i-abc123",
      "parameters": {},
      "data_classification": "internal",
      "environment": "development",
      "jurisdiction": ["US"],
      "estimated_cost_impact": {"monthly": 127.43}
    }],
    "policy_requirements": {
      "min_risk_tier": "low",
      "required_approvals": [],
      "evidence_level": "standard"
    },
    "compilation_metadata": {
      "compiled_at": "timestamp",
      "policy_version": "2.1.0",
      "schema_version": "1.0.0"
    }
  }
  ```
- Fail-closed semantics:
  - Ambiguous input → compilation error
  - Unknown action → compilation error
  - Policy violation → compilation error
  - No guessing, no defaults

Acceptance Criteria:
- Compilation is deterministic (same input → same IR)
- Compilation time <100ms
- Zero ambiguous outputs
- All compilation errors have actionable messages
- IR is verifiably safe (static analysis proves properties)

**2.3 Natural Language Parser (Optional UX Layer)**

Purpose: Convenience layer to suggest structured intent from NL, requires human confirmation

Requirements:
- LLM-based extraction to Intent schema
- Structured output with confidence scores
- Present to user for approval before compilation
- Clear indication this is a suggestion, not executed
- User can edit suggested intent before confirming
- Fallback to manual schema entry

Acceptance Criteria:
- NL parser never directly triggers execution
- User sees structured intent and must approve
- Editing UI validates against schema in real-time
- Compilation happens only after user confirmation
- Audit trail shows NL input → structured intent → user approval → compilation

---

## BUILD 3: Policy Engine

### Objective
Deterministic policy evaluation with versioning, testing, and performance guarantees.

### Components to Build

**3.1 Policy Graph Database**

Purpose: Store, version, and query policy rules efficiently

Requirements:
- Policy structure:
  ```yaml
  policy_id: "cost-optimization-v1"
  version: "1.0.0"
  tenant_id: "tenant-uuid"
  jurisdiction: ["US", "EU"]
  
  rules:
    - rule_id: "r1"
      name: "prohibit_production_deletion"
      priority: 100  # Higher priority = evaluated first
      condition:
        and:
          - field: "environment"
            operator: "equals"
            value: "production"
          - field: "action"
            operator: "equals"
            value: "delete"
      effect: "deny"
      evidence_required: true
      
    - rule_id: "r2"
      name: "require_approval_high_cost"
      priority: 90
      condition:
        field: "monthly_cost_impact"
        operator: "greater_than"
        value: 5000
      effect: "require_approval"
      approvers:
        - role: "finops_manager"
        - role: "engineering_director"
      timeout_hours: 24
      
    - rule_id: "r3"
      name: "auto_cleanup_completed_dev"
      priority: 10
      condition:
        and:
          - field: "environment"
            operator: "equals"
            value: "development"
          - field: "project_status"
            operator: "equals"
            value: "completed"
          - field: "idle_days"
            operator: "greater_than"
            value: 90
          - field: "risk_score"
            operator: "less_than"
            value: 30
      effect: "allow_auto"
      require_snapshot: true
  
  risk_scoring:
    factors:
      - name: "data_sensitivity"
        weight: 0.35
        mapping:
          "public": 0
          "internal": 10
          "confidential": 25
          "pii": 40
          "phi": 50
      
      - name: "environment"
        weight: 0.25
        mapping:
          "development": -15
          "staging": 0
          "production": 25
      
      - name: "financial_impact"
        weight: 0.20
        formula: |
          if monthly_cost > 10000: return 30
          elif monthly_cost > 5000: return 20
          else: return 0
  ```
- Policy versioning (immutable versions)
- Policy inheritance (tenant → workspace → agent)
- Policy testing framework (simulate rule evaluation)

Acceptance Criteria:
- Policy stored in PostgreSQL JSONB for fast queries
- Policy evaluation <30ms (cached) or <100ms (uncached)
- Policy versions are immutable
- Policy changes trigger re-certification
- Audit log of all policy modifications

**3.2 Policy Evaluation Engine**

Purpose: Evaluate policy rules against intents/IR deterministically

Requirements:
- Rule evaluation order: priority descending
- Short-circuit evaluation (first deny/require_approval wins)
- Context enrichment:
  - Retrieve data classification from lineage
  - Calculate financial impact
  - Lookup project status
  - Compute risk score
- Evaluation result:
  ```json
  {
    "allowed": true,
    "effect": "allow_auto",
    "matched_rules": ["r3"],
    "risk_score": 24,
    "risk_tier": "low",
    "required_approvals": [],
    "constraints": {
      "require_snapshot": true,
      "notification_channels": ["#engineering"]
    },
    "evaluation_time_ms": 45
  }
  ```
- Caching strategy:
  - Cache policy version per tenant (TTL 1 hour)
  - Cache risk factor mappings (TTL 1 day)
  - Invalidate on policy update

Acceptance Criteria:
- Evaluation is deterministic (same inputs → same result)
- Evaluation <30ms for 95th percentile
- Zero false positives (denying valid actions)
- Zero false negatives (allowing invalid actions)
- Cache hit rate >80%

**3.3 Policy Testing Framework**

Purpose: Test policies before deployment with simulation and verification

Requirements:
- Test case format:
  ```yaml
  test_case:
    name: "high_cost_production_requires_approval"
    intent:
      action: "terminate"
      target: {resource_id: "i-abc123"}
      environment: "production"
      monthly_cost: 8000
    expected_result:
      effect: "require_approval"
      approvers: ["finops_manager", "engineering_director"]
  ```
- Batch test execution
- Coverage analysis (which rules tested)
- Regression testing (policy changes don't break existing tests)
- Performance testing (evaluate 1000 policies in <1s)

Acceptance Criteria:
- Test framework can run 100+ test cases in <5 seconds
- Coverage report shows % of rules tested
- CI/CD integration blocks policy deployment if tests fail
- Test results are auditable

---

## BUILD 4: Evidence Vault with Selective Disclosure

### Objective
Cryptographically verifiable evidence with public integrity verification and no metadata leakage.

### Components to Build

**4.1 Evidence Packet Structure**

Purpose: Standardized format for immutable, signed audit evidence

Requirements:
- Packet structure:
  ```json
  {
    // PUBLIC FIELDS (always disclosed)
    "evidence_id": "uuid",
    "schema_version": "2.0",
    "evidence_hash": "sha256:...",
    "signature": "base64-encoded",
    "verification_url": "https://verify.arqai.com/evidence/{id}",
    
    // PROTECTED FIELDS (redacted by default)
    "tenant_id": "uuid",  // Requires tenant auth to view
    "agent_id": "uuid",   // Requires tenant auth to view
    "timestamp": "ISO-8601",  // Rounded to hour in public view
    
    // EVIDENCE CONTENT (requires tenant auth)
    "request": {
      "intent": {...},
      "context": {...}
    },
    "compliance_ir": {
      "operations": [...]
    },
    "policy_validation": {
      "policy_id": "...",
      "policy_version": "...",
      "policy_hash": "sha256:...",
      "evaluation_result": {...}
    },
    "risk_assessment": {
      "risk_score": 24,
      "risk_tier": "low",
      "factors": {...}
    },
    "capability_token": {
      "token_id": "...",
      "scope": {...},
      "constraints": {...}
    },
    "execution": {
      "pre_action_state": {...},
      "action_trace": [...],
      "post_action_state": {...}
    },
    "financial_impact": {
      "monthly_savings": 127.43,
      "annual_projection": 1529.16
    },
    
    // CHAIN INTEGRITY
    "previous_hash": "sha256:...",  // Links to previous evidence
    "block_number": 12345
  }
  ```
- Hash computation (deterministic, all fields except signature)
- Signature algorithm: ECDSA with SHA-256
- Chain linking (each evidence references previous)

Acceptance Criteria:
- Evidence packet is immutable once stored
- Hash computation is deterministic
- Signature verifies with public key
- Chain integrity verifiable
- Selective disclosure works (public sees hash+sig only)

**4.2 Append-Only Ledger**

Purpose: Store evidence with database-enforced immutability

Requirements:
- PostgreSQL table with constraints:
  ```sql
  CREATE TABLE evidence_ledger (
    evidence_id UUID PRIMARY KEY,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    tenant_id UUID NOT NULL,
    agent_id UUID NOT NULL,
    schema_version VARCHAR(10) NOT NULL,
    
    -- Evidence data (JSONB for queryability)
    evidence_data JSONB NOT NULL,
    
    -- Integrity fields
    evidence_hash TEXT NOT NULL,
    signature TEXT NOT NULL,
    previous_hash TEXT,
    block_number BIGSERIAL,
    
    -- Immutability enforced by DB
    CONSTRAINT no_updates CHECK (false),
    CONSTRAINT no_deletes CHECK (false),
    
    -- Indexes for fast lookup
    INDEX idx_tenant_id (tenant_id),
    INDEX idx_created_at (created_at),
    INDEX idx_block_number (block_number)
  );
  
  -- Revoke UPDATE and DELETE privileges
  REVOKE UPDATE, DELETE ON evidence_ledger FROM arqai_app;
  GRANT INSERT, SELECT ON evidence_ledger TO arqai_app;
  ```
- Write-ahead log (WAL) archival for disaster recovery
- Read replicas for audit queries (don't impact writes)
- Retention: 7 years minimum (configurable per tenant)

Acceptance Criteria:
- INSERT succeeds, UPDATE/DELETE fail at DB level
- Write throughput: 1000+ evidence packets/second
- Query performance: <10ms by evidence_id
- Chain verification <100ms for 1000 evidence packets
- Backup and recovery tested (RPO <1 hour, RTO <4 hours)

**4.3 Public Verification Service**

Purpose: Allow anyone to verify evidence integrity without revealing sensitive data

Requirements:
- Public API endpoint (no authentication required):
  ```
  GET https://verify.arqai.com/api/v1/evidence/{evidence_id}/verify
  
  Response:
  {
    "evidence_id": "uuid",
    "valid": true,
    "verified_at": "timestamp",
    "hash_verified": true,
    "signature_verified": true,
    "chain_verified": true,
    
    // Public metadata (no sensitive data)
    "schema_version": "2.0",
    "timestamp_hour": "2025-01-29T10:00:00Z",  // Rounded to hour
    "evidence_hash": "sha256:...",
    
    // NO tenant_id, agent_id, or detailed content
  }
  ```
- Verification algorithm:
  1. Fetch evidence by ID
  2. Compute hash from evidence_data
  3. Compare computed hash to stored hash
  4. Verify signature using public key
  5. Verify chain link (previous_hash matches)
- Rate limiting (100 requests/min per IP)

Acceptance Criteria:
- Verification succeeds for valid evidence
- Verification fails for tampered evidence
- No sensitive metadata disclosed in public response
- Verification time <50ms
- Rate limiting prevents abuse

**4.4 Selective Disclosure API**

Purpose: Allow tenants and auditors to access detailed evidence with proper authorization

Requirements:
- Authenticated API (requires valid token):
  ```
  GET https://api.arqai.com/api/v1/evidence/{evidence_id}
  Headers:
    Authorization: Bearer {tenant_token}
  
  Response: Full evidence packet (all fields)
  ```
- Authorization rules:
  - Tenant can see their own evidence
  - Auditor (with tenant-granted token) can see specific evidence
  - Platform admin can see evidence for support (with approval)
- Audit log of all evidence access attempts
- Field-level filtering (request specific fields only)

Acceptance Criteria:
- Tenant can retrieve full evidence for their agents
- Cross-tenant access denied
- Auditor access logged and attributable
- Response time <100ms
- Field filtering works correctly

**4.5 Evidence Export for Compliance**

Purpose: Generate compliance-ready reports from evidence

Requirements:
- Export formats:
  - SOC 2 audit package (PDF with evidence packets)
  - ISO 27001 compliance report
  - GDPR data processing records
  - Custom CSV export
- Report generation:
  - Query evidence by date range, agent, action type
  - Aggregate statistics (actions taken, policies enforced)
  - Include policy versions used during period
  - Cryptographic verification of all included evidence
- Report signing (report itself is signed)

Acceptance Criteria:
- SOC 2 package generates in <2 minutes for 10K evidence packets
- Report includes all required evidence fields
- Report signature verifiable
- Auditors confirm reports meet compliance requirements

---

## BUILD 5: Risk Scoring Engine

### Objective
Compute contextual risk scores using weighted factors and deterministic algorithms.

### Components to Build

**5.1 Risk Factor Evaluator**

Purpose: Compute individual risk factor scores based on context

Requirements:
- Factor definitions (from policy graph):
  ```yaml
  factors:
    - name: "data_sensitivity"
      weight: 0.35
      type: "mapping"
      values:
        "public": 0
        "internal": 10
        "pii": 40
    
    - name: "environment"
      weight: 0.25
      type: "mapping"
      values:
        "development": -15
        "production": 25
    
    - name: "financial_impact"
      weight: 0.20
      type: "formula"
      code: |
        if context.monthly_cost > 10000:
            return 30
        elif context.monthly_cost > 5000:
            return 20
        else:
            return 0
    
    - name: "idle_duration"
      weight: 0.15
      type: "formula"
      code: |
        if context.idle_days > 180:
            return -50
        elif context.idle_days > 90:
            return -30
        else:
            return 0
  ```
- Context enrichment service:
  - Data sensitivity: query lineage service
  - Financial impact: query cost estimation service
  - Idle duration: query resource monitoring service
  - Project status: query project management integration
- Safe formula execution (sandboxed Python eval with timeout)

Acceptance Criteria:
- Factor evaluation <10ms per factor
- Formula execution timeout at 100ms (fail-safe)
- No side effects in formula evaluation
- All factors logged in risk assessment

**5.2 Risk Score Aggregator**

Purpose: Combine factor scores into overall risk score and tier

Requirements:
- Weighted sum computation:
  ```
  risk_score = sum(factor_score * factor_weight for each factor)
  risk_score = clamp(risk_score, 0, 100)
  ```
- Risk tier determination:
  ```
  if risk_score < 30: tier = "low"
  elif risk_score < 60: tier = "medium"
  elif risk_score < 80: tier = "high"
  else: tier = "critical"
  ```
- Reasoning generation (explain why score is what it is):
  ```json
  {
    "risk_score": 24,
    "risk_tier": "low",
    "reasoning": [
      "data_sensitivity=internal (+10 points, 35% weight)",
      "environment=development (-15 points, 25% weight)",
      "financial_impact=$127/month (+0 points, 20% weight)",
      "idle_days=94 (-30 points, 15% weight)",
      "Final: (10*0.35) + (-15*0.25) + (0*0.20) + (-30*0.15) = 24"
    ]
  }
  ```

Acceptance Criteria:
- Risk score computation <20ms
- Score is in range [0, 100]
- Reasoning is human-readable
- Risk tier accurately reflects score

**5.3 Risk Score Cache**

Purpose: Cache risk scores for identical contexts to improve performance

Requirements:
- Cache key: hash of (intent + context)
- Cache TTL: 5 minutes
- Cache invalidation: on policy change
- Cache storage: Redis
- Cache hit rate target: >70%

Acceptance Criteria:
- Cache hit response time <5ms
- Cache miss response time <30ms
- Cache hit rate >70% in production
- Cache correctly invalidates on policy changes

---

## BUILD 6: Orchestration Engine

### Objective
Execute actions with governance checkpoints at every step.

### Components to Build

**6.1 Orchestration Pipeline**

Purpose: Coordinate compilation → policy check → risk scoring → token issuance → execution → evidence

Requirements:
- Pipeline stages:
  1. **Compile**: Intent → IR (deterministic compiler)
  2. **Static Check**: IR → Policy evaluation
  3. **Risk Scoring**: IR + Context → Risk score
  4. **Authorization**: Risk score → Capability token (if allowed)
  5. **Execution**: IR + Token → Action execution
  6. **Evidence**: All above → Evidence packet
  
- Pipeline state machine:
  ```
  States: [pending, compiling, checking, scoring, authorized, executing, completed, failed, denied]
  
  Transitions:
  pending → compiling (start compilation)
  compiling → checking (compilation succeeded)
  compiling → failed (compilation failed)
  checking → scoring (policy check passed)
  checking → denied (policy check failed)
  scoring → authorized (risk acceptable, token issued)
  scoring → denied (risk too high)
  authorized → executing (token validated, execution started)
  executing → completed (execution succeeded)
  executing → failed (execution failed)
  ```
  
- Error handling:
  - Compilation error → stop, return error to user
  - Policy denial → stop, log evidence of denial
  - Risk too high → escalate for approval
  - Execution failure → rollback if possible, log evidence

Acceptance Criteria:
- Pipeline execution <1 second for low-risk actions
- State transitions logged for audit
- Failed pipelines don't leave partial state
- Evidence generated for all outcomes (success, fail, deny)

**6.2 Action Executor**

Purpose: Execute validated actions against integrated systems

Requirements:
- Executor interface:
  ```python
  class ActionExecutor:
      def execute(
          self,
          ir_operation: IROperation,
          capability_token: CapabilityToken
      ) -> ExecutionResult:
          # 1. Validate token
          # 2. Capture pre-action state
          # 3. Execute action
          # 4. Verify action succeeded
          # 5. Capture post-action state
          # 6. Return result with evidence
  ```
- Integration adapters:
  - AWS adapter (EC2, RDS, S3, Cost Explorer)
  - Jira adapter (project tracking)
  - (Future: Azure, GCP, Asana, Linear)
- Execution modes:
  - Live: actually execute
  - Dry-run: simulate and report what would happen
  - Shadow: monitor and suggest (no action)
- Rollback support:
  - Snapshot before destructive operations
  - Rollback mechanism (restore from snapshot)
  - Rollback window (30 days)

Acceptance Criteria:
- Executor validates token before every action
- Pre/post state captured for all actions
- Dry-run mode accurately predicts outcomes
- Rollback succeeds for supported operations
- Execution failures return actionable error messages

**6.3 Approval Workflow Service**

Purpose: Handle human-in-the-loop approvals for medium/high-risk actions

Requirements:
- Approval request structure:
  ```json
  {
    "approval_id": "uuid",
    "action_summary": "Terminate 5 VMs from Project Phoenix",
    "risk_score": 45,
    "risk_tier": "medium",
    "policy_requirements": {
      "approvers": [
        {"role": "finops_manager", "user_id": "optional"},
        {"role": "team_lead", "user_id": "optional"}
      ],
      "timeout_hours": 24,
      "delegation_allowed": false
    },
    "evidence_preview": {
      "resources_affected": [...],
      "estimated_savings": "$635/month"
    },
    "created_at": "timestamp",
    "expires_at": "timestamp"
  }
  ```
- Notification channels:
  - Slack (inline approval buttons)
  - Email (approval link)
  - Mobile push (future)
- Approval actions:
  - Approve: issue token, execute action
  - Reject: deny action, log evidence of rejection
  - Delegate: transfer to another approver
  - Request more info: pause for clarification
- Emergency break-glass:
  - Override approval requirement
  - Requires justification + emergency contact
  - Immediately notifies exec team (CIO, CEO)
  - Full audit trail of override

Acceptance Criteria:
- Approval request created in <100ms
- Notifications sent within 5 seconds
- Approval/rejection logged immediately
- Expired requests auto-reject
- Break-glass generates special evidence packet
- Delegation chain tracked in audit

---

## BUILD 7: Integration Layer

### Objective
Connect to external systems with evidence-first design and consistent interface.

### Components to Build

**7.1 Integration Framework**

Purpose: Standard interface for all integrations with evidence enforcement

Requirements:
- Base connector interface:
  ```python
  class IntegrationConnector:
      # Connection management
      def connect() -> bool
      def disconnect() -> None
      def test_connection() -> ConnectionStatus
      def test_permissions() -> PermissionReport
      
      # Action execution (enforces evidence)
      def execute_action(
          action: Action,
          capability_token: CapabilityToken
      ) -> ActionResult
      
      # State capture for evidence
      def capture_pre_state(action: Action) -> State
      def capture_post_state(action: Action) -> State
      
      # Query operations (read-only)
      def query_resources(filters: Dict) -> List[Resource]
      def get_resource_metadata(resource_id: str) -> Metadata
  ```
- Connector lifecycle:
  - Install: deploy connector
  - Configure: set credentials, endpoint
  - Test: validate connection and permissions
  - Activate: enable for use by agents
  - Monitor: health checks, error rates
  - Update: new version deployment
  - Deactivate: disable temporarily
  - Uninstall: remove completely
- Error handling patterns:
  - Retry with exponential backoff
  - Circuit breaker (stop after N failures)
  - Fallback to read-only mode
  - Alert on critical failures

Acceptance Criteria:
- All connectors implement base interface
- Evidence automatically generated for all actions
- Connection failures don't crash agents
- Permission checks complete before action attempts
- Health checks run every 60 seconds

**7.2 AWS Connector**

Purpose: Integrate with AWS for cost optimization use case

Requirements:
- Authentication:
  - IAM role assumption (preferred)
  - Access key + secret (fallback)
  - MFA support
- Required permissions:
  ```
  Read:
  - ec2:DescribeInstances
  - ec2:DescribeImages
  - rds:DescribeDBInstances
  - s3:ListBucket
  - ce:GetCostAndUsage (Cost Explorer)
  - cloudtrail:LookupEvents
  
  Write (with approval):
  - ec2:StopInstances
  - ec2:TerminateInstances
  - ec2:CreateImage (for snapshots)
  - rds:ModifyDBInstance
  - s3:PutLifecycleConfiguration
  ```
- Supported actions:
  - EC2: stop, terminate, create AMI
  - RDS: stop, modify (instance class)
  - S3: set lifecycle policy
  - Cost Explorer: query costs by resource
- Resource tagging (for correlation):
  - Read tags: project, environment, owner
  - Write tags: arqai:managed, arqai:evidence_id
- CloudTrail integration:
  - Query who created resource
  - Trace resource lineage

Acceptance Criteria:
- Connection test validates all required permissions
- Actions respect AWS API rate limits
- Errors include AWS error codes and messages
- Resource state captured before/after actions
- CloudTrail events linked to evidence

**7.3 Jira Connector**

Purpose: Track project lifecycle for correlation to cloud resources

Requirements:
- Authentication:
  - API token (Jira Cloud)
  - OAuth (Jira Data Center)
- Query operations:
  - Get project by ID
  - Get project status
  - Get project completion date
  - Get issues by project
  - Search by JQL
- Webhook integration:
  - Listen for project status changes
  - Listen for project closure
  - Trigger agent workflows on events
- Resource correlation:
  - Match resource tags to Jira project keys
  - Parse resource descriptions for issue keys
  - Use custom fields (e.g., "AWS Account ID")

Acceptance Criteria:
- Projects queryable by key or ID
- Webhook events received within 5 seconds
- Project status changes trigger agent workflows
- Correlation accuracy >80% for tagged resources
- Pagination handles projects with 1000+ issues

---

## BUILD 8: Wedge Template - ArqOptimize

### Objective
Build first production template using all governance components.

### Components to Build

**8.1 Project Lifecycle Tracker**

Purpose: Monitor Jira projects and detect completed projects

Requirements:
- Polling strategy:
  - Poll Jira every 15 minutes
  - Query: projects updated in last 30 days
  - Filter: status = "Done" OR "Closed" OR "Archived"
- Project state tracking:
  ```json
  {
    "project_id": "PHOENIX",
    "project_name": "Mobile App Redesign",
    "status": "completed",
    "completion_date": "2024-10-15",
    "last_activity_date": "2024-10-20",
    "days_since_completion": 94
  }
  ```
- Completion criteria (configurable):
  - Status in completed states for 30+ days
  - No issues reopened
  - No activity in last 30 days

Acceptance Criteria:
- Detects completed projects within 15 minutes
- Handles Jira API rate limits gracefully
- Accurately calculates days since completion
- Stores project state in database for tracking

**8.2 Resource Correlator**

Purpose: Link cloud resources to Jira projects

Requirements:
- Correlation methods (priority order):
  1. **Tag-based** (60% coverage expected):
     - Resource has tag: `project=PHOENIX`
     - Direct match, highest confidence
  
  2. **Lineage-based** (30% coverage):
     - CloudTrail shows resource created by IAM user
     - IAM user maps to person
     - Person assigned to Jira project
     - Indirect match, medium confidence
  
  3. **Behavioral-based** (10% coverage):
     - Resources deployed at same time
     - Resources share security groups
     - Resources in same VPC
     - Pattern match, lowest confidence
- Correlation confidence score (0-100)
- Manual override (user can correct correlations)
- Correlation cache (avoid re-computing)

Acceptance Criteria:
- Correlation runs in <5 seconds per project
- Confidence score correlates with accuracy
- High-confidence matches (>80) are >95% accurate
- Low-confidence matches (40-60) flagged for review
- Manual overrides persisted and auditable

**8.3 Cost Analyzer**

Purpose: Determine if resource should be cleaned up and estimate savings

Requirements:
- Analysis factors:
  - Monthly cost (from Cost Explorer)
  - Resource utilization (CPU, memory, network)
  - Last activity timestamp
  - Project status (active vs completed)
  - Environment (dev, staging, prod)
  - Dependencies (other resources depend on this)
- Cleanup recommendation:
  ```json
  {
    "should_cleanup": true,
    "confidence": 85,
    "justification": "Dev resource, project completed 94 days ago, <5% CPU, $127/month",
    "estimated_savings": {
      "monthly": 127.43,
      "annual": 1529.16
    },
    "recommended_action": "terminate",
    "require_snapshot": true,
    "risk_factors": {
      "data_sensitivity": "internal",
      "environment": "development",
      "dependencies": []
    }
  }
  ```
- Conservative defaults (prefer safety over savings):
  - Production: never auto-cleanup
  - Has dependencies: never auto-cleanup
  - High data sensitivity: require approval
  - Cost >$1K/month: require approval

Acceptance Criteria:
- Analysis completes in <500ms per resource
- False positive rate <1% (shouldn't cleanup but recommends)
- False negative rate <10% (should cleanup but doesn't)
- Savings estimates within ±10% of actual
- Justification is human-readable

**8.4 ArqOptimize Agent Template**

Purpose: Orchestrate end-to-end cost optimization workflow

Requirements:
- Workflow stages:
  1. **Discover**: Query Jira for completed projects
  2. **Correlate**: Find cloud resources for each project
  3. **Analyze**: Determine cleanup opportunities
  4. **Compile**: Generate intent for each opportunity
  5. **Evaluate**: Policy check + risk scoring
  6. **Authorize**: Get token or approval
  7. **Execute**: Perform cleanup
  8. **Evidence**: Generate evidence packet
  
- Configuration:
  ```yaml
  arqoptimize:
    cleanup_window_days: 90  # Only cleanup projects completed >90 days ago
    risk_thresholds:
      low: 30
      medium: 60
      high: 80
    environments:
      development:
        auto_cleanup: true
        require_snapshot: true
      staging:
        auto_cleanup: false  # Require approval
      production:
        auto_cleanup: false  # Always require approval
    whitelisted_resources:
      - "i-prod-critical-001"
      - "db-prod-main"
  ```
  
- Batch processing:
  - Process up to 100 opportunities per run
  - Throttle API calls to cloud provider
  - Pause between batches (avoid rate limits)
- Dashboard display:
  - Opportunities found
  - Actions taken (auto, approved, denied)
  - Savings achieved (verified from cost data)
  - Evidence packets generated

Acceptance Criteria:
- End-to-end workflow runs in <10 minutes for 100 resources
- Zero unauthorized actions (all have token or approval)
- 100% evidence coverage (every action has packet)
- Savings calculated accurately (±10%)
- Dashboard updates in real-time

---

## BUILD 9: Management UI (Minimal)

### Objective
Basic web interface for policy management, evidence viewing, and agent monitoring.

### Components to Build

**9.1 Policy Editor**

Purpose: Edit and test policies before deployment

Requirements:
- YAML editor with syntax highlighting
- Schema validation (real-time)
- Test runner (run test cases against policy)
- Version history viewer
- Diff viewer (compare policy versions)
- Deployment workflow:
  - Draft → Test → Review → Deploy
  - Rollback option (revert to previous version)

Acceptance Criteria:
- Syntax errors highlighted immediately
- Test runner executes in <5 seconds
- Deployment requires explicit confirmation
- Rollback completes in <10 seconds
- Version history shows who changed what when

**9.2 Evidence Explorer**

Purpose: Search and view evidence packets

Requirements:
- Search filters:
  - Date range
  - Agent ID
  - Action type
  - Risk tier
  - Result (success, failed, denied)
- Evidence detail view:
  - All fields with formatting
  - Verification status
  - Timeline visualization
  - Download as JSON
  - Export to PDF (compliance report)
- Chain visualization:
  - Show evidence chain (previous → current → next)
  - Highlight chain breaks (if any)

Acceptance Criteria:
- Search returns results in <1 second
- Detail view loads in <500ms
- Chain visualization works for 1000+ evidence packets
- PDF export includes all required fields
- Public verification link works correctly

**9.3 Agent Dashboard**

Purpose: Monitor agent status, execution history, and savings

Requirements:
- Agent list view:
  - Agent name, status, last execution
  - Health indicator (green/yellow/red)
  - Actions taken (today, this week, this month)
- Agent detail view:
  - Configuration
  - Execution history (timeline)
  - Savings achieved (cumulative)
  - Evidence packets generated
  - Alerts and errors
- Real-time updates:
  - WebSocket for live execution updates
  - Notifications for important events

Acceptance Criteria:
- Dashboard loads in <2 seconds
- Real-time updates appear within 5 seconds
- Savings calculations accurate
- Health indicators reflect actual agent status
- Execution history paginated (50 per page)

**9.4 Integration Management**

Purpose: Configure and test integrations

Requirements:
- Integration list (available connectors)
- Installation wizard:
  - Select connector
  - Enter credentials
  - Test connection
  - Test permissions
  - Activate
- Connection testing:
  - Run test queries
  - Validate permissions
  - Check rate limits
- Health monitoring:
  - Connection status
  - API call success rate
  - Error rates
  - Rate limit consumption

Acceptance Criteria:
- Installation completes in <2 minutes
- Connection test provides clear pass/fail
- Permission test lists missing permissions
- Health dashboard updates every 60 seconds
- Errors include actionable resolution steps

---

## BUILD 10: Deployment & Infrastructure

### Objective
Production-ready infrastructure with monitoring, security, and scalability.

### Components to Build

**10.1 Kubernetes Deployment**

Purpose: Deploy all services to Kubernetes cluster

Requirements:
- Services to deploy:
  - API Gateway (3 replicas, autoscale 3-10)
  - Policy Engine (3 replicas, autoscale 3-10)
  - Risk Scoring Service (3 replicas, autoscale 3-10)
  - Orchestration Engine (5 replicas, autoscale 5-20)
  - Evidence Vault Writer (3 replicas, autoscale 3-10)
  - Integration Services (2 replicas each)
  - Worker Queue (Celery, 10 workers, autoscale 10-50)
- Kubernetes objects:
  - Deployments (for each service)
  - Services (ClusterIP for internal, LoadBalancer for API)
  - ConfigMaps (configuration)
  - Secrets (credentials, keys)
  - HorizontalPodAutoscalers (CPU-based)
  - NetworkPolicies (service isolation)
  - PodDisruptionBudgets (availability during updates)
- Helm charts for all services

Acceptance Criteria:
- All services deploy successfully
- Health checks pass for all pods
- Autoscaling triggers correctly under load
- Rolling updates complete without downtime
- Resource limits prevent OOM kills

**10.2 Database Setup**

Purpose: Deploy PostgreSQL and Redis with HA

Requirements:
- PostgreSQL:
  - Primary-replica configuration
  - Automated failover (Patroni or RDS Multi-AZ)
  - Connection pooling (PgBouncer)
  - Backup: daily full, continuous WAL archival
  - Retention: 30 days backups
- Redis:
  - Master-replica configuration
  - Sentinel for failover
  - Persistence: RDB + AOF
  - Memory limit: 16GB (adjust based on load)
- Database schemas:
  - evidence_ledger (append-only)
  - policy_graph (JSONB for policies)
  - agent_registry (agent configurations)
  - execution_history (logs)
  - approval_queue (pending approvals)

Acceptance Criteria:
- Failover completes in <30 seconds
- Connection pool handles 1000+ concurrent connections
- Backups complete successfully daily
- Restore from backup works (tested monthly)
- Query performance meets SLAs (<100ms p95)

**10.3 Monitoring & Observability**

Purpose: Monitor system health and performance

Requirements:
- Metrics (Prometheus):
  - Request rate, error rate, latency (RED metrics)
  - Policy evaluations per second
  - Risk scoring latency
  - Evidence writes per second
  - Database connection pool usage
  - Cache hit rate
- Dashboards (Grafana):
  - System overview (all services)
  - API performance
  - Database performance
  - Evidence generation pipeline
  - Cost tracking
- Alerts (Alertmanager):
  - API error rate >1%
  - Policy evaluation latency >100ms (p95)
  - Evidence write failures
  - Database replication lag >10 seconds
  - Disk usage >80%
- Logs (Elasticsearch + Kibana):
  - Structured logging (JSON)
  - Request tracing (OpenTelemetry)
  - Log retention: 90 days

Acceptance Criteria:
- All metrics collected successfully
- Dashboards load in <3 seconds
- Alerts fire within 2 minutes of issue
- Logs searchable in real-time
- Traces show end-to-end request flow

**10.4 Security Hardening**

Purpose: Implement security best practices

Requirements:
- Network security:
  - VPC isolation (control plane, data plane)
  - Security groups (least privilege)
  - Network policies (pod-to-pod restrictions)
  - No public database access
  - API behind WAF (rate limiting, DDoS protection)
- Secret management:
  - Vault for all secrets
  - Encrypted at rest and in transit
  - Automatic rotation (keys, tokens)
  - No secrets in environment variables
  - No secrets in logs
- Authentication:
  - JWT tokens (short TTL)
  - Refresh token rotation
  - MFA for admin access
  - API key for service-to-service
- Audit logging:
  - All API requests logged
  - All policy changes logged
  - All evidence access logged
  - Logs tamper-evident (write-once)

Acceptance Criteria:
- Secrets never exposed in logs or errors
- API requires valid authentication
- Admin actions require MFA
- Audit logs immutable
- Security scan (OWASP) passes

**10.5 CI/CD Pipeline**

Purpose: Automate testing, building, and deployment

Requirements:
- Pipeline stages:
  1. **Lint**: Code style checks
  2. **Test**: Unit tests, integration tests
  3. **Security Scan**: Dependency vulnerabilities, secrets detection
  4. **Build**: Docker images
  5. **Push**: Container registry
  6. **Deploy Dev**: Automatic deployment to dev environment
  7. **Integration Tests**: E2E tests in dev
  8. **Deploy Staging**: Manual approval
  9. **Deploy Production**: Manual approval + smoke tests
- Quality gates:
  - Test coverage >80%
  - No critical vulnerabilities
  - No secrets in code
  - All tests pass
- Rollback strategy:
  - Keep last 5 deployments
  - One-click rollback
  - Automatic rollback on health check failure

Acceptance Criteria:
- Pipeline completes in <10 minutes
- Failed tests block deployment
- Rollback completes in <2 minutes
- All deployments logged and auditable
- Zero-downtime deployments

---

## PHASE 0 COMPLETE: TRUST PROVEN (Month 6)

### Acceptance Criteria

**Functional Requirements:**
- [ ] ArqOptimize agent discovers completed projects in Jira
- [ ] Correlates AWS resources to projects (>80% accuracy)
- [ ] Analyzes cleanup opportunities with cost estimates
- [ ] Compiles cleanup intents deterministically
- [ ] Evaluates policies correctly (0 false positives/negatives)
- [ ] Computes risk scores accurately
- [ ] Issues capability tokens for low-risk actions
- [ ] Requires approval for medium/high-risk actions
- [ ] Executes cleanup actions successfully
- [ ] Generates evidence packets for all actions
- [ ] Evidence verifiable publicly (no metadata leakage)

**Performance Requirements:**
- [ ] Policy evaluation: <30ms p95
- [ ] Risk scoring: <50ms p95
- [ ] Token issuance: <20ms p95
- [ ] Evidence write: <100ms p95
- [ ] End-to-end workflow: <10 minutes for 100 resources
- [ ] API latency: <200ms p95

**Security Requirements:**
- [ ] All keys stored in Vault
- [ ] Keys rotate automatically
- [ ] Tokens are single-use
- [ ] Evidence is immutable
- [ ] Public verification reveals no sensitive data
- [ ] No secrets in logs or errors

**Reliability Requirements:**
- [ ] Uptime: >99% (43 minutes downtime/month)
- [ ] Database failover: <30 seconds
- [ ] Backups: daily, restore tested monthly
- [ ] Error rate: <0.1%

**Compliance Requirements:**
- [ ] SOC 2 audit package generatable
- [ ] Evidence retention: 7 years
- [ ] Audit trail: complete and tamper-evident
- [ ] Data residency: configurable by tenant
- [ ] GDPR-compliant data processing

**Business Requirements:**
- [ ] ArqOptimize saves Gen II $100K+ in first 30 days
- [ ] Evidence packets approved by external auditor
- [ ] Gen II signs annual contract
- [ ] 2-3 additional pilots secured based on demo

---

# DEVELOPMENT WORKFLOW

## For Claude Code

### Starting a New Build

1. **Read this spec section completely**
2. **Create project structure**:
   ```
   arqai-foundry/
   ├── services/
   │   ├── identity/          # BUILD 1
   │   ├── compiler/          # BUILD 2
   │   ├── policy/            # BUILD 3
   │   ├── evidence/          # BUILD 4
   │   ├── risk/              # BUILD 5
   │   ├── orchestration/     # BUILD 6
   │   ├── integrations/      # BUILD 7
   │   └── agents/            # BUILD 8
   ├── api/                   # API Gateway
   ├── ui/                    # BUILD 9
   ├── infrastructure/        # BUILD 10
   ├── tests/
   └── docs/
   ```
3. **Choose testing framework**:
   - Python: pytest
   - Type checking: mypy
   - Integration: pytest + docker-compose
4. **Write tests first** (TDD approach)
5. **Implement to pass tests**
6. **Generate documentation** from code
7. **Create deployment manifests**
8. **Update this spec** with any deviations

### Acceptance Testing

For each build:
1. **Unit tests** (80%+ coverage)
2. **Integration tests** (API contracts)
3. **Performance tests** (latency requirements)
4. **Security tests** (OWASP checks)
5. **Manual testing** (UI/UX validation)

### Quality Gates

Before marking build complete:
- [ ] All tests pass
- [ ] Code reviewed
- [ ] Documentation updated
- [ ] Deployed to dev environment
- [ ] Acceptance criteria verified
- [ ] Performance benchmarks met

---

# SUCCESS METRICS

## Month 6 Demo to Gen II

**Must demonstrate:**
1. Live ArqOptimize workflow execution
2. Evidence packet generation and verification
3. Policy enforcement (show denial of high-risk action)
4. Approval workflow (medium-risk action)
5. Savings dashboard ($100K+ projected annual savings)
6. Audit report generation (SOC 2 format)

**Evidence of success:**
- Gen II signs $500K annual contract
- External auditor approves evidence format
- 2-3 additional pilot customers secured
- Zero security incidents
- Zero data leaks
- Zero policy bypass incidents

**Investor update:**
- Trust core proven in production
- Regulated vertical validated (FinOps)
- $500K ARR secured
- Ready to expand to additional verticals
- Series A trajectory on track

---

# NOTES FOR CLAUDE CODE

## Critical Design Principles

1. **Governance cannot be optional** - Build it into base classes, not as decorators
2. **Evidence is automatic** - Every action MUST generate evidence, no exceptions
3. **Fail-closed** - On ambiguity or error, deny action, don't guess
4. **Deterministic** - Same input must always produce same output
5. **Cryptographically verifiable** - Use proper signatures, not just hashes
6. **Selective disclosure** - Public verification reveals nothing sensitive
7. **Tenant isolation** - Cross-tenant access must be cryptographically impossible

## When in Doubt

- **Security**: Choose more secure option (fail-closed)
- **Performance**: Optimize later, correctness first
- **Features**: Build minimum viable, iterate based on usage
- **Dependencies**: Prefer mature libraries over custom code
- **Testing**: Write tests first, implementation second

## Red Flags (Stop and Ask)

- Non-deterministic behavior in governance paths
- Secrets in logs or error messages
- Policy bypass mechanisms (even "for testing")
- Evidence generation that can be skipped
- Public APIs exposing sensitive metadata
- Cross-tenant data leakage

---

# READY TO BUILD

This specification is complete and ready for implementation by Claude Code. Each build has clear objectives, requirements, and acceptance criteria. Start with BUILD 1 (Identity & Key Management) and proceed sequentially.

Good luck building the ArqAI Foundry.
