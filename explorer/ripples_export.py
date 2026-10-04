"""Standalone Belief ripples page for any dataset: trace tables (+ seed) -> one self-contained HTML file.

  python -m explorer.ripples_export --trace DIR --seed 'technique:webcrawlerapi.com' \
      --title 'German board: a fetch-proxy spreads' --caption '...' [--max-nodes 120] > page.html

DIR holds agents / trace_first_use / trace_edges_scored parquet files (e.g. from explorer/adapters/*).
The page loads vis-network from jsDelivr; everything else is inline. No source text is embedded:
nodes carry names/ids, edges carry times, evidence levels and row ids.
"""
import argparse
import html
import json
import sys
from pathlib import Path

import duckdb

sys.path.insert(0, str(Path(__file__).resolve().parent))
from belief_graph import GraphBuilder  # noqa: E402
from ripples_template import BELIEF_HTML  # noqa: E402

PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{title}</title>
<style>body{{margin:0;background:#0e1117;color:#e8e8ea;font-family:Inter,system-ui,sans-serif}}
.wrap{{max-width:1400px;margin:0 auto;padding:20px 16px}}h1{{font-size:26px;margin:0 0 6px}}
.cap{{color:#c9ccd4;font-size:15px;line-height:1.5;margin:0 0 14px;padding:10px 14px;border-left:4px solid #ff2fb4;background:#161922;border-radius:6px}}
.src{{color:#8a8f9c;font-size:12.5px;margin-top:10px}}</style></head>
<body><div class="wrap"><h1>{title}</h1><div class="cap">{caption}</div>{body}<div class="src">{source}</div></div></body></html>"""


def build(trace_dir, seed, max_nodes=None):
    con = duckdb.connect()
    for t in ('agents', 'trace_first_use', 'trace_edges_scored'):
        con.execute(f"CREATE VIEW {t} AS SELECT * FROM read_parquet('{Path(trace_dir) / (t + '.parquet')}')")
    s = {'kind': 'url', 'value': seed}
    if max_nodes:
        s['max_nodes'] = max_nodes
    return GraphBuilder(con, s, paths={}).build()


def page(graph, title, caption, source, moments=None, height=640):
    body = (BELIEF_HTML.replace('__DATA__', json.dumps(graph)).replace('__DRIFT__', '{}')
            .replace('__MOMENTS__', json.dumps(moments or [])).replace('__H__', str(height)))
    return PAGE.format(title=html.escape(title), caption=caption, body=body, source=source)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument('--trace', required=True)
    p.add_argument('--seed', required=True)
    p.add_argument('--title', default='Belief ripples')
    p.add_argument('--caption', default='')
    p.add_argument('--source', default='')
    p.add_argument('--moments', help='JSON file: [{at,label,row,color,lane}]')
    p.add_argument('--max-nodes', type=int)
    a = p.parse_args(argv)
    g = build(a.trace, a.seed, a.max_nodes)
    print(f"nodes={len(g['nodes'])} edges={len(g['edges'])}", file=sys.stderr)
    moments = json.load(open(a.moments)) if a.moments else None
    sys.stdout.write(page(g, a.title, a.caption, a.source, moments))


if __name__ == '__main__':
    main()
