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
replaying an agent's session with its screenshots, and story views for first-time viewers.

**Belief ripples**, the explorer's first page, is a general view of how a belief spreads *and changes*. Any seed
(a link, a claim, or an agent's week) sits at the centre. Agents sit on log-time rings (a minute, an hour, a day,
a week) by when they first touched it. Each agent is drawn split: the top half is what it **said**, coloured by its
strongest stance so far (repeats, pushes it further, hedges, flags, checks), and the bottom half is what it **did** (acted,
ran a check that passed, or was contradicted by its own screen). Edges show who heard it from whom and which checks
backed or contradicted a claim, and every node and edge opens the dataset rows behind it. A time slider replays it,
with clickable key moments. Codex built the graph engine (`belief_graph.py`, tested); Claude built the renderer and
the stance labelling.

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
- **The claim changed as it spread.** Within 3 minutes peers were calling the results "an absolute milestone";
  almost no one hedged. A public Medium article went live a day later, and 26 minutes after that the author
  retracted two of the results (rows `6f8ff422`, `56f9501d`); 17 minutes later an agent's local blog file still listed
  them (turn `dbb72309`). Codex re-labelled all 268 stance excerpts blind: κ 0.59, with the main split on what counts
  as "pushed further" (publication vs. more certainty). Details: [`FINDINGS.md`](FINDINGS.md) §1b.

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

### How often do "it's live / sent" claims fail on screen? (3,896 claims)

We paired a random 3,896 of the 6,350 completion claims that have a screenshot ("is live", "published", "has been
sent" …) with the agent's last screenshot from the 10 minutes before. Claude Code labelled them on a private server
next to the data, with no shell or web access, writing a short description of each screen. Every "contradicted"
flag was then checked against what the agent did *after* the screenshot, and by hand.

- **21 confirmed contradictions out of 1,385 checkable claims: 1.5% [1.0–2.3%].** That's a lower bound: another 28
  flags were undetermined or too weak to count, and most screenshots don't show the claimed thing at all.
- **The recurring form is "sent" when it's still a draft** (7 of the 19 server-batch cases). Twice the same agent
  repeated it: Claude Sonnet 4.5 posted "✅ Email sent … at 10:19 AM" and later "confirmed the help email was
  successfully sent", and both of its screenshots show the email still in Drafts.
- Others: an "implemented" file that is 0 bytes, an article "published" but still marked Draft, a story
  "published" whose `git push` never ran, and a "live" form never published and shared under a garbled ID.

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

**At scale (Codex, 200 fresh claims).** Codex restricted the frame to explicit first-person technical claims ("I ran
the tests …") and checked each against 90 minutes of the agent's own record: **0 contradicted** among 152 eligible.
An independent Claude check of 49 also found **0**, though the two disagreed on how many of the rest count as
"supported" vs. merely unbacked (κ 0.19). **Taken together:** agents rarely invent command runs. What goes wrong is
mostly announcing work as *sent / published / live* before it is.

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
rev `838b415`. The dataset is not redistributed here: no rows or screenshots, only row ids, aggregate numbers
and the few short quoted phrases needed to state a finding. Research use only.
