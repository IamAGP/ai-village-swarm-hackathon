import json

import duckdb
import pytest

from explorer.belief_graph import build_graph, GraphBuilder, GRAFFITI_URL


@pytest.fixture
def con():
    c = duckdb.connect()
    c.execute('CREATE TABLE agents(id VARCHAR, name VARCHAR)')
    c.execute("INSERT INTO agents VALUES ('a','Alpha'),('b','Beta'),('c','Gamma'),('d','Delta')")
    c.execute('CREATE TABLE trace_first_use(url VARCHAR,actor VARCHAR,is_human BOOLEAN,channel VARCHAR,first_at TIMESTAMP,row_id VARCHAR)')
    c.execute('CREATE TABLE trace_edges_scored(url VARCHAR,source VARCHAR,target VARCHAR,s_at TIMESTAMP,t_at TIMESTAMP,source_row VARCHAR,target_row VARCHAR,evidence VARCHAR)')
    c.execute('CREATE TABLE f1_verify(agent VARCHAR,created_at TIMESTAMP,row_id VARCHAR,status VARCHAR)')
    c.execute('CREATE TABLE chat_messages(id VARCHAR,agent_speaker_id VARCHAR,created_at TIMESTAMP,content VARCHAR)')
    c.execute('CREATE TABLE screen_labels(claim_id VARCHAR,turn_id VARCHAR,label VARCHAR)')
    c.execute('CREATE TABLE screen_adjudications(claim_id VARCHAR,acted_after BOOLEAN,confirmed BOOLEAN)')
    yield c
    c.close()


def use(c, actor, channel, at, row, url=GRAFFITI_URL):
    c.execute('INSERT INTO trace_first_use VALUES (?,?,false,?,?,?)',[url,actor,channel,at,row])


def told(c, source, target, evidence='explicit', url=GRAFFITI_URL, at='2026-07-29 12:01'):
    c.execute("INSERT INTO trace_edges_scored VALUES (?,?,?,'2026-07-29 12:00',?,?,?,?)",
              [url,source,target,at,'post-'+source,'adopt-'+target,evidence])


def assert_contract(graph):
    ids = {n['id'] for n in graph['nodes']}
    assert graph['edges'] == sorted(graph['edges'],key=lambda e:(e['at'],e['id']))
    assert graph['nodes'] == sorted(graph['nodes'],key=lambda n:(n['first_at'],n['id']))
    assert len({e['id'] for e in graph['edges']}) == len(graph['edges'])
    for n in graph['nodes']:
        assert len(n['label']) <= 80
        assert n['first_at'].endswith('Z')
    for e in graph['edges']:
        assert e['source'] in ids and e['target'] in ids
        assert e['at'].endswith('Z')
        assert (len(e['rows'])==2 and all(e['rows'])) if e['kind']=='told' else bool(e['row'])
        if e.get('artifact'): assert e['artifact'] in ids
    json.dumps(graph)


def test_url_channels_verifier_signals_and_row_provenance(con):
    for channel,row in [('chat','chat-row'),('model_output','out-row'),('action','action-row'),('memory','memory-row')]:
        use(con,'a',channel,'2026-07-29 12:00',row)
    told(con,'a','b')
    for evidence in ('none','stale','cross_room'): told(con,'a','c',evidence)
    told(con,'a','d','mention')
    con.execute("INSERT INTO f1_verify VALUES ('Beta','2026-07-30 14:00','run-ok','success'),('Beta','2026-07-30 13:59','run-fail','fail'),('Gamma','2026-07-30 14:01','run-unknown','unknown')")
    graph=build_graph(con,{'kind':'url','value':GRAFFITI_URL+'.git/#fragment'})
    assert graph['seed']['value']==GRAFFITI_URL
    counts={kind:sum(e['kind']==kind for e in graph['edges']) for kind in ('said','did','told','checked')}
    assert counts=={'said':2,'did':2,'told':2,'checked':3}
    assert {e['row']:e['status'] for e in graph['edges'] if e['kind']=='checked'}=={'run-ok':'supported','run-fail':'contradicted','run-unknown':'unknown'}
    assert graph['meta']['omitted']['excluded_told_evidence']==3
    assert_contract(graph)


def test_claim_requires_confirmed_screen_contradiction_and_never_exports_text(con):
    con.execute("INSERT INTO chat_messages VALUES ('claim','a','2026-07-29 12:00','PRIVATE SOURCE MESSAGE')")
    con.execute("INSERT INTO screen_labels VALUES ('claim','screen-row','contradicted')")
    con.execute("INSERT INTO screen_adjudications VALUES ('claim',false,NULL)")
    seed={'kind':'claim','value':'claim'}
    graph=build_graph(con,seed)
    checked=next(e for e in graph['edges'] if e['kind']=='checked')
    assert checked['status']=='unknown' and checked['row']=='screen-row'
    assert checked['claim_row']=='claim' and checked['retrospective'] is True
    assert 'PRIVATE SOURCE MESSAGE' not in json.dumps(graph)
    con.execute('UPDATE screen_adjudications SET confirmed=true')
    assert next(e for e in build_graph(con,seed)['edges'] if e['kind']=='checked')['status']=='contradicted'
    con.execute('UPDATE screen_adjudications SET acted_after=true')
    assert next(e for e in build_graph(con,seed)['edges'] if e['kind']=='checked')['status']=='unknown'
    assert_contract(graph)


def test_supported_unknown_and_conflicting_screen_labels(con):
    con.execute("INSERT INTO chat_messages VALUES ('claim','a','2026-07-29 12:00','unexported')")
    con.execute("INSERT INTO screen_labels VALUES ('claim','screen','supported')")
    seed={'kind':'claim','value':'claim'}
    assert next(e for e in build_graph(con,seed)['edges'] if e['kind']=='checked')['status']=='supported'
    con.execute("INSERT INTO screen_labels VALUES ('claim','screen','contradicted')")
    graph=build_graph(con,seed)
    assert len([e for e in graph['edges'] if e['kind']=='checked'])==1
    assert next(e for e in graph['edges'] if e['kind']=='checked')['status']=='unknown'


def test_agent_window_is_first_hop_and_utc_inclusive(con):
    use(con,'a','action','2026-07-29 12:00','action')
    use(con,'b','action','2026-07-29 12:00','neighbour-action','https://outside.example')
    told(con,'a','b')
    told(con,'b','c')
    told(con,'d','a','temporal')
    told(con,'a','c',at='2026-07-29 12:02')
    graph=build_graph(con,{'kind':'agent','value':'a','start':'2026-07-29T17:30:00+05:30','end':'2026-07-29T12:01:00Z'})
    assert {n['id'] for n in graph['nodes']}=={'agent:a','agent:b','agent:d','artifact:'+GRAFFITI_URL}
    assert len([e for e in graph['edges'] if e['kind']=='told'])==2
    assert graph['meta']['window']['start']=='2026-07-29T12:00:00.000000Z'
    assert_contract(graph)


def test_caps_keep_complete_edges_and_report_exact_omissions(con):
    con.execute("INSERT INTO agents SELECT 'x'||i,'Neighbour '||i FROM range(100) t(i)")
    for i in range(100): told(con,'a','x'+str(i),url='https://artifact.example/'+str(i))
    seed={'kind':'agent','value':'a','max_nodes':60}
    graph=build_graph(con,seed)
    assert len(graph['nodes'])<=60 and graph['edges']
    assert 'agent:a' in {n['id'] for n in graph['nodes']}
    assert graph['meta']['nodes_before_cap']==201
    assert graph['meta']['nodes_cut']==201-len(graph['nodes'])
    assert graph['meta']['edges_cut']==100-len(graph['edges'])
    assert_contract(graph)
    assert graph==build_graph(con,seed)


def test_order_independent_of_input_order_and_duplicate_rows(con):
    use(con,'b','action','2026-07-29 12:01','b')
    use(con,'a','chat','2026-07-29 12:00','a')
    told(con,'a','b')
    seed={'kind':'url','value':GRAFFITI_URL}
    first=build_graph(con,seed)
    con.execute('CREATE TABLE tmp AS SELECT * FROM trace_first_use ORDER BY row_id DESC')
    con.execute('DELETE FROM trace_first_use')
    con.execute('INSERT INTO trace_first_use SELECT * FROM tmp')
    con.execute('INSERT INTO trace_edges_scored SELECT * FROM trace_edges_scored')
    assert first==build_graph(con,seed)


def test_empty_optional_sources_and_invalid_seeds(con):
    graph=build_graph(con,{'kind':'url','value':'https://empty.example'})
    assert graph['nodes']==graph['edges']==[] and graph['t0'] is None
    for seed in ({'kind':'invalid','value':'a'},{'kind':'url','value':''},{'kind':'agent','value':'missing'},
                 {'kind':'agent','value':'a','max_nodes':True},
                 {'kind':'agent','value':'a','start':'2026-07-30','end':'2026-07-29'}):
        with pytest.raises(ValueError): build_graph(con,seed)


def test_file_loading_on_read_only_connection_and_cli_stdout(tmp_path,con,capsys):
    from explorer.belief_graph import main
    for name in ('agents','trace_first_use','trace_edges_scored','chat_messages','f1_verify'):
        path=str(tmp_path/(name+'.parquet')).replace("'","''")
        con.execute(f"COPY {name} TO '{path}' (FORMAT parquet)")
    use(con,'a','chat','2026-07-29 12:00','chat')
    db=tmp_path/'read-only.duckdb'
    duckdb.connect(str(db)).close()
    readonly=duckdb.connect(str(db),read_only=True)
    paths={name:str(tmp_path/(name+'.parquet')) for name in ('agents','trace_first_use','trace_edges_scored')}
    g=GraphBuilder(readonly,{'kind':'url','value':'https://empty.example'},paths).build()
    assert g['nodes']==[]
    readonly.close()
    main(['url','https://empty.example','--parquet',str(tmp_path),'--trace',str(tmp_path),'--findings',str(tmp_path)])
    out=capsys.readouterr()
    assert json.loads(out.out)['nodes']==[]
    assert 'belief_graph' in out.err


def test_screen_only_agent_default_window_is_bounded(con):
    con.execute("INSERT INTO chat_messages VALUES ('early','a','2026-07-01','private'),('late','a','2026-07-20','private')")
    con.execute("INSERT INTO screen_labels VALUES ('early','first-screen','supported'),('late','later-screen','supported')")
    graph=build_graph(con,{'kind':'agent','value':'a'})
    assert graph['meta']['window']=={'start':'2026-07-01T00:00:00.000000Z','end':'2026-07-08T00:00:00.000000Z'}
    assert {e['row'] for e in graph['edges']}=={'early','first-screen'}


def test_invalid_future_exposure_and_human_rows_are_reported(con):
    con.execute("INSERT INTO trace_first_use VALUES (?,'human:organizer',true,'chat','2026-07-29','human-post')",[GRAFFITI_URL])
    told(con,'a','b',at='2026-07-29 11:00')
    graph=build_graph(con,{'kind':'url','value':GRAFFITI_URL})
    assert graph['edges']==[]
    assert graph['meta']['omitted']=={'human_uses':1,'invalid_told_rows':1}


def test_named_confirmed_case_stale_override_and_missing_label(con):
    cid='d9f1dcc2-synthetic'
    con.execute("INSERT INTO chat_messages VALUES (?,'a','2026-07-29','private')",[cid])
    seed={'kind':'claim','value':cid}
    graph=build_graph(con,seed)
    assert graph['meta']['omitted']['unlabelled_claim']==1
    con.execute("INSERT INTO screen_labels VALUES (?,'screen','contradicted')",[cid])
    assert next(e for e in build_graph(con,seed)['edges'] if e['kind']=='checked')['status']=='contradicted'
    con.execute('INSERT INTO screen_adjudications VALUES (?,false,false)',[cid])
    assert next(e for e in build_graph(con,seed)['edges'] if e['kind']=='checked')['status']=='unknown'


def test_replayed_false_positive_overrides_old_positive_adjudication(con):
    cid = 'd1630bc1-synthetic'
    con.execute("INSERT INTO chat_messages VALUES (?,'a','2026-07-29','private')", [cid])
    con.execute("INSERT INTO screen_labels VALUES (?,'cached-tree','contradicted')", [cid])
    con.execute('INSERT INTO screen_adjudications VALUES (?,false,true)', [cid])
    graph = build_graph(con, {'kind': 'claim', 'value': cid})
    checked = next(e for e in graph['edges'] if e['kind'] == 'checked')
    assert checked['status'] == 'unknown'
    assert graph['meta']['omitted']['unconfirmed_screen_flags'] == 1
