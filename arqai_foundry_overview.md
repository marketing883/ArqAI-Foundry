# ArqAI Foundry: System Overview & Architecture
## What Claude Code is Building

---

# THE END RESULT

## What You're Building

An **Enterprise Foundry for Trusted AI** - a platform that enables regulated industries (finance, healthcare, energy, government) to deploy autonomous AI agents with **governance embedded by design**, not bolted on as an afterthought.

Think of it as: **"The operating system for trusted AI agents in regulated environments"**

---

# THE PROBLEM WE'RE SOLVING

## Current State: AI Chaos

Enterprises want to deploy AI agents but face critical barriers:

1. **No Trust**: AI systems are black boxes - CIOs can't explain why an agent made a decision
2. **No Compliance**: Agents bypass existing governance, violating regulations (GDPR, HIPAA, SOC 2)
3. **No Evidence**: When auditors ask "prove this action was authorized and compliant," there's no answer
4. **No Control**: Agents take unauthorized actions because risk assessment happens too late or not at all

**Result**: Promising AI projects stuck in "pilot purgatory" - never reaching production because risk is unacceptable.

---

# OUR SOLUTION

## Three Patented Technologies

We make AI agents trustworthy by embedding three governance technologies into the runtime:

### 1. Trust-Aware Agent Orchestration™

**What it does**: Every action an agent wants to take is risk-scored in context, and authorized with a single-use cryptographic token.

**How it works**:
- Agent requests action: "Terminate idle VM i-abc123"
- System computes risk score based on: data sensitivity, environment (dev/prod), financial impact, compliance requirements
- If risk acceptable: Issue capability token (scoped, time-bound, single-use)
- Agent executes action with token
- System generates immutable evidence packet

**Why it matters**: Eliminates unauthorized actions. Every action is evaluated, authorized, and evidenced.

### 2. Compliance-Aware Prompt Compiler™

**What it does**: Transforms natural language or structured intents into compliance-annotated execution plans, validated against policy before execution.

**How it works**:
- User/Agent submits intent: "Clean up resources from completed Project Phoenix"
- Compiler parses intent into typed schema (strict, no ambiguity)
- Static policy check: Does this violate any rules?
- Dynamic policy check: Given current context (data classification, jurisdiction), is this allowed?
- If passes: Generate Intermediate Representation (IR) with compliance metadata
- IR executes with runtime validation

**Why it matters**: Policy violations are **impossible** - system fails-closed if anything is ambiguous or non-compliant.

### 3. Observability-Driven Adaptive RAG™

**What it does**: Continuously monitors retrieval quality and adapts parameters (chunk size, source weights, embedding refresh) to maintain accuracy.

**How it works**:
- Agent queries knowledge base: "What's the policy for handling PII in EU?"
- RAG retrieves relevant policy documents
- System monitors: retrieval accuracy, user feedback, data drift
- If quality degrades: Automatically adjust chunk sizes, refresh embeddings, re-weight sources
- All within policy constraints (can't access forbidden data sources)

**Why it matters**: Agents stay accurate as data evolves, without manual tuning.

---

# THE ARCHITECTURE

## System Components (High Level)

```
┌─────────────────────────────────────────────────────────────┐
│                      USERS & AGENTS                          │
│  - Data Scientists deploying agents                          │
│  - FinOps teams managing costs                               │
│  - Compliance officers reviewing evidence                    │
│  - Auditors verifying actions                                │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                   CONTROL PLANE (ArqAI SaaS)                 │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌───────────────────┐  ┌────────────────────┐              │
│  │  Identity & Key   │  │  Policy Engine     │              │
│  │  Management       │  │  - Rules           │              │
│  │  - Agent IDs      │  │  - Risk Scoring    │              │
│  │  - Capability     │  │  - Evaluation      │              │
│  │    Tokens         │  └────────────────────┘              │
│  └───────────────────┘                                       │
│                                                               │
│  ┌───────────────────┐  ┌────────────────────┐              │
│  │  Compiler         │  │  Evidence Vault    │              │
│  │  - Intent → IR    │  │  - Append-only     │              │
│  │  - Validation     │  │  - Cryptographic   │              │
│  │                   │  │  - Verification    │              │
│  └───────────────────┘  └────────────────────┘              │
│                                                               │
│  ┌───────────────────────────────────────────────────────┐  │
│  │             Orchestration Engine                       │  │
│  │  Coordinates: Compile → Check → Score → Authorize →   │  │
│  │               Execute → Evidence                       │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                               │
│  ┌───────────────────────────────────────────────────────┐  │
│  │             Management UI                              │  │
│  │  - Policy Editor                                       │  │
│  │  - Evidence Explorer                                   │  │
│  │  - Agent Dashboard                                     │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                               │
└─────────────────────────────────────────────────────────────┘
                            ↓
                   CAPABILITY TOKENS
                  (scoped, single-use)
                            ↓
┌─────────────────────────────────────────────────────────────┐
│              DATA PLANE (Customer VPC - Optional)            │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌───────────────────────────────────────────────────────┐  │
│  │             Agent Runtime                              │  │
│  │  - Executes actions with tokens                        │  │
│  │  - Accesses customer data (stays in VPC)              │  │
│  │  - Sends evidence hashes back (no data leaves)        │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                               │
│  ┌───────────────────┐  ┌────────────────────┐              │
│  │  Cloud APIs       │  │  Data Sources      │              │
│  │  - AWS            │  │  - Databases       │              │
│  │  - Azure          │  │  - File Systems    │              │
│  │  - GCP            │  │  - SaaS Apps       │              │
│  └───────────────────┘  └────────────────────┘              │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

## Key Architectural Decisions

### 1. Control Plane / Data Plane Separation

**Why**: Regulated customers need to ensure their data never leaves their environment.

**How**:
- **Control Plane** (ArqAI hosted): Policy evaluation, risk scoring, token issuance, evidence storage
- **Data Plane** (Customer VPC): Agent execution, data access, cloud API calls
- **Communication**: Control plane sends capability tokens → Data plane uses tokens → Data plane sends evidence hashes back (no actual data)

### 2. Capability Tokens (Zero Trust Authorization)

**Why**: Traditional API keys give broad access. We need fine-grained, time-bound, single-use authorization.

**How**:
- Every action requires a unique token
- Token scope: exactly one resource, one action, with constraints
- Token TTL: 5 minutes maximum
- Token is single-use (can't be replayed)
- Token is cryptographically signed (can't be forged)

**Example**:
```json
{
  "token_id": "tok-abc123",
  "agent_identity": "agent-xyz",
  "scope": {
    "resource": "i-instance123",
    "action": "terminate",
    "constraints": {
      "create_snapshot": true,
      "environment": "development"
    }
  },
  "expires_at": "2025-01-30T10:05:00Z",
  "signature": "..."
}
```

### 3. Immutable Evidence Ledger

**Why**: Auditors need tamper-proof proof that actions were authorized and compliant.

**How**:
- Append-only database (INSERT allowed, UPDATE/DELETE blocked)
- Every action generates evidence packet
- Evidence contains: request, policy version, risk score, token, execution trace, results
- Evidence is cryptographically signed
- Evidence is hash-chained (each packet references previous)
- Public verification API (anyone can verify integrity without seeing sensitive data)

### 4. Selective Disclosure for Privacy

**Why**: Public verification is valuable, but can't leak tenant data or patterns.

**How**:
- Public verification reveals: evidence_hash, signature, verification_url
- Public verification DOES NOT reveal: tenant_id, agent_id, precise timestamp, action details
- Tenant can access full evidence with authentication
- Auditors can access evidence with tenant-granted token
- Cryptographic proof without data disclosure

---

# THE FIRST USE CASE: ArqOptimize

## What We're Building First (Month 1-6)

**Product**: ArqOptimize - Project-aware cloud cost optimization

**Problem**: Enterprises waste 30-40% of cloud spending on "zombie resources" - infrastructure from completed projects that continues running indefinitely because no one remembers to clean it up.

**Solution**: Automatically detect completed projects (via Jira), correlate cloud resources to those projects (via tags and lineage), determine what's safe to cleanup (via risk scoring and policy), and clean up with full audit trail.

**Customer**: Gen II (our first pilot) - $18M/year cloud spend, $5.4M waste

**Value**: $450K/month savings with zero manual effort and 100% audit trail

## User Journey

**Persona**: FinOps Manager at Gen II

**Workflow**:

1. **Setup** (one-time):
   - Connect ArqAI to AWS account (read-only + limited write)
   - Connect ArqAI to Jira (read project status)
   - Configure policy (e.g., "auto-cleanup dev resources from projects completed >90 days ago")
   - Deploy ArqOptimize agent

2. **Automated Execution** (daily):
   - Agent queries Jira: "Which projects completed recently?"
   - Agent queries AWS: "Which resources belong to those projects?" (via tags, lineage)
   - Agent analyzes each resource: "Should we clean this up?"
   - For each cleanup opportunity:
     - Agent compiles intent: "Terminate i-abc123 (dev resource, project completed 94 days ago, $127/month)"
     - System validates against policy
     - System computes risk score: 24 (low risk)
     - System issues capability token
     - Agent executes cleanup (creates snapshot first)
     - System generates evidence packet
   - Dashboard shows: "Terminated 15 VMs, saved $1,905/month, evidence packets generated"

3. **Approval Flow** (for medium-risk):
   - Agent identifies production resource eligible for cleanup
   - System computes risk score: 45 (medium risk)
   - System sends Slack message: "ArqOptimize wants to downsize db-prod-analytics (monthly savings: $2,400). Approve?"
   - FinOps Manager clicks "Approve" in Slack
   - System issues token, agent executes, evidence generated

4. **Audit** (quarterly):
   - Auditor requests: "Prove all infrastructure changes were authorized and compliant"
   - FinOps Manager exports evidence: "Q4 2024 ArqOptimize Actions"
   - Export includes: 347 evidence packets, all cryptographically verified, showing policy compliance
   - Auditor verifies evidence independently (public verification API)
   - Audit passes, no manual work required

## Why This Proves the Thesis

1. **Real ROI**: $5.4M savings over 24 months, paid from savings (not budget)
2. **Regulated Vertical**: FinOps + SOC 2 compliance = perfect fit for trust story
3. **Narrow Scope**: AWS + Jira only, proves concept without building 100 integrations
4. **Reusable Foundation**: Trust core (identity, tokens, evidence) works for any vertical
5. **Auditor Validation**: External auditor confirms evidence meets SOC 2 requirements

---

# SUCCESS METRICS

## Technical Success (Month 6)

- [ ] **Zero unauthorized actions**: Every action has valid capability token
- [ ] **Zero policy bypasses**: Policy violations blocked at compile time
- [ ] **100% evidence coverage**: Every action has immutable evidence packet
- [ ] **Public verification works**: Anyone can verify evidence integrity
- [ ] **Performance SLAs met**: <200ms governance overhead, <1s end-to-end
- [ ] **Zero security incidents**: No key leaks, no data leaks, no token forgery

## Business Success (Month 6)

- [ ] **Gen II contract signed**: $500K annual contract (20% of $2.5M savings)
- [ ] **Savings delivered**: $100K+ verified savings in first 30 days
- [ ] **Auditor approval**: External auditor confirms evidence meets SOC 2 requirements
- [ ] **Additional pilots**: 2-3 new customers signed based on Gen II demo
- [ ] **Reference story**: Gen II willing to be public reference customer

## Product Validation (Month 6)

- [ ] **Trust core proven**: Identity, tokens, evidence work in production
- [ ] **Reusable architecture**: Can extend to new verticals without rebuilding core
- [ ] **Deterministic governance**: Same input always produces same output
- [ ] **Selective disclosure works**: Public verification reveals no sensitive data
- [ ] **Performance acceptable**: Governance overhead doesn't slow operations

---

# USER PERSONAS

## 1. FinOps Manager (Primary User - Month 1-6)

**Goals**:
- Reduce cloud waste without breaking production
- Prove cost discipline to CFO
- Meet audit requirements (SOC 2)

**Needs**:
- Automated cleanup (no manual work)
- Safety guarantees (no production impact)
- Audit trail (evidence of all actions)
- Approval workflows (control over high-risk actions)

**Success Criteria**:
- Monthly cloud bill decreases 30%+
- Zero production incidents from cleanup
- Audit passes with minimal preparation time
- Team understands and trusts the system

## 2. Compliance Officer (Secondary User - Month 1-6)

**Goals**:
- Ensure AI agents comply with policies
- Prepare for audits efficiently
- Demonstrate control to auditors

**Needs**:
- Evidence of policy enforcement
- Audit trail of all actions
- Ability to export compliance reports
- Verification that evidence is tamper-proof

**Success Criteria**:
- Audit preparation time: 3 weeks → 4 hours
- Auditor accepts evidence without manual work
- Zero compliance violations found
- Policy changes reflected immediately

## 3. Platform Engineer (Supporting User - Month 1-6)

**Goals**:
- Integrate ArqAI with existing systems
- Monitor agent health
- Troubleshoot issues

**Needs**:
- Clear integration docs (AWS, Jira)
- Health dashboard (agent status)
- Error logs and debugging tools
- Performance metrics

**Success Criteria**:
- Integration completes in <2 hours
- Health monitoring shows green status
- Issues are debuggable without ArqAI support
- Performance meets SLAs

---

# TECHNICAL REQUIREMENTS

## Functional Requirements

### Core Capabilities
- [x] Cryptographic agent identity (unique per agent)
- [x] Capability token issuance (scoped, time-bound, single-use)
- [x] Policy evaluation (deterministic, <30ms)
- [x] Risk scoring (contextual, multi-factor)
- [x] Intent compilation (typed schema → IR)
- [x] Evidence generation (immutable, signed, hash-chained)
- [x] Public verification (no metadata leakage)
- [x] Approval workflows (Slack integration)

### ArqOptimize Specific
- [x] Jira integration (project lifecycle tracking)
- [x] AWS integration (EC2, RDS, S3, Cost Explorer)
- [x] Resource correlation (tags, lineage, behavioral)
- [x] Cost analysis (estimate savings)
- [x] Cleanup execution (with snapshots)
- [x] Savings tracking (verified from cost data)

## Non-Functional Requirements

### Performance
- Policy evaluation: <30ms (p95)
- Risk scoring: <50ms (p95)
- Token issuance: <20ms (p95)
- Evidence write: <100ms (p95)
- End-to-end workflow: <10 minutes for 100 resources
- API latency: <200ms (p95)

### Scalability
- Support: 100 concurrent agents
- Handle: 1000 actions/minute
- Store: 1M+ evidence packets
- Query: <100ms for evidence by ID

### Reliability
- Uptime: 99% (43 minutes downtime/month)
- Database failover: <30 seconds
- Backup: daily full, continuous WAL
- Restore: tested monthly

### Security
- Keys: HSM-backed, auto-rotated
- Tokens: single-use, cryptographically signed
- Evidence: immutable, tamper-evident
- API: authenticated, rate-limited
- Secrets: Vault-managed, never logged

### Compliance
- Evidence retention: 7 years
- Audit trail: complete, immutable
- Data residency: configurable
- GDPR: compliant data processing
- SOC 2: audit package generatable

---

# WHAT MAKES THIS DIFFERENT

## vs. Traditional Governance Tools

**Traditional**: Governance is separate from execution
- Agent requests action
- Compliance team reviews
- Manual approval (slow)
- No evidence trail
- Policies hard to enforce

**ArqAI**: Governance is embedded in execution
- Agent requests action
- Policy checked automatically (fast)
- Approval only if needed (risk-based)
- Evidence generated automatically
- Policy violations impossible

## vs. Other AI Platforms

| Capability | LangChain | AWS Bedrock | Microsoft Copilot Studio | ArqAI |
|------------|-----------|-------------|--------------------------|-------|
| Governance | Optional | Manual | Basic | **Mandatory** |
| Evidence | None | Logs | Basic | **Cryptographic** |
| Policy Enforcement | External | External | Basic | **Embedded** |
| Audit Trail | Manual | CloudTrail | Basic | **Immutable Ledger** |
| Risk Assessment | None | None | None | **Contextual** |
| Capability Tokens | No | No | No | **Yes** |
| Public Verification | No | No | No | **Yes** |
| Regulated Industries | No | Limited | Limited | **Core Focus** |

---

# THE BUILD PHASES

## Phase 0: Trust Core (Months 1-6) ← YOU ARE HERE

**Goal**: Prove trust in one narrow workflow

**What to Build**:
1. Identity & key management
2. Typed intent + deterministic compiler
3. Policy engine
4. Evidence vault + selective disclosure
5. Risk scoring
6. Orchestration engine
7. AWS + Jira integrations only
8. ArqOptimize agent template
9. Minimal management UI
10. Production infrastructure

**Success**: Gen II saves $100K+ with 100% audit trail, signs annual contract

## Phase 1: Expand Vertically (Months 7-12)

**Goal**: Prove trust core is reusable across verticals

**What to Build**:
- Second vertical (QUEST supply chain)
- Third vertical (Petra Energy predictive maintenance)
- Extract common patterns into Studio
- Policy editor, testing sandbox, evidence explorer

**Success**: 3 verticals live, reusable core validated

## Phase 2: Platform Scale (Months 13-18)

**Goal**: Enable others to build templates

**What to Build**:
- Visual workflow builder
- Integration SDK
- Marketplace
- Partner program
- 50+ templates

**Success**: 100+ customers, ecosystem emerging

---

# FOR CLAUDE CODE

## How to Use This Document

1. **Read this document FIRST** before looking at build specifications
2. **Understand the big picture**: What we're building and why
3. **Understand user journeys**: How people will actually use this
4. **Understand success metrics**: How we know it works
5. **Then read BUILD specifications**: Detailed requirements for each component

## Key Principles to Remember

1. **Governance is mandatory** - Never allow bypassing trust/policy/evidence
2. **Evidence is automatic** - Every action must generate evidence packet
3. **Fail-closed** - On ambiguity or error, deny action
4. **Deterministic** - Same input → same output (no randomness in governance)
5. **Cryptographically verifiable** - Use proper signatures, not just hashes
6. **Selective disclosure** - Public verification reveals nothing sensitive
7. **Tenant isolation** - Cross-tenant access cryptographically impossible

## When Building Each Component

Ask yourself:
- **Does this support the end goal?** (Trust-aware agents for regulated industries)
- **Does this enable the user journey?** (FinOps Manager using ArqOptimize)
- **Does this meet success metrics?** (Zero unauthorized actions, 100% evidence)
- **Could this bypass governance?** (If yes, fix the design)
- **Could this leak sensitive data?** (If yes, fix the design)

## The North Star

Every component you build should contribute to this outcome:

> **"An external auditor reviews evidence from ArqOptimize and confirms it meets SOC 2 requirements without any manual work from the customer."**

That's how we know we've built the right thing.

---

# READY TO BUILD

Now that you understand WHAT we're building, WHY, and HOW it all fits together, you're ready to start implementing the BUILD specifications.

Start with BUILD 1: Identity & Key Management System.

Remember: You're not just building components. You're building the **foundation for trustworthy AI in regulated industries**.

Good luck.
