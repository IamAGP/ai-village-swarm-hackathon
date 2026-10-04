"""German message board (collusion.wiki export) -> Events for the shared tracer.

Input: revisions.jsonl.gz from https://collusion.wiki/explorer/download (public; no license stated).
Each revision is a full page body written by a self-chosen pseudonymous `label`, timed from request
logs. Modelling choices (stated so they can be challenged):

  agent      = label. Pseudonyms are self-chosen: one agent may use many labels and a label is not
               verified. Blank labels are skipped.
  artifacts  = URLs a revision *added* relative to the page's previous revision (a revision stores the
               whole page, so the body alone would credit an editor with everything already there),
               plus `technique:<host>` for each added URL that routes another URL through a fetch/CORS
               proxy (host path embeds http(s):// or www.); writing a new proxied URL counts as using the
               technique even when the page already showed it.
  seen       = page-edit exposure PROXY: the label edited a page whose preceding revision contained the
               artifact; source = the label that first added it there. Not proof of reading: the investigators
               report agents wrote to this wiki with direct GET requests, without loading the page
               (collusion.wiki). Includes the adoption edit itself; see docs/GERMAN_ADVERSARIAL_REVIEW.md.
  channel    = 'chat': a wiki edit is a public statement.

Usage: python -m explorer.adapters.german_wiki <revisions.jsonl.gz> [--out DIR]
Writes aggregate trace tables as parquet (no page text) and prints a timestamped summary.
"""
import argparse
import gzip
import json
import re
import sys
import time
from collections import Counter
from pathlib import Path

try:
    from .common import Event, load_into, parse_utc, trace_tables
except ImportError:  # run as a script
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from common import Event, load_into, parse_utc, trace_tables

URL = re.compile(r'https?://[^\s\]\)\|<>"\'}]+')
PROXY = re.compile(r'^https?://([^/]+)/.*?(https?(%3A|:)|www\.)', re.I)


def log(msg):
    print(time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), msg, file=sys.stderr, flush=True)


def urls_in(body):
    return {u.rstrip('.,;:!?') for u in URL.findall(body or '')}


def techniques(urls):
    return {'technique:' + m.group(1).lower() for m in map(PROXY.match, urls) if m}


def artifacts_in(body):
    urls = urls_in(body)
    return urls | techniques(urls)


def events(revisions):
    """revisions: iterable of dicts with page_id, seq, label, time, rev_id, body."""
    page_state = {}      # page_id -> {artifact: (adder_label, rev_id, at)}
    out = []
    for r in sorted(revisions, key=lambda r: (r['page_id'], int(r['seq']))):
        at = parse_utc(r['time'])
        label = (r.get('label') or '').strip()
        before = page_state.get(r['page_id'], {})
        urls = urls_in(r.get('body'))
        now = urls | techniques(urls)
        state = {a: before[a] for a in now if a in before}
        new_urls = {u for u in urls if u not in before}
        # a technique is *used* by any edit that writes a new proxied URL, even if the page already had one
        added = frozenset(new_urls | techniques(new_urls))
        for a in added:
            state.setdefault(a, (label or None, r['rev_id'], at))
        page_state[r['page_id']] = state
        if not label:
            continue
        seen = tuple((a, src, row, at) for a, (src, row, _) in sorted(before.items()) if src and src != label)
        out.append(Event(r['rev_id'], label, at, 'chat', added, seen))
    return out


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument('revisions')
    p.add_argument('--out', default='data/german_wiki')
    a = p.parse_args(argv)
    log(f'READ {a.revisions}')
    revs = [json.loads(l) for l in gzip.open(a.revisions, 'rt')]
    log(f'REVISIONS {len(revs)}')
    evs = events(revs)
    log(f'EVENTS {len(evs)} labels={len({e.agent for e in evs})}')
    agents, first_use, edges, stats = trace_tables(evs)
    log(f'TABLES agents={len(agents)} first_use={len(first_use)} edges={len(edges)} evidence={stats}')
    import duckdb
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    load_into(con, agents, first_use, edges)
    for t in ('agents', 'trace_first_use', 'trace_edges_scored'):
        con.execute(f"COPY {t} TO '{out / (t + '.parquet')}' (FORMAT parquet)")
    tech = Counter(u for u, *_ in first_use if u.startswith('technique:'))
    log('TOP_TECHNIQUES ' + json.dumps(tech.most_common(10)))
    log(f'DONE {out}')


if __name__ == '__main__':
    main()
