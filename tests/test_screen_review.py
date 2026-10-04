import json

import pytest

from explorer.trace_screen_review import audit, validated_labels
from explorer import trace_shotnext_label as labeler


def record(cid='abcdef01', **changes):
    row = dict(claim8=cid, claim_id=cid+'-synthetic', paired_at='2026-01-01 12:00:00',
                claim_at='2026-01-01 12:01:00', next_at='2026-01-01 12:02:00',
                paired_action='left_click', next_action='mouse_move',
                next_turn='next', acted_after=False)
    return row | changes


def label(cid='abcdef01', value='not_done'):
    return {'claim8': cid, 'label': value}


def test_two_not_done_screens_are_candidates_even_with_own_send_click():
    report = audit([record()], [label()])
    assert report['literal_gate_candidates'] == ['abcdef01']
    assert 'confirmed' not in report
    assert 'target-specific' in report['interpretation']


def test_done_after_claim_is_observation_not_overturned_verdict():
    report = audit([record()], [label(value='done')])
    assert report['done_labels'] == ['abcdef01']
    assert report['literal_gate_candidates'] == []
    assert 'overturned' not in report


def test_same_next_screen_discordant_labels_remain_visible():
    report = audit([record(), record('abcdef02')], [label(), label('abcdef02', 'unclear')])
    assert len(report['reused_next_turns']) == 1
    assert len(report['discordant_reused_next_turns']) == 1


def test_missing_next_is_not_silently_included_as_labelled():
    r = record()
    r.update(next_turn=None, next_at=None)
    assert audit([r], [])['next_screens'] == 0
    with pytest.raises(ValueError, match='coverage'):
        audit([r], [label()])


@pytest.mark.parametrize('rows,expected,error', [
    ([label(), label()], ['abcdef01'], 'duplicate'),
    ([label()], ['abcdef01', 'abcdef01'], 'duplicate expected'),
    ([], ['abcdef01'], 'coverage'),
    ([label('abcdef02')], ['abcdef01'], 'coverage'),
    ([label(value='probably')], ['abcdef01'], 'invalid label'),
])
def test_labels_reject_duplicate_missing_unknown_and_invalid(rows, expected, error):
    with pytest.raises(ValueError, match=error):
        validated_labels(rows, expected)


def test_timestamp_checks_compare_instants_not_string_order():
    r = record()
    r.update(next_at='2026-01-01T17:30:30+05:30')
    assert audit([r], [label()])['timing_issues'] == [
        {'claim8': 'abcdef01', 'issue': 'next_not_after_claim'}]
    r.update(next_at='2026-01-01T12:16:00Z')
    assert audit([r], [label()])['timing_issues'] == [
        {'claim8': 'abcdef01', 'issue': 'outside_15_minute_window'}]


def test_duplicate_records_and_truthy_string_action_flag_are_rejected():
    with pytest.raises(ValueError, match='duplicate'):
        audit([record(), record()], [label()])
    r = record()
    r['acted_after'] = 'false'
    with pytest.raises(ValueError, match='must be boolean'):
        audit([r], [label()])


def test_failed_combine_preserves_previous_output(tmp_path, monkeypatch):
    chunk = tmp_path/'chunks'/'c00'
    chunk.mkdir(parents=True)
    (chunk/'labels.jsonl').write_text(json.dumps(label())+'\n'+json.dumps(label())+'\n')
    (tmp_path/'next.jsonl').write_text(json.dumps(record())+'\n')
    prior = tmp_path/'next_labels.jsonl'
    prior.write_text('previous checkpoint\n')
    monkeypatch.setattr(labeler, 'D', str(tmp_path))
    monkeypatch.setattr(labeler, 'W', str(tmp_path/'chunks'))
    with pytest.raises(ValueError, match='duplicate'):
        labeler.combine()
    assert prior.read_text() == 'previous checkpoint\n'
