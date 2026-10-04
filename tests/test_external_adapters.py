import hashlib
import json
import csv
import io
import zipfile

import pytest

from explorer.adapters.swarmtraces import SwarmTracesAdapter
from explorer.adapters.transluce import TransluceAdapter
from explorer.adapters.common import urls_in_text
from explorer.external_spread import SpreadAnalysis


def swarm(text='inert synthetic text', **changes):
    return {'id':'synthetic1', 'cite':'synthetic citation', 'kind':'payload',
            'parent_id':None, 'time_utc':None, 'tags':'', 'text':text, **changes}


def trans(**changes):
    return {'report_id':'synthetic-report', 'report_url':'https://example.test/report/1',
            'report_date_utc':'2026-01-01T01:00:00+01:00', 'timestamp_precision':'second',
            'disposition':'included', 'confidence':'significant', 'broad_class':'synthetic',
            'why_included':'Synthetic explanatory metadata', 'caveat':'Not an authenticated actor', **changes}


def test_swarm_missing_time_and_parent_are_not_invented_actor_or_exposure():
    obs = SwarmTracesAdapter().adapt(swarm(parent_id='synthetic-parent'))
    assert obs.event['t'] is None
    assert obs.event['agent'] == 'unknown'
    assert obs.event['kind'] == 'said'
    assert obs.quality['parent_id'] == 'synthetic-parent'
    with pytest.raises(ValueError, match='Undated'):
        obs.validate(dated=True)


def test_full_text_features_before_clipping_and_redaction_exclusion():
    text = 'padding '*30 + ' https://EXAMPLE.test/resource?q=A CVE-2026-12345 https://example.test/[REDACTED]'
    obs = SwarmTracesAdapter(clip_chars=3).adapt(swarm(text))
    assert obs.event['text'] == 'pad'
    assert obs.event['urls'] == ['https://example.test/resource?q=A']
    assert 'cve:CVE-2026-12345' in obs.event['tokens']
    assert 'redacted-sha256:' + hashlib.sha256(text.encode()).hexdigest() in obs.event['tokens']
    assert obs.quality['text_clipped']


def test_transluce_scan_timestamp_and_reference_are_not_agent_execution():
    obs = TransluceAdapter().adapt(trans())
    obs.validate(dated=True)
    assert obs.event['t'] == '2026-01-01T00:00:00Z'
    assert obs.event['agent'] == 'unknown'
    assert obs.event['tokens'] == []
    assert obs.quality['artifact_basis'] == 'report_reference_only'
    assert obs.quality['confidence'] == 'significant'
    assert obs.quality['identity_quality'] == 'absent'
    with pytest.raises(ValueError, match='timezone'):
        TransluceAdapter().adapt(trans(report_date_utc='2026-01-01'))


def test_unknown_rows_only_recur_never_become_agents_or_cascades():
    a = SpreadAnalysis()
    for i in range(3):
        a.add(SwarmTracesAdapter().adapt(swarm(id=str(i))).event)
    r = a.result()
    assert r['known_agents'] == 0
    assert r['artifacts_shared_by_at_least_two_known_agents'] is None
    assert r['top_5_co_use_sequences'] == []
    assert r['repeated_across_rows'] == 1
    assert r['top_5_row_recurrences_not_cascades'][0]['first_use_order'] is None


def test_first_observed_co_use_lags_ties_and_undated_actor():
    a = SpreadAnalysis()
    for i, agent, t in [('3','B','2026-01-01T00:00:10Z'), ('2','A','2026-01-01T00:00:03Z'),
                         ('1','A','2026-01-01T00:00:00Z'), ('4','C','2026-01-01T00:00:10Z')]:
        event = SwarmTracesAdapter().adapt(swarm(id=i,time_utc=t)).event
        event['agent'] = agent
        a.add(event)
    row = a.result()['top_5_co_use_sequences'][0]
    assert [r['agent'] for r in row['first_use_order']] == ['A','B','C']
    assert [r['seconds'] for r in row['inter_agent_lags']] == [10,0]
    assert row['inter_agent_lags'][1]['ordering'] == 'tied'
    assert row['causal_source'] is None
    undated = SwarmTracesAdapter().adapt(swarm(id='5')).event
    undated['agent'] = 'A'; a.add(undated)
    assert a.result()['top_5_co_use_sequences'][0]['first_use_order'] is None
    with pytest.raises(ValueError,match='Duplicate'):
        a.add(undated)


def test_fractional_seconds_are_sorted_as_instants_not_iso_spelling():
    a = SpreadAnalysis()
    for i, t in [('B', '2026-01-01T00:00:00.500Z'), ('A', '2026-01-01T00:00:00Z')]:
        event = SwarmTracesAdapter().adapt(swarm(id=i, time_utc=t)).event
        event['agent'] = i
        a.add(event)
    r = a.result()['top_5_co_use_sequences'][0]
    assert [x['agent'] for x in r['first_use_order']] == ['A', 'B']
    assert r['inter_agent_lags'][0]['seconds'] == .5


def test_zip_reads_union_only_and_never_double_counts_components(tmp_path):
    source = io.StringIO()
    writer = csv.DictWriter(source, fieldnames=sorted(TransluceAdapter.fields))
    writer.writeheader(); writer.writerow(trans())
    p = tmp_path/'synthetic.zip'
    with zipfile.ZipFile(p, 'w') as archive:
        archive.writestr('package/all-reports.csv', source.getvalue())
        archive.writestr('package/reports.csv', source.getvalue())
        archive.writestr('package/additional-cited-reports.csv', source.getvalue())
    assert len(list(TransluceAdapter().rows(p))) == 1


def test_url_normalization_does_not_merge_distinct_case_sensitive_userinfo():
    urls = urls_in_text('https://CASE:Pass@EXAMPLE.test/A?b=C https://case:pass@example.test/A?b=C')
    assert urls == ['https://CASE:Pass@example.test/A?b=C', 'https://case:pass@example.test/A?b=C']
    assert urls_in_text('https://example.test:symbolic/thing') == []
