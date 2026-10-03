# Contributing

repo-memory is an early-stage exploration of durable engineering memory for software repositories and AI agents.

Contributions are welcome, especially when they challenge the assumptions in the design.

## Useful contributions

- concrete examples of repository context that agents repeatedly miss
- counterexamples where memory creates risk or noise
- proposals for permission-aware retrieval
- memory lifecycle designs
- evaluation methods
- small reference implementations
- MCP integrations
- GitHub workflow experiments
- approaches for stale or contradictory memory

## Design philosophy

Please prefer the smallest mechanism that can test an idea.

In particular, avoid adding infrastructure simply because it is common in AI architectures. A vector database, knowledge graph, event stream, or agent framework should earn its place through a demonstrated requirement.

## Issues

For design discussions, open an issue describing:

1. the engineering scenario
2. the context an agent currently lacks
3. why the source repository alone is insufficient
4. what durable memory would change
5. potential risks or failure modes

## Pull requests

Keep PRs narrow and explain the architectural reason for the change.

When introducing a dependency or subsystem, include the use case that requires it.

## Principle

The project should optimize for **useful durable context**, not maximum stored context.
