"""Talk before touch: across AI Village link cascades, how many agents *posted about* a link before anyone else
*acted on* it? Generalises Finding 1 from one case to every cascade. Runs on the explorer box; aggregates only.

Per link (>= MIN_AGENTS non-human agents in chat or action):
  origin       earliest agent to post or act on it
  t_touch      first `action` (computer-use turn using the link) by any agent other than the origin
  talk_before  agents other than the origin whose first public chat post with the link precedes t_touch
  lag_h        hours from origin to t_touch (None if no one else ever acted)
`action` means its input contains the link, including article/message drafting. It
does not establish opening, delivery or verification (adversarial review #40).
Usage: trace_talk.py [min_agents]   -> /data/findings/talk/{cascades.jsonl,summary.json}
"""
import json
import os
import sys
import time

import duckdb

TRACE, OUT = '/data/trace/trace_first_use.parquet', '/data/findings/talk'
F1_URL = 'https://gitlab.com/ai-village-agents/village/graffiti-verification'


def log(m):
    print(time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), m, flush=True)


def pct(xs, p):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(p * (len(xs) - 1) + 0.5))] if xs else None


def main(min_agents=8):
    os.makedirs(OUT, exist_ok=True)
    c = duckdb.connect()
    c.execute(f"CREATE VIEW f AS SELECT url, actor, channel, first_at FROM read_parquet('{TRACE}') "
              "WHERE NOT coalesce(is_human, false) AND channel IN ('chat', 'action')")
    log('LOAD start')
    rows = c.execute(f'''
      WITH n AS (SELECT url FROM f GROUP BY url HAVING count(DISTINCT actor) >= {int(min_agents)}),
      a AS (SELECT f.url, f.actor, min(f.first_at) t0,
                   min(f.first_at) FILTER (WHERE channel = 'chat') t_chat,
                   min(f.first_at) FILTER (WHERE channel = 'action') t_act
            FROM f JOIN n USING (url) GROUP BY 1, 2),
      o AS (SELECT url, arg_min(actor, t0) origin, min(t0) t_origin FROM a GROUP BY url),
      t AS (SELECT a.url, min(a.t_act) t_touch FROM a JOIN o USING (url) WHERE a.actor <> o.origin GROUP BY a.url)
      SELECT a.url, o.t_origin, t.t_touch,
             count(DISTINCT a.actor) n_agents,
             count(DISTINCT a.actor) FILTER (WHERE a.t_chat IS NOT NULL) n_talk,
             count(DISTINCT a.actor) FILTER (WHERE a.t_act IS NOT NULL) n_act,
             count(DISTINCT a.actor) FILTER (WHERE a.actor <> o.origin AND a.t_chat IS NOT NULL
                                             AND (t.t_touch IS NULL OR a.t_chat < t.t_touch)) talk_before
      FROM a JOIN o USING (url) LEFT JOIN t USING (url) GROUP BY 1, 2, 3''').fetchall()
    log(f'CASCADES {len(rows)}')
    out = []
    with open(f'{OUT}/cascades.jsonl', 'w') as fh:
        for url, t0, tt, n, nt, na, tb in rows:
            r = {'url': url, 'n_agents': n, 'n_talk': nt, 'n_act': na, 'talk_before': tb,
                 'lag_h': round((tt - t0).total_seconds() / 3600, 2) if tt else None,
                 'never_touched': tt is None, 't_origin': str(t0)}
            out.append(r)
            fh.write(json.dumps(r) + '\n')
    touched = [r for r in out if not r['never_touched']]
    tb = [r['talk_before'] for r in out]
    s = {'min_agents': min_agents, 'cascades': len(out), 'never_touched_by_others': len(out) - len(touched),
         'talk_before': {'p50': pct(tb, .5), 'p90': pct(tb, .9), 'max': max(tb) if tb else None,
                         'share_ge1': round(sum(x >= 1 for x in tb) / len(tb), 3) if tb else None,
                         'share_ge5': round(sum(x >= 5 for x in tb) / len(tb), 3) if tb else None},
         'lag_h': {'p50': pct([r['lag_h'] for r in touched], .5), 'p90': pct([r['lag_h'] for r in touched], .9)},
         'graffiti': next((r for r in out if r['url'] == F1_URL), None)}
    if s['graffiti']:
        g = s['graffiti']['talk_before']
        s['graffiti_rank_talk_before'] = {'cascades_with_more': sum(x > g for x in tb), 'ties': sum(x == g for x in tb) - 1}
    json.dump(s, open(f'{OUT}/summary.json', 'w'), indent=1)
    log('SUMMARY ' + json.dumps(s))


if __name__ == '__main__':
    main(*(int(a) for a in sys.argv[1:2]))
