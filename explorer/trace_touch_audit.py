"""Read-only extraction for the adversarial touch/run audit; private outputs only.

Retains every action URL occurrence for selected cascades, not just first-use rows,
and every bash command containing a selected repository basename. Never executes
source commands. The existing detector is copied into the private output for provenance.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import time

import duckdb


REPO_URL = re.compile(r'^https?://(?:www\.)?(github\.com|gitlab\.com)/(?:[^/\s]+/)+([^/\s#?]+?)(?:\.git)?/?$')


def log(stage, **values):
    print(json.dumps({'at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                      'stage': stage, **values}), flush=True)


class AuditExporter:
    def __init__(self, parquet, trace, out):
        self.out = Path(out)
        self.out.mkdir(parents=True, exist_ok=False)
        self.c = duckdb.connect()
        self.c.execute("SET memory_limit='2GB'")
        self.c.execute('SET threads=2')
        self.c.execute('SET temp_directory=?', [str(self.out / 'spill')])
        for alias, path in [('first_use', Path(trace) / 'trace_first_use.parquet'),
                            ('uses', Path(trace) / 'trace_uses.parquet'),
                            ('turns', Path(parquet) / 'turns_slim.parquet'),
                            ('computer', Path(parquet) / 'computer_use_turns.parquet'),
                            ('agents', Path(parquet) / 'agents.parquet')]:
            self.c.read_parquet(str(path)).create_view(alias)

    def jsonl(self, name, sql, parameters=None):
        query = self.c.execute(sql, parameters or [])
        columns = [x[0] for x in query.description]
        count = 0
        with (self.out / name).open('x') as f:
            while rows := query.fetchmany(1000):
                for row in rows:
                    f.write(json.dumps(dict(zip(columns, row)), default=str) + '\n')
                    count += 1
        log(name, rows=count)
        return count

    def export(self):
        self.c.execute('''CREATE TEMP TABLE selected AS
          SELECT url FROM first_use WHERE NOT coalesce(is_human,false)
          AND channel IN ('chat','action') GROUP BY url HAVING count(DISTINCT actor)>=8''')
        urls = [r[0] for r in self.c.execute('SELECT url FROM selected ORDER BY url').fetchall()]
        repos = {u: REPO_URL.match(u).group(2) for u in urls
                 if REPO_URL.match(u) and len(REPO_URL.match(u).group(2)) >= 5}
        (self.out / 'repos.json').write_text(json.dumps(repos, indent=2))
        counts = {}
        counts['first_use'] = self.jsonl('first_use.jsonl', '''SELECT f.* FROM first_use f
            JOIN selected s USING(url) WHERE channel IN ('chat','action') ORDER BY url,first_at,actor''')
        counts['roster'] = self.jsonl('roster.jsonl', 'SELECT id::VARCHAR id,name,model_string FROM agents')
        counts['actions'] = self.jsonl('actions.jsonl', '''WITH a AS
          (SELECT DISTINCT u.url,u.row_id,u.created_at,u.agent_id::VARCHAR actor FROM uses u
           JOIN selected s USING(url) WHERE u.channel='action' AND u.agent_id IS NOT NULL)
          SELECT a.*, t.action,ct.agent_action::VARCHAR agent_action FROM a
          JOIN turns t ON t.id::VARCHAR=a.row_id JOIN computer ct ON ct.id=a.row_id
          ORDER BY a.created_at,a.row_id,a.url''')
        pattern = '|'.join(re.escape(n.lower()) for n in sorted(set(repos.values())))
        counts['commands'] = self.jsonl('commands.jsonl', '''SELECT t.id::VARCHAR row_id,
          t.agent_id::VARCHAR actor,t.created_at,ct.agent_action->>'command' command
          FROM turns t JOIN computer ct ON ct.id=t.id WHERE t.action='bash'
          AND regexp_matches(lower(ct.agent_action->>'command'),?) ORDER BY t.created_at,t.id''', [pattern])
        hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                  for p in self.out.iterdir() if p.is_file()}
        manifest = {'complete': True, 'cascade_threshold': 8, 'cascades': len(urls),
                    'repos': len(repos), 'counts': counts, 'sha256': hashes,
                    'scope': 'saved URL frame; own bash commands with explicit selected basename'}
        (self.out / 'manifest.json').write_text(json.dumps(manifest, indent=2))
        log('complete', **counts)


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--parquet', default='/data/parquet')
    p.add_argument('--trace', default='/data/trace')
    p.add_argument('--out', required=True)
    args = p.parse_args()
    AuditExporter(args.parquet, args.trace, args.out).export()
