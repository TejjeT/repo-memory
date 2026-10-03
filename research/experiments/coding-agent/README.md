# Coding-Agent Evaluation Experiment

Status: initial design  
Created: 2026-10-03

## Objective

Use one or more coding agents as real consumers of repo-memory.

The goal is to measure whether durable Engineering Assertions improve an agent's implementation when the required context is **not fully available in the active repository**.

The experiment is intentionally vendor-neutral. Any coding agent that can work in the target repository and consume the same retrieval interface may participate.

## Hypothesis

A coding agent with access to repository source alone may produce a locally reasonable but organizationally incorrect change.

The same agent with access to repo-memory should retrieve durable engineering constraints and produce a more policy-compliant implementation.

## Experiment structure

Run the same coding task under three conditions.

### A. Repository only

The agent receives:

- target repository
- task description
- normal repository files

No repo-memory access.

### B. Repository + live retrieval

The agent receives:

- target repository
- task description
- normal repository files
- ordinary searchable reference material

No durable Engineering Assertions.

### C. Repository + repo-memory

The agent receives:

- target repository
- task description
- normal repository files
- repo-memory access

Relevant Engineering Assertions should be discoverable.

## Primary scenario

Target repository:

`payment-worker`

Task:

> Add retry handling for settlement submission failures.

Relevant durable context:

- `EA-002` — idempotency keys must survive gateway, queue, and worker retry boundaries
- `EA-006` — retry must exist at exactly one orchestration layer; gateway and client retries must not both be enabled

The active repository should not independently contain enough history to fully explain both rules.

## Expected failure without engineering memory

A reasonable coding agent may:

- add a new retry loop locally
- regenerate request metadata
- duplicate retry behavior already performed elsewhere
- miss the incident-derived idempotency constraint

The code may look locally correct while violating system-level guidance.

## Expected behavior with repo-memory

The agent should:

1. retrieve the relevant assertions
2. surface their engineering meaning
3. preserve idempotency metadata
4. avoid introducing duplicate retry layers
5. reference permitted provenance when explaining the implementation

## Secondary scenario

Target repository:

`legacy-settlement`

Task:

> Upgrade the service to the current enterprise Java runtime.

Relevant durable context:

- `EA-001` — enterprise Java 25 policy
- `EA-003` — approved exception allowing legacy-settlement to remain on Java 17 until retirement milestone M-2027-01

Expected result with repo-memory:

- the agent should not blindly upgrade the runtime
- it should surface the approved exception and review date

## Supersession scenario

Task:

> Configure gateway retries for settlement calls.

Relevant durable context:

- `EA-005` — historical retry guidance
- `EA-006` — current guidance superseding EA-005

Expected result:

- EA-006 is treated as current
- EA-005 is not presented as active guidance

## Authorization scenario

Caller:

`external-integrations` user with access to `payment-api` only.

Task:

> Explain the settlement retry rule.

Expected behavior:

- only assertions the caller may discover/read enter the candidate set
- restricted provenance is redacted where policy allows the approved conclusion to be shared
- inaccessible assertions must not influence ranking

## Metrics

Record for each run:

- task completion success
- engineering-policy violations
- repeated failed approaches
- relevant assertions retrieved
- irrelevant assertions retrieved
- stale/superseded assertions used
- provenance cited correctly
- number of agent turns
- approximate context usage
- implementation diff quality
- human reviewer judgment

## Scoring

Do not create a single opaque score initially.

Capture raw outcomes first.

Suggested fields:

```yaml
condition:
task:
agent:
model:
repo_revision:
memory_revision:
completed:
policy_violations:
assertions_expected:
assertions_retrieved:
assertions_missed:
stale_assertions_used:
provenance_used:
turns:
notes:
```

## Operating prompt

Start the coding agent in the target repository and use a prompt similar to:

```text
Read the repository instructions first.

Implement retry handling for settlement submission failures.

Before making changes, inspect all relevant engineering constraints available
to you. Do not assume repository-local behavior is the complete system policy.

Keep the change minimal and explain any cross-repository or organizational
constraint that changes your implementation.
```

For the repo-memory condition, the agent should have access to the same repo-memory MCP or equivalent retrieval interface.

## Cross-agent comparison

Once the experiment works with one agent runtime, repeat it with at least one other agent runtime using:

- the same repository revision
- the same task prompt
- the same Engineering Assertions
- the same retrieval interface
- the same evaluation template

The purpose is not to rank agents. The purpose is to test whether the memory contract remains portable across agent runtimes.

## Exit criterion

The experiment is successful when we can run the same task under at least two conditions and show whether Engineering Assertions materially changed:

- implementation correctness
- policy compliance
- engineering reasoning

A positive result is useful.

A negative result is also useful: it may show that live retrieval is sufficient and durable memory adds little value for that class of task.
