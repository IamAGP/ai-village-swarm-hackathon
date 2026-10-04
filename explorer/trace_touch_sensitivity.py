"""Reconstruct legacy aggregates and conservative sensitivities from private exports.

All source content and per-cascade URLs stay in the private output directory.
This is a selected-frame intent analysis; it cannot establish authorship, success,
independent checking, cross-turn cwd, or complete execution recall.
"""
from collections import defaultdict
from datetime import datetime
import argparse
import json
from pathlib import Path
import random
import re
import statistics
from urllib.parse import urlsplit

from trace_exec import runs_repo
from trace_shell_audit import shell_evidence, strict_touch


GRAFFITI = 'https://gitlab.com/ai-village-agents/village/graffiti-verification'


def root_candidate(url):
    """URL-shape sensitivity; project existence is not inferred from a URL alone."""
    parsed = urlsplit(url)
    parts = parsed.path.strip('/').split('/')
    if parsed.hostname == 'github.com':
        return len(parts) == 2
    if parsed.hostname == 'gitlab.com':
        # The dataset's village namespace has projects below it, not at this group URL.
        return (parts[:1] != ['api'] and '-' not in parts and
                parts != ['ai-village-agents', 'village'] and len(parts) >= 2)
    return False


def read_rows(path):
    with Path(path).open() as f:
        for line in f:
            yield json.loads(line)


def median(xs):
    return statistics.median(xs) if xs else None


def hours(a, b):
    return (datetime.fromisoformat(a) - datetime.fromisoformat(b)).total_seconds() / 3600


def main(frame, out):
    frame, out = Path(frame), Path(out)
    out.mkdir(parents=True, exist_ok=False)
    repos = json.loads((frame / 'repos.json').read_text())
    first = defaultdict(list)
    for r in read_rows(frame / 'first_use.jsonl'):
        first[r['url']].append(r)
    origins, human_origins, first_action, human_action, chat = {}, {}, {}, {}, {}
    tie_count = 0
    for url, rows in first.items():
        agents = sorted((r for r in rows if not r['is_human']), key=lambda r: (r['first_at'], r['actor'], r['channel']))
        origin = agents[0]
        tie_count += len({r['actor'] for r in agents if r['first_at'] == origin['first_at']}) > 1
        origins[url] = origin
        human_origins[url] = min(rows, key=lambda r: (r['first_at'], r['actor'] or ''))
        human_action[url] = min((r for r in agents if r['channel']=='action' and
                                r['actor'] != human_origins[url]['actor']), key=lambda r:r['first_at'],default=None)
        others = [r for r in agents if r['actor'] != origin['actor']]
        first_action[url] = min((r for r in others if r['channel'] == 'action'), key=lambda r: r['first_at'], default=None)
        chat[url] = [r for r in others if r['channel'] == 'chat']
    strict_first, first_kinds, action_lookup = {}, {}, {}
    for r in read_rows(frame / 'actions.jsonl'):
        url = r['url']
        action_lookup[r['row_id']] = r
        if r['actor'] == origins[url]['actor']:
            continue
        kind = strict_touch(r['agent_action'], url)
        if first_action[url] and r['row_id'] == first_action[url]['row_id']:
            first_kinds[url] = kind
        if kind and url not in strict_first:
            strict_first[url] = dict(r, category=kind)
    talk = []
    for url, origin in origins.items():
        loose, strict = first_action[url], strict_first.get(url)
        human = human_origins[url]
        talk.append({'url': url, 'origin': origin, 'human_inclusive_origin': human,
                     'first_touch': loose, 'first_strict_touch': strict,
                     'strict_first_category': first_kinds.get(url),
                     'loose_h': hours(loose['first_at'], origin['first_at']) if loose else None,
                     'strict_h': hours(strict['created_at'], origin['first_at']) if strict else None,
                     'human_seed_loose_h': hours(human_action[url]['first_at'], human['first_at']) if human_action[url] else None,
                     'talk_before_loose': sum(not loose or r['first_at'] < loose['first_at'] for r in chat[url]),
                     'talk_before_strict': sum(not strict or r['first_at'] < strict['created_at'] for r in chat[url])})
    by_name = defaultdict(list)
    for url, name in repos.items():
        by_name[name.lower()].append(url)
    name_pattern = re.compile('|'.join(re.escape(n) for n in sorted(by_name, key=lambda n: (-len(n), n))))
    events, contrib, human_runs = defaultdict(list), defaultdict(dict), {}
    # Reservoirs: one deterministic random row per repo and predicted class.
    reservoirs, sizes = {}, defaultdict(int)
    rng = random.Random(40)
    commands = {}
    for index,r in enumerate(read_rows(frame / 'commands.jsonl'),1):
        if index % 10000 == 0:
            print(json.dumps({'stage':'commands','processed':index}),flush=True)
            (out/'progress.json').write_text(json.dumps({'processed':index,'complete':False}))
        cmd = r['command'] or ''
        # Preserve legacy substring matching for overlapping names (foo vs foo-rest).
        matches = {m.group(0) for m in name_pattern.finditer(cmd.lower())}
        names = {n for match in matches for n in by_name if n in match}
        for name in names:
            old = runs_repo(cmd, name)
            strict = shell_evidence(cmd, name)
            for url in by_name[name]:
                origin = origins[url]
                human = human_origins[url]
                if old and r['actor'] != human['actor'] and r['created_at'] >= human['first_at']:
                    human_runs.setdefault(url,r)
                if r['actor'] == origin['actor'] or r['created_at'] < origin['first_at']:
                    if strict.contribution:
                        contrib[url].setdefault(r['actor'], r)
                    continue
                prior = contrib[url].get(r['actor'])
                rec = {'row_id': r['row_id'], 'actor': r['actor'], 'at': r['created_at'],
                       'legacy_run': old, 'strict_run': strict.run,
                       'prior_contribution_row': prior['row_id'] if prior else None,
                       'same_turn_contribution': strict.contribution}
                if old or strict.run:
                    events[url].append(rec)
                key = (url, old)
                sizes[key] += 1
                if rng.randrange(sizes[key]) == 0:
                    reservoirs[key] = dict(rec, url=url, repo_name=name, command=cmd)
                if strict.contribution:
                    contrib[url].setdefault(r['actor'], r)
        # Only retain commands needed for the earliest per-repo legacy witnesses.
        if any(e and e[-1]['row_id'] == r['row_id'] and len(e) == 1 for e in events.values()):
            commands[r['row_id']] = cmd
    run_rows = []
    for url in repos:
        origin = origins[url]
        seq = events[url]
        old = next((e for e in seq if e['legacy_run']), None)
        strict = next((e for e in seq if e['strict_run']), None)
        noncontrib = next((e for e in seq if e['strict_run'] and not e['prior_contribution_row'] and not e['same_turn_contribution']), None)
        no_prior = next((e for e in seq if e['strict_run'] and not e['prior_contribution_row']),None)
        row = {'url': url, 'origin': origin, 'legacy_first': old, 'strict_first': strict,
               'no_observed_prior_contribution_first': noncontrib,
               'no_prior_record_first': no_prior,
               'human_inclusive_origin': human_origins[url]}
        for field, event in [('legacy_h', old), ('strict_h', strict), ('noncontrib_h', noncontrib),('no_prior_h',no_prior)]:
            row[field] = hours(event['at'], origin['first_at']) if event else None
        human_run = human_runs.get(url)
        row['human_seed_legacy_h'] = hours(human_run['created_at'], human_origins[url]['first_at']) if human_run else None
        row['touch_h'] = hours(first_action[url]['first_at'], origin['first_at']) if first_action[url] else None
        run_rows.append(row)
    def describe(rows, field):
        xs = [r[field] for r in rows if r[field] is not None]
        g = next((r[field] for r in rows if r['url'] == GRAFFITI), None)
        return {'n': len(rows), 'observed': len(xs), 'missing': len(rows)-len(xs), 'median_h': median(xs),
                'within_1h': sum(x <= 1 for x in xs), 'within_24h': sum(x <= 24 for x in xs),
                'graffiti_h': g, 'faster_than_graffiti': sum(x < g for x in xs) if g is not None else None}
    summary = {'tie_origins': tie_count, 'talk': {k: describe(talk, k) for k in ['loose_h', 'strict_h', 'human_seed_loose_h']},
               'first_actions_explicit_retrieval': sum(bool(x) for x in first_kinds.values()),
               'human_earlier_cascades': sum(human_origins[u]['first_at'] < origins[u]['first_at'] for u in first),
               'talk_before_loose': {'median': median([r['talk_before_loose'] for r in talk]),
                                     'max': max(r['talk_before_loose'] for r in talk),
                                     'any': sum(r['talk_before_loose']>0 for r in talk)},
               'talk_before_strict': {'median': median([r['talk_before_strict'] for r in talk]),
                                      'max': max(r['talk_before_strict'] for r in talk),
                                      'any': sum(r['talk_before_strict']>0 for r in talk)},
               'repos': {k: describe(run_rows, k) for k in ['touch_h','legacy_h','strict_h','noncontrib_h','no_prior_h','human_seed_legacy_h']},
               'legacy_first_prior_contributor': sum(bool(r['legacy_first'] and r['legacy_first']['prior_contribution_row']) for r in run_rows),
               'strict_first_prior_contributor': sum(bool(r['strict_first'] and r['strict_first']['prior_contribution_row']) for r in run_rows),
               'graffiti': next(r for r in run_rows if r['url'] == GRAFFITI)}
    root_rows = [r for r in run_rows if root_candidate(r['url'])]
    summary['root_only'] = {k:describe(root_rows,k) for k in ['touch_h','legacy_h','strict_h','noncontrib_h','no_prior_h','human_seed_legacy_h']}
    summary['root_only']['legacy_first_prior_contributor'] = sum(bool(r['legacy_first'] and r['legacy_first']['prior_contribution_row']) for r in root_rows)
    summary['root_only']['strict_first_prior_contributor'] = sum(bool(r['strict_first'] and r['strict_first']['prior_contribution_row']) for r in root_rows)
    summary['ui_frame'] = {k:describe([r for r in run_rows if '/api/' not in r['url']],k) for k in ['touch_h','legacy_h']}
    summary['root_only']['paired_gap_run_minus_loose_touch_h'] = median([r['strict_h']-r['touch_h'] for r in root_rows if r['strict_h'] is not None and r['touch_h'] is not None])
    summary['root_only']['run_precedes_loose_touch'] = sum(r['strict_h']<r['touch_h'] for r in root_rows if r['strict_h'] is not None and r['touch_h'] is not None)
    summary['root_only']['strict_first_same_turn_contribution'] = sum(bool(r['strict_first'] and r['strict_first']['same_turn_contribution']) for r in root_rows)
    summary['talk_before_strict_observed'] = {'n':len(strict_first), 'any':sum(r['talk_before_strict']>0 for r in talk if r['first_strict_touch']), 'median':median([r['talk_before_strict'] for r in talk if r['first_strict_touch']])}
    roster = {r['id']:r for r in read_rows(frame/'roster.jsonl')}
    summary['origins_without_roster_model'] = [u for u,o in origins.items() if not roster.get(o['actor'],{}).get('model_string')]
    for name, rows in [('talk.jsonl',talk),('runs.jsonl',run_rows)]:
        with (out / name).open('x') as f:
            for row in rows:
                f.write(json.dumps(row)+'\n')
    with (out/'run_events.jsonl').open('x') as f:
        for url,seq in events.items():
            for event in seq:
                f.write(json.dumps(dict(event,url=url))+'\n')
    samples = []
    for positive in [True,False]:
        pool = sorted((v for (u,p),v in reservoirs.items() if p == positive and root_candidate(u)), key=lambda r:r['url'])
        for r in rng.sample(pool,min(30,len(pool))):
            samples.append(r)
    rng.shuffle(samples)
    with (out/'sample_key.jsonl').open('x') as f:
        for i,r in enumerate(samples,1):
            f.write(json.dumps(dict(r,case=f'S{i:02d}'))+'\n')
    with (out/'sample_blind.jsonl').open('x') as f:
        for i,r in enumerate(samples,1):
            f.write(json.dumps({k:r[k] for k in ['row_id','repo_name','command']}|{'case':f'S{i:02d}'})+'\n')
    # First-touch random sample is separate from the command-class samples.
    selected = rng.sample(sorted(talk,key=lambda r:r['url']),min(30,len(talk)))
    with (out/'touch_sample.jsonl').open('x') as f:
        for i,r in enumerate(selected,1):
            a = action_lookup.get(r['first_touch']['row_id']) if r['first_touch'] else None
            f.write(json.dumps({'case':f'T{i:02d}','url':r['url'],'action':a})+'\n')
    (out/'summary.json').write_text(json.dumps(summary,indent=2))
    (out/'progress.json').write_text(json.dumps({'processed':index,'complete':True}))
    print(json.dumps(summary,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--frame',required=True)
    p.add_argument('--out',required=True)
    a=p.parse_args()
    main(a.frame,a.out)
