# Independent drift review — issue #28

Codex independently labelled all 268 supplied messages using the supplied rubric and excerpts,
then froze the labels before opening either Claude label file. The primary file is
`/work/drift72_codex/drift.jsonl` on the explorer; SHA-256:
`e6edb76799ddc8b5ca44d2d6fae0eda4e0e74d128877e11e0586147bc2a63982`.
The freeze manifest records 2026-10-03 03:46:24 UTC. Every cue was checked as an exact substring
of its input excerpt. These are stance judgements, not mathematical truth labels.

Agreement was **178/268 (66.4%)**, Wilson 95% interval **[60.6%, 71.8%]**;
seven-class Cohen's **κ = 0.594**, message-bootstrap 95% interval **[0.528, 0.660]**
(10,000 draws, seed 28). These intervals assume independent messages; correlated messages
within one cascade make them descriptive rather than a population reliability guarantee.
Neither annotator is treated as ground truth, and agreement is not precision.

The confusion matrix has frozen Codex labels as rows and Claude labels as columns:

| Codex / Claude | original | repeats | amplifies | hedges | checks | flags | neutral | total |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| original | 45 | 0 | 0 | 0 | 3 | 0 | 0 | 48 |
| repeats | 0 | 11 | 0 | 0 | 0 | 0 | 1 | 12 |
| amplifies | 0 | 37 | 47 | 0 | 2 | 0 | 11 | 97 |
| hedges | 0 | 1 | 0 | 1 | 0 | 0 | 4 | 6 |
| checks | 1 | 0 | 0 | 1 | 24 | 0 | 1 | 27 |
| flags | 2 | 6 | 0 | 1 | 0 | 11 | 1 | 21 |
| neutral | 1 | 9 | 3 | 1 | 2 | 2 | 39 | 57 |
| total | 49 | 64 | 50 | 4 | 31 | 13 | 57 | 268 |

The rubric explicitly includes publication/marketing in amplification. Codex applied that
literally, including news dispatches that preserve the mathematical strength of the source.
**37 messages were amplifies for Codex and repeats for Claude.** Across all 65 disagreements
involving either amplification or flagging, 31 adjudication records identify publication alone
as the distinguishing dimension. Publication alone must not be presented as false belief,
increased mathematical certainty, or a verification failure. Mixed messages also require a
precedence rule: an explicit report of the speaker's own mathematical verifier takes precedence
over a publication request; routine growing-count synchronization is neutral; explicit retraction
or attribution-error remediation can be flags. Article-content verification is not mathematical
verifier execution.

Every one of those 65 disagreements has a separate row-ID decision, reason and reasonable
alternative in `/work/drift72_codex/adjudication.jsonl`. Eight decisions change the frozen Codex
stance. The provisional targeted-adjudication totals are original 48 / repeats 13 / amplifies 94 /
hedges 6 / checks 29 / flags 18 / neutral 60. This is **one reviewer's adjudication**, not consensus
gold; 25 other disagreements remain unresolved. The original independent labels are unchanged.
Use the separate adjudication rationale for interpretation, not agreement measured after adjudication.

The denominator is the **provided text-selected frame**, not all cascade communication. Two raw
Gemini retraction acknowledgments are absent from that frame (`0628b53a-6256-44a8-8c96-3bd2df611d8c`,
`d4752edc-d66a-4538-a4c3-47cf0902250b`). Also, 264/268 inputs equal their full raw chat messages;
4/268 are exact 1,500-character prefixes. The blind judgements used the excerpts only. This review
does not independently label the separate first-text inputs used in the dashboard's agent peaks.

The raw chat timeline below uses database `created_at` timestamps, in UTC on 2026-07-30:

| Event | Time | Row ID |
|---|---|---|
| Opus 5 announces 258/259 | 18:18:18.585603 | `b66a02b9-d270-4ce4-88aa-b8fd47476072` |
| Opus 5 retracts both | 19:20:58.248631 | `56f9501d-c70a-42bc-9786-2c432a7e8597` |
| GLM relays retraction | 19:21:15.743861 | `e7a98bf1-f5a1-4b5e-a190-f562e311062b` |
| Gemini acknowledges and promises edit | 19:21:29.556812 | `0628b53a-6256-44a8-8c96-3bd2df611d8c` |
| Opus 4.8 reports hub correction | 19:23:40.010036 | `d1b5a134-b859-4cb4-b4aa-1a617dc6362d` |
| DeepSeek acknowledges and promises edit | 19:23:55.953603 | `a87d0122-5dcf-4175-b02f-c3ed4ef08855` |
| Grok announces retraction news | 19:30:57.222944 | `4edcdfff-e1f1-4fe7-a434-a24774926b09` |
| Gemini reports completed Medium correction | 19:39:39.479008 | `d4752edc-d66a-4538-a4c3-47cf0902250b` |

Announcement to retraction was **1 h 2 min 39.663 s**; retraction to GLM relay was **17.495 s**.
The relay preserves the requested removal and count but **reverses the explanation of the
definition error** relative to the author's retraction. Fast propagation of a correction does
not guarantee a faithful explanation of it. This is a comparison of recorded statements, not
an independent proof of the underlying graph-theory interpretation.

Observed artifacts give a more limited result than the agents' platform-completion reports:

| Evidence | Recorded turn time (UTC) | Row ID | What it establishes |
|---|---|---|---|
| Source README fetched through GitLab API | 19:25:59.037673 | `d80bb29c-8105-405f-ad56-200a4a943b69` | Explicit withdrawal in retrieved source text; the same turn's local hub checkout is stale, so do not confuse it with the served hub. |
| Public hub fetched with curl | 19:26:19.548990 | `1e4344bd-62c6-4321-bf38-2aa77fc1c73f` | Served hub text has the reduced count. |
| Retraction news sampled with HTTP 200 and title | 19:30:51.327551 | `400da024-e23b-4de5-a9d6-7870295aaaee` | Retraction headline was served; this does not expose both old article bodies. |
| Banners inserted into both original news posts and pushed | 19:34:36.551559 | `abdf6042-4628-4506-95b2-663082dc5cda` | Two existing articles receive explicit retraction warnings; push is recorded. |
| Banner deployment pipeline checked | 19:35:09.091242 | `5803b06f-b18c-4bbb-b495-c21fce12115f` | Successful deployment of the banner commit; not a direct read of each served article body. |
| Local blog HTML printed | 19:38:37.905321 | `dbb72309-a238-468a-9515-435c07268467` | Actual local artifact text still presents 258/259 as counterexamples, 17 min 39.657 s after the retraction. This is not a public HTTP response. |
| Corrected blog HTML printed | 19:39:38.449447 | `683d5d5a-813d-4c41-8fcc-accc03d693f1` | Local correction text and reduced list are observed. |
| Blog correction committed and pushed | 19:39:53.657089 | `e6a0697c-1405-46f1-b37e-41d971db945f` | Successful correction push; public serving remains unconfirmed. |
| Public blog HTTP probe | 20:10:43.047068 | `b7f1b92e-0666-4479-993b-018cec6d216b` | Authentication redirect, not article content. |

These are recorded turn timestamps, not measured completion times for individual shell subcommands.
Medium's post-retraction editor actions refer to the two old list entries and culminate in save/publish
clicks (`1cf3f2c7-624d-42b1-8a1d-08e1af2baf48`, `0ce42d5f-a349-49db-9e93-c5d4f46c87fc`). They support
an attempted edit, not a direct read of the subsequently served article body. This text audit therefore
**does not establish an uncorrected publicly served Medium or old news article body after retraction**.
It does establish stale local public-facing blog text and later corrective actions. Existing screenshots
can support a separate visual check; their contents are not inferred from action descriptions.

Later counts of ten or more do not by themselves show persistence of 258/259: a new 287 announcement
occurs at 19:44:57.937973 (`8aff9559-3745-494d-b533-3a3a2bc09d8a`). Nor does mentioning 258/259 inside
a correction notice constitute endorsing the withdrawn results.

Proposed Finding 1 addendum sentences:

> Independent blind annotation of the 268 supplied message excerpts agreed with the first annotator
> on 178/268 (66.4%; descriptive Wilson 95% CI 60.6–71.8%), with seven-class Cohen's κ = 0.594
> (descriptive iid-message bootstrap 95% CI 0.528–0.660); the broad publication/marketing rule yielded
> 97/268 amplification labels for Codex versus 50/268 for Claude, so these labels cannot all be interpreted
> as increased mathematical certainty or false belief. The supplied frame omits some retraction
> acknowledgments and truncates 4/268 messages, and separate first-text agent peaks were not revalidated.
>
> Opus 5 withdrew its two 258/259 claims 1 h 2 min 39.663 s after announcing them; GLM relayed the
> withdrawal 17.495 s later but reversed the definition-error explanation (chat rows `b66a02b9`,
> `56f9501d`, `e7a98bf1`). The recorded public hub fetch shows the reduced count (turn `1e4344bd`),
> while a local public-facing blog file still presents both withdrawn counterexamples in a turn recorded
> 17 min 39.657 s after retraction (`dbb72309`), before the observed correction and push (`683d5d5a`,
> `e6a0697c`); this establishes local artifact lag, not an uncorrected publicly served Medium or blog body.

Reproduce the comparison on the box:

```sh
/opt/explorer/venv/bin/python /work/drift72_codex/drift_compare.py \
  --primary /work/drift72_codex/drift.jsonl \
  --reference /work/drift72_0/drift.jsonl /work/drift72_1/drift.jsonl \
  --items /work/drift72_0/items.jsonl /work/drift72_1/items.jsonl \
  --frozen-sha256 e6edb76799ddc8b5ca44d2d6fae0eda4e0e74d128877e11e0586147bc2a63982 \
  --output /work/drift72_codex/comparison_reproduced.json
```

Only comparison code, synthetic tests, aggregate review and evidence identifiers belong in git.
Labels, cues, row-level adjudication and raw evidence remain on the explorer. No tracer rebuild,
Streamlit restart or instance lifecycle operation was performed.
