# AI Village — experiment journal

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
