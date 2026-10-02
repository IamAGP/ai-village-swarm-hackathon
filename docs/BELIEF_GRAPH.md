# Belief graph data engine

`explorer/belief_graph.py` implements issue #26's evidence graph. It preserves row references and
separates recorded speech, actions/memory, candidate exposure, and verification signals. These are
observations, not direct access to an agent's beliefs.

```python
from explorer.belief_graph import build_graph

graph = build_graph(con, {"kind": "url", "value": url})
graph = build_graph(con, {"kind": "claim", "value": chat_message_id})
graph = build_graph(con, {
    "kind": "agent", "value": agent_id,
    "start": "2026-07-29T00:00:00Z", "end": "2026-08-05T00:00:00Z",
    "max_nodes": 60,
})
```

Use a caller-owned DuckDB connection/cursor. Existing tables/views are used first; missing inputs are
mounted as temporary views from the standard explorer paths. Persistent databases and source files
are not written, and read-only DuckDB connections work. Required missing inputs fail explicitly;
missing optional verification/audit inputs are listed in `meta.missing_optional_sources`.
For custom paths, the CLI or `GraphBuilder(con, seed, paths).build()` supplies the same engine.

```sh
python explorer/belief_graph.py url "$ARTIFACT_URL" > graph.json
python explorer/belief_graph.py claim "$CHAT_MESSAGE_ID" > claim.json
python explorer/belief_graph.py agent "$AGENT_ID" \
  --start 2026-07-29T00:00:00Z --end 2026-08-05T00:00:00Z > agent.json
```

CLI diagnostics go to stderr; stdout is one JSON object. Path options: `--parquet`, `--trace`,
`--findings`. Source paths default to `/data/parquet`, `/data/trace`, `/data/findings`.

## Contract and deterministic limits

Required fields match #26: `seed`, `t0`, `nodes`, `edges`. All times are UTC ISO strings with a `Z`
suffix and six fractional digits. Edges sort by `(at,id)`, nodes by `(first_at,id)`; edge IDs are stable
hashes of their evidence-bearing fields. Repeated identical input rows collapse into one edge.
No message prose is exported. Agent labels are names; artifact labels are URLs limited to 80
characters or a generic claim label. Full canonical URLs/claim IDs remain the artifact identifiers.
An empty graph has `t0: null`, empty node/edge arrays and explanatory metadata.

Additional fields that the frontend may ignore:

- `meta`: inclusive time window, cap, before/after counts, omissions and evidence semantics.
- `told.artifact`: the artifact node ID, needed to distinguish URLs in an agent neighbourhood.
- `checked` with `basis: screen`: `claim_row` is the chat ID, `row` is the screenshot turn ID,
  `retrospective: true` distinguishes review from an agent performing a check, and `adjudicated`
  says whether a contradiction was explicitly confirmed.

Agent seeds include only the selected agent's own said/did/checked edges and directly incident told
edges. Neighbours are not recursively expanded. Without dates, the window is seven days from the
first observed trace event, or first available screen/verifier event if trace activity is absent.
An end without a start selects the preceding seven days; a start without an end selects the following
seven days. Explicit dates apply inclusively. Source evidence for a told edge can predate the window;
that source node's `first_at` and thus `t0` may precede `meta.window.start`.

Agent graphs have at most 60 nodes; smaller `max_nodes` values are accepted (minimum two). Complete
edge groups are retained greedily by `(at,id)`, reserving the seed node and keeping each edge's
endpoints and artifact together. Dropped counts are exact. URL/claim seeds have no default cap, but
can use `max_nodes`. Human/non-agent uses and sources, invalid references and excluded evidence
classes have separate omission counters. A claim without an audit label remains a said-only graph
with an `unlabelled_claim` omission; it does not acquire a fabricated checked edge.

## Evidence interpretation

URL seeds use `trace_first_use` and `trace_edges_scored`. Chat/model-output first use becomes `said`;
action/memory becomes `did`. Memory does not prove action, model output need not endorse a URL, and
an action mentioning a URL does not prove successful use. Only explicit/temporal/mention candidate
exposures become `told`; none/stale/cross_room are omitted. URL spelling normalization reuses the
tracer expression, applied twice to also handle a trailing slash following a `.git` suffix.

For the Graffiti URL, `f1_verify` contributes every recorded verifier turn: success → supported,
fail → contradicted, otherwise unknown, exactly as required by #26. These are filename/output
heuristics, not mathematical verdicts or provenance-checked verifier copies. An import failure is a
failed run signal, not evidence that the conjecture claim was false. The frontend should distinguish
that meaning from a confirmed screen contradiction.

Claim seeds join `chat_messages` with `labels_all.jsonl` and `contra_check.jsonl`. Screen judgments
are retrospective, attached at claim time; `row` lets the UI retrieve the earlier screenshot and
actual turn timestamp. Raw supported labels are model judgments, not independently confirmed truth.
Unrelated/unclear/conflicting labels are unknown. A flagged contradiction is red only when an explicit
`confirmed: true` adjudication exists or the case is explicitly named as confirmed in EVAL. Any
`acted_after: true` or `confirmed: false` overrides that confirmation and leaves the flag unknown.
The present EVAL allowlist contains ten named cases, not all nineteen confirmed cases reported in
aggregate. No-action-between alone never confirms a flag. Further claim repetition/replies are not
inferred: the source has no structured reply link, and name/text similarity is insufficient evidence.

## Real verification, 2026-10-02

The isolated engine under `/data/codex26/code` produced `/data/findings/belief_graffiti.json`:
**30 nodes, 382 edges** (24 said, 47 did, 28 told, 283 checked). Check signals: 210 supported,
12 failed/contradicted, 61 unknown. One scored exposure was excluded. Build time: 0.287 s;
a repeated build was identical. SHA-256 of the final export:
`028250eccc5827381ac9d64f6bf6d8f763c873cfa3c920a54618da1fa39f93c4`.

The two confirmed screen examples are exported privately as `belief_claim_d9f1dcc2.json` and
`belief_claim_fc4a8296.json` under `/data/findings`. Claims
`d9f1dcc2-1353-4788-bccd-f3a6ebbebdaf` and `fc4a8296-c8d2-4fd1-a126-61b5c759c2d1`
share screenshot turn `5909dbc2-5b44-408f-9056-2687aafebadf`; each graph has said plus a confirmed
screen-contradiction edge. These are repeated observations sharing evidence, not independent episodes.
A real April agent window returned 60 nodes/176 edges and reported 244 nodes/552 edges cut.
All generated JSON stays on the box. No instance stop, Streamlit restart or source-data write was made.
