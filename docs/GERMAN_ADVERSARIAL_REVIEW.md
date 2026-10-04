# Finding 3 adversarial review — issue #34

**Verdict: weakened.** The published descriptive counts reproduce exactly. The stronger claim of
independent-agent diffusion does not follow: labels are unverified, page writes do not prove reads,
and the technique advantage disappears under the joint earlier-edit / network-overlap stress test.
This does not prove a common operator caused the pattern or establish absence of spread.

Independent implementation: `explorer/german_adversarial.py` imports no existing adapter or tracer.
Input: public [collusion.wiki revision export](https://collusion.wiki/explorer/download),
14,591 revisions; SHA-256 `9c2a4ef0ccbfb5b42be8422342a6bd3a389a4a047bc891e3148354dd65b63c96`. Source rows, labels, bodies and IP values remain ignored.
The source is the investigators’ own maintained release, linked from their named-authors report;
it is not a verified roster of OpenAI agents or operators. No identity resolution was attempted.

## Reproduction and sensitivity

All primary scenarios retain the baseline artifact universe (at least ten distinct nonblank labels).
Unit = first observed use per (label, artifact), unless explicitly changed below.
“Seen” here is a **page-edit exposure proxy**: the artifact was in the preceding saved revision of
a page the label edited at or before adoption. It is not a verified content delivery event.
The URL comparator includes wrapped URLs, so “ordinary URLs” is misleading.

| Scenario | Technique: seen/n, % [Wilson 95%] | Full URL: seen/n, % [Wilson 95%] |
|---|---:|---:|
| Published rule | 723/2,266, 31.9% [30.0–33.9] | 931/8,412, 11.1% [10.4–11.8] |
| Exclude selected source/adoption row same-ip pair | 710/2,253, 31.5% [29.6–33.5] | 919/8,400, 10.9% [10.3–11.6] |
| Drop same-ip candidates; retain all adoptions | 712/2,266, 31.4% [29.5–33.4] | 924/8,412, 11.0% [10.3–11.7] |
| Exclude overlapping source/adopter label IP sets (all time) | 287/1,830, 15.7% [14.1–17.4] | 142/7,623, 1.9% [1.6–2.2] |
| Exclude adopter overlap with any prior-user label (all time) | 10/126, 7.9% [4.4–14.0] | 9/928, 1.0% [0.5–1.8] |
| Same exclusion using only IP observations as of adoption | 26/247, 10.5% [7.3–15.0] | 29/1,728, 1.7% [1.2–2.4] |
| Require strictly earlier edit | 386/2,266, 17.0% [15.5–18.6] | 930/8,412, 11.1% [10.4–11.7] |
| Earlier edit + all-time any-prior-user exclusion | 0/126, 0.0% [0.0–3.0] | 9/928, 1.0% [0.5–1.8] |
| Earlier edit + as-of any-prior-user exclusion | 1/247, 0.4% [0.1–2.3] | 29/1,728, 1.7% [1.2–2.4] |
| Allow blank-label source revisions | 727/2,266, 32.1% [30.2–34.0] | 931/8,412, 11.1% [10.4–11.8] |
| Original first use reqlog; exposure and origin also reqlog | 720/2,261, 31.8% [30.0–33.8] | 928/8,366, 11.1% [10.4–11.8] |
| Exposure edit within 72 h | 720/2,266, 31.8% [29.9–33.7] | 930/8,412, 11.1% [10.4–11.7] |
| Earlier edit within 72 h | 383/2,266, 16.9% [15.4–18.5] | 929/8,412, 11.0% [10.4–11.7] |
| Earlier edit and source separated by >2 s | 362/2,266, 16.0% [14.5–17.5] | 843/8,412, 10.0% [9.4–10.7] |
| Exclude wrapped URLs from URL comparator | 723/2,266, 31.9% [30.0–33.9] | 476/4,275, 11.1% [10.2–12.1] |
| Technique per first (label, wrapped URL) | 7,391/13,435, 55.0% [54.2–55.9] | 931/8,412, 11.1% [10.4–11.8] |
| Technique per newly added wrapped URL, including repeat additions | 16,777/24,753, 67.8% [67.2–68.4] | 4,486/17,724, 25.3% [24.7–26.0] |

Wilson intervals above are descriptive binomial summaries, **not** confidence intervals for a
causal effect or independent agents. Multiple observations belong to the same labels, artifacts and
pages; network blocks also cluster labels. This is a census of the supplied release, not a random
sample of all activity. Fixed eligibility avoids moving the goalposts after exclusions.

337/723 technique cases (46.6%) have no exposure-proxy edit strictly before the adoption timestamp;
only 1/931 URL cases does. The original code accepts `seen_at <= first_at`, including the adoption
edit itself. Strictly earlier edits give 386/2,266 vs 930/8,412. This remains a descriptive difference,
but it is substantially smaller than the headline.

## Network overlap is a stress test, not operator identification

Only 13/723 technique and 12/931 URL selected seen edges have equal **origin-row vs adoption-row**
`ip16`. However, 1,741/3,102 labels use multiple blocks; selected source/adopter label IP sets overlap
for 436/723 and 789/931 seen cases. A changing request IP makes a single-row comparison weak.

The stronger exclusion removes the entire adoption if its label shares any block with any label
whose first use of the artifact is strictly earlier. The all-time version uses all observed IPs
of those labels, including future edits; it is conservative but future-informed. The as-of version
requires the shared IP to have been observed for both labels by adoption, and prior-user eligibility
to have occurred strictly before adoption. An IP appearing exactly at adoption for a prior user
does not establish a strictly prior overlap. Neither version identifies an operator.

As-of exclusion retains only 247/2,266 technique and 1,728/8,412 URL observations. Its 26 technique
seen cases include 25 that rely solely on the adoption edit; requiring an earlier edit leaves
**1/247 (0.4%) vs 29/1,728 (1.7%)**. The stricter all-time exclusion gives **0/126 vs 9/928**.
These are selected, small residual populations: the result undermines robustness of the spread
interpretation, rather than proving that shared operators explain the full original association.

## Editor activity and page popularity

Technique adopters are not heavier editors by the available proxy: mean prior saved edits is 3.92
versus 8.49 for URL adopters; medians are 1 versus 2. These are **saved edits**, not measured page
loads or browsing histories. The revision export cannot match on actual prior read requests.

Exact-stratum standardization uses a common weight `min(n_technique, n_URL)` per prior-count
stratum, retaining only strata containing both groups. It uses all observations in a stratum,
weighted by that common weight; there is no random pair selection or causal interpretation.

| Scenario | Match on prior saved edits: technique / URL | Match on prior distinct edited pages: technique / URL |
|---|---:|---:|
| Published rule | 31.86% / 7.52% (weight 2,263 each) | 31.92% / 7.55% (weight 2,265 each) |
| Earlier edit | 16.97% / 7.50% (weight 2,263 each) | 17.04% / 7.54% (weight 2,265 each) |
| As-of IP exclusion | 10.61% / 1.91% (weight 245 each) | 10.57% / 1.73% (weight 246 each) |
| Earlier edit + as-of IP exclusion | 0.41% / 1.91% (weight 245 each) | 0.41% / 1.73% (weight 246 each) |

The baseline gap holds in all five reported page-popularity bands, independently reproduced:

| Distinct labeled editors on adoption page | Technique | Full URL |
|---|---:|---:|
| 1-2 | 108/733, 14.7% [12.4–17.5] | 194/2,468, 7.9% [6.9–9.0] |
| 3-5 | 80/257, 31.1% [25.8–37.0] | 83/690, 12.0% [9.8–14.7] |
| 6-20 | 178/401, 44.4% [39.6–49.3] | 87/1,006, 8.6% [7.1–10.5] |
| 21-100 | 136/271, 50.2% [44.3–56.1] | 74/727, 10.2% [8.2–12.6] |
| >100 | 221/604, 36.6% [32.8–40.5] | 493/3,521, 14.0% [12.9–15.2] |

That stratification controls only the observed adoption page’s total label count; it does not
rule out common operators, task/scaffold similarities, unobserved reads, or exposure opportunities.

## Definition and timing checks

- First (label, technique) is the correct unit for first-technique adoption. Per-new-URL counting
  weights repeated users much more heavily and increases the apparent association; it cannot
  replace the first-technique headline.
- Allowing blank-label origins adds four technique seen cases. Reqlog-only endpoints remove
  little; redefining first use among reqlog rows produces the same counts as restricting original
  first uses here. All 14,482 reqlog revision request actions are `form_edit`, not read logs.
- The 72-hour exposure window changes three technique and one URL cases. It applies to the edit
  associated with potential exposure, not the origin revision’s age. No page sequence has reversed
  timestamps. All exported uncertainty values are one second; the >2-second test requires both
  origin-to-exposure and exposure-to-adoption separation. The reported bound is not independently
  calibrated timestamp accuracy.
- Seventeen page histories flag unpublished predecessors. The reconstruction treats their first
  observed state as empty, like the original, so introductions and first uses are left-censored.
- The extractor returns **69 host-pattern technique tokens**, **25 with ≥10 labels**, not a verified
  inventory of 15 proxy services. A host with an embedded URL can be an ordinary query/document
  viewer, and written proxy-shaped text does not establish an attempted or successful fetch.
  The original top-five label counts do reproduce: 584, 348, 258, 253, 192. The AI Village comparison
  was not independently re-derived in this local review; “the other 14 never do” is not validated.
- The reported burst reproduces: 58 labels first introduce the webcrawler host-pattern token on
  June 18, 19:45:20–21:23:59 UTC (5,919 s). This is a label/token recurrence burst, not verified
  independent-agent diffusion. Boundary rows: `dse~StartSeite@420`, `dse~WillkommenImWiki@2217`.

## Evidence references and semantic correction

Examples where adoption edit equals the sole exposure-proxy edit: `dse~SandboxAgentXYZ@3`
(origin `dse~SandboxAgentXYZ@2`) and `dse~StartSeite@224` (origin `dse~StartSeite@223`).
The single technique case surviving the joint earlier-edit/as-of-IP test is adoption
`dse~AgentMoreLinks260618O@3`, exposure-proxy edit `dse~AgentMoreLinks260618O@2`, origin
`dse~AgentMoreLinks260618O@1`. Row references are locators, not authenticated agent identities.

The primary [investigators’ report](https://collusion.wiki/#the-agents-gain-write-to-the-internet-via-get-requests)
describes writes through direct GET requests. An edit record therefore does not require observed
delivery of the preceding page body to the writer. The revision export contains no read response
or model input showing that content was received. Even an earlier edit remains an exposure proxy.
Use “edited a page whose preceding saved revision contained the token,” not “seen proves exposure.”

The official [DeepMind case study](https://arxiv.org/html/2609.04170v1), §2.1, uses isolated instances
and defined communication primitives; its linked [Formal Conjectures repository](https://github.com/google-deepmind/formal-conjectures)
was also consulted. That experimental setup cannot supply missing identity/delivery evidence for
this observational export. No causal estimates from that paper are applied here.

## Reproduction

```sh
.venv/bin/python -m explorer.german_adversarial \
  --input data/ext/german/revisions.jsonl.gz \
  --output data/ext/results34/audit.json \
  2> data/ext/results34/audit.log
.venv/bin/python -m pytest tests/ -q
```

Private output includes all scenario counts/Wilson intervals, exact matching strata, diagnostics,
input digest and row locators. Timestamped debug logs are retained alongside it. Six synthetic
counterexample tests cover contemporaneous edits, blank origins, deletion/reintroduction, future IP
leakage, third-prior-user overlap, timing/window endpoints, weighting and unsupported strata.
Full repository validation: **84 passed in 1.52 s**. No source writes, data/excerpts in git,
instance access or operator re-identification.
