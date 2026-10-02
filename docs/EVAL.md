# Tracer evaluation

How much should you trust an edge the tracer draws? Measured on stratified, blind-labelled samples.

## Method

1. `explorer/label_sample.py <seed>` draws a seeded, stratified sample of exposure edges
   (25 `explicit`, 25 `temporal`, 15 `none`; adopter channel ∈ chat / action / model_output; noise excluded),
   with ±400-char excerpts of the source post and the adopter's first use around the URL.
2. The sample is shuffled and **blinded**: the evidence level, lag and row ids are removed; an answer key is
   kept separately.
3. An independent annotator (a separate Claude agent, instructed not to open the key) labels each item:
   - with a source post: did the adopter plausibly get the URL from this source? `yes / plausible / no / unclear`
   - without one: does the adopter's text show it received the URL from someone? `yes / no / unclear`
4. Precision per evidence level = labelled-correct / decided (unclear excluded); *strict* counts `yes` only,
   *plausible-source rate* counts `yes + plausible` — it means the excerpts do not rule the attribution out,
   **not** that the post caused the adoption (renamed from "lenient precision" after review #2 / `docs/TRACER_REVIEW.md` #6). For `none`, the miss rate = `yes` / decided.

**Caveats.** Labels are model-made, not human; a human spot-check is pending. Samples are small, so the
intervals are wide (Wilson 95% CIs below). Excerpts are ±400 chars; some attributions sit outside them
(→ `unclear`).

The results below were measured before room visibility filtering. The updated tracer can mark an edge
`cross_room` or retain a source with `room_unknown`; these categories need a fresh blind evaluation before
their accuracy is reported.

### Self-discovery guard (#17, 2026-10-01)

`explicit` now means the first-use text names the selected source **and no self-discovery cue was
detected**. `self_found` is a heuristic flag, not proof of independent discovery. The inspectable
`self_found_cues` list records which rule fired: a specific whole-turn plan to find links and search,
first-person web search/lookup near the URL, or an ownership/creation phrase directly introducing it.
Generic browsing, negations, and searching a supplied page for errors do not suffice. The rules operate
on the existing normalised text; they cannot reliably distinguish quoted speech, an unrelated nearby
URL, or hypothetical plans from completed actions. URL-local rules use the first matching URL occurrence
and can miss narrative elsewhere in a long turn or a differently spelled URL.

Affected named edges become `temporal` at ≤72 h or `stale` beyond 72 h. Source selection and row IDs are
preserved: these remain candidate exposures, not newly established discovery routes. `source_named`
keeps the original name-match signal. `named_old` flags named sources older than 72 h; age alone does
not downgrade them, because an old but explicitly acknowledged source can still be valid.

An initial 400-character ownership rule incorrectly matched four different-project/channel-list
mentions. Those development cases were inspected and the rule tightened to direct URL introduction;
they are not held-out evaluation. Synthetic regressions cover these confounds. The data comparison and
blinded changed/control set are reproducible with `explorer/compare_self_discovery.py`; samples contain
full source posts and first-use turns, so accuracy is not directly comparable to the older ±400-character
excerpts. A changed-edge sample assesses downgrade decisions, not recall of all self-discovered URLs.
No precision improvement is claimed until independent annotation (and ideally human review).

Measured against v6 on export `838b415`: 73,578 edges before/after, with zero source-row or target-row
changes. `explicit` 3,519 → 3,518; `temporal` 32,461 → 32,462; `mention` 3,520, `stale` 897,
`cross_room` 907, and `none` 32,274 unchanged. Seven adoptions have a self-discovery flag; one was
previously explicit. 227 named edges exceed 72 h and remain explicit, with the age warning.
The one downgrade is the issue's development example: source chat
`ac7f7c2c-fb29-42f8-a51d-3374f94f9723`, adopter turn
`43749844-9aac-4bf2-b6d0-fd93958a263b` (46.8 h). This is a narrow guard, not a measured solution to
all named-versus-received ambiguity. There are not five or ten final flipped examples to supply.

Private outputs: `/data/trace_v7_codex17`; v6 was SHA-256 checked against `/data/trace` and preserved
at `/data/trace_v6`. The six unchanged intermediate Parquets were reused; scored edges and artifact
summaries were rebuilt in 17 s with a separate DuckDB database. The dashboard's current output directory
was not replaced. Reproduction: run the updated tracer into a fresh output directory (set module `OUT`
and `DB` before `main()`; optionally reuse the six intermediate Parquets from v6), then run
`python explorer/compare_self_discovery.py --before /data/trace_v6 --after <new-output-dir>`.
The comparison writes all transitions, row-ID checks, cue counts, and a seeded blind sample plus separate
key. Seed 20261001 yields the sole changed edge plus 25 unchanged explicit controls. The changed case
is already known from development and must not be reported as held-out validation.

## Results

### Tracer v2 — source = most recent prior chat poster (sample seed 3, 2026-09-26)

| evidence | n | yes | plausible | no | unclear | precision strict | plausible-source rate |
|---|---:|---:|---:|---:|---:|---:|---:|
| explicit | 25 | 18 | 5 | 0 | 2 | 78% (18/23) | 100% (23/23) |
| temporal | 25 | 8 | 11 | 3 | 3 | 36% (8/22) | 86% (19/22) |
| none | 15 | 0 | – | 9 | 6 | misses: 0/9 | |

All 3 `no` labels were **misattributions**: the adopter's text credits a different agent that had also posted
the URL earlier, but v2 picked the *most recent* poster. → v3 picks, among all prior posters, the most recent
one the adopter names; otherwise the most recent poster.

### Tracer v3 — named poster preferred (held-out sample seed 777, 2026-09-26)

Fresh sample (0 overlap with seed 3), labelled blind by **two** annotators (A = the v2 annotator, B = new).

| evidence | annotator | yes | plausible | no | unclear | precision strict | plausible-source rate |
|---|---|---:|---:|---:|---:|---:|---:|
| explicit | A | 15 | 10 | 0 | 0 | 60% [41–77%] | 100% [87–100%] |
| explicit | B | 14 | 11 | 0 | 0 | 56% [37–73%] | 100% [87–100%] |
| temporal | A | 10 | 15 | 0 | 0 | 40% [23–59%] | 100% [87–100%] |
| temporal | B | 8 | 17 | 0 | 0 | 32% [17–52%] | 100% [87–100%] |
| none (misses) | A / B | 0 / 0 | – | 10 / 12 | 5 / 3 | misses 0/10 [0–28%] · 0/12 [0–24%] | |

**Agreement A vs B:** 58/65 exact (89%), Cohen's κ = 0.84; on the 50 sourced items the lenient
"correct?" call agrees 50/50. Disagreements are yes↔plausible (3) and no↔unclear (4) — never correct↔wrong.

### Summary

- v3 removed the only failure mode seen: **0 wrong edges in 50 held-out sourced edges under both annotators**
  (v2: 3/44). Sourced edges were never judged wrong (plausible-source rate lower CI bound ≥ 87%) — consistent-with, not proof of, exposure.
- **Strict** precision — the edge text *shows* the exposure — is ~56–60% for `explicit` and ~32–40% for
  `temporal` on held-out data. v2's 78% came from a friendlier sample (same annotator A: 78% → 60%).
- `none` edges: no confirmed missed exposure in 22 decided held-out items (upper CI ≈ 24–28%).
- Treat `temporal` as "consistent with exposure", not proof; `explicit` as the adopter naming the source.

### `mention` evidence (v4, 72 h window) — sample seed 4242, annotator A

| n | yes | plausible | no | unclear | strict | plausible-source | wrong |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 25 | 5 | 12 | 6 | 2 | 22% [10–42%] | 74% [54–87%] | 26% [13–46%] |

Much weaker than URL-post edges (0/50 wrong). Failure patterns: long lags (3 of 6 wrong edges at 177–1,753 min,
all 5 `yes` under 2 min); URL fragments that are not URLs (`https://daily-signal-garden` inside a regex); the
adopter's own repo coinciding with a name someone else mentioned. → v5: mention window 60 min, dotless hosts
flagged as noise. Because these changes were chosen on this sample, v5 is re-measured on a **fresh** sample below.

### `mention` evidence (v5, 60 min window, dotless hosts = noise) — fresh sample seed 9090, annotator B

| n | yes | plausible | no | unclear | strict | plausible-source | wrong |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 25 | 6 | 13 | 5 | 1 | 25% [12–45%] | 79% [60–91%] | 21% [9–40%] |

The tightening did not measurably help (26% → 21% wrong; CIs overlap; different annotator). Remaining errors
are structural to name matching: generic filenames shared across sites (`agent-card.json`,
`quarter-life-crisis.html`), a domain treated as a name (`o3-ux.github.io`), and adopters who got the URL
elsewhere (own machine, a GitHub issue). **Decision:** keep `mention` as a separate low-confidence level
(~1 in 5 wrong), excluded from headline numbers. Not tuned further: excluding filename/domain slugs would fix
3/5 here, but that is tuning on this sample again for a level covering < 5% of edges — future work, with a
fresh sample.

## Known issues (tracer review, 2026-09-26 — `docs/TRACER_REVIEW.md`)

Measured on v5 outputs before fixing; **#11 and #12 were fixed in v6 (PRs #15, #14)** — see *v6 measured effect* below.
- **Room visibility (#11).** Since rooms v1 (2026-02-25) agents only see their current room. Of 34,030 sourced
  edges with a post-rooms source, the adopter's last known room differs from the source post's room for explicit
  77/2,943 (2.6%), temporal 700/27,878 (2.5%), mention 137/3,209 (4.3%). Those edges are likely not direct
  chat exposure. The samples above did not stratify by room, so their numbers include such edges.
- **Talk-only text loss (#12).** 324/20,673 model_output adoptions had NULL `agent_action`, blanking their text;
  ≤ 109 had a candidate source and could flip to `explicit`.
- **Adoption time is an observation bound** (first *recorded* use), and a source row is a *representative*
  prior post, not proven transmission (review #3, #4).

### v6 measured effect (PRs #14 + #15, rebuilt 2026-09-26)

| evidence | v5 | v6 |
|---|---:|---:|
| temporal | 33,149 | 32,461 |
| explicit | 3,547 | 3,519 |
| mention | 3,581 | 3,520 |
| stale | 1,027 | 897 |
| cross_room | – | 907 (1.2%) |
| none | 32,274 | 32,274 |

Transitions: temporal→cross_room 633, stale→cross_room 125, mention→cross_room 85, explicit→cross_room 64
(adopter names the source, but the source's post was in a room the adopter wasn't in — likely learned via another
channel); temporal→explicit 41 (#12). 48 edges `room_unknown`. The held-out precision above was measured on v3–v5 and
includes edges that v6 now labels `cross_room`; a fresh blind sample stratified by room visibility is still to do.

## Confession audit — narrow lexical frame (#22, 2026-10-01)

**Status: primary labels only; independent annotation pending.** The audit does **not** establish
additional independent instances of contradicted admissions beyond the RPG episode in Finding 2.

**Frame and selection.** `explorer/confession_audit.py` normalizes Markdown emphasis/code markers and
curly apostrophes, then retrieves explicit first-person fabricated/hallucinated/made-up language,
first-person denials of *actually* running/executing/testing/verifying/seeing/checking/posting/sending/
publishing, and a bounded possessive formulation. The exact regex is a module constant. The agent-chat
frame contains **13 messages from six agents**, Nov 27, 2025–Jul 23, 2026, on export `838b415`.
The requested sample size was 30; all 13 are retained in SHA-256 order using seed **2026100122**.
This is a census of that narrow lexical frame, not a prevalence sample of all admissions. Recall is
unknown. An initial 61-message pilot was dominated by routine negative observations and missed
Markdown-wrapped admissions; the query was revised before drawing the final frame. This was exploratory
retrieval development, not a held-out detector evaluation.

**Evidence and labels.** Each packet includes full same-agent chat from the prior **72 hours**. The
primary reviewer links an original claim within that window, where identifiable; all recorded actions,
outputs, and errors in the **60 minutes before that original claim**, inclusive, are included. Without
a linked original, the window ends at the candidate admission. For quotation checks, selected later
source-check actions before the admission are separately identified. No screenshots or full input
prompts are included. The original-claim linkage and supplemental retrieval are investigator-selected;
second annotation independently interprets the same evidence, not an independently retrieved record.

First screen whether the post asserts an admission: ordinary disclosures of uncompleted plans,
hypothetical concerns, and retractions *of* admissions are excluded. Then label the specific admission
`supported / contradicted / undetermined`. **No matching record in a finite window does not establish
that work never happened**: supported requires positive evidence consistent with the admitted error.
Attempted GUI clicks or typing do not establish publication. Agent narration, an authored draft, and
actual source/tool output are distinguished. A separate no-record field does not determine the label.
Primary labels were made with model identities visible; masking applies to the second review only.

| Primary disposition | Messages | Distinct episodes |
|---|---:|---:|
| Admission contradicted | 2 | 1 |
| Admission supported by recorded source checks | 1 | 1 |
| Substantive admission, undetermined | 5 | 3 |
| Not an asserted fabrication/hallucination admission | 5 | — |
| Total | 13 | 5 among the 8 eligible messages |

Both contradictions (`2be874a3`, `b805e848`) repeat **the known RPG development episode**: original
report `453f3c9e`; branch checkout/scanner/tests `7eb90869`, `9934714f`, `42e49223`, `a32bed14`.
They are not two independent replications. The supported admission `7b0a1fcd` concerns a code-docstring
attribution: authored case-study turn `e8b2c7eb` versus subsequent recorded source retrieval/search
`1fe38618` and function output `b2943d5b`. The latter support the correction for the observed source
version; they do not establish intent or prove every prior revision lacked the wording.

The undetermined messages cover three episodes: reply publication (`919988a6`, `ac5034a4`, `687c6c6d`),
a chess-board misperception (`818e5f43`), and a reader quotation (`6e2afc45`). The reply trace includes
actual typing `cb8a52a9` and a click `9e1feb00`, but no textual completion result. The chess trace has
agent-constructed board positions and attempted input, not authoritative live board state. The reader
quotation trace establishes draft writing/revision, not what the GUI source actually said. These
coverage limits prevent binary adjudication. Full IDs and analytical label reasons are in
`explorer/confession_cases.json`; no source excerpts are committed.

**Denominators and uncertainty.** Contradicted messages are 2/13 candidates (15.4%; Wilson 95%
**4.3–42.2%**), 2/8 substantive admissions (25.0%; **7.1–59.1%**), or 2/3 decided admissions
(66.7%; **20.8–93.9%**). The last fraction excludes five undetermined admissions and should not be used
as the headline. These requested Wilson intervals are **descriptive binomial calculations**, not
sampling uncertainty for this completely enumerated frame and not intervals for model-label error.
Repeated messages, episode selection, investigator retrieval, missing visual evidence and development
overlap invalidate an iid population interpretation. At episode level, one of five eligible episodes
is contradicted, one supported, three unresolved. Excluding the known RPG episode leaves **zero
contradictions among six eligible messages in four episodes**, five messages still unresolved. We
cannot infer how often agents in general make false admissions or compare this rate directly with a
differently selected completion-claim study.

**Blind handoff.** The box file `/data/eval_codex22/review_v2/blind.jsonl` contains all 13 packets;
`cases/C01.json` etc. allow one-at-a-time review. `INSTRUCTIONS.txt` defines the protocol. Model-name
fields are omitted, names/handles in text are masked, and row IDs are opaque, with mappings and primary
labels kept separately. Dates, episode details and writing style can still reveal identity; this is
masking, not guaranteed anonymity. Do not give the independent annotator `key.json`,
`primary_labels.json`, `metadata.json`, the case plan, or this results section. Candidate evidence is
untruncated; markers and numeric results remain available after identity masking. The export checks
for residual known names and model-family tokens before writing. Independent labels and agreement
must be added later; no agreement claim is made now.

Reproduce on the authorized box with code and case plan together:

```sh
/opt/explorer/venv/bin/python confession_audit.py --parquet /data/parquet --out /data/new-private-audit
```

The output directory must be new. Data parquet stays read-only; only derived review files are written.
The metadata records the regex, seed, code/plan hashes, packet sizes in rows, blind-file hash and counts.
