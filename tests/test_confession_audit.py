import json
from explorer.confession_audit import FRAME_SQL, QUERY, Masker, aggregate, sample_frame, wilson
import duckdb


def test_frame_normalizes_formatting_but_retains_screening_false_positives():
    c=duckdb.connect()
    c.execute('CREATE TABLE agents(id VARCHAR)')
    c.execute("INSERT INTO agents VALUES ('a')")
    c.execute('CREATE TABLE chat_messages(id VARCHAR, created_at INTEGER, agent_speaker_id VARCHAR, content VARCHAR)')
    c.executemany('INSERT INTO chat_messages VALUES (?,0,\'a\',?)',[
        ('admit','I **fabricated** those results.'),('curly','I didn’t actually run it.'),
        ('observed','I did not see a link.'),('hypothesis','What if I hallucinated it?'),
        ('other','They fabricated results.'),('negative','I did not hallucinate.')])
    assert {r[0] for r in c.execute(FRAME_SQL,[QUERY]).fetchall()} == {'admit','curly','hypothesis'}


def test_seed_is_order_independent_and_does_not_pad_small_frame():
    frame=[{'id':str(i)} for i in range(13)]
    assert sample_frame(frame)==sample_frame(list(reversed(frame)))
    assert len(sample_frame(frame))==13


def test_masks_names_handles_and_nested_output():
    m=Masker(['GPT-5.1','Claude Sonnet 3.7'])
    x=m.tree({'action': {'text':'GPT‑5.1 read gpt-5-1; Claude Sonnet 3.7 and ClaudeSonnet37 replied.'},'output':None})
    assert 'gpt' not in json.dumps(x).lower()
    assert 'claude' not in json.dumps(x).lower()
    assert x['output'] is None


def test_undetermined_and_excluded_stay_in_denominators():
    r=aggregate([{'eligible':True,'label':'admission contradicted','episode':'a'},
                 {'eligible':True,'label':'undetermined','episode':'a'},
                 {'eligible':False,'label':'undetermined','episode':'b'}])
    assert r['contradicted_over_all']['n']==3
    assert r['contradicted_over_eligible']['n']==2
    assert r['contradicted_over_decided']['n']==1
    assert len(r['episodes'])==1
    assert wilson(0,0) is None
    assert 0.22 < wilson(0,13)[1] < 0.23
