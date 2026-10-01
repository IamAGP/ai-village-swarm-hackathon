"""Synthetic self-discovery cases: no dataset excerpts or answer keys."""
import re

import duckdb
import pytest

from explorer.tracer import TRACE_DISCOVERY_SQL
from test_room_visibility import URL, edge


def normalized(text):
    return ' ' + re.sub('[^a-z0-9.-]+', ' ', text.lower()) + ' '


@pytest.mark.parametrize('text,cue', [
    ("I'll have to find their links first, then I will start searching for them.", 'url_search_plan'),
    ("I searched the web for Alice's site.", 'web_search'),
    ("I am searching Google for Alice.", 'web_search'),
    ("I looked up the URL for Alice.", 'link_lookup'),
    ("I found Alice's page through a web search.", 'search_result'),
    ("Alice reviewed my own website: {url}", 'own_resource'),
    ("Alice, I created this page at {url}", 'created_resource'),
])
def test_cues_downgrade_named_candidate(text, cue):
    result = edge(posts=[('alice', '2026-03-01 12:00:00', 'alice-post', 'room')],
                  target_text=normalized(text.format(url=URL) + ' Alice ' + URL))
    assert result['source_named']
    assert result['self_found']
    assert cue in result['self_found_cues']
    assert result['evidence'] == 'temporal'
    assert result['source_row'] == 'alice-post'


@pytest.mark.parametrize('text', [
    'Alice shared this link; I will browse it.',
    'I will search the page for errors; Alice sent it.',
    'I did not search Google; Alice supplied the URL.',
    'I never created this page; Alice did.',
    'Alice created this site and asked for a review.',
    'Alice says you should search Google for the URL.',
    'Alice sent a search engine article.',
    'I will look up the error code while testing what Alice shared.',
    'I found the URL in chat from Alice.',
    'Alice shared {url}; my own repository is now redundant.',
    'Alice shared {url}; I will test my own repo before checking hers.',
    'Alice shared {url}. Approved channels: newsletters, our own website, forums.',
    'I created this page. Alice shared a different page: {url}',
])
def test_generic_search_negations_and_other_actors_do_not_downgrade(text):
    result = edge(posts=[('alice', '2026-03-01 12:00:00', 'alice-post', 'room')],
                  target_text=normalized(text.format(url=URL) + ' ' + URL))
    assert not result['self_found']
    assert result['self_found_cues'] == []
    assert result['evidence'] == 'explicit'


def test_gemini_style_list_search_plan_can_be_far_from_url():
    # A synthetic counterpart of the issue's list-building failure, not a copied row.
    text = "I'll need to find their URLs first, so I'll start searching. " + 'padding ' * 150
    result = edge(posts=[('alice', '2026-02-27 13:22:00', 'alice-post', 'room')],
                  target_text=normalized(text + ' Alice: ' + URL))
    assert result['self_found_cues'] == ['url_search_plan']
    assert result['evidence'] == 'temporal'


def test_unrelated_distant_search_does_not_contaminate_other_url():
    text = 'I searched Google for a recipe. ' + 'padding ' * 150 + ' Alice shared ' + URL
    result = edge(posts=[('alice', '2026-03-01 12:00:00', 'alice-post', 'room')],
                  target_text=normalized(text))
    assert not result['self_found']
    assert result['evidence'] == 'explicit'


@pytest.mark.parametrize('lag,old', [(72 * 3600, False), (72 * 3600 + 1, True)])
def test_named_age_flag_boundary_without_age_only_reclassification(lag, old):
    from datetime import datetime, timedelta
    post_at = datetime(2026, 3, 1, 12, 10) - timedelta(seconds=lag)
    result = edge(posts=[('alice', post_at, 'alice-post', 'room')],
                  target_text=normalized('Alice shared ' + URL))
    assert result['named_old'] is old
    assert result['evidence'] == 'explicit'


def test_self_found_old_candidate_is_stale_not_recent_temporal():
    result = edge(posts=[('alice', '2026-02-20 12:00:00', 'alice-post', 'room')],
                  target_text=normalized('I searched Google for Alice ' + URL))
    assert result['named_old']
    assert result['evidence'] == 'stale'


def test_memory_or_missing_text_has_no_self_discovery_signal():
    con = duckdb.connect()
    con.execute('CREATE TABLE trace_adopt (url VARCHAR, target_text VARCHAR)')
    con.execute('INSERT INTO trace_adopt VALUES (?, NULL)', [URL])
    assert con.execute(f'SELECT self_found, self_found_cues FROM ({TRACE_DISCOVERY_SQL})').fetchone() == (False, [])


def test_self_found_does_not_invent_a_source_or_override_room_filter():
    text = normalized('I searched Google for Alice ' + URL)
    assert edge(target_text=text)['evidence'] == 'none'
    result = edge(posts=[('alice', '2026-03-01 12:00:00', 'alice-post', 'room-b')],
                  presence=[('2026-03-01 11:00:00', 'room-a')], target_text=text)
    assert result['evidence'] == 'cross_room'
    assert result['source'] is None
