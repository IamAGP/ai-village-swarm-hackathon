"""Synthetic counterexamples: no private data or mirrored semantic labels."""
import json

import duckdb
import pytest

from explorer.trace_retraction import ANNOUNCEMENT_ID, RETRACTION_ID, RetractionExporter
from explorer.trace_retraction_review import decode_text, line_contexts, IDENTIFIED
from explorer.trace_retraction_labels import LabelAudit, agreement


def test_export_window_and_channels(tmp_path):
    source = tmp_path/'parquet';source.mkdir()
    con = duckdb.connect()
    con.execute("CREATE TABLE agents(id VARCHAR,name VARCHAR); INSERT INTO agents VALUES ('a','Synthetic')")
    con.execute('CREATE TABLE chat_messages(id VARCHAR,created_at TIMESTAMP,agent_speaker_id VARCHAR,content VARCHAR,room_id VARCHAR)')
    con.executemany('INSERT INTO chat_messages VALUES (?,? ,?,?,?)',[
        (ANNOUNCEMENT_ID,'2026-07-30 18:18:18.585603','a','conjectures 258 and 259','r'),
        (RETRACTION_ID,'2026-07-30 19:20:58.248631','a','withdraw 258/259','r'),
        ('before','2026-07-30 18:18:18.585602','a','258','r'),
        ('last','2026-08-06 18:18:18.585602','a','eleven conjectures','r'),
        ('outside','2026-08-06 18:18:18.585603','a','258','r')])
    con.execute('CREATE TABLE agent_memories(id VARCHAR,created_at TIMESTAMP,updated_at TIMESTAMP,agent_id VARCHAR,content VARCHAR)')
    con.execute("INSERT INTO agent_memories VALUES ('m','2026-07-30 19:22:00','2026-07-30 19:22:01','a','eleven results')")
    con.execute('CREATE TABLE computer_use_sessions(id VARCHAR,agent_id VARCHAR)')
    con.execute("INSERT INTO computer_use_sessions VALUES ('s','a')")
    con.execute('CREATE TABLE computer_use_turns(id VARCHAR,created_at TIMESTAMP,session_id VARCHAR,agent_action VARCHAR,agent_messages VARCHAR,output VARCHAR,error VARCHAR)')
    con.execute("INSERT INTO computer_use_turns VALUES ('t','2026-07-30 19:23:00','s','read local blog','', '258/259', '')")
    con.execute('CREATE TABLE claude_code_messages(id VARCHAR,created_at TIMESTAMP,agent_id VARCHAR,content VARCHAR,message_type VARCHAR)')
    for table in ['agents','chat_messages','agent_memories','computer_use_sessions','computer_use_turns','claude_code_messages']:
        con.execute(f"COPY {table} TO '{source/table}.parquet' (FORMAT PARQUET)")
    out = tmp_path/'frame';out.mkdir()
    RetractionExporter(source,out).export()
    manifest = json.loads((out/'manifest.json').read_text())
    rows = [json.loads(line) for part in manifest['partitions'] for line in (out/part['path']).read_text().splitlines()]
    assert manifest['complete'] and manifest['candidate_count'] == 5
    assert {r['id'] for r in rows} == {ANNOUNCEMENT_ID,RETRACTION_ID,'last','m','t'}
    assert next(r for r in rows if r['id']=='t')['agent_id']=='a'
    assert next(r for r in rows if r['id']=='m')['updated_at']=='2026-07-30 19:22:01'


def test_display_keeps_distant_withdrawal_qualification():
    text = '# Earlier\nConjectures 258/259 disproved.\n\n' + 'unrelated\n'*100 + '# Current\nRetracted 258/259; nine remain.\n'
    contexts = list(line_contexts(text,IDENTIFIED))
    assert contexts and 'Retracted 258/259' in contexts[0]['text']
    assert contexts[0]['clipped']
    assert decode_text('{"type":"assistant", "content":["Withdraw 258/259"]}') == 'assistant\nWithdraw 258/259'


def test_later_count_alone_does_not_identify_old_membership():
    assert list(line_contexts('New result 287 restores ten disproofs.',IDENTIFIED)) == []
    assert list(line_contexts('Conjectures 258/259 were withdrawn; new result 287.',IDENTIFIED))


def make_audit(tmp_path):
    row = dict(id='row',channel='turn',actor='a',at='2026-07-30 19:21:00')
    (tmp_path/'blind.jsonl').write_text(json.dumps(dict(case_id='R001',source_author=False,contexts=[]))+'\n')
    (tmp_path/'key.json').write_text(json.dumps(dict(rows={'r_one':row},cases={'R001':dict(actor='a',name='Synthetic')})))
    return LabelAudit(tmp_path)


def label():
    return dict(case_id='R001',a=False,b=True,c=True,mentioned=True,a_public=False,
                c_public=False,c_artifact=True,c_private=False,a_evidence=[],
                b_evidence=['r_one'],c_evidence=['r_one'],first_a=None,
                first_b='2026-07-30 19:21:00',first_c='2026-07-30 19:21:00',
                last_c='2026-07-30 19:21:00',reason='Own correction and stale artifact coexist.')


def test_overlapping_knowledge_and_artifact_lag_are_valid(tmp_path):
    audit = make_audit(tmp_path)
    assert audit.validate([label()])['R001']['b'] is True
    bad = label();bad['c_artifact']=False
    with pytest.raises(ValueError,match='union mismatch'):audit.validate([bad])
    bad = label();bad['a_public']=True
    with pytest.raises(ValueError,match='public spread'):audit.validate([bad])


def test_evidence_identity_phase_endpoint_and_freeze(tmp_path):
    audit = make_audit(tmp_path)
    audit.rows['r_one']['actor']='other'
    with pytest.raises(ValueError,match='another case'):audit.validate([label()])
    audit.rows['r_one']['actor']='a';audit.rows['r_one']['at']='2026-07-30 19:20:00'
    with pytest.raises(ValueError,match='wrong evidence phase'):audit.validate([label()])
    audit.rows['r_one']['at']='2026-07-30 19:21:01'
    with pytest.raises(ValueError,match='endpoint'):audit.validate([label()])
    frozen = tmp_path/'frozen';frozen.mkdir()
    (frozen/'labels.jsonl').write_text(json.dumps(label())+'\n')
    (frozen/'freeze.json').write_text(json.dumps(dict(sha256='tampered',packet_sha256=audit.packet_hash)))
    with pytest.raises(ValueError,match='hash mismatch'):audit.load_frozen(frozen)


def test_kappa_class_imbalance_and_degenerate_marginals():
    assert agreement([False]*27,[False]*27)['kappa'] is None
    result = agreement([False,False,True,True],[False,True,True,True])
    assert result['agree']==3 and result['kappa']==pytest.approx(.5)
    assert result['wilson95'][0] < .75 < result['wilson95'][1]
