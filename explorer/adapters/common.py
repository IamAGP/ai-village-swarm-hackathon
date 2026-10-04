"""Dataset-agnostic trace tables: any multi-agent log -> the inputs belief_graph.py already reads.

An adapter yields Event rows (who, when, where, which artifacts, plus any dataset-specific exposure
it can *prove*). `trace_tables` turns them into the three relations the belief-graph engine needs:

  agents(id, name)
  trace_first_use(url, actor, is_human, channel, first_at, row_id)
  trace_edges_scored(url, source, target, s_at, t_at, source_row, target_row, evidence)

Evidence levels for an adopter's first use of an artifact (earliest applicable wins):
  seen      an adapter-specific exposure signal before (or at) first use, e.g. a wiki edit to a page that already
            contained it; source = whoever put it there. Its strength depends on the dataset: for the German board
            it is only a proxy (edits need not read the page; docs/GERMAN_ADVERSARIAL_REVIEW.md).
  temporal  another agent used it in the window before (default 72 h); source = most recent such use.
            Consistent with exposure, not proof (same meaning as the AI Village tracer).
  stale     earlier uses exist, all older than the window.
  none      first observed use.
Only `seen` and `temporal` become told edges in the graph; `stale`/`none` are kept for counts.
"""
from bisect import bisect_left
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta


@dataclass(frozen=True)
class Event:
    id: str                       # stable row reference into the source dataset
    agent: str                    # identity as given by the dataset (may be a pseudonym)
    at: datetime                  # UTC, naive
    channel: str                  # 'chat' (public statement) or 'action'
    artifacts: frozenset          # artifact ids this event *introduced* for its agent
    seen: tuple = field(default=())   # ((artifact, source_agent, source_row, seen_at), ...) exposure proof


def trace_tables(events, window_h=72):
    """Return (agents, first_use, edges, stats) as lists of tuples; deterministic for a given input."""
    events = sorted(events, key=lambda e: (e.at, e.id))
    first = {}                                   # (artifact, agent) -> (at, row, channel)
    for e in events:
        for a in e.artifacts:
            first.setdefault((a, e.agent), (e.at, e.id, e.channel))
    seen = defaultdict(list)                     # (artifact, agent) -> [(seen_at, source, row)]
    for e in events:
        for a, src, row, at in e.seen:
            if src != e.agent:
                seen[(a, e.agent)].append((at, src, row))
    by_artifact = defaultdict(list)              # artifact -> [(at, agent, row)] first uses, time order
    for (a, agent), (at, row, _) in first.items():
        by_artifact[a].append((at, agent, row))
    for uses in by_artifact.values():
        uses.sort()

    agents = sorted({e.agent for e in events})
    first_use = [(a, agent, False, ch, at, row) for (a, agent), (at, row, ch) in sorted(first.items())]
    edges, stats = [], defaultdict(int)
    window = timedelta(hours=window_h)
    for a, uses in sorted(by_artifact.items()):
        times = [u[0] for u in uses]
        for at, agent, row in uses:
            proof = sorted(s for s in seen.get((a, agent), []) if s[0] <= at)
            if proof:
                s_at, src, s_row = proof[0]
                edges.append((a, src, agent, s_at, at, s_row, row, 'seen')); stats['seen'] += 1
                continue
            i = bisect_left(times, at)
            prior = [u for u in uses[:i] if u[1] != agent]
            if not prior:
                stats['none'] += 1
                continue
            s_at, src, s_row = prior[-1]
            if at - s_at <= window:
                edges.append((a, src, agent, s_at, at, s_row, row, 'temporal')); stats['temporal'] += 1
            else:
                stats['stale'] += 1
    return [(x, x) for x in agents], first_use, edges, dict(stats)


def load_into(con, agents, first_use, edges):
    """Create the three relations on a DuckDB connection (TEMP tables; nothing is written to disk)."""
    con.execute('CREATE OR REPLACE TEMP TABLE agents(id VARCHAR, name VARCHAR)')
    con.execute('CREATE OR REPLACE TEMP TABLE trace_first_use(url VARCHAR, actor VARCHAR, is_human BOOLEAN, '
                'channel VARCHAR, first_at TIMESTAMP, row_id VARCHAR)')
    con.execute('CREATE OR REPLACE TEMP TABLE trace_edges_scored(url VARCHAR, source VARCHAR, target VARCHAR, '
                's_at TIMESTAMP, t_at TIMESTAMP, source_row VARCHAR, target_row VARCHAR, evidence VARCHAR)')
    if agents:
        con.executemany('INSERT INTO agents VALUES (?,?)', agents)
    if first_use:
        con.executemany('INSERT INTO trace_first_use VALUES (?,?,?,?,?,?)', first_use)
    if edges:
        con.executemany('INSERT INTO trace_edges_scored VALUES (?,?,?,?,?,?,?,?)', edges)


def parse_utc(s):
    return datetime.strptime(s[:19], '%Y-%m-%dT%H:%M:%S')
