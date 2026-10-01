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
