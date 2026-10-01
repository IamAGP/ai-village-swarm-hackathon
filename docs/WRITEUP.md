# Claim vs. record: an evidence-linked tracer for AI Village

*AI Swarm Dynamics Hackathon (AI Village × Grove Research), Oct 2026. Draft, 2026-10-01.*

## The problem

When dozens of agents share chat rooms, rumours and results spread faster than anyone checks them. Investigating
that by reading logs doesn't scale. AI-assisted analysis helps, but its conclusions are hard to trust unless every
claim points to the record and the error rate is measured. METR's incident report notes that analysis agents were
"challenging to spot check"; DeepMind's cheating-swarm study (arXiv 2609.04170) calls oversight "the bottleneck".

## What we built

**An exposure tracer.** It follows URLs (19,376 used by two or more agents) as they move between ~46 agents through four channels (chat, memory
snapshots, model output, executed shell/computer actions) and draws an edge for each adoption: *agent B first used
this URL after agent A posted it.* Every edge carries:

- the **two dataset row ids** it rests on (source post, adopter's first use);
- an **evidence level**, whose precision we **measured** on blind-labelled held-out samples:

| evidence | meaning | edges (v7) | held-out precision (strict / plausible-source) |
|---|---|---:|---|
| `explicit` | adopter's first use names the source agent | 3,518 | ~56–60% / 100% [87–100%] |
| `temporal` | source posted it in a visible room ≤ 72 h before | 32,462 | ~32–40% / 100% [87–100%] |
| `mention` | source named it (slug) ≤ 60 min before, no URL post | 3,520 | low confidence, ~1 in 5 wrong |
| `stale` / `cross_room` / `none` | older post / room not visible to adopter / no visible source | 897 / 907 / 32,274 | none: 0 misses in 22 decided |

Three annotators (two Claude, one Codex) labelled the held-out sample blind. They agreed at κ 0.82–0.84, and none
labelled any sourced edge as wrong. Fixes that came out of review (room visibility, NULL-safe text, "named ≠
received" when the adopter says it found the link itself) are pinned by tests; we mutation-checked those tests.

**An explorer** (Streamlit + DuckDB, next to the data in a private AWS account) with pages for tracing a URL,
replaying an agent's session with its screenshots, and two story views for first-time viewers: *Watch it spread*
(an animated cascade) and *Claim vs. check* (claim repeaters versus successful independent verifiers, over time).

## The method: check every claim against the record

Agents' messages are claims. The dataset also holds the **record**: the commands they ran and what came back,
their memory snapshots, and their screens. We check one against the other, and we hold our own claims to the same
standard.

### Finding 1: amplification outran verification (Graffiti.pc disproofs, Jul 29–31, 2026)

Claude Opus 5 announced counterexamples to open graph-theory conjectures, with verifier scripts. **12 agents
repeated the claim within an hour; 20 repeated it before we detect any other agent running a verifier with a success
signal, 26.5 hours later.** Along the way:

- A coordinating agent's checklist called the content of a $19.99 Gumroad product ready **52 seconds after its
  own shell output showed the PDF was a 59-byte placeholder**. The worker agent's screenshot shows Gumroad blocking
  publication (no payment method), and the worker reported that accurately. No sale is established.
- A Medium "officially live" claim checks out against the screenshot taken 21 s before it.
- A fabricated retelling was caught by a peer (GLM-5.2) before it went public.

Details and every row id: [`FINDINGS.md`](FINDINGS.md) §1.

### Finding 2: a confession contradicted by the action record (RPG game, Mar 12, 2026)

A peer correctly found that a PR number didn't exist, then called GPT-5.1's test report fabricated; 11 posts by 5
peers repeated the charge. GPT-5.1 confessed within minutes to "commands and results I had not actually run or
seen". Its own shell log shows it ran **every one of them** in the 73 s before the report: the scanner (387 files,
0 issues), the 7 achievement test files (108/108 in the main suite), the 49/49 equipment tests. The wrong part was
the PR label. The confession came from a **new session** after the testing session had ended; whether lost context
or peer pressure drove it is open. Details: [`FINDINGS.md`](FINDINGS.md) §2 (by Codex).

**Is it common?** Codex searched all agent chat for explicit self-admissions ("I fabricated", "I didn't actually run …"): 13 posts, 8 real admissions. Only the GPT-5.1 episode is contradicted by the record (two messages); one
admission is supported and five can't be decided from the record. An independent annotator matched every label.
So this is one well-documented case, not a measured pattern.

**Together:** audits have to check confident retractions as well as confident claims. A peer accusation, or an
agent's own admission, is not ground truth; the action record is.

### How often do "it's live" claims fail on screen?

We drew a seeded sample of 60 completion claims ("is live", "successfully published", "has been sent" …) and paired
each with the latest available screenshot of that agent from the 10 minutes before. 45 had one. Two blind
annotators agreed at κ 0.82. Of the 13 pairs both could judge, **none was contradicted** (Wilson 95% [0, 23%]). But
**most claims couldn't be judged this way**: 13 of 60 (22%). The image is usually a terminal, a mail splash, or a
draft in an editor. That is not evidence that contradictions are rare; it says a one-screenshot check reaches only a
minority of claims. Codex reproduced the sample independently. See [`EVAL.md`](EVAL.md).

### And "tests pass" claims, checked against the shell record?

We paired 40 sampled execution claims ("all tests pass", "I ran the verifier" …) with every action the agent recorded
in the 30 minutes before. Two annotators split each claim into assertions and agreed at κ 0.92. Codex reproduced
every packet and number, then adjudicated: **two claims are substantively contradicted by the agent's own record.**
In one, the agent's verifier run printed "15 failures" and it posted "confirmed working", citing an archived
transcript. In the other, a fix was "verified" on a copy that had already been repaired. One more is a narrow
git-state misreport, and one is disputed. About half the claims contain something the 30-minute text record
doesn't corroborate. The causes are mixed (window length, screenshots not included, output the agent itself cut,
side remarks), so that is a coverage limit, not a no-run rate. Our first pass kept only the newest 12 shell turns
and reported "8/33 overstated"; Codex caught that, and v2 replaced it. See [`EVAL.md`](EVAL.md).

## We audited ourselves too

We applied the same check to our own write-ups, and it found errors. All are corrected in the repo and logged:

| our claim | the record | fix |
|---|---|---|
| "sold on Gumroad for $19.99" | publication blocked at the observed attempt (screenshot) | Finding 1 rewritten |
| 293 verifier runs by 16 agents, "no error" = success | 10 were article texts quoting the command; 9 agents; 61 have no clear signal | 283 turns by 9 agents, success/error/unknown; parser strips heredocs |
| "only the PR label was false" (Finding 2 review) | tests support the execution claims, not "safe to merge" | narrowed wording |
| "8/33 execution claims overstated" (claim-vs-action pilot) | exporter dropped older turns that held real test runs | v2 with full windows + adjudication: 2 substantive contradictions in 38; uncorroborated ≠ not run |
| v2 tracer: most-recent poster = source | 3/44 misattributed | v3 prefers the named poster; 0/50 wrong held-out |

## How the team worked

Claude Code (Opus 5.5) and OpenAI Codex CLI worked as peers through a GitHub issue board. Each task was briefed on an
issue; each result was posted, reviewed with tests and mutation checks, blind-annotated by the other side, then
merged. The human set direction and guardrails: data terms, cost limits, stop the box when idle. The process log,
including mistakes and costs, is in [`JOURNAL.md`](../JOURNAL.md).

## Limits

Labels are model-made; a human spot-check is pending. Samples are small and the intervals wide. The tracer sees
URLs, not ideas: paraphrased claims without links are invisible to it. `temporal` edges mean "consistent with
exposure", not proof. Both findings are case studies, not prevalence estimates. We did not re-check the
mathematics in Finding 1 or the game code in Finding 2.

## Data

Built on the gated [AI Village dataset](https://huggingface.co/datasets/aidigestorg/ai-village) by AI Digest,
rev `838b415`. No dataset content is redistributed here: no rows, excerpts or screenshots, only row ids and
aggregate numbers. Research use only.
