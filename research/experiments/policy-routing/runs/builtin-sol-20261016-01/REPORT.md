# Policy-routing: built-in Sol batch 2026-10-16

Nine actual fresh built-in worker trials completed: **repository only 0/3,
generic retrieval 3/3, repo-memory 3/3**. All repository-only workers explicitly
abstained because the organizational policy was unavailable. Complete policy
documents and documents plus memory tied on correct implementation. This is
exploratory evidence of context value on one synthetic task; it demonstrates
no incremental coding benefit from repo-memory over complete documents.

## Results and measurements

| Arm | Completed / assigned | Passed / assigned | Abstentions | MCP calls | Median end-to-end seconds | Delivered JSONL bytes, r1/r2/r3 |
|---|---|---|---|---|---|---|
| repo-only | 3/3 | 0/3 | 3 | 0 | 32.97 | 5381, 5381, 5381 |
| generic-retrieval | 3/3 | 3/3 | 0 | 0 | 29.92 | 7878, 7878, 7878 |
| repo-memory | 3/3 | 3/3 | 0 | 3 | 52.56 | 9268, 9268, 9268 |

Every receipt/evidence check passed; there were no timeouts, protocol failures,
missing trials or replacement runs. All six submitted policies pass the exact
ownership/unknown-repository checks and all 15 downstream settlement scenarios.
Abstention is complete but unsolved under the predeclared primary outcome; it
is not an incorrect implementation. No matches for the four predefined
restricted markers occurred in any delivered job, MCP response, citation or
raw worker output. This marker scan is not a general noninterference proof.

Times cover collector start through receipt capture, including parent scheduling,
registration, model/tool work and process shutdown. They are not pure model
latency or a causal speed comparison. Memory delivered 1,390 more JSONL bytes
per trial than the document arm. Bytes are not token counts; token usage and
cost were unexposed. MCP call counts exclude mailbox I/O and hidden model turns.

## Assigned schedule and attribution

| Order | Trial / receipt | Observed built-in agent name | Outcome | Seconds | MCP calls | Collector execution ID |
|---|---|---|---|---|---|---|
| 1 | [repo-memory-r2](trials/repo-memory-r2/receipt.json) | /root/measured_trial_01 | passed | 43.51 | 1 | `973e4bcf-a13b-4189-802f-970efbaef515` |
| 2 | [generic-retrieval-r3](trials/generic-retrieval-r3/receipt.json) | /root/measured_trial_02 | passed | 29.92 | 0 | `2472e4f5-a894-42eb-9795-a9927d3a6bf4` |
| 3 | [repo-only-r1](trials/repo-only-r1/receipt.json) | /root/measured_trial_03 | abstained; unsolved | 43.33 | 0 | `2fc668e5-ce18-465c-beaa-0a85aaf3f6f0` |
| 4 | [repo-only-r2](trials/repo-only-r2/receipt.json) | /root/measured_trial_04 | abstained; unsolved | 32.72 | 0 | `e60e6e66-ec3d-423c-a3b1-89c4870db49b` |
| 5 | [generic-retrieval-r1](trials/generic-retrieval-r1/receipt.json) | /root/measured_trial_05 | passed | 49.24 | 0 | `c52a9f90-f27a-4ac8-bc61-5ce9bff2d36a` |
| 6 | [repo-memory-r3](trials/repo-memory-r3/receipt.json) | /root/measured_trial_06 | passed | 56.18 | 1 | `9257a655-de69-445d-8485-1fd3984638a9` |
| 7 | [generic-retrieval-r2](trials/generic-retrieval-r2/receipt.json) | /root/measured_trial_07 | passed | 29.88 | 0 | `d8623cba-05ec-457b-ad1a-1ac2fdc473f4` |
| 8 | [repo-memory-r1](trials/repo-memory-r1/receipt.json) | /root/measured_trial_08 | passed | 52.56 | 1 | `04a3e514-3e59-4c37-a34a-ff792759790b` |
| 9 | [repo-only-r3](trials/repo-only-r3/receipt.json) | /root/measured_trial_09 | abstained; unsolved | 32.97 | 0 | `495f28ca-6802-4509-9d78-be7273662a94` |

The requested model was `gpt-6.1-sol` in every observed `spawn_agent` call,
with `fork_turns: none` and no reasoning override. Each call returned the
canonical task name recorded in that trial's `agent.json`. Actual resolved
model version, effective reasoning/sampling settings, model-internal turns,
provider request IDs, token counts and cost were not exposed. Canonical agent
names are platform-observed task identities, not independent provider IDs.

Each `agent.json` contains the exact common-template request, a timestamp
before the request, the subsequently observed tool response and its observation
time. The collector's terminal hook bound that registration, bridge audit,
raw stdin/stdout, per-trial MCP log, invocation and final response into its
receipt. `bridge.jsonl` binds each exact forwarded JSONL message to the
agent/trial; the collector owns actual MCP execution and credential injection.
The parent supplied no candidate code and did not rewrite worker messages.

## Frozen inputs and isolation limits

Source revision: `f2281fd98ca5c1f2941b9b67d67d1ecc0cacb38c`, clean at preparation.
The [manifest](manifest.json) fixes 21 source/schema/fixture files, nine opaque
trial IDs and exact jobs, common worker prompt/model configuration, command
hashes, a randomized schedule (seed 20261016), 180 seconds per trial and eight
MCP requests maximum. Manifest SHA-256:
`83af842d63fa8ba06e1e879072150d9310aaf34fc44f26ea14d324a5fc651e7e`.

Both retrieval arms received the complete, identical permitted ordinary corpus;
this is an oracle-document baseline. Memory also offered authenticated structured
assertions of those same facts. The common job instruction required a supplied
tool to be consulted before completion. All memory workers made one successful
`memory_search(clearing-adapter)` call and received the active approved exception.
All six final patches cited the delivered current-rule and exception documents.

Fresh workers were requested without this conversation's history and instructed
to read only their assigned mailbox. They shared filesystem/tool access; there
was no filesystem sandbox or independent access audit. The orchestrator knew
the expected solution. The stored prompt and requested session setting support
procedural separation; hashes and process IDs do not prove machine-enforced
blinding, model identity or hidden-session freshness. This is a small synthetic
configuration task, not a real-repository pilot or statistically powered study.

## Separate boundary diagnostic

The coding workers queried only the exception, so this measured batch did not
directly exercise the current assertion's mixed-provenance redaction. Do not
infer that coverage from zero marker matches. After collection, an operator-driven
[diagnostic](boundary-diagnostic/report.json) used the same frozen MCP server/core:

- Default search returned only current guidance, withholding historical/private assertions.
- Exception search returned only the applicable approved exception.
- Explicit historical get retained superseded status.
- Search/get of the current rule retained its permitted conclusion and redacted private provenance/rationale.
- Private and nonexistent gets produced identical generic error content.
- All six responses had no restricted-marker matches.

All six diagnostic checks passed. Its real MCP responses, timestamps, manifest
binding and stderr hash are preserved. The exact executed source is saved as
[probe-source.txt](boundary-diagnostic/probe-source.txt), matching the report's
source hash. [boundary_probe.py](../../boundary_probe.py) supplies the same
behavior with a subsequent style-only context-manager simplification. This
diagnostic was added after the
model batch; it is not a model trial, collection-time agent behavior, or part of
the primary denominator. No original job, source snapshot or receipt was changed.

## Decision and next work

Keep repo-memory as a deterministic policy/reference layer with a thin read-only
transport. This study provides no reason to expand it into a broader memory
platform or claim superiority to ordinary retrieval. Close #5's bounded revised
study with this negative/tied incremental result and the stated evidence limits.

Next, #29 should reconcile the roadmap and historical protocols with delivered
work and this result. Then #8 should collect human-labeled real engineering
cases where durable context is difficult to reconstruct. Select a narrowly
scoped real-repository pilot only if those cases establish a concrete need;
keep governed lifecycle mutations (#3) deferred until selected. Preserve the
historical Java/retry/supersession reports, including the incomplete #27 trial.

## Replay and artifacts

The original collection bundle was copied byte-for-byte, excluding only Python
bytecode caches. A relocated replay exactly matches [report.json](report.json).
[metrics.json](metrics.json) contains descriptive aggregates; [artifact-index.json](artifact-index.json)
is a post-collection integrity inventory, not an execution attestation.

From the repository root with Python 3.11+ and `.[dev]` installed:

```bash
BUNDLE=research/experiments/policy-routing/runs/builtin-sol-20261016-01
python "$BUNDLE/snapshot/experiment/run.py" score "$BUNDLE" > /tmp/routing-replay.json
```

Exit status **1 is expected** because repository-only assigned trials did not
solve the task. Compare the parsed JSON with the committed report. Collection
cannot overwrite started trials. Original absolute workspace/interpreter paths
remain in invocation records for historical fidelity; score supports relocation.

To repeat the separately labeled diagnostic without replacing its saved output:

```bash
python research/experiments/policy-routing/boundary_probe.py "$BUNDLE" /tmp/new-routing-boundary-check
```

Code validation: Ruff and the full 275-test suite. Harness synthetic workers
remain explicitly test-only; none of their outputs are counted in this batch.
