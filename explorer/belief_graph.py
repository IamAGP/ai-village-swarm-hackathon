"""Row-linked evidence graphs; source tables are read-only and text is not exported.

build_graph accepts {kind, value, label?, start?, end?, max_nodes?}. Existing
DuckDB tables/views win; missing inputs are mounted as TEMP views from the usual
explorer paths. meta reports exclusions/caps and the limitations of checked edges.
"""
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
import argparse
import hashlib
import json
from pathlib import Path
import sys

import duckdb

try:
    from .tracer import canonical
except ImportError:
    from tracer import canonical

GRAFFITI_URL = 'https://gitlab.com/ai-village-agents/village/graffiti-verification'
# Explicitly confirmed case prefixes in docs/EVAL.md (Oct 2 screen audit).
# No-action-between is necessary, not sufficient; never infer confirmation from it.
CONFIRMED_SCREEN_PREFIXES = frozenset({
    'adc5e76b', 'b7835bdc', 'd9f1dcc2', 'fc4a8296', '652c7de0',
    '3b0c4655', '3c29f7ca', 'ca23d4d2', '9ceccafd', 'dc559060',
})
TOLD_EVIDENCE = ('explicit', 'temporal', 'mention')
CHANNELS = {'chat': 'said', 'model_output': 'said', 'memory': 'did', 'action': 'did'}
DEFAULT_PATHS = {
    'agents': '/data/parquet/agents.parquet',
    'chat_messages': '/data/parquet/chat_messages.parquet',
    'trace_first_use': '/data/trace/trace_first_use.parquet',
    'trace_edges_scored': '/data/trace/trace_edges_scored.parquet',
    'f1_verify': '/data/findings/f1_verify.parquet',
    'screen_labels': '/data/findings/claims_all/labels_all.jsonl',
    'screen_adjudications': '/data/findings/claims_all/contra_check.jsonl',
}


def utc(value):
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if not isinstance(value, datetime):
        raise ValueError(f'Expected timestamp, got {type(value).__name__}')
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def iso(value):
    return utc(value).isoformat(timespec='microseconds').replace('+00:00', 'Z')


def short_label(value):
    return ' '.join(str(value).split())[:80]


class Sources:
    """Use caller-owned views or temporary read-only file projections, never a shared DB write."""
    def __init__(self, con, paths=None):
        self.con = con
        self.paths = {**DEFAULT_PATHS, **(paths or {})}
        self.missing = []
        self.cache = {}

    def relation(self, name, required=False):
        if name not in self.cache:
            try:
                self.con.execute(f'SELECT * FROM {name} LIMIT 0')
                self.cache[name] = name
            except duckdb.CatalogException:
                path = self.paths.get(name)
                if path and Path(path).is_file():
                    reader = 'read_json_auto' if str(path).endswith('.jsonl') else 'read_parquet'
                    escaped = str(path).replace("'", "''")
                    view = '_belief_' + name
                    self.con.execute(f"CREATE OR REPLACE TEMP VIEW {view} AS SELECT * FROM {reader}('{escaped}')")
                    self.cache[name] = view
                else:
                    self.cache[name] = None
                    self.missing.append(name)
        table = self.cache[name]
        if required and table is None:
            raise FileNotFoundError(f'Missing belief graph input {name}: {self.paths.get(name)}')
        return table

    def records(self, name):
        table = self.relation(name)
        if table is None:
            return []
        cursor = self.con.execute(f'SELECT * FROM {table}')
        fields = [r[0] for r in cursor.description]
        return [dict(zip(fields, r)) for r in cursor.fetchall()]


class GraphBuilder:
    def __init__(self, con, seed, paths=None):
        if not isinstance(seed, dict) or seed.get('kind') not in ('url', 'claim', 'agent'):
            raise ValueError('seed must be a dict with kind url, claim, or agent')
        if not isinstance(seed.get('value'), str) or not seed['value'].strip():
            raise ValueError('seed.value must be a nonempty string')
        self.con, self.seed = con, dict(seed)
        self.sources = Sources(con, paths)
        self.nodes, self.edges = {}, {}
        self.omissions = Counter()
        self.start = utc(seed['start']) if seed.get('start') else None
        self.end = utc(seed['end']) if seed.get('end') else None
        if self.start and self.end and self.start > self.end:
            raise ValueError('start must not be after end')
        self.cap = seed.get('max_nodes', 60 if seed['kind'] == 'agent' else None)
        if self.cap is not None:
            if isinstance(self.cap, bool) or not isinstance(self.cap, int) or self.cap < 2:
                raise ValueError('max_nodes must be an integer >= 2')
            if seed['kind'] == 'agent':
                self.cap = min(self.cap, 60)
        agents = self.sources.relation('agents', required=True)
        rows = con.execute(f'SELECT id::VARCHAR, name FROM {agents}').fetchall()
        self.names = dict(rows)
        by_name = defaultdict(list)
        for identifier, name in rows:
            by_name[name].append(identifier)
        self.ids_by_name = {n: ids[0] for n, ids in by_name.items() if len(ids) == 1}
        self.labels = None
        self.adjudications = None
        self.anchor = None

    def in_window(self, at):
        at = utc(at)
        return (self.start is None or at >= self.start) and (self.end is None or at <= self.end)

    def node(self, identifier, kind, label, at):
        at = iso(at)
        existing = self.nodes.get(identifier)
        if existing:
            existing['first_at'] = min(existing['first_at'], at)
        else:
            self.nodes[identifier] = {'id': identifier, 'kind': kind, 'label': short_label(label), 'first_at': at}
        return identifier

    def agent(self, identifier, at):
        return self.node('agent:' + identifier, 'agent', self.names.get(identifier, identifier), at)

    def artifact(self, identifier, at, claim=False):
        return self.node('artifact:' + identifier, 'artifact',
                         'Claim ' + identifier[:8] if claim else identifier, at)

    def edge(self, kind, source, target, at, **fields):
        edge = {'kind': kind, 'source': source, 'target': target, 'at': iso(at), **fields}
        identity = json.dumps(edge, sort_keys=True, separators=(',', ':'))
        edge['id'] = kind + ':' + hashlib.sha256(identity.encode()).hexdigest()[:24]
        self.edges[edge['id']] = edge

    def bounds_sql(self, column):
        clauses, params = [], []
        for operator, bound in [('>=', self.start), ('<=', self.end)]:
            if bound is not None:
                clauses.append(f'{column} {operator} ?')
                params.append(bound.replace(tzinfo=None))
        return (' AND ' + ' AND '.join(clauses) if clauses else ''), params

    def uses(self, url=None, actor=None):
        table = self.sources.relation('trace_first_use', required=True)
        bounds, params = self.bounds_sql('first_at')
        where, values = [], []
        for field, value in [('url', url), ('actor', actor)]:
            if value is not None:
                where.append(field + ' = ?'); values.append(value)
        clause = ' AND '.join(where) or 'TRUE'
        rows = self.con.execute(f"SELECT url,actor,is_human,channel,first_at,row_id FROM {table} WHERE {clause}{bounds}", values + params).fetchall()
        for url, actor, human, channel, at, row in rows:
            if human or str(actor).startswith('human:'):
                self.omissions['human_uses'] += 1; continue
            if not url or not actor or not row or at is None or channel not in CHANNELS:
                self.omissions['invalid_or_unknown_channel_uses'] += 1; continue
            source = self.agent(str(actor), at)
            target = self.artifact(url, at)
            self.edge(CHANNELS[channel], source, target, at, channel=channel, row=str(row))

    def told(self, url=None, actor=None):
        table = self.sources.relation('trace_edges_scored', required=True)
        bounds, params = self.bounds_sql('t_at')
        clause, values = ('url = ?', [url]) if url is not None else ('source = ? OR target = ?', [actor, actor])
        rows = self.con.execute(f"SELECT url,source,target,s_at,t_at,source_row,target_row,evidence FROM {table} WHERE ({clause}){bounds}", values + params).fetchall()
        for url, source, target, s_at, at, s_row, t_row, evidence in rows:
            if evidence not in TOLD_EVIDENCE:
                self.omissions['excluded_told_evidence'] += 1; continue
            if not source or not target or str(source).startswith('human:') or str(target).startswith('human:'):
                self.omissions['human_or_missing_told_actor'] += 1; continue
            if not url or not s_row or not t_row or at is None or source == target or (s_at and utc(s_at) > utc(at)):
                self.omissions['invalid_told_rows'] += 1; continue
            a = self.agent(str(source), s_at or at)
            b = self.agent(str(target), at)
            artifact = self.artifact(url, s_at or at)
            self.edge('told', a, b, at, evidence=evidence, rows=[str(s_row), str(t_row)], artifact=artifact)

    def verifiers(self, actor=None):
        table = self.sources.relation('f1_verify')
        if table is None:
            return
        bounds, params = self.bounds_sql('created_at')
        clause, values = ('agent = ?', [self.names.get(actor)]) if actor else ('TRUE', [])
        rows = self.con.execute(f"SELECT agent,created_at,row_id,status FROM {table} WHERE {clause}{bounds}", values + params).fetchall()
        for name, at, row, status in rows:
            identifier = self.ids_by_name.get(name)
            if not identifier or not row or at is None:
                self.omissions['unresolved_verifier_rows'] += 1; continue
            a = self.agent(identifier, at)
            artifact = self.artifact(GRAFFITI_URL, at)
            self.edge('checked', a, artifact, at, status={'success':'supported', 'fail':'contradicted'}.get(status, 'unknown'), row=str(row), basis='verifier')

    def screens(self, claim=None, actor=None):
        if self.labels is None:
            self.labels = self.sources.records('screen_labels')
            self.adjudications = defaultdict(list)
            for record in self.sources.records('screen_adjudications'):
                self.adjudications[str(record.get('claim_id'))].append(record)
        selected = [r for r in self.labels if claim is None or str(r.get('claim_id')) == claim]
        if not selected:
            if claim is not None:
                self.omissions['unlabelled_claim'] += 1
            return
        chat = self.sources.relation('chat_messages', required=True)
        ids = sorted({str(r['claim_id']) for r in selected if r.get('claim_id')})
        rows = self.con.execute(f'SELECT id::VARCHAR,agent_speaker_id,created_at FROM {chat} WHERE id IN (SELECT unnest(?))', [ids]).fetchall()
        claims = {str(cid):(str(a) if a else None, at) for cid,a,at in rows}
        groups = defaultdict(list)
        for record in selected:
            groups[(str(record.get('claim_id')), str(record.get('turn_id') or ''))].append(record)
        for (cid, turn), records in sorted(groups.items()):
            speaker, at = claims.get(cid, (None, None))
            if not speaker or at is None or not turn:
                self.omissions['missing_screen_claim_or_turn'] += 1; continue
            if actor is not None and speaker != actor:
                continue
            if not self.in_window(at):
                continue
            labels = {r.get('label') for r in records}
            verdict = next(iter(labels)) if len(labels) == 1 else 'unknown'
            adjudications = self.adjudications.get(cid, [])
            stale = any(r.get('acted_after') is True for r in adjudications)
            explicit_confirmed = any(r.get('confirmed') is True for r in adjudications)
            explicit_rejected = any(r.get('confirmed') is False for r in adjudications)
            confirmed = (explicit_confirmed or cid[:8] in CONFIRMED_SCREEN_PREFIXES) and not stale and not explicit_rejected
            status = 'supported' if verdict == 'supported' else ('contradicted' if verdict == 'contradicted' and confirmed else 'unknown')
            if verdict == 'contradicted' and status == 'unknown':
                self.omissions['unconfirmed_screen_flags'] += 1
            a = self.agent(speaker, at)
            artifact = self.artifact(cid, at, claim=True)
            self.edge('said', a, artifact, at, channel='chat', row=cid)
            self.edge('checked', a, artifact, at, status=status, row=turn, basis='screen', claim_row=cid,
                      retrospective=True, adjudicated=bool(verdict == 'contradicted' and confirmed))

    def claim(self):
        cid = self.seed['value']
        table = self.sources.relation('chat_messages', required=True)
        row = self.con.execute(f'SELECT agent_speaker_id,created_at FROM {table} WHERE id = ?', [cid]).fetchone()
        if not row or not row[0]:
            raise ValueError('Claim seed must identify an agent chat message')
        if self.in_window(row[1]):
            a, artifact = self.agent(str(row[0]), row[1]), self.artifact(cid, row[1], claim=True)
            self.anchor = artifact
            self.edge('said', a, artifact, row[1], channel='chat', row=cid)
        self.screens(claim=cid)

    def agent_graph(self):
        actor = self.seed['value']
        if actor not in self.names:
            raise ValueError('Unknown agent seed')
        uses = self.sources.relation('trace_first_use', required=True)
        edges = self.sources.relation('trace_edges_scored', required=True)
        if self.start is None:
            if self.end:
                self.start = self.end - timedelta(days=7)
            else:
                at = self.con.execute(f"SELECT min(seen_at) FROM (SELECT first_at AS seen_at FROM {uses} WHERE actor=? UNION ALL SELECT t_at FROM {edges} WHERE source=? OR target=?)", [actor,actor,actor]).fetchone()[0]
                if at is None:
                    # A screen-only or verifier-only agent still gets a bounded
                    # default window, rather than silently scanning all time.
                    candidates = []
                    verify = self.sources.relation('f1_verify')
                    if verify:
                        v_at = self.con.execute(f'SELECT min(created_at) FROM {verify} WHERE agent=?', [self.names[actor]]).fetchone()[0]
                        if v_at:
                            candidates.append(v_at)
                    chat = self.sources.relation('chat_messages')
                    ids = sorted({str(r['claim_id']) for r in self.sources.records('screen_labels') if r.get('claim_id')})
                    if chat and ids:
                        c_at = self.con.execute(f'SELECT min(created_at) FROM {chat} WHERE agent_speaker_id=? AND id IN (SELECT unnest(?))', [actor,ids]).fetchone()[0]
                        if c_at:
                            candidates.append(c_at)
                    at = min(candidates) if candidates else None
                if at:
                    self.start = utc(at)
        if self.end is None and self.start:
            self.end = self.start + timedelta(days=7)
        self.anchor = 'agent:' + actor
        self.uses(actor=actor)
        self.told(actor=actor)
        self.verifiers(actor=actor)
        self.screens(actor=actor)

    def finish(self):
        nodes = sorted(self.nodes.values(), key=lambda n:(n['first_at'], n['id']))
        total_nodes, total_edges = len(nodes), len(self.edges)
        if self.cap is not None and len(nodes) > self.cap:
            keep = {self.anchor} if self.anchor in self.nodes else set()
            # Keep complete earliest evidence groups; selecting nodes alone can
            # exhaust the budget on agents and remove every artifact/edge.
            for edge in sorted(self.edges.values(), key=lambda e:(e['at'], e['id'])):
                needed = {edge['source'], edge['target']}
                if edge.get('artifact'):
                    needed.add(edge['artifact'])
                if len(keep | needed) <= self.cap:
                    keep.update(needed)
            nodes = [n for n in nodes if n['id'] in keep]
        kept = {n['id'] for n in nodes}
        edges = [e for e in self.edges.values() if e['source'] in kept and e['target'] in kept and (e.get('artifact') is None or e['artifact'] in kept)]
        edges.sort(key=lambda e:(e['at'], e['id']))
        meta = {'window':{'start':iso(self.start) if self.start else None, 'end':iso(self.end) if self.end else None},
                'max_nodes':self.cap, 'nodes_before_cap':total_nodes, 'edges_before_cap':total_edges,
                'nodes_cut':total_nodes-len(nodes), 'edges_cut':total_edges-len(edges),
                'omitted':dict(sorted(self.omissions.items())), 'missing_optional_sources':sorted(self.sources.missing),
                'claim_followups':'not inferred: source has no structured reply linkage',
                'screen_confirmation':'explicit confirmed=true or EVAL-named allowlist; stale/rejected flags remain unknown',
                'semantics':{
                    'told':'candidate exposure, not proven transmission',
                    'said':'first recorded chat/model-output URL use, not necessarily endorsement',
                    'did':'first recorded action/memory URL use, not successful execution',
                    'verifier':'filename/output heuristic; failure is a run signal, not mathematical disproof',
                    'screen':'retrospective reviewer judgment at claim time, not an agent verification action',
                }}
        return {'seed':{'kind':self.seed['kind'], 'value':self.seed['value'],
                        'label':short_label(self.seed.get('label') or self.names.get(self.seed['value']) or ('Claim '+self.seed['value'][:8] if self.seed['kind']=='claim' else self.seed['value']))},
                't0':min((n['first_at'] for n in nodes),default=None), 'nodes':nodes, 'edges':edges, 'meta':meta}

    def build(self):
        if self.seed['kind'] == 'url':
            self.seed['value'] = self.con.execute('SELECT ' + canonical(canonical('?')), [self.seed['value']]).fetchone()[0]
            self.anchor = 'artifact:' + self.seed['value']
            self.uses(url=self.seed['value'])
            self.told(url=self.seed['value'])
            if self.seed['value'] == GRAFFITI_URL:
                self.verifiers()
        elif self.seed['kind'] == 'claim':
            self.claim()
        else:
            self.agent_graph()
        return self.finish()


def build_graph(con, seed):
    """Build the #26 JSON contract using caller views or standard explorer files."""
    return GraphBuilder(con, seed).build()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('kind', choices=['url','claim','agent'])
    parser.add_argument('value')
    parser.add_argument('--start'); parser.add_argument('--end')
    parser.add_argument('--max-nodes', type=int)
    parser.add_argument('--parquet', default='/data/parquet')
    parser.add_argument('--trace', default='/data/trace')
    parser.add_argument('--findings', default='/data/findings')
    args = parser.parse_args(argv)
    paths = {name:str(Path(args.parquet)/f'{name}.parquet') for name in ('agents','chat_messages')}
    paths.update({name:str(Path(args.trace)/f'{name}.parquet') for name in ('trace_first_use','trace_edges_scored')})
    paths['f1_verify'] = str(Path(args.findings)/'f1_verify.parquet')
    paths['screen_labels'] = str(Path(args.findings)/'claims_all/labels_all.jsonl')
    paths['screen_adjudications'] = str(Path(args.findings)/'claims_all/contra_check.jsonl')
    seed = {k:v for k,v in {'kind':args.kind,'value':args.value,'start':args.start,'end':args.end,'max_nodes':args.max_nodes}.items() if v is not None}
    con = duckdb.connect()
    con.execute("SET threads=2; SET memory_limit='4GB'; SET TimeZone='UTC'")
    try:
        graph = GraphBuilder(con,seed,paths).build()
    finally:
        con.close()
    print(f"belief_graph nodes={len(graph['nodes'])} edges={len(graph['edges'])} cut={graph['meta']['nodes_cut']}/{graph['meta']['edges_cut']}",file=sys.stderr)
    json.dump(graph,sys.stdout,sort_keys=True); print()


if __name__ == '__main__':
    main()
