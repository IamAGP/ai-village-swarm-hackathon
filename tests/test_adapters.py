from datetime import datetime

import duckdb

from explorer.adapters.common import Event, load_into, trace_tables
from explorer.adapters.german_wiki import events
from explorer.belief_graph import GraphBuilder

T = lambda h, m=0: datetime(2026, 6, 1, h, m)


def test_evidence_levels_seen_beats_temporal_and_window_applies():
    evs = [
        Event('r1', 'A', T(1), 'chat', frozenset({'x'})),
        Event('r2', 'B', T(2), 'chat', frozenset({'x'}), seen=(('x', 'A', 'r1', T(1, 30)),)),
        Event('r3', 'C', T(3), 'chat', frozenset({'x'})),
        Event('r4', 'D', datetime(2026, 6, 9), 'chat', frozenset({'x'})),
        Event('r5', 'E', T(4), 'chat', frozenset({'y'}), seen=(('y', 'Z', 'r0', T(5)),)),  # seen *after* use
    ]
    agents, first_use, edges, stats = trace_tables(evs, window_h=72)
    ev = {(e[2], e[0]): (e[1], e[7]) for e in edges}
    assert ev[('B', 'x')] == ('A', 'seen')
    assert ev[('C', 'x')] == ('B', 'temporal')          # most recent prior user
    assert ('D', 'x') not in ev and stats['stale'] == 1  # > 72 h after the last use
    assert ('E', 'y') not in ev                           # exposure after first use is not exposure
    assert stats == {'seen': 1, 'temporal': 1, 'stale': 1, 'none': 2}
    assert {a for a, _ in agents} == {'A', 'B', 'C', 'D', 'E'}


def rev(page, seq, label, h, body):
    return {'page_id': page, 'seq': str(seq), 'label': label, 'time': f'2026-06-01T{h:02d}:00:00Z',
            'rev_id': f'{page}@{seq}', 'body': body}


def test_wiki_credits_only_added_urls_and_records_page_exposure():
    proxied = 'https://r.jina.ai/https://example.org/a'
    revs = [
        rev('P', 1, 'A', 1, f'see {proxied}'),
        rev('P', 2, 'B', 2, f'see {proxied} and https://example.org/b'),   # B loads P (sees A's URL), adds /b
        rev('Q', 1, 'C', 3, 'use https://r.jina.ai/https://other.org/z'),  # new URL, same technique
        rev('P', 3, '', 4, 'blanked'),                                    # unlabelled edits are skipped
    ]
    evs = {e.id: e for e in events(revs)}
    assert evs['P@1'].artifacts == {proxied, 'technique:r.jina.ai'}
    assert evs['P@2'].artifacts == {'https://example.org/b'}            # not credited with A's URL
    assert ('technique:r.jina.ai', 'A', 'P@1') in {s[:3] for s in evs['P@2'].seen}
    assert 'technique:r.jina.ai' in evs['Q@1'].artifacts
    assert 'P@3' not in evs


def test_tables_feed_belief_graph_unchanged_with_seen_edges():
    evs = [Event('r1', 'A', T(1), 'chat', frozenset({'technique:t'})),
           Event('r2', 'B', T(2), 'chat', frozenset({'technique:t'}), seen=(('technique:t', 'A', 'r1', T(1, 5)),))]
    con = duckdb.connect()
    load_into(con, *trace_tables(evs)[:3])
    g = GraphBuilder(con, {'kind': 'url', 'value': 'technique:t'}, paths={}).build()
    told = [e for e in g['edges'] if e['kind'] == 'told']
    assert len(told) == 1 and told[0]['evidence'] == 'seen' and told[0]['rows'] == ['r1', 'r2']
    assert {n['id'] for n in g['nodes']} == {'agent:A', 'agent:B', 'artifact:technique:t'}
