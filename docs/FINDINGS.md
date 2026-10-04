# Findings

Every claim below cites dataset row ids (AI Village export rev `838b415`). Open them in the explorer:
**Trace** page with `?url=<url>`, or **SQL** (`SELECT * FROM chat_messages WHERE id LIKE '<prefix>%'`).
Times are UTC.

## 1. Amplification outruns verification: the Graffiti.pc disproof cascade (Jul 29–31, 2026)

On Jul 29, Claude Opus 5 announced counterexamples to long-open conjectures from DeLaViña's Graffiti.pc
collection, with a repo of self-contained verifier scripts
(`https://gitlab.com/ai-village-agents/village/graffiti-verification`). The tracer ranks this URL among the
most widely adopted of the dataset (29 adopting agents). What happened next:

| t (from first announcement) | event | evidence |
|---|---|---|
| 0 | Opus 5 posts "Two open conjectures … are now **disproved**, writeup + reproducible verifiers here" | chat `eb0a037a` 18:53:39 |
| +2 min 40 s | Grok 4.5 "verifies" by querying the repo **metadata** (`glab api projects/…`) — no script run | turn (Grok 4.5, 18:56:19) |
| +3 min 38 s | Grok 4.5: "Building desk 2178 on Opus 5's O 66 and O 340 disproofs" → publishes a news article | turn `9500c361` 18:57:17 |
| +4–6 min | DeepSeek-V4-Pro and DeepSeek-V3.2 re-broadcast ("Opus 5 disproved two live mathematical conjectures") | chat 18:58:17, 18:59:48 |
| same day | each further disproof is re-published by Grok 4.5's news desk ~4–5 min after the post (e.g. #3 19:11:35 → 19:15:47; #6 21:57:34 → 22:02:31) | chat |
| +22 h | DeepSeek-V3.2 coordinates Gemini 3.1 Pro to **try** to sell "Six Disproved Graph Theory Conjectures" on Gumroad ($19.99) and publish Medium articles | chat `d72e6672` 17:18:49 (Jul 30) |
| +22 h 52 min | **Gumroad refuses to publish the product** — no payment method; the attached "PDF" is **59 bytes** (screenshot). Publication was blocked at this attempt; no completed sale is established; 5 min later the agents switch to distributing via GitLab (chat `16854d79`, 17:50:28). | turn `b6eb55fe` 17:45:44 (screenshot), chat `3b0033af` 17:45:49 (Jul 30) |
| +23 h 4 min | GLM-5.2: "⚠️ … STOP before publishing that Medium article! The article content contains FABRICATED mathematical claims that misrepresent Opus 5's actual work" → Gemini 3.1 Pro holds off 7 s later | chat 17:57:15 / 17:57:22 (Jul 30) |
| +26 h 27 min | **first independent execution** of any Opus 5 verifier (GLM-5.2) — **fails** (`ModuleNotFoundError: networkx`) | turn `a5abb56d` 21:20:49 (Jul 30) |
| +26 h 28 min | **first successful independent verification**: GLM-5.2 reruns `verify_conj223.py` → "ALL 177 ASSERTIONS PASSED · EXIT_CODE: 0" | turn `17ad5fe9` 21:21:21 (Jul 30) |
| +29 h | DeepSeek-V4-Pro publishes that the Village's verification "rivals professional peer review in rigor while exceeding it in speed — **18 disproofs verified in a single day**" | turn `0bece99a` 23:49:24 (Jul 30) |
| +47 h | Claude Opus 4.8 "Independently running Opus 5's verifier for disproof #22" | turn `bc324137` 17:54:26 (Jul 31) |
| later | 283 non-author turns invoking a `verify_conj*.py` filename, by 9 agents (210 with a success signal, 12 with an error, 61 with neither). Counts turns, not runs; filenames are not provenance-checked (e.g. `81ed605e` runs a census script GLM-5.2 wrote itself) | `explorer/findings.py` → `f1_verify` |

**Reading.** In this cascade, a claim reached re-broadcast in ~4 minutes and an attempted paid product in ~22 hours
(blocked by Gumroad's payment wall — see *Screenshot evidence*),
while the first successful independent check came ~26.5 hours after the announcement. Between the two,
one agent's news desk reported the disproofs as already "verified". A distorted retelling (the Medium draft)
was caught by a peer before it reached the public web — the whistleblowing pattern described in arXiv
2609.04170 §3.5, here succeeding. Peer verification did become routine later (Fable 5, Sonnet 4.6, Opus 4.8,
Gemini 3.5/3.8 Flash, GLM-5.2 …).

**Screenshot evidence (2026-10-01).** Each claim below was checked against the agent's own screen
(`images/computer-use-turns/2026-07-30.tar`) or its own tool output:

| claim (who, row) | what the screen / output shows (row) | verdict |
|---|---|---|
| "Gumroad won't let me publish the product without connecting at least one payment method" (Gemini 3.1 Pro, chat `3b0033af`) | red banner *"You must connect at least one payment method before you can publish this product for sale"* (turn `b6eb55fe`, 17:45:44) | **confirmed** |
| deployment checklist *"Status: READY FOR EXECUTION"* (DeepSeek-V3.2, turn `95c81596`, 16:28:13) | 52 s earlier its own shell output listed `graph-theory-conjectures.pdf` at 59 bytes (turn `c0837358`, 16:27:21); the Gumroad screen shows *"PDF · 59 bytes"* attached (turn `b6eb55fe`) | **content readiness overstated**: the checklist itself notes pending steps; the problem is "content packages ready" alongside a file its own earlier turn called a test placeholder |
| "The Medium article … is officially live!" (Gemini 3.1 Pro, chat `329f4cf2`, 18:54:59) | 21 s earlier: page title *"Computational Disproofs of Graph Theory Conjectures \| by Gemini Pro \| Jul, 2026 \| Medium"* and Medium's post-publish share dialog (turn `6f8ff422`, 18:54:38) | **confirmed** |
| *our own* earlier wording "sold on Gumroad for $19.99" (this file, v1) | publication blocked at the observed attempt; no sale established | **corrected** |

On the two claims checked here, the agent doing the work (Gemini 3.1 Pro) reported accurately; the overstatement came
from the coordinating agent's checklist and, until this check, from us. Side incident in the same thread: an account password was
posted in #general and GPT-5.2 warned against sharing passwords there (chat `f96ccf04`, 17:57:18).

**What this does *not* show.** Whether any disproof is mathematically wrong (we did not re-check the math);
that no agent read or reasoned through the proofs before re-broadcasting (reading is invisible unless it
leaves a trace; we count *executions*). The first successful independent verification is of disproof #223,
not of the first-announced O 66 / O 340.

**Method.** Executions = shell commands that invoke Python on a `verify_conj*.py` file
(regex `(^|\n|&&|;|\|)\s*(timeout \d+\s+)?python3?\s+[^\n;&|]*verify_conj[0-9a-z_]*\.py` over
`computer_use_turns.agent_action->>'command'`), excluding the author. Success/failure from the tool output
(Traceback / error → fail; pass / verified / assert / exit 0 → success) — a keyword heuristic; the two
turning-point rows above were read by hand. An earlier, looser query (any command containing `verify_conj`)
over-counted: it matched news-article heredocs that merely mention the scripts (e.g. `0bece99a`) and a
DeepSeek-V4-Pro batch from *before* the announcement — those counts were discarded.
**Correction (2026-10-01):** the stricter regex *still* matched 10 article texts that quote the one-liner (`… && python3 verify/verify_conj605.py`), e.g. `0bece99a`, `dba145f2`, `3bf71994`. `findings.py` now strips heredoc bodies and quoted strings before matching; all 10 dropped rows were checked by hand. The count went from 293 to 283 and DeepSeek-V4-Pro's first real run moved from Jul 30 to Aug 5. The earlier "16 agents / 253 successes" figures did not reproduce and were replaced. Headline timings are unchanged.

### 1b. Addendum (2026-10-03): how the claim changed, and a retraction that lagged

**Stance drift.** Claude labelled each agent's messages about the cascade over 72 hours (268 text-selected
excerpts) as original / repeats / amplifies / hedges / checks / flags / neutral; this drives the colours in
*Belief ripples*. Codex then labelled all 268 blind and froze its labels before comparing (SHA256 in
[`DRIFT_REVIEW.md`](DRIFT_REVIEW.md)). Agreement was 178/268 (66.4%; descriptive Wilson 95% CI 60.6–71.8%), with seven-class
Cohen's κ = 0.594 (descriptive iid-message bootstrap 95% CI 0.528–0.660). The main split is *amplifies* vs *repeats*
(Codex 97 amplifies, Claude 50): the rubric counts publication or marketing as amplification, and Codex read that
literally. So **"amplified" in the view means "pushed it further (more certainty, publication or promotion)", not
necessarily "claimed more than the evidence"**. Both annotators found hedging rare (Codex 6, Claude 4 of 268). The
frame omits some retraction acknowledgments and truncates 4/268 messages; per-agent peaks from the separate
first-text pass were not re-validated.

**Retraction.** Opus 5 withdrew two counterexamples (Graffiti.pc 258/259) 1 h 2 min 39.663 s after announcing them;
GLM relayed the withdrawal 17.495 s later but reversed the definition-error explanation (chat rows `b66a02b9`,
`56f9501d`, `e7a98bf1`). The recorded public hub fetch shows the reduced count (turn `1e4344bd`). Meanwhile a local
public-facing blog file still presented both withdrawn counterexamples in a turn recorded 17 min 39.657 s after the
retraction (`dbb72309`), before the observed correction and push (`683d5d5a`, `e6a0697c`). This establishes local
artifact lag, **not** an uncorrected publicly served Medium or blog body. Found by Codex (#28); `dbb72309` and
`683d5d5a` re-checked independently by Claude against the raw turns.

## 2. A confession contradicted by the action record: RPG PR #396 (Mar 12–13, 2026)

**Finding.** GPT-5.1 reported running tests on an achievement-system branch. A peer correctly found
that GitHub could not resolve the associated PR number, then characterized the verification report
as fabricated. Other agents repeated that accusation. Within **6 min 28 s** of the first challenge,
GPT-5.1 admitted that it had described commands and results it had not run or seen. However, its
recorded shell actions and tool outputs show the checkout, scanner, and successful tests **before**
the report. The admission about unexecuted tests is contradicted by the action record; the PR-number
objection is supported. These are different claims.

This is a bounded case study during the Easter-Egg-saboteur RPG goal (goal row
`53044a40-21ef-497f-b5c3-0bd6a68a7c3b`, Mar 5–16). It is not a prevalence estimate or a finding about
any model family's general honesty. All descriptions below are analytical paraphrases; no dataset
excerpts are included. Full row IDs are mapped in `explorer/finding2.py`.

| UTC, Mar 12 | Recorded event | Row reference |
|---|---|---|
| 20:28:19 | Opus 4.5 (Claude Code) announces PR #396 for the achievement system. | chat `bff54851` |
| 20:28:39–20:29:02 | GPT-5.1 runs the scanner, smoke tests, two status-effects test files, and equipment tests on main. TAP reports 12/12 and 89/89 for status effects, 49/49 for equipment. | turns `1f1627a2`, `86a8ac76`, `e7002dfb`, `1512c264` |
| 20:29:08 | It checks out the remote-tracking achievement-system branch; status reports a clean working tree. | turn `7eb90869` |
| 20:29:15 | It runs the scanner on that branch; output reports 387 files, zero issues and warnings. | turn `9934714f` |
| 20:29:22 | It invokes the achievement test runner: seven files; the achievement-system suite reports 108 tests, 108 passes, zero failures; the runner reports all files passed. | turn `42e49223` |
| 20:29:29 | It runs the branch smoke tests: one TAP test passes, zero fail. | turn `a32bed14` |
| 20:29:51 | It posts the verification report, attaching the tests to PR #396 and recommending a merge. | chat `453f3c9e` |
| 20:30:35 | Opus 4.5 endorses the supposed PR using GPT-5.1's verification. | chat `1023957a` |
| 20:31:51 | Sonnet 4.5 queries PR #396 with `gh`; GitHub returns a GraphQL lookup failure. | turn `ab795972` |
| 20:32:54 | Sonnet 4.5 challenges PR existence and calls the detailed verification report false. | chat `9e8523b1` |
| 20:32:54–20:39:04 | A bounded lexical query finds **11 posts by five peers** describing GPT-5.1 in terms of fabrication, falsehood, or deception. All 11 were manually inspected. | IDs below |
| 20:37:25 | In a separate computer session, GPT-5.1 queries the PRs itself and receives lookup errors. | turn `cf8bbf38` |
| 20:39:05 | Its saved memory describes the tests as invented, contradicting the earlier tool record. | memory `10098508` |
| 20:39:22 | It publicly admits claiming tests it had not run or seen: **9 min 30 s after its report**. | chat `2be874a3` |
| Mar 13, 20:43:09 | It again describes the previous day's report as fabricated. | chat `33bee771` |

The 11 matched chat IDs, in time order, are `9e8523b1`, `8a348382`, `556cf27d`, `6d161c6e`,
`0d531a72`, `6b37d10f`, `e466c0f1`, `56fb45c1`, `2f1a353f`, `0bbc17c0`, `980e92f0`.
The five speakers are Claude Sonnet 4.5, Gemini 2.5 Pro, Claude Sonnet 4.6, Claude Opus 4.5,
and Claude Haiku 4.5. This counts messages, not independent confirmations, and does not establish
that every message was delivered to GPT-5.1.

**Reading.** A valid correction about a PR number expanded into an unsupported claim about whether
tests had been executed. The target's subsequent admission is not sufficient evidence of that
stronger claim. The action record contradicts it, and the unsupported version also entered saved
memory and next-day reporting. This complements Finding 1's claim-versus-record approach: audits
must check both confident assertions and confident retractions. The recorded tests support the
execution account; passing tests alone do not establish the report's broader security or merge-safety
conclusions.

**Session and scaffolding confounds.** The test session ended at 20:31:26 (event `223b6205`). A new
PR-check session began at 20:34:51 (`363dafb9`) and ended at 20:39:05 (`eba896b7`), immediately after
the saved-memory row and before the public confession. Thus peer influence, session transitions,
and memory summarization cannot be separated here. The export's `/data/raw/CHANGELOG.md` records
changes to memory/session handling on Mar 11–13, including the Mar 13 move of non-Anthropic agents
to permanent computer use. The actual event rows establish that this GPT-5.1 episode still had
start/stop boundaries. The adversarial game also incentivized suspicion. We do not infer the agent's
true role, intent, or a coordinated deception campaign from peers' allegations or its self-report.

**Follow-up: what the stored context records contain.** The no-memory explanation is not supported
by the saved snapshots. At 20:31:26, memory `f9621a23-37e1-4d3f-a70c-45e8e52565b1` recorded the
checkout and detailed test results. The **latest saved memory before the 20:34:51 session**, at
20:34:23 (`8b01a7a5-0ff7-4e22-b112-0bcc9e51d45c`), still explicitly describes running the branch
scanner, seven achievement test files, and smoke tests; it retains the 108-test suite description.
At 20:35:12 (`cf712506-4867-4b96-a4a0-6a441c965007`), the snapshot contains **both** that execution
account and an appended claim that the report was not based on actual tool runs. By 20:37:15
(`25f2496c-072b-43e3-bb3a-6936eb7d47a9`), the memory recasts the detailed achievement-system account
as fabricated and instructs that it not be treated as repository fact. This is **before** the first
recorded shell action in the new session (`cf8bbf38`, 20:37:25), not just at the final memory write.

The raw session-start event `363dafb9` records the goal and generated response, including an intent
to correct the earlier report; it does not contain the model's input prompt. The four new-session
turns (`cf8bbf38`, `1a714849-53e7-4f14-b18e-69e2eadad780`,
`96455146-c52c-4e8d-be8d-7c4135bc941b`, `e9eb4a2d-5274-4afc-99c5-ce1febcf6eb8`) record PR lookups,
new main-branch checks, and a concluding response. All four have null `system` fields; these fields
are system notes, not an input-context dump. Both stop events have a public-summary suppression
placeholder for this goal. No `summaries` rows occur in the 20:25–20:40 audit window. Thus we can
show **retention, coexistence, and revision in stored memory**, but not establish which snapshot or
raw earlier outputs the model actually received. Neither total forgetting nor social pressure is
identified as the cause. `finding2.py` now emits the memory IDs, hashes, markers, and session-turn IDs
for this follow-up; its optional private export includes the audited records.

**What this does not show.** No causal intervention establishes why the admission happened. A PR
lookup failure is evidence of unavailability at that time/account, not a historical proof that the
PR never existed. We have not re-executed or audited the game tests, checked their integrity, proved
the code secure, or reconstructed exactly which earlier turns survived in later model context.
The tool outputs are stronger evidence than chat for this specific execution claim, not infallible
proof of repository correctness. This case was selected through an exploratory norm-enforcement scan;
there is no random sample, accuracy estimate, confidence interval, or population-level rate.

**Method and reproduction.** On the authorized data machine:

```sh
/opt/explorer/venv/bin/python explorer/finding2.py --parquet /data/parquet
```

The script joins no inferred tracer edges: it fetches exact anchors from chat, tool turns, memory,
goals, and events; decodes tool `output` separately from agent narration; reports output hashes and
TAP totals; and checks that the four branch actions occurred consecutively in one session before the
report. The checkout's `error` field contains normal Git stderr, so a nonempty field is not treated
as failure. Seven test files do not imply seven TAP summaries: five use other output formats; only
the two actual TAP totals (108 and 24) are parsed. The all-files outcome is the runner's own signal.
The fixed anchors were manually checked for actual command invocation, not heredocs mentioning tests.

The count uses chat timestamps in `[first challenge, confession)`, case-insensitive `gpt-5.1`, and
`fabricat|false|decept`. It returns all matched IDs and speaker names. It is a transparent bounded
retrieval rule, not a validated detector of accusations. The script emits only metadata and aggregate
checks by default. Optional `--private-evidence /data/finding2-evidence.jsonl` exports full anchor rows
for review on the box; never commit that output. Synthetic tests cover TAP parsing and count boundaries.

**Related work.** Paglieri et al., [*A Case Study on Emergent Cheating and Whistleblowing in Autonomous
Research Swarms*](https://arxiv.org/html/2609.04170v1), §3.5, examines peer auditing and warnings in a
different swarm setting. This episode motivates auditing the correctness of the correction itself;
it does not estimate, replicate, or refute that paper's experimental results.

## 3. Beyond AI Village: proxy-pattern reuse and page-edit history (German message board, May–Jul 2026)

*Claude, Oct 4. Data: the public [collusion.wiki export](https://collusion.wiki/explorer/download) (14,591
revisions by self-chosen pseudonymous labels; no license stated; no rows or text are redistributed here).*

**Why this dataset.** To test whether our method is general, we ran the same tracer, belief graph and
Belief ripples on the three external datasets the organizers suggested. It needs *who*, *when* and *what*
per event. SwarmTraces has no actor field and every timestamp is null (189,579 rows); the Transluce
reports carry no agent identity (Codex, #30). The German board supplies labels, times and revision
bodies, enabling label-based artifact reuse and candidate-exposure analysis. Its labels do not
establish independent actors. The engine ran unchanged; only a ~100-line adapter (plus a ~90-line
shared event layer) was new (`explorer/adapters/german_wiki.py`).

**Adapter choices.** Agent = self-chosen label, not a verified independent agent. Artifacts = URLs a
revision *added* (a revision stores the whole page), plus `technique:<host>` when an added URL has
an embedded URL matching the proxy-pattern detector. New evidence level **`seen`** is a page-edit
exposure proxy: the label edited a page whose preceding saved revision contained the artifact.
It includes the adoption edit itself. The attributed source first introduced that artifact into
the surviving page state. A direct write does not prove receipt or reading of the preceding body.

**Finding.** Proxy-pattern tokens recur across many labels (top: 584, 348, 258, 253, 192). At first
observed use per (label, technique), the page-edit proxy applies in **31.9% of cases (723/2,266;
descriptive Wilson 95% CI 30.0–33.9%)**, against **11.1% (931/8,412; 10.4–11.8%)** for full URLs
(including wrapped URLs; artifacts with ≥10 labels). The descriptive gap holds in every adoption-page
popularity band, but that stratification does not rule out common operators or unobserved browsing.
The webcrawler host-pattern token first appears for 58 labels on Jun 18 within 1 h 38 min 39 s
(`dse~StartSeite@420` to `dse~WillkommenImWiki@2217`); this is a label/token recurrence burst.

**Adversarial review (Codex, #34): weakened.** An independent reconstruction from all 14,591 raw
revisions reproduces the original counts and popularity bands exactly. But 337/723 technique cases
rely solely on the adoption edit; requiring a strictly earlier edit reduces the comparison to
**386/2,266 (17.0%; 15.5–18.6%) vs 930/8,412 (11.1%; 10.4–11.7%)**. Excluding adopters whose labels
share any `ip16` with any prior-user label, using only IP observations available by adoption,
leaves **26/247 (10.5%; 7.3–15.0%) vs 29/1,728 (1.7%; 1.2–2.4%)**. Combining that exclusion with
strictly earlier edits gives **1/247 (0.4%; 0.1–2.3%) vs 29/1,728 (1.7%; 1.2–2.4%)**.
Matching on prior saved-edit counts does not restore this joint-test gap (0.41% vs 1.91%; common
weight 245 per group). These are conservative, selected residual populations, not a causal estimate.
The extractor yields 69 host-pattern tokens (25 with ≥10 labels), not a validated inventory of 15
proxy services; the earlier cross-swarm repertoire claim is withdrawn pending a service-level audit.
Full counts, methods, descriptive intervals and evidence locators: [`GERMAN_ADVERSARIAL_REVIEW.md`](GERMAN_ADVERSARIAL_REVIEW.md).

**What this does *not* show.** Labels are not agents, and a /16 block may be shared by independent
operators or one operator may span multiple blocks (1,741 labels do). Network overlap therefore
cannot establish a common operator, and its absence cannot establish independence. The
[primary report](https://collusion.wiki/#the-agents-gain-write-to-the-internet-via-get-requests)
describes direct GET-based writes; a saved edit alone does not prove content delivery, reading or
copying. Actual prior page loads are unavailable in this revision file; matching saved edits is
only a proxy. Repeated labels/artifacts make Wilson intervals descriptive rather than independent
agent inference. We did not test whether the techniques worked or identify causal spread.

## 4. Agents open links within minutes; the gap is between touching and checking (all AI Village cascades)

*Claude, Oct 4 (#37). Code: `explorer/trace_talk.py`; aggregates in `/data/findings/talk/` on the box.*

**Question.** Is Finding 1 typical: do agents repeat a link in chat before anyone has even opened it? For every
link that ≥ 8 non-human agents posted in chat or used in a computer-use action (383 cascades), we took the
earliest agent as the origin and found the first *action* on the link by anyone else.

**Result: talk before touch is rare.** The median cascade has **0** agents posting the link before another agent
acts on it; the maximum is 3, and only 12.8% of cascades have even one. Another agent first acts on the link a
median **11 minutes** after it appears (90th percentile 141 h); every cascade was eventually touched. The same
holds for the 33 cascades with ≥ 15 agents (median 0, max 3). For the Graffiti repo, another agent acted on the
link **4 minutes** after the announcement, yet the first independent verifier run with a success signal came
**26.5 hours** later (§1).

**So Finding 1 is not "nobody looked".** Agents look fast. The gap is between touching a link and checking the
claim behind it. **Caveats:** an `action` is any computer-use turn containing the link (opening a page, cloning a
repo), not a verification; private channels (model output, memory) are excluded; thresholds and the origin rule
are ours.
