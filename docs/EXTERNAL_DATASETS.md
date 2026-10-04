# External-data portability audit — issue #30

The adapters run on both downloaded releases, but **neither release identifies cross-agent spread**.
SwarmTraces lacks actor identities and timestamps; Transluce supplies scan timestamps but no actor
identities or underlying payload/target inventories. Row recurrence is measurable. Cross-agent
sharing, inter-agent first-use order, lags and exposure edges are not identifiable, rather than zero.

Sources: [SwarmTraces report](https://swarmtraces.org/) and its
[redacted release](https://swarmtraces.org/data/final/redacted.jsonl.gz);
[Transluce report](https://transluce.org/agent-activity) and its
[catalog release](https://transluce.org/data/urlquery-agent-activity-2026-09-23.zip).
The supplied files remain under gitignored `data/ext/`; no rows, excerpts or derived event exports
are redistributed. No dataset license was verified; this work uses the research-only scope in #30.

| Property | SwarmTraces | Transluce |
|---|---|---|
| Raw records | 189,579 unique IDs | 38,160 unique report IDs in `all-reports.csv` |
| Subsets | 91,037 payload; 75,534 recovered_text; 23,008 response | 37,649 included; 432 review_required; 79 background |
| Attribution confidence | No actor field | 6,467 significant; 31,182 suggestive; 511 blank; these are activity labels, not verified actors |
| Identity | `agent="unknown"`; no authenticated author identity inferred from embedded strings | `agent="unknown"`; report IDs, source categories and method classes are not agent IDs |
| Time | All 189,579 `time_utc` values null; no defensible error bound or order | All 38,160 report times have second precision; offset from agent action is unknown, not estimated ±1 second |
| Recovery structure | 61,125 parent links, all resolving to supplied records | Union catalog plus supplemental components; read the union once |
| Strict dated event export | 0 events; 189,579 observations retained separately with `t=null` | 38,160 dated scan-metadata observations |
| Timestamp/identity quality | Explicit missing-time and absent-identity metadata | Explicit scan-time and absent-identity metadata, with disposition/confidence preserved |

SwarmTraces fields are `id`, `cite`, `kind`, `parent_id`, `time_utc`, `tags`, `text`.
Transluce's union catalog fields are `report_id`, `report_url`, `report_date_utc`,
`timestamp_precision`, `disposition`, `confidence`, `broad_class`, `why_included`, `caveat`.
All 15 files listed in Transluce's packaged manifest match their supplied size and SHA-256 values.
This is an internal consistency check, not a signed authenticity guarantee.

The nine-field #30 dated-event contract is preserved. Missing timestamps are **not** replaced with
publication dates, row order or the epoch. SwarmTraces' separate undated inventory has the same fields
but a nullable `t`, and must not be fed to a consumer requiring dated events. Metadata lives in a
quality sidecar keyed by event ID, preserving recovery parents and source-record kinds. SwarmTraces
`said` denotes preserved text, not an observed agent utterance; Transluce `did` denotes a recorded
scan, not proven execution of a submitted program, AI authorship, or successful access. These kinds
are transport categories and must be interpreted with channel and quality metadata.

Artifact extraction is offline and happens before clipping displayed text to 2,000 characters.
No payload is executed, decoded into executable code, or fetched. SwarmTraces features are literal
HTTP(S) strings, exact SHA-256 hashes of released redacted text, and literal CVE mentions. URL host
case is normalized while path/query/userinfo case is preserved; symbolic ports and obvious redaction
placeholders are excluded. This is a text matcher, not a complete inventory of executed requests:
computed URLs and syntactic fragments cannot be resolved. Redaction and boilerplate can also merge
otherwise distinct artifacts. Transluce report links are evidence references, not shared agent targets;
its prose categories are not promoted into artifact tokens.

| Artifact frame | Distinct literal URLs | URLs in ≥2 rows | Distinct released-text hashes | Hashes in ≥2 rows | Distinct CVE mentions | CVEs in ≥2 rows |
|---|---:|---:|---:|---:|---:|---:|
| All 189,579 SwarmTraces records | 1,028 | 589 | 163,851 | 19,035 | 11 | 8 |
| Only 91,037 payload records | 751 | 260 | 88,672 | 500 | 10 | 5 |

The full-record frame contains derivative recovery and response records, so its recurrence counts
must not be presented as independent adoptions. Even the payload-only frame has no known actors or
times. Transluce contributes 38,160 distinct report-reference URLs, none recurring across report rows;
the absence of shared reference URLs says nothing about shared targets hidden behind those reports.

There are **no identifiable top-five cross-agent cascades** in either supplied release. As an explicit
alternative, the five largest payload-only row recurrences are below. The artifact identifiers are
hashed so no source URL text is committed. Representative row IDs are lexicographic examples, not
temporal first uses. Full artifact hashes and counts are in the private analysis JSON.

| Hashed artifact ID prefix | Payload rows | Representative source IDs | Actor order / inter-agent lag |
|---|---:|---|---|
| `url:sha256:fa7895c07ac8698e…` | 1,206 | `R0000554`, `R0000558` | Not identifiable |
| `url:sha256:3a8816e620b21cd1…` | 909 | `R0003424`, `R0003596` | Not identifiable |
| `url:sha256:45f86be609ea11a3…` | 744 | `R0000146`, `R0000317` | Not identifiable |
| `url:sha256:7f963849f5d16ee1…` | 573 | `R0005256`, `R0005578` | Not identifiable |
| `url:sha256:e4d15e625542207f…` | 460 | `R0000593`, `R0000598` | Not identifiable |

The analysis returns `artifacts_shared_by_at_least_two_known_agents=null`,
`cross_agent_status="not_identifiable_missing_actor_identity"`, empty co-use sequence lists,
and no causal source. A numerical lower bound of zero observed identified-agent artifacts is
separately labelled; it is not an estimate of zero spread. For future data with identifiable actors,
the analyzer computes first **observed** use and adjacent time differences, marks ties, suppresses
order when any actor has undated uses, and still labels the result as co-use without exposure evidence.

This distinction also matters when comparing to the
[DeepMind swarm case study, arXiv:2609.04170](https://arxiv.org/html/2609.04170): its investigation uses
communication channels and actor-resolved traces. Its benchmark comes from the official
[Formal Conjectures repository](https://github.com/google-deepmind/formal-conjectures).
That study's communication evidence cannot be substituted for missing fields in these releases.

Run from the repository root (all outputs remain ignored):

```sh
.venv/bin/python -m explorer.adapters.swarmtraces \
  --input data/ext/swarmtraces/redacted.jsonl.gz \
  --output data/ext/results30/swarmtraces/events.jsonl \
  --undated-output data/ext/results30/swarmtraces/undated.jsonl \
  --metadata data/ext/results30/swarmtraces/quality.jsonl \
  --profile data/ext/results30/swarmtraces/profile.json

.venv/bin/python -m explorer.adapters.transluce \
  --input data/ext/transluce/urlquery.zip \
  --output data/ext/results30/transluce/events.jsonl \
  --metadata data/ext/results30/transluce/quality.jsonl \
  --profile data/ext/results30/transluce/profile.json

.venv/bin/python -m explorer.external_spread \
  --records data/ext/results30/swarmtraces/undated.jsonl \
  --channel recovered_payload \
  --output data/ext/results30/swarmtraces/payload_spread.json

.venv/bin/python -m explorer.external_spread \
  --records data/ext/results30/transluce/events.jsonl \
  --output data/ext/results30/transluce/spread.json
```

Adapters/analysis emit timestamped JSON log lines per step. Logs are in `data/ext/results30/logs/`.
Profiles include input hashes; private integrity summaries record catalog-manifest checks and
SwarmTraces parent resolution. Tests use synthetic records only, covering missing identity/time,
recovery-versus-exposure, extraction before clipping, redaction filtering, URL case, union-only ZIP
reading, duplicate IDs, timestamp offsets/fractions, first-use order, tied times and unknown actors.
Repository validation: **75 tests passed in 1.54 s**. No AI Village EC2 access was used.

Proposed write-up (four sentences):

> We applied offline adapters to 189,579 SwarmTraces records, including 91,037 payloads, and
> 38,160 Transluce scan-catalog records, preserving evidence IDs and missing-data quality.
> SwarmTraces' payload-only inventory contains 751 literal URLs and 88,672 exact redacted-text hashes,
> with 260 URLs and 500 hashes recurring across rows, but the release supplies neither actor identities
> nor usable timestamps, so these are artifact recurrences rather than diffusion cascades.
> Transluce supplies second-precision scan timestamps and activity-confidence labels for 37,649
> included reports, but its public catalog has no agent identities, submitted payloads or target-URL
> inventory; its unique report links are evidence references, not observed shared targets.
> Our tools therefore report cross-agent sharing, inter-agent lags and causal sources as not
> identifiable in these releases, demonstrating portability of evidence ingestion without inventing spread.
