# Policy-routing study (issue #5)

Status: fixture, evaluator and command-collection path. **No measured model
batch has been collected.** The tests use an explicit synthetic worker that
emits a known solution; its passes validate the harness, not memory benefit.

## Question and task

Does deterministic scope/lifecycle/override resolution improve policy
implementation beyond a strong ordinary-document baseline?

Implement retry ownership for three repositories. A current settlement
default supersedes historical dual-layer retries; an approved, dated
clearing-adapter exception overrides the default for that repository alone.
A current analytics rule belongs to another system. The generic settlement
plumbing and neutral starting policy contain no stale-policy comments,
assertion IDs, repository-to-policy mapping or expected solution.

This is an explicitly **synthetic** operational decision. Unlike the prior
one-constant fixture, code alone cannot establish which organizational
decision applies. It tests configuration implementation and downstream
settlement behavior, not arbitrary large code changes or production utility.
It does not satisfy #8's separate human-annotation study.

## Predeclared comparison

Three assigned trials per arm, all using the same worker command and
operator-declared model, fresh processes/workspaces, a fixed randomized
schedule (seed 20261016), 180 seconds per trial and at most eight tool calls.
The worker adapter owns fresh model sessions and must not resume history.
Model-internal turns/sampling are unknown unless recorded by the adapter;
the runner's tool limit is not a claim about unobserved model generations.

| Arm | Delivered input |
|---|---|
| repo-only | Same task, output contract and three fixture files |
| generic-retrieval | Above + complete permitted ordinary corpus |
| repo-memory | Above + the same corpus + authenticated live MCP reads |

The generic arm is an **oracle-document baseline**: no retrieval miss can
starve it of the current rule or exception. Memory has additional structured
representations of the same policy facts and additional transport overhead.
Token/latency differences must be reported, not hidden. A tie is plausible
and valid. This experiment does not benchmark a semantic retrieval model.

`corpus.md` maps all permitted assertions to ordinary sources. Both arms
have the same dates, scope, supersession and exception facts. Private
incident background exists only in the server-side assertion snapshot;
permitted conclusions remain usable with provenance/rationale redacted.

## Outcome and evidence gates

Primary outcome is passes / **assigned** trials, including failures,
timeouts and incomplete collection. Report completed counts separately.
A valid explicit abstention is completed but unsolved. Invalid protocol,
nonzero exit, missing receipt, drift or unauthorized citations cannot pass.
The memory arm must actually receive at least one successful MCP response
to qualify; a correct patch without MCP use remains recorded but fails
this protocol qualification. Transport failures therefore count against
end-to-end reliability, not just policy implementation.

`rubric.py` applies only the replacement policy.py in a temporary fixture
copy. Deterministic checks cover exact ownership for all repositories,
unknown-repository rejection, happy path, two transient failures,
ambiguous post-commit response loss, permanent errors and retry exhaustion.
Observed call identity, settlement count, actual response and exercised
gateway retries are checked. Seven known-invalid patches plus the neutral
starting fixture fail. No LLM scores the output.

## Run with an actual worker adapter

Requires the repository's Python 3.11+ environment with `.[dev]` installed.
Use an absolute executable/script path. The adapter implements the JSONL
contract below and invokes the chosen model; the runner does not contain a
model provider or credentials. Keep credentials in the adapter's environment,
never in argv, output or bundle files.

```bash
python research/experiments/policy-routing/run.py prepare /tmp/routing-study-01 \
  --worker-command '["/absolute/path/to/python", "/absolute/path/to/model_adapter.py"]' \
  --model 'provider/model-version'
python research/experiments/policy-routing/run.py run /tmp/routing-study-01
python research/experiments/policy-routing/run.py score /tmp/routing-study-01 > /tmp/routing-study-01/report.json
```

Do not point `prepare` at an existing directory. `run` resumes only unissued
trials; it cannot overwrite a started workspace or receipt. A trial
interrupted before its receipt is explicitly incomplete and requires a new
study ID for recollection. Do not retrofit a receipt or replace a failure.
`score` exits nonzero unless every assigned trial passes; a nonzero study
result is legitimate evidence, not an instruction to repair the receipts.

### Built-in fresh-agent bridge

`bridge.py` forwards a worker's mailbox JSON to the same collector protocol.
The parent starts collection, records an actual built-in `spawn_agent` request
and response in `agent.json`, and supplies that registration before forwarding
worker output. `builtin-agent.json` freezes the common prompt, requested
`gpt-6.1-sol` model and `fork_turns: none`; only the mailbox path changes.
Pass this configuration to `prepare(..., agent_config=config)` in Python.
The parent must never supply a candidate answer or rewrite worker messages.

The bridge records agent/trial IDs and exact forwarded message hashes;
collection receipts bind registration and bridge records. Score checks the
prompt against its frozen template, requested model/history settings, and
message/transport linkage. These are operator-observed records, not independent
provider attestations. Agents share tools and filesystem access and are
instructed to use only their assigned mailbox; this is procedural isolation.
Token usage, cost, resolved model version and internal reasoning settings are
unexposed unless reported by the platform.

### Worker adapter contract

The runner starts a new command process in a new workspace for each trial.
Read one JSON job from stdin. It contains task, exact fixture contents,
documents, available tools and the output contract. Supply only this context
to a fresh model session. No evaluator, assertion JSON or experiment history
is passed to the worker. Model/provider setup outside this job is the
adapter's responsibility and must be documented for the real batch.

Write a single JSON object per stdout line, flushing immediately:

```json
{"type":"tool_call","name":"memory_search","arguments":{"repository":"clearing-adapter"}}
```

Read one JSON `tool_result` from stdin after each request. `memory_search`
accepts one target repository; `memory_get` accepts an `assertion_id`.
The collector supplies a per-trial credential to the frozen server, binds
the caller to `doc://` grants, and records the actual stdio tool exchange.
The worker cannot choose identity, grants or credentials.

Finish with one `final` object containing complete `code` and `citations`
(a list of delivered document URIs/assertion IDs), or an `abstain` object
with `reason` and `citations`. Optional `metadata` can record provider
execution ID, exact model/version, sampling, usage and cost; these remain
explicitly worker-reported. Diagnostic output belongs on stderr. Exit zero
after the terminal response. Malformed/trailing stdout is a protocol failure.

## Frozen inputs and collection artifacts

`prepare` snapshots the fixture, corpus, assertions, server, evaluator,
runner, core package and schema; hashes them before invocation; and records
Git revision/dirty state, Python/MCP versions, command file hashes, model
declaration, schedule and limits. Every job is checked against its frozen
payload, so rehashed metadata cannot omit supplemental documents.

Each trial has its own opaque trial/execution IDs, workspace, invocation
record (including process ID), exact `worker.stdin`/`worker.stdout`, stderr,
MCP stderr, transport log, terminal response and collection-hook receipt.
Receipts bind the manifest, job and exact artifacts. Score verifies the
snapshot, file set, timing window, identities, tool-request/output linkage,
delivered responses and citations before outcome checks. Full delivered
context/tool responses and raw output are scanned for restricted markers.
Elapsed wall time and delivered byte counts are measured; token/cost/model
details stay unknown unless the adapter supplies them.

These are reproducible artifact bindings, not independent execution
attestations. Fresh cwd/process is not a filesystem/network sandbox, and
the runner cannot inspect a remote model's hidden session state. Run adapters
in an appropriate isolated execution environment for a blinded study and
retain provider/session creation records. Do not claim machine-proven
blinding from a job hash or a process ID alone.

The historical Java/retry/supersession artifacts are preserved. A future
measured batch must publish raw failures, the complete frozen bundle, all
nine assigned outcomes and a bounded interpretation. No improvement over
ordinary retrieval has been demonstrated by this new scaffold.
