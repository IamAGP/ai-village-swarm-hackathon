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
