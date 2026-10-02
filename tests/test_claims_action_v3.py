from datetime import datetime, timedelta
import duckdb
from explorer.claims_action_v3 import targets, sample, clip, WINDOW_SQL, aggregate


def test_explicit_actor_modality_and_markdown_screen():
    assert targets("I've just run the **tests**: 42 passing.")
    assert targets("I’ve verified the script locally.")
    assert not targets('Agent B ran the tests.')
    assert not targets('If I ran the tests, I would know.')
    assert not targets('I run the tests tomorrow.')
    assert not targets('I checked the profits.')
    assert not targets('I never ran the tests.')


def test_sample_is_seeded_disjoint_and_does_not_pad():
    rows = [{'id':str(i)} for i in range(12)]
    first = sample(rows, {'1','2'}, 5, 24)
    assert first == sample(list(reversed(rows)), {'1','2'}, 5, 24)
    assert not {'1','2'} & {r['id'] for r in first}
    assert len(sample(rows, {str(i) for i in range(11)}, 5, 24)) == 1


def test_window_preserves_all_actions_and_exact_actor_time_bounds():
    c = duckdb.connect()
    c.execute('create table chat_messages(id varchar,created_at timestamp,agent_speaker_id varchar)')
    c.execute('create table turns_slim(id varchar,created_at timestamp,agent_id varchar,action varchar)')
    c.execute('create table computer_use_turns(id varchar,agent_action varchar,output varchar,error varchar)')
    at = datetime(2026,10,2,10)
    c.execute('insert into chat_messages values (?,?,?)',['claim',at,'actor'])
    events = [('boundary',90,'actor','type'),('recent',0,'actor','bash'),
              ('too_old',91,'actor','bash'),('future',-1,'actor','bash'),('foreign',10,'other','bash')]
    for identifier,minutes,actor,kind in events:
        c.execute('insert into turns_slim values (?,?,?,?)',[identifier,at-timedelta(minutes=minutes),actor,kind])
        c.execute('insert into computer_use_turns values (?,?,?,?)',[identifier,'{}','"ok"',None])
    rows = c.execute(WINDOW_SQL,[['claim']]).fetchall()
    assert [r[1] for r in rows] == ['boundary','recent']


def test_clip_marks_omission_and_keeps_head_tail():
    assert clip('abcdefghij',6) == 'abc\n[… 4 characters omitted by exporter …]\nhij'
    assert clip('abcdef',6) == 'abcdef'


def test_aggregation_keeps_unverified_in_denominator_and_paired_transitions():
    labels = [{'eligible':True,'label_30':'unverified','label_90':'supported'},
              {'eligible':True,'label_30':'contradicted','label_90':'contradicted'},
              {'eligible':False,'label_30':'unverified','label_90':'unverified'}]
    a = aggregate(labels)
    assert a['90']['denominator'] == 2
    assert a['90']['counts'] == {'supported':1,'contradicted':1}
    assert a['paired_transitions']['unverified->supported'] == 1
