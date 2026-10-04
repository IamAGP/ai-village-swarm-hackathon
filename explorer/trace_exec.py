"""Legacy touch/run candidate scan; not verified execution or independent checking.
Extends Finding 4. Runs on the explorer box; aggregates only. Writes /data/findings/exec/{cascades.jsonl,summary.json}.

Repo cascade: a GitHub/GitLab repo URL (owner/name) that >= MIN_AGENTS non-human agents posted or acted on.
Execution: a bash turn by a non-origin agent whose command, after stripping heredoc bodies and quoted strings
(articles quoting a command are not runs; FINDINGS §1 correction), mentions the repo name and runs an interpreter
or test/build tool. Confirmed false positives include comments, standard-library
utilities and unrelated programs in the same turn. URL candidates also contain
non-repo pages. See docs/TOUCH_RUN_REVIEW.md; results are preserved for sensitivity
comparison, not validated execution. Exit status and checkout provenance are unused.
"""
import json
import os
import re
import statistics
import sys
import time

import duckdb

PQ, TRACE, OUT = '/data/parquet', '/data/trace/trace_first_use.parquet', '/data/findings/exec'
REPO = re.compile(r'^https?://(?:www\.)?(github\.com|gitlab\.com)/(?:[^/\s]+/)+([^/\s#?]+?)(?:\.git)?/?$')
# an interpreter/test tool invoked on a file or module; `python3 -c` and `| python3` (parsing API output) are not runs
RUN = re.compile(r'(^|[\s;&(])(python3?\s+(-m\s+\S+|[^\s-]\S*\.py)|pytest\b|node\s+[^\s-]\S*\.(c?js|mjs)|npm\s+(run|test)\b|npx\s+\S+|'
                 r'(ba)?sh\s+[^\s-]\S*\.sh|make\b|cargo\s+(run|test)|go\s+(run|test))')
HEREDOC = re.compile(r"<<-?\s*['\"]?(\w+)['\"]?.*?\n.*?\n\1\b", re.S)
QUOTED = re.compile(r"'[^']*'|\"[^\"]*\"")


def log(m):
    print(time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), m, flush=True)


def runs_repo(cmd, name):
    """True if the command runs code *inside* the repo: cd into it (or a path through it) plus a file-level run."""
    body = QUOTED.sub(' ', HEREDOC.sub(' ', cmd or '')).lower()
    n = re.escape(name.lower())
    inside = re.search(r'\bcd\s+\S*' + n + r'\b', body) or re.search(n + r'/\S+', body)
    return bool(inside) and RUN.search(body) is not None


def main(min_agents=8):
    os.makedirs(OUT, exist_ok=True)
    c = duckdb.connect()
    c.execute(f"CREATE VIEW f AS SELECT url, actor, channel, first_at FROM read_parquet('{TRACE}') "
              "WHERE NOT coalesce(is_human, false) AND channel IN ('chat', 'action')")
    casc = c.execute(f'''WITH a AS (SELECT url, actor, min(first_at) t0, min(first_at) FILTER (WHERE channel='action') ta
                                  FROM f GROUP BY 1, 2),
                        n AS (SELECT url FROM a GROUP BY url HAVING count(*) >= {int(min_agents)})
                        SELECT a.url, arg_min(a.actor, a.t0), min(a.t0), count(*) FROM a JOIN n USING (url) GROUP BY 1''').fetchall()
    repos = {}
    for url, origin, t0, n in casc:
        m = REPO.match(url)
        if m and len(m.group(2)) >= 5:
            repos[url] = {'name': m.group(2), 'origin': origin, 't0': t0, 'n_agents': n}
    log(f'REPO_CASCADES {len(repos)} of {len(casc)}')
    touch = dict(c.execute('''SELECT f.url, min(f.first_at) FROM f JOIN (SELECT url, arg_min(actor, first_at) o FROM f GROUP BY url) o
                              USING (url) WHERE f.channel='action' AND f.actor <> o.o GROUP BY 1''').fetchall())
    names = sorted({r['name'] for r in repos.values()})
    pat = '(' + '|'.join(re.escape(x) for x in names) + ')'
    log('SCAN bash commands mentioning any repo name')
    cmds = c.execute(f'''SELECT t.agent_id::VARCHAR, t.created_at, ct.agent_action->>'command', t.id::VARCHAR
                         FROM read_parquet('{PQ}/turns_slim.parquet') t JOIN read_parquet('{PQ}/computer_use_turns.parquet') ct ON ct.id = t.id
                         WHERE t.action = 'bash' AND regexp_matches(lower(ct.agent_action->>'command'), lower(?))''', [pat]).fetchall()
    log(f'CANDIDATE_CMDS {len(cmds)}')
    out = []
    for url, r in sorted(repos.items()):
        ex = sorted((at, aid, rid) for aid, at, cmd, rid in cmds if aid != r['origin'] and at >= r['t0'] and runs_repo(cmd, r['name']))
        first = ex[0] if ex else None
        tt = touch.get(url)
        rec = {'url': url, 'n_agents': r['n_agents'], 'touch_h': round((tt - r['t0']).total_seconds() / 3600, 2) if tt else None,
               'run_h': round((first[0] - r['t0']).total_seconds() / 3600, 2) if first else None,
               'run_agents': len({e[1] for e in ex}), 'first_run_row': first[2][:8] if first else None}
        out.append(rec)
    with open(f'{OUT}/cascades.jsonl', 'w') as fh:
        for rec in out:
            fh.write(json.dumps(rec) + '\n')
    ran = [r for r in out if r['run_h'] is not None]
    med = lambda xs: sorted(xs)[len(xs) // 2] if xs else None
    s = {'repo_cascades': len(out), 'ever_run_by_others': len(ran),
         'touch_h_median': med([r['touch_h'] for r in out if r['touch_h'] is not None]),
         'run_h_median_when_run': statistics.median([r['run_h'] for r in ran]) if ran else None,
         'gap_h_median_when_run': med([r['run_h'] - r['touch_h'] for r in ran if r['touch_h'] is not None]),
         'graffiti': next((r for r in out if 'graffiti-verification' in r['url']), None)}
    json.dump(s, open(f'{OUT}/summary.json', 'w'), indent=1)
    log('SUMMARY ' + json.dumps(s))
    for r in sorted(out, key=lambda r: -r['n_agents'])[:25]:
        print(r['n_agents'], r['touch_h'], r['run_h'], r['run_agents'], r['url'][:90])


if __name__ == '__main__':
    main(*(int(a) for a in sys.argv[1:2]))
