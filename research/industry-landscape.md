# Industry Landscape

Baseline observed: 2026-10-03

This is an initial normalization of systems that overlap with repo-memory.

## Snapshot

| System | Primary abstraction | Repo-aware | Cross-repo / org | Provenance / freshness | Agent-neutral |
| --- | --- | --- | --- | --- | --- |
| GitHub Copilot Memory | learned repo facts + user preferences | strong | repo facts limited to same repo | code citations + branch validation + TTL | no |
| Cursor Memories | generated project rules | strong | repo/project scoped | human approval; limited documented provenance | no |
| AGENTS.md / repo instructions | committed instructions | strong | manual | Git history | relatively strong |
| Bedrock AgentCore Memory | short/long-term agent memory records | indirect | namespaces/actors | configurable retention/strategies | API-level |
| Zep / Graphiti | temporal context graph | indirect | strong general model | temporal graph + source episodes | yes |
| Letta | persistent agent memory blocks | indirect | shared blocks possible | persistent structured blocks | yes |
| OpenViking | context database: resources + memory + skills | strong context model | broad hierarchical context | session extraction + directory model | yes |
| Sourcegraph Cody/context | live code context/search | very strong | strong remote code search | source is live code | product-specific |

## GitHub Copilot Memory

GitHub's current Copilot Memory public preview is the closest direct benchmark.

Documented behavior includes repository-level facts such as coding conventions, architectural decisions, build commands, and project-specific rules; user-level preferences; repository facts shared with users who have access to memory for that repository; facts stored with citations to supporting code; citations checked against the current branch before a fact is used; unused memories automatically deleted after 28 days; and repository owners able to inspect and delete stored repository facts.

Important boundary: repository-level facts are documented as usable only in operations on the same repository.

Why it matters to repo-memory: it validates learned repository facts, provenance, revalidation, stale-memory handling, and cross-surface reuse. It also means that a project that only implements vector search over learned repo facts is not differentiated.

Potential areas to explore beyond the documented Copilot model include organization/domain/system-level memory, cross-repository relationships, agent-neutral interfaces, explicit approval workflows, richer provenance beyond code citations, supersession/contradiction semantics, and an open schema.

Sources:
- https://docs.github.com/en/copilot/concepts/agents/copilot-memory
- https://docs.github.com/en/copilot/how-tos/use-copilot-agents/copilot-memory/manage-for-yourself

## Cursor Memories and Rules

Cursor documents project rules plus automatically generated memories. Project rules are version-controlled and can be global, path-attached, agent-requested, or manually invoked. Cursor Memories are generated from conversations and scoped to the Git repository. Cursor describes a sidecar model that observes conversations and proposes memories; background-generated memories require user approval before being saved.

This is a strong precedent for the flow: agent discovers context, proposes memory, human approves.

Sources:
- https://docs.cursor.com/context/rules
- https://docs.cursor.com/en/context/memories

## AGENTS.md and repository instruction files

Coding agents increasingly consume persistent instruction files. OpenAI Codex documents hierarchical AGENTS.md discovery from global configuration through repository directories, with deeper instructions overriding earlier ones. GitHub Copilot also supports repository-wide, path-specific, and agent instruction files.

This demonstrates that hierarchical scope is already useful for coding-agent context. However, instruction files are usually human-authored, checked into source control, and awkward for private, cross-repo, or automatically learned context.

Sources:
- https://developers.openai.com/api/docs/guides/latest-model
- https://docs.github.com/en/copilot/how-tos/copilot-on-github/customize-copilot/add-custom-instructions/add-repository-instructions

## Amazon Bedrock AgentCore Memory

AgentCore Memory separates short-term raw interactions from long-term extracted records. Long-term memory uses configurable strategies such as semantic, summarization, preferences, episodic, or custom strategies. Memory can be organized with actor, session, strategy, and namespace concepts.

This is a strong general-purpose benchmark for extraction pipelines, memory strategies, namespace organization, and retention, but it is not repository-specific by default.

Sources:
- https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/how-it-works.html
- https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/memory-strategies.html
- https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/memory-organization.html

## Zep / Graphiti

Zep positions itself as a governed enterprise context layer using temporal Context Graphs. Graphiti emphasizes incremental updates, temporal relationships, historical context, and hybrid semantic/keyword/graph retrieval.

This is highly relevant to contradiction, history, and supersession research. repo-memory should not assume it needs a knowledge graph, but Graphiti is a mature benchmark for what temporal relationships can provide.

Sources:
- https://help.getzep.com/overview
- https://help.getzep.com/v2/understanding-the-graph
- https://github.com/getzep/graphiti

## Letta

Letta focuses on stateful agents. Its memory blocks are persistent structured sections of agent context and can be attached to agents. This is useful as a benchmark for always-visible core memory, mutable persistent agent state, and memory sharing/attachment models.

Sources:
- https://docs.letta.com/
- https://docs.letta.com/v1-sdk/memory/memory-blocks

## OpenViking

OpenViking is particularly relevant because it frames the problem as a context database rather than only an agent memory store. It organizes resources, memories, and skills through a filesystem-like hierarchy with viking URIs. It supports layered summaries, directory-aware retrieval, and coding-agent integrations including Claude Code, Codex, Cursor, and MCP.

OpenViking overlaps with several repo-memory ideas: remote context service, hierarchy, progressive context loading, coding-agent integration, memory plus repository resources, and retrieval scope before vector ranking. This deserves an early deep dive.

Sources:
- https://openviking.ai/docs
- https://openviking.ai/learn/
- https://github.com/volcengine/OpenViking

## Sourcegraph

Sourcegraph's coding context stack demonstrates a different approach: derive context from a powerful live code index rather than storing learned repository memories. Cody can retrieve context across local and remote codebases using code search.

This gives us an important control question: before storing something as memory, can strong live retrieval reconstruct it reliably? If yes, storing an additional durable fact may only create staleness risk.

Source:
- https://sourcegraph.com/docs/cody

## Initial pattern

The market appears to be converging around persistent instructions, learned facts, event-derived long-term memory, hierarchical namespaces, semantic retrieval, human control, provenance validation, and context assembly across tools.

repo-memory should not compete by merely reimplementing those primitives. Its strongest potential contribution is a specifically engineering-oriented memory contract spanning repository, system, and organization boundaries.
