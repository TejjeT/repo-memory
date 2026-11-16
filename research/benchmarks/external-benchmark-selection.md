# External Benchmark Selection

Issue #39. Observed 2026-11-11. Each paper's arXiv HTML was downloaded and its
abstract, method, results and limitations sections were read. Data
repositories were **not** opened, so licences of the data itself are
unverified. No model was run. Numbers lost in HTML math rendering are marked
"not legible".

## Candidates: documented

| | SWE-ContextBench | VibeMemBench | RepoComplianceBench | Stale-document poisoning |
|---|---|---|---|---|
| Source | [arXiv 2602.08316](https://arxiv.org/abs/2602.08316) | [arXiv 2609.23570](https://arxiv.org/abs/2609.23570) | [arXiv 2607.26819](https://arxiv.org/abs/2607.26819) | [arXiv 2609.31342](https://arxiv.org/abs/2609.31342) |
| Measures | Reuse of earlier task experience on related tasks | Whether a memory system improves executable coding outcomes | Whether agents find and follow a repository's AI-contribution rules | Whether outdated retrieved evidence overturns a correct answer |
| Size | 1,100 base + 376 related tasks, 51 repositories, 9 languages. Lite: 300 + 99, Python, 12 repositories | 111 targets from 90 repositories; 3,634 history trajectories | 106 issues from 49 repositories | 317 reversals: medicine, law, software, platform policy |
| Task type | Repository bug fix (built on SWE-Bench Lite, Multilingual, Verified) | Repository coding task (SWE-rebench V2 style) | Repository contribution under rules | Question answering |
| Scoring | Tests; resolved rate | Executable tests | Mechanical verifier plus an evidence-bound LLM judge with human rubrics | Answer match against dated official sources |
| Arms in the paper | No context; free and oracle retrieval of trajectories; free and oracle summaries; four memory frameworks (Mem0, OpenViking, LangMem, Supermemory) | Memory off; frozen verified experience injected; irrelevant-memory control; four memory systems | Unaided; extra prompts; rule disclosure; verifier feedback | No retrieval; outdated evidence; up-to-date evidence |
| Headline | Lite, Claude Sonnet 4.5: 26.26% no context; 34.34% oracle summary; oracle summary beats free summary by 12.12 points. Free retrieval gives limited or negative benefit | Injection raises resolution by 1.1–4.5 points on four of five solvers; "all five bootstrap intervals cross zero". Eleven of twelve memory-system pairings fail to exceed the matched baseline | Agents proactively read rule files in 3.5% of runs; refusal and handoff compliance 0% for every agent | Outdated retrieval flips 30% (Llama) and 37% (Qwen) of answers; up-to-date evidence followed in 97–100% of trials |
| Cost stated | $0.53–$0.62 per instance for the memory frameworks | Not found | Not found | Not applicable |
| Code/data location | Not found in the paper text. "we release SWE-ContextBench Lite" | [AlibabaResearch/DAMO-ConvAI, VibeMemBench](https://github.com/AlibabaResearch/DAMO-ConvAI/tree/main/VibeMemBench) | Not found in the paper text | "URLs and capture statuses are retained in the release"; location not found |
| Infrastructure | Clone, checkout, install dependencies, run tests per task | Docker image per target | Sandbox per issue | None beyond a model |
| Supersession, exceptions, scope or access control in tasks | None described | Mentions "stale, conflicting, or irrelevant context" as a control; no supersession structure described | None described | Supersession only (old vs new evidence), with dates |

Two related studies bear directly on our own results:

- [arXiv 2607.27250](https://arxiv.org/abs/2607.27250), "Do Context Files Help
  Coding Agents?": 17 real tasks from 3 repositories, 288 evaluated runs, two
  agents, gold tests. Reports a bounded null on correctness. Its own power
  analysis states a minimum detectable effect of 30 points at that size and
  that detecting a smaller effect "at 80% power requires 120–200 tasks".
  Data: [codeprakhar25/context-files-coding-agents](https://github.com/codeprakhar25/context-files-coding-agents).
- [arXiv 2606.26511](https://arxiv.org/abs/2606.26511), MemStrata: a
  "deterministic (subject, relation, object) supersession rule" applied at
  extraction time, evaluated against plain retrieval. Closest published
  analogue of our supersession semantics. No access control or scope hierarchy
  found by keyword.

## Interpretation

- **No candidate tests what is distinctive here.** None includes exceptions
  that override a named rule, hierarchical scope across repositories, or
  restricted guidance. An external benchmark can answer "does a memory layer
  help agents at all, at an adequate sample size", not "do repo-memory's
  semantics matter".
- **The published results already point the same way as ours.** Benefit
  appears when the right context is selected and compact (oracle summaries),
  and free retrieval or memory systems mostly fail to beat the baseline.
  VibeMemBench could not separate its effect from zero at 111 targets.
- **Sample size is now grounded.** Two independent papers report that about
  100 tasks is not enough for effects of a few points, and one puts the
  requirement at 120–200 tasks. This supersedes the rough per-arm guide
  written in #42.

## Recommendation

1. **For the powered study (#42): SWE-ContextBench Lite**, if its release can
   be located and its licence permits. Reasons: 99 evaluation tasks with
   test-based scoring, an oracle arm already defined, per-instance cost stated
   (about $0.55), and OpenViking, which this project already adapts to, has a
   published result to compare against (29.20% resolved). Its limit is the
   same as above: the "memory" is prior task experience, so repo-memory's
   scope and lifecycle semantics would have nothing to act on. Expect a tie
   with other retrieval paths unless assertions are curated from the base
   tasks, and count that curation cost.
2. **Fallback: VibeMemBench**, whose code location is stated and whose
   protocol already declares memory-on and memory-off conditions.
3. **For supersession with real cases: the stale-document benchmark's software
   and platform-policy items**, as a question-answering complement to #43.
   The per-domain item counts were not legible in the HTML.
4. **RepoComplianceBench is not a fit** as a memory benchmark, but its
   discovery finding (3.5%) matters for design: agents do not go looking for
   rules. Any arm that relies on the agent choosing to call a memory tool
   should expect low use; #32 had to instruct agents to consult it.

## Estimated runs and cost for #42

Using SWE-ContextBench Lite's 99 related tasks and its stated per-instance
cost as a guide only (different models will differ):

| Design | Runs | Rough cost at $0.55 per run |
|---|---|---|
| 4 arms × 99 tasks × 1 repeat | 396 | about $220 |
| 4 arms × 99 tasks × 3 repeats | 1,188 | about $650 |

The base-task context pool (300 tasks) may need to be regenerated or obtained
from the release; that is extra. At 99 tasks the study can detect large
effects only (tens of points). Detecting a few points would need the full
376-task set.

## Open before #42 can be frozen

- Locate the SWE-ContextBench release and confirm its licence.
- Decide whether repo-memory's arm gets curated assertions (and who writes
  them) or only the same experience pool as the other arms.
- Model and budget (deferred by the maintainer).
