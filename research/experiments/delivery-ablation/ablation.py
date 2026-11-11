"""Model-free context-delivery ablation.

Question: which parts of repo-memory's deterministic resolution can an
ordinary, well-configured retrieval path reproduce with flat metadata
filters, and which parts need relation-following?

Everything here is synthetic and deterministic. No model is called. The
ground truth comes from the generator's own construction records, never
from ``repo_memory.policy``. See README.md for limits.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import re
import statistics
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from repo_memory.models import (  # noqa: E402
    EngineeringAssertion,
    Provenance,
    Scope,
    Target,
)
from repo_memory.policy import ResolutionContext, resolve_assertions  # noqa: E402

NOW = datetime(2026, 11, 1, tzinfo=UTC)
ORG = "acme"
TOPIC_A = ["retry", "timeout", "runtime", "logging", "schema", "cache", "queue", "auth"]
TOPIC_B = ["ownership", "budget", "version", "format", "migration", "limit", "rotation"]
ROLES = ["api", "worker", "gateway", "batch"]


@dataclass(frozen=True, slots=True)
class Config:
    """Generator parameters. All probabilities are per construction step."""

    seed: int = 0
    domains: int = 4
    systems_per_domain: int = 4
    topics: int = 40
    queries: int = 400
    p_unflipped: float = 0.3
    p_exception: float = 0.25
    p_complement: float = 0.3
    p_target: float = 0.3
    p_restricted: float = 0.15


@dataclass(frozen=True, slots=True)
class Doc:
    """One assertion plus the flat metadata an ordinary index would hold."""

    assertion: EngineeringAssertion
    topic: str
    restricted: bool
    text: str


@dataclass(frozen=True, slots=True)
class Query:
    scope: Scope
    topic: str
    text: str  # topic words only; used when scope is a structural filter
    scoped_text: str  # topic plus scope words; used when it is not
    cleared: bool
    required: frozenset[str]
    tags: frozenset[str]


@dataclass(frozen=True, slots=True)
class World:
    docs: tuple[Doc, ...]
    queries: tuple[Query, ...]

    def digest(self) -> str:
        payload = json.dumps(
            [[d.assertion.id, d.text, d.assertion.status] for d in self.docs]
            + [[q.text, sorted(q.required), sorted(q.tags), q.cleared] for q in self.queries]
        )
        return hashlib.sha256(payload.encode()).hexdigest()


# --------------------------------------------------------------------------
# Generator. Ground truth is recorded while building, per (repository, topic).
# --------------------------------------------------------------------------


def generate(config: Config) -> World:
    rng = random.Random(config.seed)
    systems = [
        (f"dom{d}", f"sys{d}x{s}")
        for d in range(config.domains)
        for s in range(config.systems_per_domain)
    ]
    repos = [(dom, sys_, f"{sys_}-{role}") for dom, sys_ in systems for role in ROLES]
    all_topics = [f"{a}-{b}" for a in TOPIC_A for b in TOPIC_B]
    topics = rng.sample(all_topics, config.topics)

    docs: list[Doc] = []
    required: dict[tuple[str, str], set[str]] = defaultdict(set)
    tags: dict[tuple[str, str], set[str]] = defaultdict(set)
    # Successors of unflipped revisions: if a caller cannot see one, nothing
    # visible names its predecessor as superseded.
    links: dict[tuple[str, str], set[str]] = defaultdict(set)
    counter = 0

    def add(topic: str, kind: str, content: str, scope: Scope, created: datetime, **extra) -> str:
        nonlocal counter
        counter += 1
        ident = f"EA-{counter:05d}"
        assertion = EngineeringAssertion(
            id=ident,
            type=kind,
            content=content,
            scope=scope,
            status=extra.pop("status", "approved"),
            importance="high",
            provenance=(Provenance(type="document", uri=f"doc://{ident}"),),
            created_at=created,
            **extra,
        )
        text = " ".join([kind, topic, content, *scope.as_path()])
        docs.append(Doc(assertion, topic, rng.random() < config.p_restricted, text))
        return ident

    def under(scope: Scope) -> list[tuple[str, str, str]]:
        return [
            r
            for r in repos
            if scope.domain in (None, r[0]) and scope.system in (None, r[1])
        ]

    for topic in topics:
        layout = rng.choices(["org", "domain", "system"], [0.2, 0.3, 0.5])[0]
        if layout == "org":
            unit_scopes = [Scope(organization=ORG)]
        elif layout == "domain":
            unit_scopes = [
                Scope(organization=ORG, domain=f"dom{d}")
                for d in range(config.domains)
                if rng.random() < 0.6
            ]
        else:
            unit_scopes = [
                Scope(organization=ORG, domain=dom, system=sys_)
                for dom, sys_ in systems
                if rng.random() < 0.5
            ]
        covered = {r for scope in unit_scopes for r in under(scope)}

        for scope in unit_scopes:
            members = under(scope)
            # Optional explicit cross-system target, only for a repository that
            # no unit of this topic covers.
            target = None
            free = [r for r in repos if r not in covered]
            if layout == "system" and free and rng.random() < config.p_target:
                target = rng.choice(free)
                covered.add(target)
            applies = (Target("repository", target[2]),) if target else ()

            length = rng.choices([1, 2, 3], [0.4, 0.4, 0.2])[0]
            flipped = [rng.random() >= config.p_unflipped for _ in range(length - 1)]
            start = NOW - timedelta(days=90 * (length + 3))
            ids = [f"EA-{counter + i + 1:05d}" for i in range(length)]
            for i in range(length):
                last = i == length - 1
                old_flipped = (not last) and flipped[i]
                add(
                    topic,
                    "policy",
                    f"{topic} rule revision {i + 1}: use setting v{rng.randint(1, 99)}.",
                    scope,
                    start + timedelta(days=90 * i),
                    status="superseded" if old_flipped else "approved",
                    supersedes=(ids[i - 1],) if i else (),
                    superseded_by=(ids[i + 1],) if old_flipped else (),
                    applies_to=applies,
                )
            current = ids[-1]
            history = set()
            if length > 1:
                history.add("history-flipped" if all(flipped) else "history-unflipped")
            # An unflipped revision whose direct successor is itself marked
            # superseded has no *active* successor naming it.
            if any(not flipped[i] and flipped[i + 1] for i in range(length - 2)):
                history.add("broken-chain")

            for repo in members + ([target] if target else []):
                key = (repo[2], topic)
                required[key] = {current}
                tags[key] |= history
                links[key] = {ids[i + 1] for i in range(length - 1) if not flipped[i]}
                if repo is target:
                    tags[key].add("explicit-target")

            for dom, sys_, name in members:
                if rng.random() >= config.p_exception:
                    continue
                state = rng.choices(["active", "expired", "future", "proposed"], [6, 2, 1, 1])[0]
                made = NOW - timedelta(days=60)
                ident = add(
                    topic,
                    "approved-exception",
                    f"{name} is exempt from the {topic} rule and uses v{rng.randint(1, 99)}.",
                    Scope(organization=ORG, domain=dom, system=sys_, repository=name),
                    made,
                    status="proposed" if state == "proposed" else "approved",
                    overrides=(current,),
                    effective_from=NOW + timedelta(days=30) if state == "future" else made,
                    expires_at=NOW - timedelta(days=5) if state == "expired" else None,
                )
                key = (name, topic)
                if state == "active":
                    required[key] = {ident}
                    tags[key].add("exception-active")
                else:
                    tags[key].add("exception-inactive")

            if rng.random() < config.p_complement:
                dom, sys_, name = rng.choice(members)
                narrower = (
                    Scope(organization=ORG, domain=dom, system=sys_)
                    if scope.system is None
                    else Scope(organization=ORG, domain=dom, system=sys_, repository=name)
                )
                ident = add(
                    topic,
                    "incident-derived-constraint",
                    f"{topic} additional constraint: also keep guard g{rng.randint(1, 99)}.",
                    narrower,
                    NOW - timedelta(days=rng.choice([30, 2000])),
                )
                for repo in under(narrower):
                    if narrower.repository in (None, repo[2]):
                        required[(repo[2], topic)].add(ident)
                        tags[(repo[2], topic)].add("complement")

    restricted = {d.assertion.id for d in docs if d.restricted}
    queries = []
    for _ in range(config.queries):
        dom, sys_, name = rng.choice(repos)
        topic = rng.choice(topics)
        cleared = rng.random() < 0.5
        req = frozenset(required.get((name, topic), ()))
        tag = set(tags.get((name, topic), ())) or {"plain" if req else "uncovered"}
        if not cleared and req & restricted:
            tag.add("governing-hidden")
        if not cleared and links.get((name, topic), set()) & restricted:
            tag.add("hidden-successor")
        queries.append(
            Query(
                scope=Scope(organization=ORG, domain=dom, system=sys_, repository=name),
                topic=topic,
                text=topic,
                scoped_text=f"{topic} {name} {sys_}",
                cleared=cleared,
                required=req,
                tags=frozenset(tag),
            )
        )
    return World(tuple(docs), tuple(queries))


# --------------------------------------------------------------------------
# Lexical ranking (BM25), shared by every system so only filtering differs.
# --------------------------------------------------------------------------


def tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


class Bm25:
    def __init__(self, docs: tuple[Doc, ...], k1: float = 1.2, b: float = 0.75) -> None:
        self.k1, self.b = k1, b
        self.tf = {d.assertion.id: Counter(tokens(d.text)) for d in docs}
        self.length = {i: sum(tf.values()) for i, tf in self.tf.items()}
        self.avg = statistics.fmean(self.length.values())
        df = Counter(term for tf in self.tf.values() for term in tf)
        n = len(docs)
        self.idf = {t: math.log(1 + (n - c + 0.5) / (c + 0.5)) for t, c in df.items()}

    def top(self, query: str, candidates: list[str], k: int) -> list[str]:
        terms = tokens(query)
        scored = []
        for ident in candidates:
            tf, score = self.tf[ident], 0.0
            norm = self.k1 * (1 - self.b + self.b * self.length[ident] / self.avg)
            for term in terms:
                if term in tf:
                    score += self.idf[term] * tf[term] * (self.k1 + 1) / (tf[term] + norm)
            if score > 0:
                scored.append((-score, ident))
        return [ident for _, ident in sorted(scored)[:k]]


# --------------------------------------------------------------------------
# Systems. Ladder filters are written independently of repo_memory.policy.
# --------------------------------------------------------------------------


def _acl(doc: Doc, query: Query) -> bool:
    return query.cleared or not doc.restricted


def _approved(doc: Doc, query: Query) -> bool:
    return doc.assertion.status == "approved"


def _dated(doc: Doc, query: Query) -> bool:
    a = doc.assertion
    return (a.effective_from is None or a.effective_from <= NOW) and (
        a.expires_at is None or a.expires_at > NOW
    )


def _scoped(doc: Doc, query: Query) -> bool:
    own, target = doc.assertion.scope, query.scope
    pairs = [
        (own.organization, target.organization),
        (own.domain, target.domain),
        (own.system, target.system),
        (own.repository, target.repository),
    ]
    if all(a is None or a == b for a, b in pairs):
        return True
    return own.organization == target.organization and any(
        t.kind == "repository" and t.id == target.repository for t in doc.assertion.applies_to
    )


LADDER = {
    "L0 lexical top-k": [],
    "L1 +ACL prefilter": [_acl],
    "L2 +status=approved": [_acl, _approved],
    "L3 +effective/expiry dates": [_acl, _approved, _dated],
    "L4 +scope ancestry/targets": [_acl, _approved, _dated, _scoped],
}
LATEST = "L5 L4 +latest-wins per topic tag"
RM = {
    "RM without relations": {"supersedes": (), "superseded_by": (), "overrides": ()},
    "RM supersession only": {"overrides": ()},
    "RM overrides only": {"supersedes": (), "superseded_by": ()},
    "RM full (policy.py)": {},
}
SYSTEMS = [*LADDER, LATEST, *RM]


def deliver(world: World, k: int) -> dict[str, list[list[str]]]:
    """Return, per system, the ordered delivered IDs for every query."""

    index = Bm25(world.docs)
    variants = {
        name: [replace(d.assertion, **blank) for d in world.docs] for name, blank in RM.items()
    }
    restricted = {d.assertion.id for d in world.docs if d.restricted}
    out: dict[str, list[list[str]]] = {name: [] for name in SYSTEMS}
    for query in world.queries:
        for name, filters in LADDER.items():
            kept = [d for d in world.docs if all(f(d, query) for f in filters)]
            text = query.text if _scoped in filters else query.scoped_text
            out[name].append(index.top(text, [d.assertion.id for d in kept], k))
        newest: dict[str, Doc] = {}
        for d in kept:  # kept is the L4 candidate set
            best = newest.get(d.topic)
            if best is None or (d.assertion.created_at, d.assertion.id) > (
                best.assertion.created_at,
                best.assertion.id,
            ):
                newest[d.topic] = d
        out[LATEST].append(index.top(query.text, [d.assertion.id for d in newest.values()], k))
        for name, assertions in variants.items():
            result = resolve_assertions(
                assertions,
                ResolutionContext(scope=query.scope, when=NOW),
                authorize=lambda a, q=query: q.cleared or a.id not in restricted,
            )
            out[name].append(index.top(query.text, [a.id for a in result.active], k))
    return out


# --------------------------------------------------------------------------
# Scoring.
# --------------------------------------------------------------------------

OUTCOMES = ["clean", "needs-resolution", "missed", "misleading"]


def outcome(query: Query, delivered: list[str], topic_of: dict[str, str]) -> str:
    """Classify one delivery against the construction ground truth.

    clean            every required assertion, no other same-topic assertion
    needs-resolution every required assertion plus non-governing same-topic
                     ones; the reader must still work out precedence
    missed           a required assertion is absent, nothing contradictory
    misleading       a required assertion is absent (or none exists) and a
                     non-governing same-topic assertion was delivered
    """

    got = set(delivered)
    extra = any(topic_of[i] == query.topic and i not in query.required for i in got)
    if query.required <= got:
        return "needs-resolution" if extra else "clean"
    return "misleading" if extra else "missed"


def evaluate(config: Config, k: int) -> dict:
    world = generate(config)
    topic_of = {d.assertion.id: d.topic for d in world.docs}
    restricted = {d.assertion.id for d in world.docs if d.restricted}
    delivered = deliver(world, k)
    report: dict = {"assertions": len(world.docs), "digest": world.digest(), "systems": {}}
    for name in SYSTEMS:
        headline: Counter[str] = Counter()
        by_tag: dict[str, Counter[str]] = defaultdict(Counter)
        hidden: Counter[str] = Counter()
        leaks = 0
        for query, got in zip(world.queries, delivered[name], strict=True):
            leaks += (not query.cleared) and bool(set(got) & restricted)
            result = outcome(query, got, topic_of)
            if "governing-hidden" in query.tags:
                hidden[result] += 1
                continue
            headline[result] += 1
            for tag in query.tags:
                by_tag[tag][result] += 1
        report["systems"][name] = {
            "headline": dict(headline),
            "by_tag": {t: dict(c) for t, c in sorted(by_tag.items())},
            "governing_hidden": dict(hidden),
            "queries_with_leak": leaks,
        }
    return report


# --------------------------------------------------------------------------
# CLI: run the frozen grid and write results.json + RESULTS.md.
# --------------------------------------------------------------------------

SEEDS = [0, 1, 2, 3, 4]
SCALES = {"4 systems": (2, 2), "16 systems": (4, 4), "64 systems": (8, 8)}
BUDGETS = [3, 5, 10]


def _pct(counter: dict[str, int], key: str) -> float:
    total = sum(counter.values())
    return 100 * counter.get(key, 0) / total if total else float("nan")


def _row(runs: list[dict], name: str, pick) -> str:
    cells = []
    for key in OUTCOMES:
        values = [_pct(pick(r["systems"][name]), key) for r in runs]
        cells.append(f"{statistics.fmean(values):.1f} ({min(values):.0f}–{max(values):.0f})")
    return f"| {name} | " + " | ".join(cells) + " |"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("out", type=Path, help="output directory")
    out = parser.parse_args().out
    out.mkdir(parents=True, exist_ok=True)

    grid: dict[str, list[dict]] = {}
    for label, (domains, per) in SCALES.items():
        for k in BUDGETS if label == "16 systems" else [5]:
            grid[f"{label}, k={k}"] = [
                evaluate(Config(seed=s, domains=domains, systems_per_domain=per), k)
                for s in SEEDS
            ]
    (out / "results.json").write_text(json.dumps(grid, indent=1, sort_keys=True) + "\n")

    head = (
        "| System | clean % | needs-resolution % | missed % | misleading % |\n"
        "|---|---|---|---|---|"
    )
    lines = [
        "# Delivery ablation results",
        "",
        "Generated by `ablation.py`. Mean over seeds 0–4 (min–max). 400 queries per seed.",
        "Queries whose governing assertion is hidden from the caller are excluded",
        "from these tables and reported separately at the end.",
    ]
    for label, runs in grid.items():
        sizes = sorted(r["assertions"] for r in runs)
        lines += ["", f"## {label} ({sizes[0]}–{sizes[-1]} assertions)", "", head]
        lines += [_row(runs, name, lambda s: s["headline"]) for name in SYSTEMS]
    runs = grid["16 systems, k=5"]
    all_tags = sorted({t for r in runs for s in r["systems"].values() for t in s["by_tag"]})
    for tag in all_tags:
        n = sum(sum(r["systems"][SYSTEMS[0]]["by_tag"].get(tag, {}).values()) for r in runs)
        lines += ["", f"## By case: {tag} (16 systems, k=5; {n} queries over 5 seeds)", "", head]
        lines += [_row(runs, name, lambda s, t=tag: s["by_tag"].get(t, {})) for name in SYSTEMS]
    n = sum(sum(r["systems"][SYSTEMS[0]]["governing_hidden"].values()) for r in runs)
    lines += ["", f"## Governing assertion hidden from caller (16 systems, k=5; {n} queries)", ""]
    lines += ["No system can be clean here. `missed` is the safe outcome.", "", head]
    lines += [_row(runs, name, lambda s: s["governing_hidden"]) for name in SYSTEMS]
    lines += ["", "## Queries with an unauthorized assertion delivered (16 systems, k=5)", ""]
    lines += ["| System | queries with leak, total over 5 seeds (of 2000) |", "|---|---|"]
    lines += [
        f"| {name} | {sum(r['systems'][name]['queries_with_leak'] for r in runs)} |"
        for name in SYSTEMS
    ]
    (out / "RESULTS.md").write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
