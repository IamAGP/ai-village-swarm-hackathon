"""Read-only candidate export and frozen-label audit for the 258/259 withdrawal.

All text-bearing outputs MUST remain on the authorized data box, outside Git.
The retrieval rule is a broad screen, never an endorsement/retraction classifier.
"""
import argparse
from collections import Counter
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import re
import sys

import duckdb


ANNOUNCEMENT_ID = 'b66a02b9-d270-4ce4-88aa-b8fd47476072'
RETRACTION_ID = '56f9501d-c70a-42bc-9786-2c432a7e8597'
SCREEN = (r'(^|[^0-9])(258|259)([^0-9]|$)|'
          r'\b(eleven|ten|11|10)\b.{0,60}(disproof|counterexample|conjecture|result)|'
          r'(disproof|counterexample|conjecture|result).{0,60}\b(eleven|ten|11|10)\b')
CHAT_CONTEXT_SCREEN = 'graffiti|disproof|counterexample|retract|withdraw|mathematical.blog|medium'


def log(step, **metadata):
    print(json.dumps(dict(at=datetime.now(timezone.utc).isoformat(), step=step, **metadata)),
          file=sys.stderr, flush=True)


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, default=str)+'\n')


def fragments(text, radius=450):
    """Display-only contexts with offsets; the complete text remains in the private frame."""
    text = text or ''
    intervals = []
    for m in re.finditer(SCREEN, text, re.I | re.S):
        lo, hi = max(0, m.start()-radius), min(len(text), m.end()+radius)
        if intervals and lo <= intervals[-1][1]:
            intervals[-1][1] = max(hi, intervals[-1][1])
        else:
            intervals.append([lo, hi])
    return [dict(start=lo, end=hi, text=text[lo:hi]) for lo, hi in intervals]


class RetractionExporter:
    def __init__(self, parquet, out):
        self.parquet, self.out = Path(parquet), Path(out)
        self.con = duckdb.connect()
        self.con.execute("SET memory_limit='2GB'")
        self.con.execute('SET threads=2')
        self.con.execute('SET temp_directory=?', [str(self.out/'spill')])
        for table in ['agents', 'chat_messages', 'computer_use_sessions', 'computer_use_turns',
                      'agent_memories', 'claude_code_messages', 'events_slim']:
            path = self.parquet/f'{table}.parquet'
            if path.exists():
                self.con.read_parquet(str(path)).create_view(table)

    def anchor(self, row_id):
        rows = self.con.execute('SELECT id,created_at,agent_speaker_id,content,room_id '
                                'FROM chat_messages WHERE id=?', [row_id]).fetchall()
        if len(rows) != 1:
            raise ValueError('Anchor must match exactly one chat row')
        rid, at, actor, text, room = rows[0]
        return dict(id=rid, at=at, agent_id=actor, text=text, room_id=room)

    def export(self):
        announcement, retraction = self.anchor(ANNOUNCEMENT_ID), self.anchor(RETRACTION_ID)
        start, stop = announcement['at'], announcement['at']+timedelta(days=7)
        roster = dict(self.con.execute('SELECT id::VARCHAR,name FROM agents').fetchall())
        manifest = dict(start=str(start), stop_exclusive=str(stop), retraction_at=str(retraction['at']),
                        screen=SCREEN, complete=False, partitions=[], roster=roster,
                        announcement=announcement, retraction=retraction,
                        activity={}, source_path=str(self.parquet))
        write_json(self.out/'manifest.json', manifest)
        sources = {
            'chat': ("SELECT id,created_at,agent_speaker_id AS agent_id,content AS text,"
                     " room_id::VARCHAR AS room_id FROM chat_messages", ['text']),
            'memory': ('SELECT id,created_at,updated_at,agent_id,content AS text FROM agent_memories', ['text']),
            'turn': ('SELECT t.id,t.created_at,s.agent_id,t.session_id, '
                     't.agent_action::VARCHAR AS action,t.agent_messages::VARCHAR AS messages,'
                     't.output::VARCHAR AS output,t.error::VARCHAR AS error '
                     'FROM computer_use_turns t JOIN computer_use_sessions s ON s.id=t.session_id',
                     ['action','messages','output','error']),
            'code_agent': ('SELECT id,created_at,agent_id,content::VARCHAR AS text,message_type '
                           'FROM claude_code_messages', ['text']),
        }
        available = {t[0] for t in self.con.execute('SHOW TABLES').fetchall()}
        seen_ids = set()
        for channel, (sql, fields) in sources.items():
            if channel == 'code_agent' and 'claude_code_messages' not in available:
                manifest['missing_code_agent_table'] = True
                continue
            for day in range(8):
                lo = max(start, datetime.combine(start.date()+timedelta(days=day),datetime.min.time()))
                hi = min(stop, datetime.combine(start.date()+timedelta(days=day+1),datetime.min.time()))
                if lo >= hi:
                    continue
                condition = ' OR '.join(f'regexp_matches(lower(coalesce({f},\'\')), ?)' for f in fields)
                bounded = f'WITH source AS ({sql}) SELECT * FROM source WHERE created_at>=? AND created_at<?'
                activity = self.con.execute(f'WITH source AS ({sql}) SELECT agent_id,count(*) FROM source '
                                            'WHERE created_at>=? AND created_at<? GROUP BY 1', [lo,hi]).fetchall()
                for actor,n in activity:
                    if actor:
                        manifest['activity'][actor] = manifest['activity'].get(actor,0)+n
                cursor = self.con.execute(bounded+' AND ('+condition+') ORDER BY created_at,id',
                                          [lo,hi]+[SCREEN]*len(fields))
                cols = [c[0] for c in cursor.description]
                name = f'{channel}_{day}.jsonl'
                count = 0
                with (self.out/name).open('w') as f:
                    while batch := cursor.fetchmany(50):
                        for values in batch:
                            item = dict(zip(cols,values))
                            key = channel+':'+item['id']
                            if key in seen_ids:
                                raise ValueError('Duplicate source row across partitions')
                            seen_ids.add(key)
                            item.update(channel=channel, agent=roster.get(item['agent_id'],'unknown'),
                                        at=str(item.pop('created_at')),
                                        fulltext_sha256={k:hashlib.sha256((item.get(k) or '').encode()).hexdigest()
                                                         for k in fields},
                                        fragments={k:fragments(item.get(k)) for k in fields})
                            f.write(json.dumps(item,default=str)+'\n')
                            count += 1
                digest = hashlib.sha256((self.out/name).read_bytes()).hexdigest()
                manifest['partitions'].append(dict(channel=channel,day=day,path=name,n=count,sha256=digest))
                write_json(self.out/'manifest.json',manifest)
                log('partition', channel=channel, day=day, candidates=count)
        manifest['complete'] = True
        manifest['candidate_count'] = len(seen_ids)
        write_json(self.out/'manifest.json',manifest)
        log('export_complete', candidates=len(seen_ids), active_agents=len(manifest['activity']))


    def export_chat_context(self, out):
        """Supplement the count/ID screen with possible correction chat, without labeling it."""
        out = Path(out)
        out.mkdir()
        start = self.anchor(ANNOUNCEMENT_ID)['at']
        stop = start + timedelta(days=7)
        sql = ("SELECT m.id,m.created_at,m.agent_speaker_id,m.room_id,m.content,a.name "
               "FROM chat_messages m JOIN agents a ON a.id=m.agent_speaker_id "
               "WHERE m.created_at>=? AND m.created_at<? "
               "AND regexp_matches(lower(m.content),?) ORDER BY m.created_at,m.id")
        cursor = self.con.execute(sql,[start,stop,CHAT_CONTEXT_SCREEN])
        n = 0
        path = out/'chat_context.jsonl'
        with path.open('w') as f:
            while batch := cursor.fetchmany(50):
                for rid,at,actor,room,text,name in batch:
                    f.write(json.dumps(dict(id=rid,at=str(at),agent_id=actor,room_id=room,
                                           text=text,agent=name,channel='chat'))+'\n')
                    n += 1
        write_json(out/'manifest.json',dict(n=n,screen=CHAT_CONTEXT_SCREEN,start=str(start),
                    stop_exclusive=str(stop),sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
        log('chat_context_complete',candidates=n)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--parquet',default='/data/parquet',type=Path)
    p.add_argument('--out',required=True,type=Path)
    p.add_argument('--chat-context-out',type=Path)
    args=p.parse_args()
    if args.out.exists():
        p.error('Output directory must be new to preserve previous frames')
    args.out.mkdir(parents=True)
    exporter = RetractionExporter(args.parquet,args.out)
    exporter.export()
    if args.chat_context_out:
        exporter.export_chat_context(args.chat_context_out)


if __name__=='__main__':
    main()
