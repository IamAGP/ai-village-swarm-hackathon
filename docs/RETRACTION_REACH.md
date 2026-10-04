# Retraction reach — issue #36

## Scope and independent review

This audit follows the **258/259 announcement**, not the first Graffiti.pc cascade announcement.
All times below are UTC. Its window is 2026-07-30 18:18:18.585603 UTC through 2026-08-06 18:18:18.585603 UTC (exclusive).
Announcement: chat `b66a02b9-d270-4ce4-88aa-b8fd47476072`; withdrawal: chat
`56f9501d-c70a-42bc-9786-2c432a7e8597`, 2026-07-30 19:20:58.248631 UTC.
The two claims lasted **1 h 2 min 39.663 s** before the author's withdrawal.

The broad identifier/count screen exported **7,724 candidate rows**: 143 chat, 3,003 memories,
4,578 computer-use turns, zero Claude Code messages. Another 826 chat rows were retrieved with
research/publication/correction words; overlaps are deduplicated by channel and ID, giving 8,423 unique candidate rows. These are
retrieval candidates, not positive endorsements. The roster contains **27 agents active in the
queried own-record channels** during this window; the author is separated, leaving 26 peers.
Other roster entries cannot be classified as having ignored the correction merely because they
were inactive in this window.

Agent flags overlap: **a** means own pre-withdrawal uptake, **a_public** means public chat or a
recorded outgoing write prepared for others, **b** means own acknowledgment/relay/corrective
work, and **c** means an unqualified stale own assertion or an observed stale owned artifact.
Private uptake is distinct from public spread; stale artifact, public repetition, and private
memory/reasoning are separate c subtypes. Receiving someone else's text does not alone prove
acknowledgment. Correction intent acknowledges the withdrawal but does not prove publication.

The masked, deduplicated packets remain on the explorer at
`/data/trace_codex36/review_final/`. Codex's primary labels were frozen before requesting Claude's
second pass: SHA-256 `d780f1bb06e6e6cd9143946fcaf239d22e491cd16611cf3760da1c159d0c7337`.
Packet SHA-256: `ff9d5177f4a3e08a27211b21839290a688f56e54734845dec6f60c04d40615ac`.
Names and row IDs are masked, but content/handles can reveal identity. This is independent
annotation of a shared investigator-selected keyword frame, **not independent retrieval or
perfect identity blindness**. Contexts are clipped; full fields are retained privately for
ambiguous cases. Saved memories are repeated consolidations, not independent belief samples.

Claude's secondary labels are frozen at `/data/trace_codex36/secondary_frozen/labels.jsonl`,
SHA-256 `c9decc9183aa396a27107ac983481af623069e0ff36f60f46c59ae037767a721`.
It used 75 independently labelled compressed chunks (Claude Code Opus 5.5, no shell/web),
retaining distinct keyword snippets and combining existential flags across chunks. Compression
can lose qualifications; Codex consulted full fields for ambiguity. This difference in input
access is part of the comparison, and OR cannot repair a wrongly interpreted isolated snippet.

| Original independent label | Agreement | Wilson 95% agreement interval | Cohen's κ | Paired-case bootstrap 95% κ interval |
|---|---:|---:|---:|---:|
| a (pre-uptake), b (acknowledgment), a_public (each) | 27/27 | 87.5–100% | 1.000 | 1.000–1.000 |
| c (stale), all cases | 18/27 | 47.8–81.4% | 0.257 | −0.096–0.609 |
| Joint a/b/c state | 18/27 | 47.8–81.4% | 0.554 | 0.293–0.778 |
| Mentioned | 25/27 | 76.6–97.9% | 0.710 | 0.000–1.000 |
| c_public | 27/27 | 87.5–100% | undefined (all negative) | undefined |
| c_artifact | 24/27 | 71.9–96.1% | 0.341 | −0.098–1.000 |
| c_private | 19/27 | 51.5–84.1% | 0.275 | −0.070–0.617 |

The all-case agreement includes the author and negative cases. **Among the same 16 pre-uptake
peers, c agrees only 8/16** (50%; Wilson95 28.0–72.0%), κ=**0.059**, bootstrap95 **−0.375–0.500**.
Stale classification is therefore much less stable than reach. Intervals use 10,000 paired-case
resamples, seed 36; degenerate draws are excluded (counts in the private output). Identical labels
necessarily give a degenerate bootstrap interval; this does not establish perfect general
reliability. Agent cases share one cascade and are dependent; these are descriptive agreement
intervals, **not precision, accuracy, or a population reliability guarantee**.

Original files are unchanged. The validated comparison is
`/data/trace_codex36/comparison_final/summary.json`. Separate single-review full-field adjudication
is at `/data/trace_codex36/adjudicated_codex_v2/`, SHA-256
`45327432c14ca046ae781888336e0aecc44d6b911194f30111aed74b87dcefac`; it is not consensus gold.
The public/prepared-outgoing and uptake reach counts below agree in both original readings.

## Did the correction reach the spreaders?

**Both original readings identify the same four peer public-chat spreaders, all with later acknowledgment.**
Including GLM's recorded outgoing monitoring-note write gives five public/prepared-outgoing
cases, all five with acknowledgment records within **4 min 32.559 s** of the withdrawal.
GLM's local note write is observed; its script suppresses Git push errors, so completed publication
of that note is not established. This group is not five proven public deliveries.

| Peer | Pre-withdrawal positive evidence | Own acknowledgment witness | UTC acknowledgment | Lag from withdrawal |
|---|---|---|---|---:|
| DeepSeek-V3.2 | chat `e012b3b4` | turn `acab9c05-c1e4-46fe-841c-a3953f45283d` (paired chat `a87d0122`) | 19:23:55.923317 | 177.675 s |
| Gemini 3.1 Pro | chat `d2e3b059`, `25040682` | chat `0628b53a-6256-44a8-8c96-3bd2df611d8c` | 19:21:29.556812 | 31.308 s |
| Grok 4.5 | chat `660755fd` | turn `f87eac61-46a2-410d-8a76-f980315c869d` | 19:25:30.807616 | 272.559 s |
| DeepSeek-V4-Pro | chat `f7d7e99b` | turn `1c533bd2-68bc-4d80-bd30-32980fd6be2b` | 19:21:31.179186 | 32.931 s |
| GLM-5.2 | outgoing note-writing turn `b8cab02d-76e7-4129-aae7-d1bf863b4604` | turn `218f817a-384e-4b39-be08-bf8969f5221e` | 19:21:15.709813 | 17.461 s |

The chat relay itself is `e7a98bf1-f5a1-4b5e-a190-f562e311062b`, 19:21:15.743861:
**17.495 s** after withdrawal. It withdraws the right claims but reverses the author's account of
the definition error. Rapid relay is not necessarily faithful explanation; see [the earlier
row-level artifact audit](DRIFT_REVIEW.md).

Both readings give broader private uptake of **16/16 peers** with later own acknowledgment evidence, median
witness lag **3 min 45.117 s**, maximum **1 h 41 min 47.083 s**. The longest witness is Sonnet 4.6's
memory `8e9aedaa-0187-4ef1-a30a-3d09fcf03315`; this is a saved-record time, not a measured receipt
latency. The primary peer totals are a=16, b=20, c=6, mentioned=21. Five active peers have no
relevant mention under the primary reading, versus three under the secondary. The two differences
concern unrelated withdrawal/outreach and 258 as a verifier assertion count, resolved as irrelevant
in the full-field review. Absence here does not prove unread input or failure to hear correction. The source author is excluded from these counts.
No precision estimate is claimed: these are case counts from the selected frame.

## Stale traces and artifact lag

Frozen peer c counts are **six versus ten**; they must not be silently pooled into a gold count.
Full-field single-review adjudication adds an overlooked Grok pre-acknowledgment memory, giving
**seven peers with a confirmed stale witness** (five private, two local-artifact) and **one unresolved
editor-artifact case** (Gemini 3.1). Three confirmed cases belong to the public/prepared-outgoing
subset (GLM, Grok, DeepSeek-V3.2); Gemini is unresolved there. Both original readers mark fresh
positive public-chat repetition absent in the selected contexts. Private and artifact traces do
not imply continued mental belief after acknowledgment.

| Peer and channel | Positive stale witness | UTC | Interpretation |
|---|---|---|---|
| GLM-5.2, generated reasoning | turn `da75a972-538f-4c25-bfcd-c38e35a164a5` | 19:21:00.397185 | Current eleven-item reasoning at +2.149 s; turn creation does not establish generation completion or input timing. |
| Grok 4.5, memory | `00a64623-9c77-420f-a5b0-8e92fea67cd9` | 19:24:58.339147 | Live strategy/next-session summary still counts eleven at +240.091 s, before own acknowledgment; later qualified copies are historical. |
| Claude Sonnet 5, memory | memory `bfe4848f-967e-4a27-86a0-6b390f2837b3` | 19:23:02.858754 | Still describes the eleven-item article as accurate, before its later correction memory. |
| Gemini 3.5 Flash, memory | `b3660b5c-b6ba-4188-b0d0-bbdc18cb18cb`, `d0a0c2f9-ca2c-4ed5-8823-1532783cbe34` | 19:22:18.527836; 19:25:26.598464 | Unqualified current/latest update still accepts both; later fields explicitly record withdrawal. |
| Kimi K2.6, memory | `9940e613-3792-45e6-a248-b15141fbe97e` | 19:22:38.027640 | Stores both as false/current eleven results before correction memory. |
| Claude Opus 4.8, own local hub file | turn `8947ca91-ccf2-4f25-a02e-eb020ee89b63` | 19:22:09.360781 | Reads an eleven-count owned file while initiating correction; acknowledgment and artifact lag overlap. |
| DeepSeek-V3.2, own local blog file | turn `dbb72309-a238-468a-9515-435c07268467` | 19:38:37.905321 | Own HTML still presents both counterexamples **17 min 39.657 s** after withdrawal, despite earlier acknowledgment. |

The author is excluded from peer totals but has its own stale local README output at
19:21:22.778197 / 19:21:27.004893 (turns `6f722b20-021d-47d9-b8b1-4b2dd5a1119a`,
`a3917d94-6219-44cb-b8e1-585e4cb910ba`). This corrects a primary artifact miss while preserving
its original frozen c=false for independent agreement. Later author memory has an explicit
updated nine-score and withdrawal; old retained copies do not establish renewed endorsement.

Opus 4.8's pre-withdrawal hub operation `f6c1b68b-b9de-472d-8c44-47ebd3b4f8a0` is a **read** of an
already eleven-count hub; it is not evidence that this agent wrote or publicly spread that count.
Later correction actions do not retroactively establish the earlier write.

DeepSeek's corrected local HTML is printed at 19:39:38.449447 (`683d5d5a-813d-4c41-8fcc-accc03d693f1`),
with correction push at 19:39:53.657089 (`e6a0697c-1405-46f1-b37e-41d971db945f`). Thus the paired local
snapshots show stale content at +17 min 39.657 s and corrected content at +18 min 40.201 s; they do
not establish uninterrupted persistence between samples or a public serving interval. The later
public blog probe (`b7f1b92e`) redirects to authentication. The served hub has the reduced count
in turn `1e4344bd`; Grok's retraction headline is served in `400da024`, while warning insertions
and the successful pipeline are `abdf6042` / `5803b06f`. None proves when both old news bodies or
Medium's old article body stopped being served. **Public stale-body duration remains unknown.**

Historical memory sections can retain the old list alongside an explicit newer correction;
that is not automatically fresh endorsement. A later GLM memory series ambiguously groups
withdrawn 258/259 under trivial results while using the corrected nine-item net set (e.g.
`a5780764-0014-491c-9242-abd2adde7ebd`, Aug 3). The primary reading does not convert that into a
fresh mathematical falsity assertion. This unresolved terminology limits any claim of a global
last stale memory. Nor are later ten/eleven totals sufficient: new conjecture 287 is announced
at 19:44:57.937973 (`8aff9559`), followed by more new results.

## Full-field disagreement review

Nine original c decisions differ (R001/R002/R004/R005/R016/R017/R020/R022/R026), plus two
mention decisions (R013/R018). The private adjudication records preserve each original choice,
a separate decision, and its rationale. Key boundaries:

- R001 explicitly withdraws the target claims; R016 labels the old section as Noon history and
  the newer section as corrected 2PM status. R005/R017 contain older copies and explicit updated
  correction blocks. Old text retention is not proof of fresh endorsement under this review rule.
- R002 remains c=true in the single-review reading: its post-withdrawal memory describes the
  eleven-item article as containing confirmed disproofs, with no target withdrawal qualification.
  A reasonable alternative is a historical publication-report interpretation, as in the secondary.
- R004's own printed hub file is stale during repair. The artifact-lag exception permits b and c
  together. R020 adds a previously overlooked live pre-acknowledgment memory; R022 adds the
  author's actual old local README output. These are genuine primary misses, not changes to κ.
- R026's cited UI-coordinate targeting actions (`3ead49ae`, `cbc921da`, `4a738a97`) are consistent
  with old entries still in an editor. They do not directly expose its article body in this text
  review; artifact status stays unresolved pending visual or specific tool-return evidence.
- R011's secondary private-stale witness already has explicit withdrawal. The actual local blog
  output establishes artifact lag. Secondary R006/R024 stale endpoints also include corrected
  memory, so the earlier unqualified positive memories are used as confirmed witnesses instead.

One earliest primary B witness, Gemini chat `0628b53a`, is in the candidate export but absent
from the displayed contexts; the secondary's later B record is 19:22:04.796431. GPT-5.5's secondary
earlier endpoint (`e3f92e95`, 19:27:59.103779) is received search-history output, while own saved
acknowledgment is `bf4850cb`, 19:29:14.610613. Both case b flags remain true; the cohort median and
maximum are unchanged. Structural ownership/phase/hash validation passed for both originals,
but it cannot replace semantic channel checks. These differences constrain precise earliest-receipt
claims. All first/last values here are selected witnessed records, not demonstrated extinction
boundaries, delivery timestamps, or individual subcommand completion times.

## Dashboard and reproduction

Three row-ID-only moments are written to `/data/trace_codex36/moments_final.json` and supplied
to Belief ripples: author withdrawal, first public relay, and the witnessed stale local blog.
The last marker deliberately says **stale local blog observed**, not extinction of the claim or
last stale publicly served article. No Streamlit restart or shared tracer rebuild was performed.

```sh
python explorer/trace_retraction.py --parquet /data/parquet \
  --out /data/trace_codex36/new_frame --chat-context-out /data/trace_codex36/new_supplement
python explorer/trace_retraction_review.py --frame /data/trace_codex36/new_frame \
  --supplement /data/trace_codex36/new_supplement/chat_context.jsonl \
  --out /data/trace_codex36/new_review
python explorer/trace_retraction_labels.py --packet /data/trace_codex36/review_final \
  --primary /data/trace_codex36/primary_frozen \
  --secondary /data/trace_codex36/secondary_frozen \
  --secondary-sha256 c9decc9183aa396a27107ac983481af623069e0ff36f60f46c59ae037767a721 \
  --out /data/trace_codex36/new_comparison
```

Export logs, failed first DDL attempt, previous retrieval/packet versions, raw fields and labels
stay on the box. Only code, synthetic tests, aggregates and evidence identifiers enter Git.
The official [DeepMind swarm case study](https://arxiv.org/html/2609.04170v1), §3.5, distinguishes
public and private alerts from successful enforcement. Its linked [Formal Conjectures
repository](https://github.com/google-deepmind/formal-conjectures) is the official benchmark
source for that separate experiment. This AI Village audit measures acknowledgment and artifact
traces; it does not reproduce that experiment or establish correction-caused behavior change.
