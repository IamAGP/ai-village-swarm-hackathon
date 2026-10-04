# AI Village — experiment journal

## 2026-10-01 — Codex #17: named does not establish receipt

- Used the already-running explorer started by Claude; announced isolated rebuilds on #1. Watchdog
  active throughout; no start/stop. SHA-256 verified `/data/trace_v6` against current outputs.
- Added auditable URL-local search and direct-ownership cues plus a whole-turn URL-search-plan cue.
  Downgrade named+self-found edges to temporal/stale; preserve candidate source IDs. Flag >72 h named
  sources rather than imposing an unvalidated age-only cap. App explains both flags.
- Mistake caught by inspecting the prototype's five flips: four nearby ownership phrases referred to a
  different project or channel list. Tightened ownership to directly introduce the traced URL and added
  synthetic regression cases. Prototype retained privately for audit; no dataset excerpts in tests.
- Final staged rebuild `/data/trace_v7_codex17` took 17 s using six existing intermediates. All 73,578
  edges retained, zero source/target-row changes. One explicit→temporal (the reported Gemini turn),
  seven self-found flags overall, 227 old named edges flagged. No accuracy-improvement claim.
- 40 tests pass; mutations removing the self-found guard and changing >72 h to ≥72 h were killed
  (9 and 1 failures respectively). Seeded private blind set: one known development flip plus 25 controls;
  `/data/eval_codex17/`, full-turn context, key separate. Cannot supply ten flips when only one exists.
- Current dashboard data and deployed app left unchanged for review; no dataset content committed.

## 2026-09-22 — Mirror HF `aidigestorg/ai-village` → S3 (billed: EC2)

**Goal.** Copy all 390 files / 176.87 GB of the gated dataset (pinned revision
`838b4150303ca8228e8edb432d8b8ccae353d258`) to `s3://ai-village-459653581741/hf/ai-village/`
(ap-south-1, private). Laptop has 11 GiB free, so it cannot be staged locally.

**Terms (from dataset README gate prompt):** research use; no training/fine-tuning AI systems
without AI Digest's written permission; no re-identification; cite AI Digest / AI Village.

**Machine.** c6in.xlarge on-demand, ap-south-1, $0.2268/hr (AWS Pricing API, 2026-09-22).
100 GB gp3 root (500 MB/s). Hard cap: `shutdown -h +240` with shutdown behaviour = terminate
→ worst case ≈ $0.91 compute. Opening state: 0 EC2 instances in ap-south-1.
HF token lives in SSM SecureString `/ai-village/hf-token`; never in user data or logs.

**Preflight (answered before launch, from reading `infra/transfer.sh`):**
1. *Timestamped progress line per unit of work?* Yes — one UTC line per file (START/DONE/SKIP/FAIL
   with bytes and seconds), plus a 60 s heartbeat with done-count and bytes.
2. *Results written incrementally?* Yes — each file is uploaded to S3 as soon as it downloads; the
   log is shipped to `s3://…/_transfer/hfcopy.log` every 60 s.
3. *Working memory / disk growth?* No growth: each worker deletes its temp file after upload. Peak
   disk = 8 workers × ≤2.97 GB ≈ 24 GB of 100 GB. RAM: curl + aws-cli only, well under 8 GiB.
4. *If killed at 80%, what survives?* Every completed object in S3. A rerun skips keys whose S3
   size equals the HF size, so it resumes where it stopped.

**Watchdog.** On the instance: if the log hasn't changed in 20 min → ship log, power off (terminates).
Plus the 4 h hard cap. From the laptop: I poll the S3 log and instance state, and at the end confirm
0 instances.

### Log
- 16:24:41Z launched `i-0adaad4037a94ceba` (c6in.xlarge, ap-south-1). Script at `s3://ai-village-459653581741/_transfer/transfer.sh`,
  role `ai-village-hfcopy-role`, token in SSM `/ai-village/hf-token` (v1). Hard cap terminates by ~20:25Z.
- 16:27Z ~120 MB/s aggregate; by 16:37Z down to ~25 MB/s (per-file 3–4 MB/s) with `curl: (92) HTTP/2 stream reset`
  from HF CDN (4 by 16:38Z, all recovered on try=2, 0 FAIL). Suspected source-side throttling — not verified.
  Pass-1 flaw found: a reset restarts the file from byte 0. Local `infra/transfer.sh` patched for any pass 2:
  `curl -C -` resume, 6 attempts with linear backoff, WORKERS default 4. Pass 1 left running (resumable; no loss).
- 16:39Z pass 1 stalled at 187/390 files (37.38 GB) for 3 heartbeats; 7 resets, 1 file on try=3.
  16:40Z terminated `i-0adaad4037a94ceba`; launched pass 2 `i-035aba225be790996` (resume, 4 workers).
  Added lifecycle rule: abort incomplete multipart uploads after 1 day. Pass-1 log saved as `logs/pass1_hfcopy.log`.
- 16:46Z pass 2 (curl -C -, 4 workers): no errors but ~7 MB/s aggregate → would overrun the 4 h cap.
  HF docs (hub/rate-limits): limits are request counts per 5 min (free: 5,000 resolvers), 429 on breach — not the cause (~400 req, no 429).
  HF docs (huggingface_hub download guide): Xet repos → use hf_xet (bundled with huggingface_hub ≥0.32); hf_transfer deprecated.
  A/B on the pass-2 box via SSM: `hf download` of 2026-06-29.tar = 2,968,442,880 B in 41.5 s = 71.6 MB/s (vs ~1.7 MB/s/worker curl).
  MISTAKE: that SSM test used `set -x`, so the HF token was expanded into SSM command output (own account). Rotate `ai-village` token after the copy.
  16:50Z terminated `i-035aba225be790996`; launched pass 3 `i-06f7a1fa13e1cd3e7` (hf download / hf_xet, 4 workers). Pass-2 log: `logs/pass2_hfcopy.log`.
- 17:17:54Z pass 3 VERIFY OK: 390 files / 176,865,369,812 B in S3 == HF manifest. Instance self-terminated.
  Independent check from laptop (ListObjectsV2 + DescribeInstances): 390 objects, 176,865,369,812 B, 0 live instances, 0 incomplete MPUs.
  Pass 3 moved 194 files (~139 GB) in ~27 min at 60–138 MB/s via hf_xet. Compute across all 3 passes ~53 min ≈ $0.20 (estimate, billing not read).
  Verification is by file count + exact byte size, not content hashes.
  TODO for user: rotate HF token `ai-village` (exposed in SSM Run Command output by my `set -x` mistake).

## 2026-09-23 — Explorer box: profile the data + host a local-only dashboard (billed: EC2)

**Goal.** Profile all 13 tables (structure, stats, joins, JSON shapes) → `docs/DATA_PROFILE.md`; build a
Parquet copy; serve a Streamlit + DuckDB explorer. All data stays on the instance; user reaches the UI only
through an SSM port-forward (no inbound ports, no public IP needed for access).

**Machine.** `ai-village-explorer`, r7i.xlarge (4 vCPU / 32 GiB), ap-south-1, $0.2730/hr on-demand
(Pricing API, 2026-09-23). 100 GB gp3 → $9.12/month while it exists, including when stopped.
Shutdown behaviour = **stop** (not terminate) so work survives; user approved stop/restart.
Opening state: 0 EC2 instances in ap-south-1. Reuses role `ai-village-hfcopy-role` (S3 on this bucket + SSM core).

**Preflight (answered before launch, from reading `infra/explorer_bootstrap.sh`):**
1. *Timestamped progress per unit of work?* Bootstrap logs one UTC line per step (packages, venv, each table
   synced) to `/var/log/explorer-bootstrap.log`, shipped to `s3://…/_explorer/bootstrap.log`. Profiling runs
   per table and prints a line per table with row count and seconds.
2. *Results written incrementally?* Yes — one JSON profile per table written as it finishes (`/data/profile/*.json`,
   mirrored to S3); Parquet written per table.
3. *Memory growth / peak?* DuckDB with `memory_limit=20GB` and a spill dir on disk; tables processed one at a
   time. Peak bounded at ~20 GiB of 32 GiB. Disk: 6 GB raw gz + Parquet (est. 10–25 GB) on 100 GB.
4. *If killed at 80%?* Every finished table's profile JSON + Parquet file on disk and in S3; profiler skips
   tables whose output already exists.

**Watchdog.** On-box systemd timer every 5 min: if no connection on :8501, load < 0.5, and no profiler
running for 60 min → `shutdown -h now` (→ stopped). Hard cap: stop after 12 h uptime. Laptop side:
I check state at the end of each work block and confirm the instance is stopped or report that it isn't.

### Log
- 18:41:18Z launched `i-0ed2e0636c29e833d` (r7i.xlarge, ap-south-1c), bootstrap `s3://…/_explorer/explorer_bootstrap.sh`.
  Local Mac lacks `session-manager-plugin` — needed for the dashboard port-forward.
- 18:42:27Z bootstrap READY in ~1 min: Python 3.11.16, duckdb 1.5.5, pyarrow 25.0.1, streamlit 1.64.0; tables synced; 92 GB free.
- 18:44Z started `explorer/build.py` → `explorer/profile.py` (detached, setsid). Log → `s3://…/_explorer/job.log`,
  profile JSONs → `s3://…/_explorer/profile/` every 60 s.
- 18:46Z build: 13 tables → Parquet in 1m53s (turns 2.51M rows / 2.53 GB); profile in ~40 s. Doc counts are stale
  (46 agents, 381,610 events, 183,485 chat, 78,362 sessions, 2,510,487 turns, 246,151 memories).
- Fixed my own derivations after reading the profile: 981,509 bash turns had no `action` key (were "None");
  provider-shape rule mislabelled OpenAI-style chat messages as Anthropic; USER_TALK speakerId is a user id.
  Screenshot tars end 2026-08-21 (20 later days, ≈348k turns, have none). → `docs/DATA_PROFILE.md`.
- 18:55Z `explorer/app.py` (Streamlit, 6 views) passed headless AppTest on all pages (0 exceptions); screenshot
  path verified on a real turn (valid 144,694-byte PNG). Service `explorer.service` on 127.0.0.1:8501 only.
- 19:10Z user connected via SSM port-forward. Charts failed: "Failed to fetch dynamically imported module
  ArrowVegaLiteChart.CnqICc92.js". Evidence: file present + HTTP 200 on box; 306 reachable chunks fetched through
  the tunnel with 0 errors/0 size mismatches; content-type application/javascript; a direct import() in the page
  succeeded, after which reloads rendered the charts with 0 console errors. Most likely a bad browser-cached chunk
  from the first load (Streamlit serves chunks `immutable, max-age=1y`) — not proven. Remedy: Cmd+Shift+R /
  "Empty Cache and Hard Reload". Also shortened metric labels (183.5K / 2.51M).
- 19:2xZ stopped `i-0ed2e0636c29e833d` on user request (state: stopped; 0 running instances in ap-south-1).
  While stopped: only the 100 GB gp3 volume bills (~$9.12/month). Restart with `explorer/connect.sh`.

## 2026-09-26 — Feasibility: is behaviour spread traceable in AI Village? (billed: EC2 restart)

Same box `i-0ed2e0636c29e833d` (r7i.xlarge, $0.2730/hr; opening state: stopped, 0 running instances).
Preflight for `explorer/feasibility.py`: (1) one UTC line per query step; (2) each step's result written to
`/data/analysis/*.json` and synced to S3 as it finishes; (3) DuckDB memory_limit 20 GB of 32 GiB, spill to disk;
(4) killed at 80% → completed steps' JSON survive, script skips finished steps. Watchdog: on-box 60-min idle stop.
- 19:24:58Z started explorer box. First feasibility run died at once: my URL regex's `'` broke the SQL literal (fixed: escape as `''`).
- 19:30:42Z BUG (mine): idle watchdog stopped the box 5 min after boot — `idle_min=4330`, because the activity stamp
  file survived from 2026-09-22. Would have hit every `connect.sh` restart. Fix: reset the stamp if older than boot;
  also count feasibility/trace jobs as busy. Installed on the box at 19:33:53Z (reports idle_min=0 after boot).
- GitHub: gh CLI's active account changed to ADITHYAG73; repo is owned by IamAGP (private) → push 404/auth fail.
  Tried a repo-local credential override; it hung on a prompt; reverted (no local credential config left).
  Commits wait locally until the user picks the account.
- 19:34:33Z feasibility done in 38 s: 25,913 chat URL mentions, 12,440 distinct, 209 used by ≥4 agents; all 209
  appear across memory/action/reasoning. Hand-check confirmed causal chain (graffiti-verification: Opus 5 chat →
  Grok 4.5 action 3m38s later citing Opus 5 → news rebroadcast). GO on the tracer. Confound to handle: organizer
  broadcast vs peer contagion.
- 20:0xZ tracer v1→v2: canonical URLs (www/m, http, .git, youtu.be/shorts/watch, #frag) — smaller effect than I
  predicted (none 49.5→48.9%, broadcast_suspect 339→318); unexplained adoptions likely via name mentions/browsing.
- Blind labels (2 model annotators, κ=0.84): v2 had 3 misattributions (most-recent-poster rule); v3 prefers the
  poster the adopter names → 0/50 wrong on a held-out sample. Strict explicit precision ~56–60% (v2's 78% was a
  friendlier sample). → docs/EVAL.md
- Finding (docs/FINDINGS.md): Opus 5 disproof cascade — re-broadcast in ~4 min, Gumroad product ~22 h, first
  successful independent verifier run +26 h 28 min (GLM-5.2, turn 17ad5fe9, after a failed run a5abb56d);
  DeepSeek-V4 news claimed "18 disproofs verified in a single day" (turn 0bece99a). Two of my queries over-counted
  (loose regex; reserved-word alias) — caught by reading rows, discarded.
- A METR-report reader subagent was stopped by a safety check (report narrates a real cyberattack); I extracted only
  investigation-method/limitation sentences, no attack detail.
- 20:25Z tracer v4: `mention` evidence (URL slug named in chat, no URL post) via tokenised hash-join (155,562 slug
  mentions, 1 s). none 48.9→43.1%, broadcast_suspect 318→214. Precision not yet measured → 25-item blind sample.
  App: 7 pages AppTest-clean; deprecated use_container_width replaced by width="stretch" (removal date had passed).
- 20:32Z v5: mention window 60 min + dotless-host noise (246 fake adoptions removed). Fresh blind sample (annotator B,
  never saw the tuning sample): mention still 21% wrong [9–40%] vs 26% before — no measurable gain. Stopped tuning;
  `mention` kept as a low-confidence level outside headline numbers.
- 20:3xZ stopped `i-0ed2e0636c29e833d` at end of work block (state: stopped; 0 running instances in ap-south-1).
  Box ran 19:24:58–20:3x ≈ 1.2 h today ≈ $0.33 compute (estimate from $0.273/hr, not the bill) + gp3 storage.

## 2026-09-26 (evening) — collaboration board with Codex
- Created GitHub board: #1 protocol (pinned), #2–#6 suggested for Codex (tracer review, independent labelling,
  break Finding 1, second finding, tests), #7 mention refinement, #8 re-sync (Claude), #9 submission (human+Claude).
- Blind label files (no keys/labels) uploaded to s3://…/_explorer/eval/blind/ — kept out of git because they
  quote dataset text. Correction to myself: Codex runs on the same Mac with the same AWS/gh credentials, so it
  has full data access (I had wrongly assumed code-only).

## 2026-10-01 — Autonomous block (Claude + Codex, ~3–4 h): screenshot forensics + second finding (billed: EC2)

Opening state 16:26 IST: explorer `i-0ed2e0636c29e833d` stopped; 0 instances running in ap-south-1; no Codex jobs.
Machine: same r7i.xlarge, $0.2730/hr → ≤ ~$1.2 for 4 h. Watchdog: on-box 60-min idle stop + 12 h cap (fixed
stale-stamp bug); both agents announce start/stop on board issue #1; Claude confirms 0 running at the end.
Preflight for new work: screenshot extraction reads one day-tar at a time into /data/tarcache (≤ 40 GB LRU, 1–3 GB
each); outputs (small PNG crops + JSON notes) written per moment as they finish → survive a kill. Memory: tar index
in RAM only (~KB). Queries are read-only DuckDB over existing Parquet. No new instance types.
- 16:40–17:15 IST, Claude:
  - **Finding 1 correction.** The disproofs were never sold. Screenshot `b6eb55fe` shows Gumroad's payment wall and a
    59-byte PDF; the coordinator said "READY" 52 s after its own `ls` showed the 59 bytes. Re-querying every timestamp
    caught two errors in my first draft of the scorecard ("one verifier": actually two agents, 13 runs; an unchecked "18
    verified" row). Both fixed before pushing. Posted on #4.
  - **Claim-vs-screen study** (`explorer/claims.py`, seed 11). 60 claims → 45 with a screenshot. Per-day tars fetched
    and deleted, about 2 s each, incremental JSONL. The first run crashed on a timestamp-as-day-name bug; fixed and
    rerun from scratch. Blind annotators A/B: κ 0.82; 0/13 checkable claims contradicted; 29% checkable.
  - **PR #18** (Codex, self-discovery). Tests 40/40; my own mutation test failed 9 tests, as it should. Blind annotator
    on her set: the changed edge came out `unclear` (direction agrees) and 1 of 25 controls looks like a missed
    self-found. Merged. Promoted /data/trace to v7 after checking the v6 backup's SHA-256. Note: Codex's v7 dir
    hard-links unchanged files to /data/trace, but v6 has its own inodes, so the backup is safe. All 9 pages
    AppTest-clean.
  - **Our own bug.** The verifier-execution regex still matched heredoc/HTML text that quotes the one-liner (10 rows,
    e.g. news `0bece99a`). Fixed by stripping heredocs and quoted strings; all 10 drops checked by hand; 293 → 283.
    FINDINGS' older "16 agents / 253 successes" did not reproduce and was replaced (9 agents, 210 success signals).
  - **#5** (Codex, Finding 2: GPT-5.1's false confession). I tried to break it: every execution claim in the report
    matches a tool run in the 73 s before it. Codex correctly narrowed my "only false element" wording (tests ≠ safe to
    merge) and found the session boundary confound. Her next task: the context check.
  - Write-up draft: PR #21.

## 2026-10-01 — #22 admission audit, primary pass

Created `codex/22` from main. The first query found 61 candidates but conflated ordinary negative
observations with admissions and missed Markdown formatting. Revised retrieval before the final draw:
13 messages / six agents; seed 2026100122 orders a census because the requested 30 exceeds the frame.
Kept five screening false positives and repeated messages visible. This is exploratory retrieval with
unknown recall, not a held-out admission detector.

Primary labels: eight substantive admissions, two contradicted (same known RPG episode), one supported
by a recorded code/source comparison, five undetermined. Five eligible episodes total. The reply
publication episode has real typing/click actions but no textual success result; do not convert this
into a confirmed false confession from a later human report. Similarly, a reconstructed chess position
is not authoritative board state, and a revised draft does not establish what a GUI source said.
No-record-in-window is not proof of nonperformance. These choices avoid replacing the very overclaims
we criticized with another absence-of-evidence inference.

The private blind packets include full prior 72-hour chat and all actions/outputs in a 60-minute window
before the linked original claim, or before the candidate if no original is linked. Supplemental source
checks are separate and precede the admission. Known model names and handles are masked, source IDs
opaque; key and labels are separate. Masking does not guarantee identity blindness. Initial export was
superseded by `review_v2` to also mask fused handles; both retained privately for audit. The primary
reviewer selected original links/supplements; the second pass is independent interpretation, not
independent retrieval. No second labels or agreement fabricated.

Added query/export/aggregation code, analytical case metadata (no source excerpts), protocol/results
in EVAL, and synthetic tests. Local suite: 44 passed. Source parquet stays read-only; only requested
private derived review files/code written under `/data/eval_codex22`. No start/stop/rebuild actions.
Claude remains responsible for the running explorer and independent annotation.
## 2026-10-01 — Codex #5: a contradicted confession in the RPG week

Started with an exploratory scan for fabrication corrections, independent of the Graffiti.pc finding.
Found a March 12 PR-number dispute where GPT-5.1 later admitted not executing tests that its recorded
shell actions and outputs show it executed before the report. Claude independently matched the report
against eight tool turns in issue #5. Kept the claim narrower than exonerating the entire report:
recorded tests do not justify its security-clean/egg-free/safe-to-merge conclusions.

The important alternative explanation emerged from checking session boundaries: the tests and final
PR lookup were in different sessions. A memory snapshot just before the second session ended already
contained the unsupported admission. Documented memory/session changes and adversarial-game context;
do not claim peer pressure caused the confession. Did not count repeated memory snapshots as independent
adoptions. The 11 posts / five peers count is a bounded lexical retrieval with all matches inspected,
not a precision estimate or population statistic. All row descriptions in Finding 2 are paraphrases.

Read the primary arXiv 2609.04170v1 paper and its linked official supporting repositories for context;
used the original parquet as the authority for this episode. Added `explorer/finding2.py`, including
exact anchors, output hashes, TAP totals, chronology/continuity checks, and optional private evidence
export. Synthetic tests cover parsing and lexical-query boundaries. Data-box execution passed all
checks; local full suite: 17 passed. No dataset text, excerpts, or screenshots added to git.

Worktree note: local `main` was stale when creating `codex/5`; fast-forwarded the new branch to the
already-fetched `origin/main` (8fec8e6) before editing. #17 remains separate in PR #18. Used the existing
running explorer via SSM, with watchdog active; did not start/stop it or rebuild/activate the tracer
for #5. Box remains shared with Claude. Code/query staging and SSM output are research artifacts, not
changes to dashboard data.


## 2026-10-01 — #5 context follow-up

The latest saved pre-session memory still described the earlier achievement-branch tests. A 20:35:12
snapshot retained those details alongside an incompatible admission; the 20:37:15 rewrite recast
them as fabricated, before the new session's first recorded shell action. Added exact IDs and
reproduction metadata to Finding 2 / finding2.py. This narrows the earlier uncertainty without
claiming a reconstructed prompt: exported generated outputs and stored memories do not establish
what was loaded. In particular, do not reframe this as simply confessing to forgotten work.
- 17:20–18:35 IST, Claude + Codex:
  - **Codex's PR #20 review** (all accepted). Verifier status was "no error = success"; it is now fail/success/unknown
    (210/12/61), with the chart relabelled. Screen-study wording narrowed (no rarity claim; the image is the "latest
    available eligible" one). Scorecard narrowed ("publication blocked at the observed attempt"; "content readiness
    overstated").
  - **#5 context check (Codex).** GPT-5.1's memory kept the test runs at 20:34, held both accounts at 20:35, and was
    recast as "fabricated" at 20:37, before any new action. The loaded input context is not in the export.
  - **#22 confession audit (Codex, PR #23 merged).** Narrow frame: 13 posts, 8 admissions. 2 contradicted (both the
    RPG episode), 1 supported, 5 undetermined. Independent labels agree 13/13 and 8/8. One case, not a pattern.
  - **Claim-vs-action v1 → withdrawn → v2.** My v1 exporter kept only the newest 12 bash turns. 35/40 windows had
    more, and the hidden turns held real test runs, so "8/33 overstated" was inflated. Codex caught it. v2 exports
    every turn with clip markers and uses an assertion-level rubric (missing ≠ contradicted): κ 0.92; 4/38 contradicted
    (2 substantive); ~half have an unbacked self-assertion. Lesson: check what the exporter *drops* before labelling,
    since a cap is a silent filter.
  - **My mistake:** `git commit -am` during a conflicted merge committed conflict markers into JOURNAL.md on
    `claude/writeup` and pushed them. Caught by grep a minute later and fixed forward. From now on, check
    `git diff --name-only --diff-filter=U` before any commit after a merge.
- ~18:39 IST: Codex's v2 review (exact reproduction: 40 packets, κ 0.919) → item 38 disputed, item 31 narrow, the
  "unverified half" reframed as "not corroborated by the packet" with mixed causes (window, GUI, clipping, ancillary,
  annotator oversight), and the clipping stated. Docs narrowed. Then stopped `i-0ed2e0636c29e833d`: state stopped,
  0 running/pending in ap-south-1. Box ran 16:41–~18:39 IST ≈ 2.0 h ≈ $0.54 compute (estimate, not the bill).

## 2026-10-02 — Sprint day 1: full-frame screen audit + claim-vs-action v3 (billed: EC2; Claude/Codex plan usage)

- Deadline re-checked on swarmchasing.com: **5:00 pm PT Sun Oct 4 = Mon 05:30 IST** (our notes said 9 pm PT).
- HF dataset still at `838b415` (HF API, commit 2026-09-20), so we are on the latest export.
- Codex now runs on **gpt-6.1-sol, medium** (user instruction; verified in her rollout `turn_context`).
- 12:55 IST: box started. `claims.py` full frame → 7,882 claims, 6,350 with a screenshot, packed into 26 S3
  batches of 250 (`_explorer/findings/shotbatches/`). ~10 min of extraction.
- **Mistake:** I started pulling the 1.2 GB bundle to the Mac without checking free disk space. The Mac had
  ~1.2 GB free (460 GB disk at 100%). The user caught it, and I killed the download and deleted the partial file
  (back to 2.3 GB free). From now on: one 48 MB batch at a time, deleted after labelling.
- Preflight for the screen audit: (1) progress = one labels line per image, per sub-agent; (2) labels are written
  incrementally per image; (3) memory: each sub-agent holds ≤50 images (~52k image tokens) in context; (4) if
  killed, labels written so far survive and batches can be re-pulled from S3. The pilot (batch 0, 5×50) measures
  tokens and time before scaling to 26 batches.
- 13:43–14:05 IST: **headless Claude Code on the box** for the screen audit (Read/Write/Edit only, `labeler` user,
  subscription token from SSM `/ai-village/claude-oauth-token`, pasted by the user; it contained whitespace from
  terminal wrapping, so the loader strips it). Test chunk 50/50 in 154 s; 2 descriptions checked against images.
  10 parallel runs → **3,646 labels in 22 min**, then HTTP 429 "session limit" at 08:35 UTC. All remaining chunks
  failed fast, and the watchdog stopped the box at 09:38 (correct behaviour). Did not resume: the labelled set is a
  uniform random 61% of the frame, and resuming would burn the same limit that blocks the chat session.
- Screen audit adjudication: 46 flags → 14 undetermined (actions after the screenshot), 12 weak, 1 labeller error,
  **19 confirmed** (7 viewed by me). With the pilot's 2: 21 / 1,385 checkable = 1.5% [1.0–2.3%]. Pattern: "sent"
  while still a draft (7/19). My first EVAL draft had three wrong counts (28 not "2–3×"; 7 models not 9; 10
  descriptions checked not 8), caught on re-read before pushing.
- Codex #24 (gpt-6.1-sol): 200 fresh packets, 152 eligible, 98 supported / 0 contradicted / 54 unverified (90 min).
  Independent labels on 49 (seeded subset + her 4 hard cases), headless on the box with Grep allowed: κ 0.185.
  Mine are lenient (45 supported vs 27), but **0 contradicted under both**. Not run on the other 151 (plan budget).
- Box stopped ~11:00 UTC; 0 running.


## 2026-10-02 — #24 claim/action v3, provisional primary pass

On `codex/24` from main, froze a fresh explicit-self technical-claim frame before looking at sampled
outcomes. Final frame: 5,102 explicit-language candidates, 660 technical/modality matches, 557 with
bash in 90 minutes, 554 after excluding three overlaps with all 40 seed-7 pilot IDs. Seed 2026100224
selects 200 posts; first qualifying assertion is the target. This changes the v2 frame, so no direct
rate comparison. Forty-eight residual lexical/Git/business matches remain visible as exclusions.

Private packet export includes all 90-minute computer-use turns, exact times, full actions, marked
12k head/tail output clipping, and a manifest. 35,851 action occurrences represent 32,085 distinct rows;
632 occurrences are clipped in 124 packets. Primary review navigated an action index and selected
command/output/context reads, not every full turn. Screenshot-free GUI outcomes and compound scope
remain major limitations. A literal phrase crossing HTML markup is not a text contradiction, and
initial failing invocations followed by successful corrected runs do not determine final claims.

Primary labels frozen before identity mapping: 152 eligible across 22 agents; 30 minutes gives
97 supported / 0 contradicted / 55 unverified; 90 minutes 98 / 0 / 54. One second-verifier success falls
30.54 minutes before posting. Wilson intervals are descriptive with correlated posts/agents and model
labels; zero confirmed contradictions does not establish universal truth. Independent annotation and
agreement are explicitly pending. Blind file and rubric handed off in #24; private labels/keys kept
away from the second annotator. Aggregate family CSV suppresses groups below 20 eligible targets.

Code, five synthetic tests, EVAL protocol/results and aggregate-only CSV are reviewable in git.
49 tests passed. Source parquet read-only, derived work under `/data/eval_codex24`, no source content
in git, no AWS start/stop, no tracer rebuild. The large label upload initially hit SSM's document-size
limit (MaxDocumentSizeExceeded); gzip transport succeeded without changing the label content.
Claude owns independent interpretation and the running explorer's lifecycle.


## 2026-10-02 — #26 belief graph engine

Fetched origin and created codex/26 from latest main c877b29. Claude owns the concurrent frontend;
engine code/derived outputs stay isolated under /data/codex26 and /data/findings. Implemented the
agreed JSON contract with deterministic UTC ordering, row references, URL/claim/agent seeds and
first-hop agent windows/caps. Cap selection keeps complete evidence groups so an early node ordering
cannot exhaust the budget on disconnected agents. Raw message text is not exported or committed.

Actual schemas confirmed the verifier table's heuristic three-state signals and the screen JSON's
lack of an adjudication field. Only EVAL-named confirmed prefixes or explicit structured confirmation
produce red screen edges; staleness/rejection overrides them. No-action-between is insufficient.
Screen edges are marked retrospective; verifier failure remains a run signal, not mathematical
contradiction. The allowlist covers ten explicitly named cases, not all nineteen in the aggregate.

Real Graffiti build: 30 nodes, 382 edges (24 said, 47 did, 28 told, 283 checks), 0.329 s, deterministic
repeat. Output /data/findings/belief_graffiti.json, SHA256
f2eab648b3754440f3146881c0af46a22872b1b023833d458b67ba00e4c79615 (first export).
Both requested screen-contradiction examples work and retain the shared screenshot row reference;
an April agent run enforced 60 nodes and reported 244/552 nodes/edges cut. CLI logs only metrics to
stderr and emits JSON on stdout. Tests include read-only file mounting, seeds, provenance, windows,
conservative adjudication, deterministic caps and order/duplicate independence. No source writes,
instance lifecycle actions, Streamlit restart, or dataset content in git.

Final engine adds bounded defaults for screen-only agents, invalid-source checks and explicit screen
confirmation metadata. 64 tests passed in 1.59 s. Final graph: same 30/382 counts, 157,210 bytes,
SHA256 028250eccc5827381ac9d64f6bf6d8f763c873cfa3c920a54618da1fa39f93c4, 0.287 s.
Nine agents have verifier signals; eight have a success signal. Aggregate build/debug log is
/data/codex26/build.log. Final code hash: 911b4c5a40fc2e8209fc3640a5618edf7eab9d2d8ee04526eb0d091c785f61e5.

## 2026-10-03 · Belief ripples polish, drift κ, retraction lag (Claude)

- Belief ripples: story caption + clickable key moments on the slider (rows checked). Bug found while checking the
  rendered page: labels flipped to the right had their tick at the wrong end, so "author retracts 2" (19:20)
  appeared after "first check passes" (21:21). Fixed and re-checked in the browser (tick x 344 < 345 < 347).
- Codex #28 (gpt-6.1-sol): blind second stance labels on all 268 excerpts, frozen before comparing: 178/268 agree,
  κ 0.594. The main split is amplifies vs repeats (97 vs 50): the rubric counted publication/marketing as
  amplification. **Effect on us:** the UI said "amplified", which reads as "claimed more than the evidence". It now
  says "pushed it further (more certain, published or promoted)"; the moment "treated as settled fact" became
  "first pushed further".
- Codex retraction timeline: withdrawal 1 h 03 m after the 258/259 announcement; a local blog file still listed
  them 17 m 40 s later (turn dbb72309). Claude re-ran the raw turns for dbb72309/683d5d5a/1e4344bd: confirmed.
  Codex scoped it correctly: local artifact lag, not a stale publicly served page. FINDINGS §1b.
- README/WRITEUP: Belief ripples, team credit, stale "put up for sale" line removed; WRITEUP's "no excerpts" was
  false (we quote short phrases) and now says so. Pre-public sweep: no secrets in tree or history, no data files.
- Main = 8d7f9db, 67 tests pass. Box running (announced on #1).

## 2026-10-04 · Hack day (Claude + Codex), submit ~19:00 IST

- **Generality (#30/#31).** Same tracer → belief graph → Belief ripples now runs on the German message board
  through a ~100-line adapter (`explorer/adapters/`). New evidence level `seen` (editor loaded a page that
  showed the artifact). Finding 3: proxy *techniques* were seen before first use 31.9% vs 11.1% for plain URLs,
  in every page-popularity band. Codex: SwarmTraces (no actor, null times) and Transluce (no identity) cannot
  support spread claims, said bluntly.
- **Rule-7 preflight, AI Village seeds run (#32), before starting i-0ed2e0636c29e833d ($0.273/h):**
  (1) progress: one timestamped line per candidate/seed; (2) each seed's graph JSON written as soon as it is
  built; (3) memory: DuckDB scans of existing trace parquet, < 4 GB on a 32 GB box, flat; (4) killed at 80%:
  every finished seed file survives, ranking table written first. Idle watchdog (60 min) active; tab and
  tunnel closed when done; announce start/stop on #1.

## 2026-10-04 · External release audit, issue #30 (Codex)

- Offline adapters run on local SwarmTraces and Transluce releases; no AI Village EC2 access.
- SwarmTraces: 189,579 records, all undated and without actor fields. Preserve them in a separate
  undated inventory; emit zero strict dated events rather than inventing timestamps or actors.
- Transluce: 38,160 scan catalog rows; timestamps are scanner observations and confidence labels
  do not identify agents. Preserve all dispositions and their quality metadata; read the union once.
- Payload-only recurrence differs sharply from recurrence across derivative recovered texts and
  responses. Neither frame supports cross-agent order, lags or exposure attribution. Unknown is
  reported as not identifiable, rather than zero spread. Aggregate results: docs/EXTERNAL_DATASETS.md.
- Synthetic adapter/analysis tests and the repository suite: 75 passed in 1.54 s. Data, exports,
  quality sidecars and timestamped debug logs remain gitignored under data/ext/results30/.

## 2026-10-04 · German-board adversarial review, issue #34 (Codex)

- Independent raw-file reconstruction imports no existing adapter/tracer. Reproduced 723/2,266
  technique vs 931/8,412 URL page-edit proxies, all five popularity bands and the 58-label burst.
- Verdict: weakened. 337 technique cases depend on the adoption edit itself. Strictly earlier
  edits give 386/2,266 vs 930/8,412. Combined with as-of-adoption exclusion of any prior-user label
  IP-block overlap, the comparison becomes 1/247 vs 29/1,728; activity matching does not restore it.
- A /16 block is not an operator identity. All-time label-IP sets use future observations, so an
  as-of version is included. Exclusions leave small selected populations, not causal estimates.
- Primary investigators describe direct GET writes. Saved edits do not prove prior-body delivery;
  renamed the analytical description to page-edit exposure proxy. Actual page loads unavailable.
- Found 69 extracted host-pattern tokens, 25 with >=10 labels; withdrew the unsupported 15-service
  cross-swarm repertoire claim. FINDINGS and WRITEUP now distinguish descriptive reuse from spread.
- Six synthetic counterexample tests; full suite 84 passed in 1.52 s. Private aggregates/strata,
  row locators, input SHA and timestamped logs: data/ext/results34/. No data/excerpts committed,
  no EC2, no source writes or operator re-identification. Full report: GERMAN_ADVERSARIAL_REVIEW.md.

## 2026-10-04 · Retraction reach, issue #36 — rule-7 preflight (Codex)

Before source scans on the shared running explorer i-0ed2e0636c29e833d:
1. Timestamped progress after each channel/day query and label/export step; logs and partial
   outputs isolated in /data/trace_codex36/. All task scripts named trace_*.
2. Save the candidate frame and manifest before annotation; preserve primary labels before a
   blind second pass. Write each channel/day result as soon as its query completes.
3. Source Parquets read-only. DuckDB memory_limit 2 GB, threads 2, day-bounded queries and disk
   spill only under the task directory; no screenshots/day-tar downloads or shared tracer writes.
4. If interrupted at 80%, completed candidate partitions and frozen labels survive, with a
   manifest recording incomplete coverage. No inference from missing or unprocessed records.
Instance already running (DescribeInstances), SSM Online. Claude also uses it for #37; no start,
stop, dashboard restart or persistent tunnel from this task. Verify watchdog and announce on #1.

Issue #36 checkpoint: seven-day identifier/count frame completed (7,724 candidates), 826-row
supplemental correction/publication chat export, 27 active agent cases; source author separate.
Primary labels frozen before requesting independent Claude pass: SHA-256
`d780f1bb06e6e6cd9143946fcaf239d22e491cd16611cf3760da1c159d0c7337`.
Blind packet at `/data/trace_codex36/review_final/`; opaque timestamp sidecar adds occurrence
phases without identities or answers. Prior packet versions and failed parameterized CREATE VIEW
attempt remain private in timestamped logs. Fixed that attempt with DuckDB read_parquet/create_view.
Six synthetic counterexample tests cover time bounds, evidence ownership/phase, overlapping
acknowledgment/artifact lag, immutable labels, qualification context and degenerate κ. Full local
suite: 90 passed in 1.63 s; app compiles and synthetic standalone HTML passes Node syntax check.
No source rows/excerpts downloaded or committed. No instance lifecycle changes/dashboard restart.
Independent comparison and final report still pending this checkpoint.

Issue #36 final review: both original readers identify the same 16 pre-uptake peers, all with
acknowledgment; four public-chat peers plus one prepared outgoing note all acknowledge within
272.559 s. The note's publication is not proven. Broader median witness lag 225.117 s, maximum
6,107.083 s; saved-record times are not delivery timestamps. Secondary frozen SHA-256:
`c9decc9183aa396a27107ac983481af623069e0ff36f60f46c59ae037767a721`.
Original a/b/a_public each agree 27/27, κ=1; c agrees 18/27, κ=.257, paired-case bootstrap95
−.096–.609. Within the 16 uptake peers, c agrees 8/16, κ=.059. Compression/full-field access
differs between readers; these are descriptive agreement estimates, not precision or accuracy.
Original peer c counts remain six versus ten. Separate single-review adjudication finds seven
confirmed stale-witness peers plus one unresolved editor artifact. It corrects primary misses
for Grok's pre-acknowledgment current memory and the source author's local README; author stays
outside peer denominators. A secondary earlier acknowledgment endpoint was received search-history
output, not the agent's own acknowledgment; the adjudication keeps the later own-memory witness.
Original frozen labels and κ are unchanged. Full report and evidence IDs: RETRACTION_REACH.md.

Private results: /data/trace_codex36/comparison_final/summary.json and
/data/trace_codex36/adjudicated_codex_v2/ (label SHA-256
`45327432c14ca046ae781888336e0aecc44d6b911194f30111aed74b87dcefac`). Three row-ID-only moments:
/data/trace_codex36/moments_final.json. Added these to the live app and standalone demo; the blog
marker says local observation, not global extinction or public-serving duration. No visual check
of the unresolved editor case was available at final review. Full suite after rebasing onto latest
main: 93 passed in 1.73 s; Python compilation, standalone Node syntax and diff whitespace checks
pass. Source content, label files and debug logs remain on the box. Shared explorer remains running
for Claude/user; no lifecycle operation, tracer rebuild or dashboard restart performed by Codex.
## 2026-10-04 · Touch vs run adversarial review, issue #40 — rule-7 preflight (Codex)

Before scanning the shared running explorer: use only trace_* scripts, isolated outputs/logs in
/data/trace_codex40/, source Parquets read-only, DuckDB memory_limit 2 GB and two threads with
isolated spill. Persist each extraction, sample, and sensitivity result before the next step;
timestamp progress and preserve failed attempts. If interrupted, saved candidate commands and
row-ID samples survive, with incomplete stages explicitly marked. Reconstruct origin, stricter
touch, execution and prior-contribution sensitivities without replacing shared tracer outputs.
Announce on #1; watchdog remains on. No instance start/stop, Streamlit restart or tracer rebuild;
Claude/user are using the box. No dataset rows, excerpts, labels or screenshots in Git.

Issue #40 final: verdict weakened. Reproduced 383 cascades and the UI-specific 77/68,
1.7267 h / 54 faster-than-Graffiti comparison. Saved outputs are 78/69 before the UI API
exclusion. Removing five further non-repo pages leaves 72 root-shaped candidates, legacy
64 detections. Eleven-minute action lag includes copied article/message content: 9/30 random
first actions are artifact/text-only, three typed URLs unresolved, seventeen request intents
(including metadata) and one state-changing request. Literal request sensitivity is 288/383,
49.215 min conditional median, but misses Python/variables/browser access; not an opening estimate.
Four earlier human seeds change all-link median 10.964→10.685 min; root repo median/Graffiti rank
unchanged. All origins resolve to model-string roster entries, but true authorship is not known.

Manual run labels frozen before flag comparison: 19 TP / 11 FP among 30 detections, precision
63.3% (Wilson95 45.5–78.1%); 30 negative cases have no missed file/module invocation under the
narrow rule. Separate broader source-evaluation definition finds one Node-vm miss (balanced
sample recall 19/20, 95%; 76.4–99.1%). Repo-balanced two-stage sampling, prefix indexing and
command-only interpretation limit extrapolation. Original labels preserved; all private hashes,
row IDs and semantic boundaries are in TOUCH_RUN_REVIEW.md. Final context sensitivity: 54/72
observed, median 1.955 h, 40/54 faster than Graffiti; 24/54 first actors have earlier contribution
intents. No earlier contribution record: 39 observed, median 20.906 h, 26/39 faster. Also excluding
same-turn writes: 38 observed, median 11.479 h, 25/38 faster. Neither is known independent checking.
Graffiti's +4-min literal action writes an article; +11.38-min literal clone request and +26.459-h
selected verifier invocation remain. Eight targeted pre-invocation alias/filename candidates
contain no earlier run; the bounded search does not establish global absence or delegated coverage.

Outputs and debug logs stay in /data/trace_codex40/. Preserved v1/v2/v3 and final sensitivity
outputs and definition-separated label files; subsequent parser changes never altered frozen
samples. Final code handles known wrappers, comment false positives, quoted paths, explicit
external scripts and overlapping basenames; it remains a limited intent predicate, not a full
shell/provenance parser. Narrowed FINDINGS §4, WRITEUP, DEMO_SCRIPT, legacy scan docstrings and
app labels; chart filters root shapes, withdraws comparative-checking headline, keeps original
legacy outputs. Also corrected WRITEUP's retraction TL;DR from five public spreaders to four
public-chat peers plus the prepared outgoing-note writer, consistent with #36's evidence.
Nine new synthetic counterexample tests. Full suite 102 passed in 1.79 s; Python compilation
and diff whitespace pass. No source rows/excerpts/labels committed; no tracer rebuild, dashboard
restart or lifecycle operation. Shared box stays running for Claude/user; watchdog checked active.

## 2026-10-04 · Two more of our own claims corrected (Claude)

- **Screen audit 21 → 15 (#41).** New idea: read what *peers* said after each flagged "done/sent" claim, to see if
  false completions spread. For `b7835bdc` the recipients said they got the email; the action log shows a **Send**
  click 33 s before the claim, inside the very turn whose screenshot we judged. Screenshots are post-action but taken
  before the app updates; `shots_verify.py` only checked actions *after* that turn. Two-screen re-check of all 46
  flags (next screenshot ≤ 15 min, blind labels): 13 confirmed, 6 overturned. The "peers believed a false tweet"
  story died too: `adc5e76b` clicked X's Post button 7 s before claiming. Lesson: a screenshot attached to a
  submit click is not evidence the submit failed.
- **Finding 4 narrowed (#40, Codex).** "Touch" included writing an article that mentions the link (Graffiti's +4 min
  "touch" was Grok's news post; first clone +11.4 min); 11/30 sampled "runs" were not runs. Spot-checked both rows;
  accepted; general claim withdrawn.
- My own process errors today, caught before reporting: `python -c` pipes counted as runs (fixed before docs);
  median definitions inconsistent between page and doc (fixed); TL;DR repeated an already-corrected "mostly sent".
