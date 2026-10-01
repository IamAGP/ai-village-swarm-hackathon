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
