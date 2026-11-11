# Calibration: real supersession rates

Issue #40. Measured 2026-11-11 with [`measure.py`](measure.py); output in
[`measured.json`](measured.json).

## Sources

| Corpus | Revision / date | Licence note |
|---|---|---|
| Python PEPs, [python/peps](https://github.com/python/peps) | commit `88b6b2d` (2026-11-10) | Header fields only were read; no PEP text is redistributed here |
| IETF RFC index, `https://www.rfc-editor.org/rfc-index.xml` | fetched 2026-11-11 | Index metadata only |
| [ADR Study Dataset](https://github.com/software-competence-center-hagenberg/ADR-Study-Dataset) | commit `771b167` (2023-06-20); crawled by its authors in 2022 | No licence file in the repository. Only aggregate counts are reported here; nothing is copied |

The source files are not committed. Fetch them and run:

```bash
python research/experiments/delivery-ablation/calibration/measure.py \
  --peps <peps checkout>/peps --rfc-index rfc-index.xml \
  --adr-dataset <ADR-Study-Dataset>/repositories
```

## What was measured

| Measure | PEPs | RFCs | ADR dataset |
|---|---|---|---|
| Documents | 747 | 9,858 | 6,362 files in 921 repositories |
| Replaced by a later document | 41 (5.5%) | 1,384 (14.0%) | 97 with a "superseded" status (1.5%; 2.3% of the 4,231 that state any status) |
| Replacement pairs | 46 | 1,543 | not available (no links in the dataset) |
| Pairs linked from both sides | 27 (59%) | 1,543 (100%) | n/a |
| Pairs linked only by the successor | 14 (30%) | 0 | n/a |
| Pairs linked only by the predecessor | 5 (11%) | 0 | n/a |
| Replaced documents whose own status does not say so | 20 of 41 (49%); 6 of them are still `Final` | 1,228 of 1,384 (89%) are not `HISTORIC` | n/a |
| Chains with one prior revision | 32 of 34 (94%) | 649 of 872 (74%) | n/a |
| Chains with two or more prior revisions | 2 of 34 (6%) | 223 of 872 (26%) | n/a |
| Files with no status at all | 0 | 0 | 2,131 (33%) |

## Reading these numbers

- **History is much rarer than the ablation assumed.** The generator gave 60%
  of rules a prior revision. In these corpora roughly 10% of current documents
  have one (RFC: 872 chain heads among 8,474 current documents; PEPs are
  similar).
- **A status field alone is not a reliable lifecycle marker.** 89% of
  obsoleted RFCs keep an ordinary status; the `obsoleted-by` link is what
  marks them. Among PEPs that were adopted and later replaced, 6 of 27 (22%)
  still read `Final`. The ablation's assumed 30% sits inside this range.
- **Links are often one-directional where nobody maintains an index.** 41% of
  PEP replacement pairs are asserted from only one side. The RFC index is
  centrally maintained and is fully bidirectional.
- **A third of real ADR files carry no status.** The ablation does not model
  missing status.

## What these corpora cannot tell us

Exception rates, complementary constraints, access restrictions and scope
hierarchy are not observable in any of the three. Those ablation parameters
remain assumptions. PEPs and RFCs are standards documents, not a company's
engineering decisions; the ADR dataset is closer in kind but has no links.
"Replaces" in a PEP header does not always mean the older PEP stopped
applying (for example PEP 333 and PEP 3333 coexist for different Python
versions). Counts are reported as found, without correcting for that.

## Effect on the ablation

Calibrated configurations use 10% of rules with history (three in four of
those with a single prior revision) and bracket the unmarked rate at 22% and
89%. Results: [`../results/CALIBRATED.md`](../results/CALIBRATED.md).

| System (16 systems, k=5) | clean %, 22% unmarked | clean %, 89% unmarked | clean %, original assumptions |
|---|---|---|---|
| L4 filter stack | 90.7 | 87.8 | 79.0 |
| L5 L4 + latest wins | 97.3 | 97.3 | 96.8 |
| Engine, supersession links only | 91.4 | 91.7 | 89.1 |
| Engine, override links only | 98.7 | 95.0 | 85.6 |
| Engine as shipped | 99.4 | 99.7 | 97.2 |

With measured history rates, supersession links change the outcome for about
1–4% of queries (L4 → supersession only), down from about 10% under the
original assumptions. Most of the remaining gap between the filter stack and
the engine now comes from exception overrides, whose rate (25%) is still an
assumption. The conclusions in the main README hold; the size of the
supersession effect was overstated by the original parameters.
