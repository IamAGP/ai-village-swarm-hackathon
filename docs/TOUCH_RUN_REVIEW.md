# Touch versus run — adversarial review of Finding 4 (#40)

**Verdict: weakened.** The original proxy figures reproduce, including the UI's 54/68
comparison. They do not establish that agents open links in eleven minutes or measure time
to independent checking. Link-bearing actions include article writing; the repo denominator
includes non-repo pages; the run detector has confirmed false positives. Graffiti's selected
first verifier invocation remains at +26.46 h, consistent with the separate hand audit in §1.

## Reconstruction and denominator

The preserved export contains 4,935 chat/action first-use records for the 383 URLs reaching
eight non-human actors, 88,491 action/URL records, and 476,843 bash commands mentioning a
selected repo basename. This reconstructs the saved tracer frame rather than independently
retrieving every possible link. Raw rows and annotation files remain private on the explorer.

The saved execution output has **78 candidate URLs / 69 detected runs**. The app removes the
API endpoint, yielding the reported **77/68**, median run lag 1.7267 h and 54 faster than
Graffiti. This explains the apparent saved-output/prose mismatch. However, GitHub issue lists,
a pull-request list and a file page remain, as does the village GitLab namespace. The URL regex
mistakes their final path components for repo names. Removing all six non-root candidates
gives **72 repo-shaped root URLs / 64 legacy detections**, median 1.3668 h, **51/64** faster
than Graffiti. Root shape is not proof that each project exists or contains runnable code.

GitHub subpages are excluded by requiring owner/repo paths. The GitLab API endpoint and known
`ai-village-agents/village` group are excluded; nested project paths are retained. This is a
dataset-specific namespace sensitivity, not universal project discovery. Basename matching
also collides across mirrors and similarly named repos, without checkout/commit provenance.
Excluded-page origin rows are `04139d10`, `9495cc09`, `d0fd9f5e`, `9e9cd74f`,
`8c7ff248`, `e41ffd60`; five have spurious legacy run matches at `b6d96d76`
(shared by both issue-list URLs), `f4b7e3d9`, `0371084d`, `d07c5566`.

## What the eleven-minute touch measures

The original median is **10.964 min** to another agent's first **link-containing action**, with
383/383 observed. Chat before that action occurs in 49/383 cascades (12.8%); median zero, max
three. This includes actions drafting public messages and writing articles with the link, so
the small talk-before-action count cannot be interpreted as independent reading before talk.

A stricter syntax sensitivity requires a literal curl/wget retrieval or git-clone request.
It finds a request in **288/383** cascades, median **49.215 min among those observed**; 95 have
no qualifying request. At the original first-action row, only 106/383 qualify. The remaining
277 are **unrecognized by this predicate**, not 277 proven trivial actions. Python fetches,
variables, URL spelling variants, browser sequences and CLI/API access can be missed. A HEAD
request can qualify without fetching the body. Neither predicate establishes successful delivery.

The median talk-before-request remains zero; 90/288 observed-request cascades have an earlier
peer chat mention. Across all 383, 152 have such a mention before the observed request or no
observed request, max eight. The latter convention treats missing requests as right-censored,
not as proof the link was never opened.

A separate seed-40 random sample of 30 original first actions was manually inspected:

| Command/action interpretation | Cases |
|---|---:|
| Fetch/clone request intent | 14 |
| Metadata request (HEAD or API) | 3 |
| Link only in written artifact/text | 9 |
| Bare typed URL; destination/outcome unestablished | 3 |
| State-changing request | 1 |

Thus **9/30 (30%; Wilson95 16.7–47.9%)** are confirmed artifact/text-only first actions, and
**17/30 (56.7%; 39.2–72.6%)** have fetch/clone/metadata request intent. These are single-reader
command/action labels, not outcome checks. Examples of artifact-only evidence are turns
`e7bb7518-0627-44e1-9785-b2f12c8a3cc5`, `a23e14e2-1dfa-47db-933a-8b55f4e057a2`,
`925bd46a-16ba-4e18-b4e5-3084a6fe698f`, `72e10b22-5d8e-4880-8789-f954e6a68ccc`,
`98072e5f-eb69-4f19-8f2a-4b57cec4383e`, `12af7e82-dd11-47de-93b4-006f88877e1f`,
`5e769e5e-7232-4208-aeef-ddd175728c32`, `06081df9-97b7-43cf-9f9c-28a46d27c116`,
and `6110dc70-643a-498c-bb9e-2752dc1027dc`.

The request predicate is deliberately incomplete: Python network calls in `be3338dc`,
`8877e8d0`, `daf0b55b`, and variable-based fetches in `d760a24a`, `2b949ba0` are genuine
request intents in this sample despite being missed. The 49-minute sensitivity therefore
must not replace eleven minutes with a supposedly measured true opening-time median.

## Graffiti anchors and origin sensitivity

The origin is Opus 5's action `e100056b-c2b2-409c-a2da-d0e9ce01cb3b`, July 29
18:53:16.044888 UTC, **not the public announcement timestamp**. Earliest non-origin literal
action `9500c361-9ce0-49ec-8155-9ee3254ce992` at 18:57:17.669099 (+4.027 min) writes a news
article containing the link; it does not open or clone that repo. The first literal clone
request is DeepSeek-V3.2's `0461fa91-5662-41de-8f1e-f5f6dd97be3e`, 19:04:38.841639
(+11.380 min), into an alias directory. Success is not inferred from the command.

The separate §1 metadata probe and verifier-outcome audit retain their own meanings. The
basename sensitivity still selects GLM-5.2's `a5abb56d-ac1c-4dc4-812e-14d1786f2858`, July 30
21:20:49.378986, **+26.459 h**, as its first invocation. A targeted pre-invocation search for
the observed clone alias and verifier filenames found only article writing, clones, reads and
file-presence checks; the eight saved rows are in `graffiti_alias.jsonl`. That search is bounded
and does not prove exhaustive absence of earlier execution under other paths or via delegation.

There are no earliest-time actor ties in the saved frame. Four cascades have an earlier human
seed. Including that seed and allowing the earliest agent's action changes the all-link median
from 10.964 to **10.685 min**; repo medians and Graffiti's legacy rank are unchanged. Every
origin resolves to a roster model string; no separate unmodelled bot origin is found. This does
not identify external bots or establish true authorship. The earliest observed agent can be a
reader of an existing third-party repo. Graffiti's known author agrees with its origin; complete
true-author exclusion for other repos is not supported by this frame.

## Manual run-detector audit

The seed-40 sample chooses one reservoir row per repo/predicted class, then 30 root candidates
from each class. This balances repos rather than uniformly sampling all turns. Commands were
labelled with predicted flags hidden, then labels were frozen before reading the key. It is one
reviewer, not independent dual annotation. The narrow rubric asks whether a file/module/test or
build invocation targets the named repo context; external scanners, standard-library utilities,
comment text, article payloads and read-only inspection are excluded. Same-name directory/file
provenance and actual outcomes cannot be established from commands alone.
The frozen v2 sample used longest-name indexing; the final aggregate reconstruction additionally
includes overlapping basename matches. Prefix-collision cases can be underrepresented in the
sample. That further limits extrapolation to the complete legacy candidate population.

Among the 30 detections: **19 true, 11 false**, selected-sample precision **63.3%**, Wilson95
**45.5–78.1%**. Among 30 non-detections: no missed file/module invocation under that narrow
rule (0/30, Wilson95 0–11.4%). The balanced sample's narrow recall is 19/19 (100%; 83.2–100%);
this is **not population recall**, especially outside explicit-basename bash commands.

| False-positive row | Failure mode |
|---|---|
| `0671593b-1bb0-4b7b-9c41-51e4c7afa319` | Standard-library HTTP server, not target repo program |
| `b22cdde4-02d2-4cbb-a89c-f3b57d9f0a1f` | JSON utility / inline artifact repair |
| `41453f44-dc8d-428e-a680-00ef0790a3be` | JSON utility for another path, followed by target API request |
| `5931e1d4-e551-4088-9200-d143db2765b4` | Build-tool token in comment; inline document edits |
| `cb94294f-3579-4fa8-845c-6702c18d5ec1` | External scanner run against target artifact |
| `048e39b2-9026-4b1d-b5ad-053272136dff` | Other repo's run before later target cd/read |
| `6147fa20-6a66-451d-b2fd-858e196b4e92` | Build-tool token in comment; file read |
| `44df6c12-7870-4dac-bb81-4fe273b7e36d` | Target file read plus another repo's script |
| `ef8da262-9232-4a48-9820-b5fa5527d5dd` | Target URL is input to another repo's probing program |
| `a8cf8dff-a78f-4caf-9e5b-60bf4934f35f` | External scanner, not target repo program |
| `3fcf1b7d-c2f1-458f-a600-e5aa2a01b1a3` | Target file read plus another repo's chat helper |

There is also a real definition boundary in a non-detection: `a560b661-6f05-4f2f-9262-50ff3905d5b7`
syntax-checks a repo JS file and uses Node vm to evaluate its extracted array expression. Counting
that partial source evaluation as execution gives **one missed case / 30 non-detections** and
balanced-sample recall **19/20 (95%; Wilson95 76.4–99.1%)**. A separate broader-definition file
records this; the narrow frozen labels remain intact. The ad hoc checker created and invoked
inside the repo in `d8fe324f` is counted under the narrow inside-directory rule, without implying
it came from the author's committed verifier. Precision does not establish independent checking.

All intervals here are descriptive binomial intervals on the stated selected case counts. Shared
repos/agents and the two-stage sampling violate simple independent-turn population assumptions.
Neither the unchanged legacy detector nor the new sensitivity has a validated global recall.

## Run and contribution sensitivity

| Rule on the same 72 root candidates | Observed | Median lag among observed | Repos faster than Graffiti |
|---|---:|---:|---:|
| Legacy detector | 64/72 | 1.367 h | 51/64 |
| Command-context run-intent sensitivity | 54/72 | 1.955 h | 40/54 |
| No earlier observed contribution record | 39/72 | 20.906 h | 26/39 |
| Also excludes any same-turn contribution intent | 38/72 | 11.479 h | 25/38 |

Of legacy first detections, **23/64** have an earlier observed repo-context contribution
intent (35.9%; Wilson95 25.3–48.2%). Under the command-context sensitivity it is **24/54**
(44.4%; 32.0–57.6%); four first-run turns also contain a contribution intent. Contribution
witness row IDs accompany every event in the private output. The paired median gap from
link-containing action to context-scoped run intent is 1.415 h among 54 observed cases;
this still is not time from reading to checking. Graffiti remains +26.459 h in all rows above.
Conditional medians can reverse when an exclusion removes an observed case; compare the
observed denominators rather than interpreting the median changes as causal delays.

The sensitivity strips comments and heredoc payloads, retains quoted path arguments, separates
simple commands, tracks explicit cd changes and excludes known standard-library utilities and
explicit external scripts. It recognizes some wrappers. It is a limited shlex-based intent
predicate, **not a full shell parser**, execution-success test or repo-provenance reconstruction.
It misses implicit cross-turn cwd, directory aliases, relative-cd history, arbitrary wrappers,
Python/Node inline execution and delegated runs. Its ranks are sensitivity results, not corrected gold.

Contribution means an earlier explicit repo-context commit/push **intent**, with no output check;
same-turn contribution is flagged separately. Absence is not proof of being a non-contributor or
independent checker. Only evidence earlier than the candidate run is used for the earlier-record
criterion; the separate same-turn exclusion is deliberately conservative and may exclude a write
that followed the run within that turn. Different observed-run subsets have different denominators;
unobserved cases are censored, not known never-run repos. This scan does not measure checking of
a claim, and pooled static-site/memory/game/research repos are not interchangeable verification tasks.

## Private outputs and reproduction

All raw content, full sample commands and labels stay under `/data/trace_codex40/`:

- `frame/manifest.json`, `first_use.jsonl`, `actions.jsonl`, `commands.jsonl`, `roster.jsonl`;
- `sensitivity_v1/` and `sensitivity_v2/` preserve the first-touch and manual run sample frames;
- `manual_frozen/`, `manual_broad_frozen/`, `manual_touch_frozen/` preserve definition-separated labels;
- `sensitivity_final/summary.json`, `talk.jsonl`, `runs.jsonl`, `run_events.jsonl`;
- `code_final/`, `trace_export.log`, `trace_sensitivity_*.log`, `graffiti_alias.jsonl`.

The narrow command labels SHA-256 is
`90d227578fb402d465dc33fbf347ffd17978e278a611748ec49108219773aa78`;
its blind sample is `d96dd0ebd56eca2b641bfe7d61db8a8aced1c8c9440eb32d9c39fe0aa1ca6e5b`.
Broader-definition labels: `86b891638551da2275ebbbc8f80d3909e157b1890335ed0511054d9ce63e995f`.
First-touch labels: `c29debcdf4a68b09bf07ebc89c77bbfa3a155232ae48b3fd5038c2a346014898`;
first-touch sample: `c06bbc923dee9fe717b0b645dd49df1096e7e4e365cd40fb6e2daae48ab556f1`.
`final_manifest.json` SHA-256: `c98b022322dd6742029ce83c9c4e2439ef3bfad9eaef33a897f2090b9248792f`.
These frozen sample frames precede final parser refinements; do not substitute a newly generated
sample from `sensitivity_final/` for the labelled `sensitivity_v1/` / `sensitivity_v2/` files.

```sh
python explorer/trace_touch_audit.py --out /data/trace_codex40/new_frame
python explorer/trace_touch_sensitivity.py --frame /data/trace_codex40/new_frame \
  --out /data/trace_codex40/new_sensitivity
```

Fresh outputs are required; source files are not mutated and source commands are never replayed.
The original `/data/findings/talk/` and `/data/findings/exec/` remain untouched. The dashboard's
legacy scatter is labelled as detector proxies; its old comparative rank is withdrawn as a headline.

The official [Python shlex documentation](https://docs.python.org/3/library/shlex.html) describes
lexical analysis and explicitly limits semantic validation; this is why shell success and full
control-flow claims are withheld. [GitLab group documentation](https://docs.gitlab.com/user/group/)
distinguishes group/namespace structure from projects. The official
[DeepMind swarm case study](https://arxiv.org/html/2609.04170v1), §2.2–3.1, illustrates a separate
case where execution success diverges from semantic proof validity; its linked
[Formal Conjectures repo](https://github.com/google-deepmind/formal-conjectures) is that experiment's
benchmark. Those sources motivate measurement distinctions, not these AI Village counts.
