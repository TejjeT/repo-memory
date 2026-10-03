# Research

This folder tracks the evolving landscape around repository memory, agent memory, coding-agent context, and enterprise engineering context.

The purpose is not to collect vendor links. It is to answer three questions continuously:

1. What is the industry already doing?
2. How do the approaches compare using the same dimensions?
3. Where are the meaningful gaps that repo-memory could explore?

Research should feed product and architecture decisions in the main project.

Last baseline refresh: 2026-10-03

## Research structure

- industry-landscape.md — normalized map of relevant products/projects
- benchmark-framework.md — common dimensions used for comparison
- gap-analysis.md — emerging whitespace and hypotheses
- sources.md — primary documentation and research sources

Future deep dives should go under research/vendors, research/open-source, research/papers, and research/experiments.

## Categories

We currently separate the landscape into five categories:

1. Coding-agent repository memory — systems that explicitly learn or persist repository-specific facts, such as GitHub Copilot Memory and Cursor Memories.
2. Repository instructions / persistent rules — context committed into the repository and loaded by coding agents, such as AGENTS.md, CLAUDE.md, GitHub Copilot instructions, and Cursor rules.
3. Agent memory infrastructure — general-purpose long-term memory platforms such as Amazon Bedrock AgentCore Memory, Letta, and Zep / Graphiti.
4. Context databases / engineering context layers — broader context systems such as OpenViking and Sourcegraph-style code context.
5. Research systems — work on memory extraction, temporal memory, hierarchical retrieval, provenance, consolidation, context selection, and evaluation.

## Research method

For every system we evaluate:

1. Prefer primary documentation or papers.
2. Record the observation date.
3. Separate documented behavior from our inference.
4. Classify it using the same benchmark dimensions.
5. Identify the primary abstraction: instruction, fact, event, conversation, graph, document/resource, engineering decision, or preference.
6. Ask what happens when the repository changes, a fact becomes stale, two memories conflict, the caller loses access, context spans multiple repositories, or another agent wants to consume the memory.

## Important principle

The benchmark is not intended to prove repo-memory is superior.

If an existing system solves the problem well, we should adopt the idea, integrate with it, or narrow repo-memory's scope.

The useful output of research is clarity, not competitive theater.
