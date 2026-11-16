# Candidates from Outside This Repository

Issue #8. Selected 2026-11-16 by an AI assistant from public sources. This
file is **safe for reviewers to read before labelling**: it contains no
proposed labels. The selector's own guesses are in
[`selector-dispositions.md`](selector-dispositions.md); do not open that file
until you have finished labelling.

## Sources

| Source | Revision | Licence | Note |
|---|---|---|---|
| Python Enhancement Proposals, [python/peps](https://github.com/python/peps) | `88b6b2d` (2026-11-10) | PEP texts are public domain or CC0 per their own copyright sections; only headers and short facts are used here | Standards documents for a language project, not a company's internal decisions |
| [alphagov/gsp](https://github.com/alphagov/gsp) (GOV.UK "GDS Supported Platform") | `a9f80de` (2021-04-30) | MIT | 46 architecture decision records; a platform team's real decisions |
| [nhsuk/connecting-to-services](https://github.com/nhsuk/connecting-to-services) | `8f11f7c` (2020-01-08) | MIT | 17 architecture decision records for one web application |

The two ADR repositories were found through the
[ADR Study Dataset](https://github.com/software-competence-center-hagenberg/ADR-Study-Dataset)
by filtering for public-sector repositories with at least one superseded
record. That is a convenience sample, not a random one.

Limits that apply to every candidate below:

- The selector read the cited files only. Nothing is known about how these
  teams actually found, missed or re-learned any of this. **Discovery effort,
  waiting time and consequences are unknown** unless the cited text states
  them.
- Both ADR repositories' last commits are years old. Whether the guidance is
  still current for those teams is unknown.
- Scope is described in the Engineering Assertion vocabulary; the sources do
  not use it.

Each entry uses the same fields: what it says, where it applies, where it
comes from, current versus historical guidance, and whether the current
source of truth settles it on its own.

---

## RM-E1: Python code in the standard library follows the PEP 8 style guide

- **Source.** `peps/pep-0008.rst`. Status `Active`, type Process, created
  2001-07-05.
- **Scope.** Organization (the CPython project); adopted as a convention by
  many other projects.
- **Current vs historical.** One living document, edited in place. No
  superseding document.
- **Does the current source settle it?** The document is easy to find. Many of
  its rules are checked mechanically by widely used linters (general
  knowledge, not verified from the source).

## RM-E2: WSGI 1.0.1 (PEP 3333) is the Python 3 form of WSGI 1.0 (PEP 333)

- **Source.** `pep-0333.rst`: status `Final`, header `Superseded-By: 3333`.
  `pep-3333.rst`: status `Final`, header `Replaces: 333`, created 2010-09-26,
  described as an update "to improve usability under Python 3".
- **Scope.** Ecosystem-wide interface between web servers and applications.
- **Current vs historical.** Both documents read `Final`. Only the header
  links say which is newer; the older one's status was never changed.
- **Does the current source settle it?** Yes if the reader notices the header
  link. A reader who lands on PEP 333 and checks only its status sees `Final`.

## RM-E3: Version numbers follow PEP 440, not PEP 386

- **Source.** `pep-0386.rst`: status `Superseded`, `Superseded-By: 440`.
  `pep-0440.rst`: status `Final`, `Replaces: 386`, created 2013-03-18.
- **Scope.** Ecosystem-wide packaging rule.
- **Current vs historical.** Cleanly marked on both sides.
- **Does the current source settle it?** Yes. Packaging tools implement the
  scheme, so an invalid version is normally rejected by tooling (general
  knowledge, not verified from the source).

## RM-E4: Incompatible changes need a deprecation period, with exceptions granted by the steering council

- **Source.** `pep-0387.rst`. Status `Active`, type Process, `Replaces: 291`.
  The text sets a minimum deprecation period and states "The steering council
  may grant exceptions to this policy."
- **Scope.** Organization-wide policy for the CPython project.
- **Current vs historical.** One living policy. Individual exceptions are
  granted case by case and are not listed in the policy itself.
- **Does the current source settle it?** The rule, yes. Whether a specific
  change holds an exception cannot be read from the policy; it has to be found
  in the record of that decision.

## RM-E5: A set of old standard-library modules is deprecated from Python 3.11 and scheduled for removal

- **Source.** `pep-0594.rst`. Status `Final`, created 2019-05-20,
  `Python-Version: 3.11`. Contains a "Deprecation schedule" section; modules
  issue warnings starting with Python 3.11.
- **Scope.** Organization-wide, time-bound.
- **Current vs historical.** A schedule that plays out over several releases.
  Before removal, guidance is "avoid new use"; after removal the modules are
  simply absent.
- **Does the current source settle it?** After removal, an import fails, so
  the code tells you. During the deprecation window a warning is emitted at
  import.

## RM-E6: Postponed evaluation of annotations (PEP 563) was accepted, shipped behind a future import, and then superseded

- **Source.** `pep-0563.rst`: status `Superseded`, `Superseded-By: 649, 749`,
  introduced as a `__future__` import in Python 3.7. `pep-0649.rst`: status
  `Final`, `Replaces: 563`, `Python-Version: 3.14`, resolution dated
  2023-05-08.
- **Scope.** Language-wide.
- **Current vs historical.** An accepted direction was reversed about five
  years later. Code written for the earlier plan still exists in the wild.
- **Does the current source settle it?** The headers are marked on both sides.
  Material written between 2017 and 2023 that describes the earlier plan as
  the future is not marked.

## RM-E7: Installers must not modify an environment marked as externally managed

- **Source.** `pep-0668.rst`. Status `Final`, created 2021-05-18. Defines a
  marker file named `EXTERNALLY-MANAGED`. The PEP carries a
  `canonical-pypa-spec` note pointing to the living specification
  `externally-managed-environments`, so the PEP is now the historical record.
- **Scope.** Cross-tool rule: operating-system distributors and Python
  installers.
- **Current vs historical.** The authoritative text moved from the PEP to a
  separately maintained specification.
- **Does the current source settle it?** The marker file is on disk and the
  installer refuses with a message. The reason and the permitted ways around
  it are in the specification.

## RM-E8: Cluster ingress uses the Istio ingress gateway, not a separate nginx ingress controller

- **Source.** alphagov/gsp `docs/architecture/adr/ADR005-ingress.md`: status
  "Superseded by ADR025". `ADR025-ingress.md`: status `Accepted`; context "We
  currently have two ingress systems … Do we need both?"; decision "No. We
  will use an Istio Ingress Gateway". ADR025's link back to ADR005 points to
  `ADR05-ingress.md`, a file that does not exist.
- **Scope.** System (one platform, all tenant namespaces).
- **Current vs historical.** Marked on the old record. The new record's
  reference to the old one is a broken link.
- **Does the current source settle it?** The deployed cluster configuration
  would show which controller exists. Why the other was removed is only in
  the ADR.

## RM-E9: Container images are stored in AWS ECR, after a period on self-hosted Harbor

- **Source.** alphagov/gsp. `ADR012-docker-image-repositories.md`: decision to
  use the vendor's managed registry (ECR); status "Superseded by ADR028".
  `ADR028-container-tools.md`: decision "We will run a self hosted set of
  Docker tools"; status "Superseded by ADR046".
  `ADR046-replace-harbor-ecr.md`: status `Accepted`; context "Harbor has
  proved itself to be rather unstable (causing several incidents from various
  root causes)"; decision to replace Harbor with ECR. An incident report
  exists at `docs/incident-reports/20190227-control-plane-and-harbor-outage.md`.
- **Scope.** System.
- **Current vs historical.** Three records. The current choice matches the
  first one, and the middle one was the accepted direction in between.
- **Does the current source settle it?** Current infrastructure code shows ECR
  is in use. That the self-hosted option was tried and abandoned because of
  incidents is only in the ADRs and the incident report.

## RM-E10: Static ingress IPs are provided by a manually created Global Accelerator, as a temporary workaround

- **Source.** alphagov/gsp `ADR042-static-ingress-ip-workaround.md`. Status
  `Accepted`. Decision: "We will manually provision a Global Accelerator
  pointing to the ingress NLB using the AWS console … This is intended to be a
  temporary solution until we are running a version of the EKS control plane
  that supports attaching EIPs to LoadBalancer Services".
- **Scope.** System; applies to production services whose users safelist IPs.
- **Current vs historical.** A deliberate deviation from the platform's own
  preference (the context says the team wants to "push back on these kinds of
  static configurations"). It names an end condition but no date, and no later
  record in the repository states that it ended.
- **Does the current source settle it?** No. The resource is created by hand
  in a console, so it is not in the infrastructure code.

## RM-E11: When replacing worker nodes, use lifecycle hooks and turn the cluster autoscaler off for the duration

- **Source.** alphagov/gsp `ADR040-cluster-stability-node-replacement.md`.
  Status `Accepted`. Context: replacing nodes one per auto-scaling group
  "terminates too many instances at once and results in the cluster becoming
  unstable". Decision: lifecycle hooks, and "turn off autoscaler while rolling
  nodes", described as "a script run before we run terraform … and
  afterwards".
- **Scope.** System; an operational procedure.
- **Current vs historical.** Single record, not superseded.
- **Does the current source settle it?** Lifecycle hooks would be visible in
  the infrastructure code. The step of scaling the autoscaler down before and
  up after is a procedure around the code, described as a script.

## RM-E12: Namespace access uses two roles, Operator and Auditor

- **Source.** alphagov/gsp `ADR032-sre-permissions.md`: status "Superseded by
  ADR043". `ADR043-k8s-resource-access.md`: status `Accepted`; decision "We
  will create two levels of access within each namespace: Operator, Auditor";
  Auditor "will be given to all authenticated users in the cluster".
- **Scope.** System.
- **Current vs historical.** Cleanly marked on the old record.
- **Does the current source settle it?** The role definitions are Kubernetes
  resources and can be read from the cluster or its configuration.

## RM-E13: Do not add cache-control headers to search results; they were removed because cached results showed stale opening times

- **Source.** nhsuk/connecting-to-services `doc/adr/0005-add-cache-control-headers.md`
  (2017-08-17, status "Superseded"). `0007-remove-cache-control-headers.md`
  (2017-10-11, `Accepted`): context "Search results are being cached for 30
  minutes giving stale opening time information"; decision "The caching will
  be removed from the site".
- **Scope.** Repository.
- **Current vs historical.** Added, then removed eight weeks later. The old
  record is marked.
- **Does the current source settle it?** The code shows there are no caching
  headers. It does not show that they were tried and why they were removed.

## RM-E14: Google Sitelinks Searchbox metadata was removed because it never worked

- **Source.** nhsuk/connecting-to-services `doc/adr/0011-…` (2018-01-23,
  status "Superceded by 13"). `0013-remove-google-sitelinks-searchbox-metadata.md`
  (2019-03-18, `Accepted`): "This never ended up working and no search box has
  been placed by Google within the search results"; decision to remove the
  code "as it is effectively redundant".
- **Scope.** Repository.
- **Current vs historical.** Marked on both records.
- **Does the current source settle it?** The code shows the metadata is
  absent.
