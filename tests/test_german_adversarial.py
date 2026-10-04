"""Synthetic counterexamples for the independent audit, no released content."""
from explorer.german_adversarial import RevisionAudit


def revision(page, seq, actor, hour, body, ip='net-a', grade='reqlog'):
    return dict(rev_id=f'{page}@{seq}', page_id=page, seq=seq, label=actor,
                ip16=ip, time=f'2026-06-01T{hour:02d}:00:00Z', time_grade=grade,
                uncertainty_seconds=1, body=body)


def audit(rows):
    result = RevisionAudit(rows)
    result.eligible = set(result.users)  # The released-data CLI keeps the >=10-label rule.
    return result


def sample(result, scenario=None, actor='B', artifact='technique:proxy.example'):
    return next(s for s in result.samples(**(scenario or {}))
                if s['row'] == result.first[artifact, actor].id and s['artifact'] == artifact)


def test_adoption_edit_is_not_a_strictly_prior_edit():
    a = audit([revision('P', 1, 'A', 1, 'https://proxy.example/https://target.example/a'),
               revision('P', 2, 'B', 2, 'https://proxy.example/https://target.example/a '
                                      'https://proxy.example/https://target.example/b', 'net-b')])
    assert sample(a)['seen'] and sample(a)['current_edit_only']
    assert not sample(a, {'strict': True})['seen']
    # Same technique, different full URL: the full URL is not a previous-page exposure.
    assert not sample(a, artifact='https://proxy.example/https://target.example/b')['seen']


def test_blank_source_and_removed_then_readded_origin():
    a = audit([revision('P', 1, '', 1, 'https://proxy.example/https://target.example/a'),
               revision('P', 2, 'B', 2, 'https://proxy.example/https://target.example/a'),
               revision('Q', 1, 'B', 3, 'https://proxy.example/https://target.example/b')])
    assert not sample(a)['seen']
    assert sample(a, {'blank': True})['seen']
    a = audit([revision('P', 1, 'A', 1, 'https://target.example/a'),
               revision('P', 2, 'C', 2, ''),
               revision('P', 3, 'D', 3, 'https://target.example/a'),
               revision('P', 4, 'B', 4, 'https://target.example/a'),
               revision('Q', 1, 'B', 5, 'https://target.example/a')])
    r = a.first['https://target.example/a', 'B']
    assert a.candidate_exposures('https://target.example/a', r)[0][1].id == 'P@3'


def test_all_time_ip_filter_does_not_leak_into_asof_filter():
    a = audit([revision('P', 1, 'A', 1, 'https://target.example/a', 'net-a'),
               revision('Q', 1, 'B', 2, 'https://target.example/a', 'net-b'),
               revision('Q', 2, 'B', 3, '', 'net-a')])
    s = sample(a, artifact='https://target.example/a')
    assert s['any_prior_overlap']
    assert not s['asof_prior_overlap']
    # A third prior user sharing B's block triggers the stronger filter even if the
    # selected source's block differs, and only after that IP has actually appeared.
    a = audit([revision('P', 1, 'A', 1, 'https://target.example/a', 'net-a'),
               revision('R', 1, 'C', 2, 'https://target.example/a', 'net-b'),
               revision('P', 2, 'B', 3, 'https://target.example/a', 'net-b'),
               revision('Q', 1, 'B', 4, 'https://target.example/a', 'net-b')])
    s = sample(a, artifact='https://target.example/a')
    assert not s['same_pair'] and s['asof_prior_overlap']


def test_reqlog_endpoints_and_exposure_age_are_separate_constraints():
    a = audit([revision('P', 1, 'A', 1, 'https://target.example/a', grade='write_date'),
               revision('P', 2, 'B', 2, 'https://target.example/a', 'net-b'),
               revision('Q', 1, 'B', 5, 'https://target.example/a', 'net-b')])
    assert sample(a, artifact='https://target.example/a')['seen']
    assert not sample(a, {'reqlog': True}, artifact='https://target.example/a')['seen']
    assert not sample(a, {'hours': 2}, artifact='https://target.example/a')['seen']
    assert sample(a, {'hours': 3}, artifact='https://target.example/a')['seen']


def test_exact_matching_uses_common_weights_and_excludes_unsupported_cells():
    rows = [dict(kind='technique', seen=True, prior_edits=1),
            dict(kind='url', seen=False, prior_edits=1),
            dict(kind='url', seen=True, prior_edits=1),
            dict(kind='technique', seen=False, prior_edits=9)]
    m = RevisionAudit.match(rows, 'prior_edits')
    assert m['matched_weight_per_group'] == 1
    assert m['percent'] == {'technique': 100, 'url': 50}
    assert m['supported_observations'] == {'technique': 1, 'url': 2}


def test_per_new_url_weighting_differs_from_first_label_technique():
    a = audit([revision('P', 1, 'A', 1, 'https://proxy.example/https://target.example/a'),
               revision('Q', 1, 'B', 2, 'https://proxy.example/https://target.example/b '
                                      'https://proxy.example/https://target.example/c'),
               revision('Q', 2, 'B', 3, 'https://proxy.example/https://target.example/b '
                                      'https://proxy.example/https://target.example/c '
                                      'https://proxy.example/https://target.example/d')])
    first = [s for s in a.samples() if s['kind'] == 'technique']
    repeated = [s for s in a.samples(unit='new_wrapped_url') if s['kind'] == 'technique']
    assert len(first) == 2 and len(repeated) == 4
    assert sum(s['seen'] for s in first) == 0
    assert sum(s['seen'] for s in repeated) == 0  # Earlier same-label origins are not peer exposure.
