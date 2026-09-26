# Tracer method review (issue #2)

Review of `explorer/tracer.py` at `a2b2a04`, 2026-09-26. This is a code and
method review; it does not claim a measured error rate. The private explorer
instance and dataset rows were not queried for this review.

## Findings

1. **High — room visibility is missing from candidate exposure.** Since rooms v1
   (2026-02-25), an agent's chat context contains only messages from its
   current room (`samples/CHANGELOG.md`). The `cand` and `mention` joins in
   `tracer.py` use URL/name and time but not room membership. A post in `#best`
   can therefore become the exposure edge for an adopter in `#rest`, even if
   the adopter never entered `#best`. `source_room` is retained but never used.
   Reconstruct the adopter's room history between the source post and adoption
   from `ENTER_ROOM` events (and the initial room state where available). Mark
   links across rooms the adopter never occupied in that interval as
   `unobserved_channel` unless an actual bridge appears in a turn, memory,
   history-search result, or accessible external artifact. Report the share of
   edges whose source room was not demonstrably visible to the adopter.

2. **High — talk-only model output loses its text during explicit matching.** In
   `trace_adopt`, `t.agent_action::VARCHAR || ' ' || t.agent_messages::VARCHAR`
   becomes `NULL` when `agent_action` is `NULL`. The surrounding `coalesce`
   then chooses `''`, even when `agent_messages` contains the URL and names
   another agent. The profile counts 80,428 turns with no action. Use
   `concat_ws(' ', t.agent_action::VARCHAR, t.agent_messages::VARCHAR)` (or
   coalesce each operand separately), and test a talk-only turn that names a
   prior poster. This can change `temporal`/`stale` to `explicit`.

3. **High — first recorded use need not be adoption time.** A memory row is a
   consolidation snapshot, so its `created_at` can lag the actual exposure.
   A model-output and its executed action also share a turn timestamp. The
   `trace_adopt` minimum over channels therefore means “first recorded URL
   occurrence,” not necessarily the first time the agent saw, accepted, or
   acted on the artifact. Report the channel and timestamp as an observation
   bound. For spread timing, prefer the first externally visible chat/action
   and show the first internal mention separately. `first_channel <> 'chat'`
   does not by itself establish `agent_created` origin.

4. **Medium — the chosen source row may not be the evidence the adopter refers to.**
   `cand` first keeps each actor's latest prior URL post. Ranking then prefers
   a named actor, but `source_row` points to that actor's latest repost, even
   if the adopter saw an earlier post or an external artifact. The row pair
   establishes temporal compatibility, not the actual transmission path.
   Keep all plausible candidate rows in the evidence inspector, or explicitly
   call the chosen row a representative prior post. Distinguish an agent
   attribution from the exact post attribution.

5. **Medium — named-source evidence can be arbitrarily old.** `explicit` is assigned
   before the 72-hour window check. A reused URL plus an old named poster can
   yield an `explicit` edge months later. Preserve the name-match signal, but
   show lag and an age/visibility warning. Measure named edges beyond 72 hours
   separately before treating them as direct exposure.

6. **High — the current precision language is too strong for its labels.**
   `docs/EVAL.md` counts `plausible` as correct, so 100% lenient precision on
   25 explicit and 25 temporal held-out edges means the supplied excerpts did
   not rule out these attributions. It does not establish that the selected
   chat post caused adoption. The two annotators share a model family, and
   sampling excludes `stale` and separately treats `mention`. Prefer
   “plausible source rate” for the lenient metric. Independently label the
   untouched blind sets, add a room-visible/cross-room stratum, and report
   precision by channel, time regime, and origin type with denominators and
   confidence intervals.

## Method judgment

“Latest prior chat post, preferring a named poster” is a useful **candidate
ranking rule** for triage. It is not an exposure observation or causal edge on
its own. The DeepMind swarm case study distinguishes spread through a shared
library from peer messages; AI Village likewise has chat, sites, code hosting,
history search, human messages, and organizer prompts. A same-URL, prior-time
pair should remain a hypothesis until the channel is visible or a target turn
records the route. Preserve `none` as “no source in indexed channels,” not
independent discovery.

Prioritize (1) and (2) before refreshing the evaluation. Then rerun a new,
seeded blind sample so its confidence intervals reflect the revised tracer.

Reference: Paglieri et al., [*A Case Study on Emergent Cheating and
Whistleblowing in Autonomous Research Swarms*](https://arxiv.org/html/2609.04170v1),
§§2.1 and 3.2 (shared knowledge library and messaging as distinct routes).
