"""Reproduce FINDINGS §3 numbers from german_wiki.py outputs (aggregates only, no text).

  python -m explorer.adapters.german_report <trace_dir> <revisions.jsonl.gz>
"""
import math
import sys

import duckdb

MIN_USERS = 10
BINS = "CASE WHEN editors<=2 THEN '1-2' WHEN editors<=5 THEN '3-5' WHEN editors<=20 THEN '6-20' " \
       "WHEN editors<=100 THEN '21-100' ELSE '>100' END"


def wilson(s, n, z=1.959963984540054):
    p = s / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return 100 * (c - h), 100 * (c + h)


def main(trace_dir, revisions):
    con = duckdb.connect()
    for t in ('agents', 'trace_first_use', 'trace_edges_scored'):
        con.execute(f"CREATE VIEW {t} AS SELECT * FROM read_parquet('{trace_dir}/{t}.parquet')")
    con.execute(f"CREATE TEMP TABLE pop AS SELECT page_key, count(DISTINCT label) FILTER (WHERE label<>'') editors "
                f"FROM read_json_auto('{revisions}') GROUP BY 1")
    base = f'''WITH a AS (SELECT url FROM trace_first_use GROUP BY url HAVING count(*) >= {MIN_USERS}),
      f AS (SELECT f.url, f.actor, split_part(f.row_id, '@', 1) page_key FROM trace_first_use f JOIN a USING (url)),
      j AS (SELECT CASE WHEN f.url LIKE 'technique:%' THEN 'technique' ELSE 'plain url' END k, p.editors, e.evidence
            FROM f JOIN pop p USING (page_key)
            LEFT JOIN trace_edges_scored e ON e.url = f.url AND e.target = f.actor)'''
    print(f'first uses of artifacts with >= {MIN_USERS} users; seen = adopter had edited a page showing it')
    for k, n, s in con.execute(base + " SELECT k, count(*), count(*) FILTER (WHERE evidence='seen') FROM j GROUP BY 1 ORDER BY 1").fetchall():
        lo, hi = wilson(s, n)
        print(f'  {k:10} {s}/{n} = {100 * s / n:.1f}% [{lo:.1f}-{hi:.1f}]')
    print('by page popularity (distinct labelled editors of the page of first use)')
    for b, k, n, s in con.execute(base + f" SELECT {BINS} b, k, count(*), count(*) FILTER (WHERE evidence='seen') FROM j GROUP BY 1, 2 ORDER BY min(editors), 2").fetchall():
        lo, hi = wilson(s, n)
        print(f'  {b:>7} {k:10} {s}/{n} = {100 * s / n:.1f}% [{lo:.1f}-{hi:.1f}]')
    print('top techniques (labels)')
    for u, n in con.execute("SELECT url, count(*) FROM trace_first_use WHERE url LIKE 'technique:%' GROUP BY 1 ORDER BY 2 DESC LIMIT 8").fetchall():
        print(f'  {n:4} {u}')


if __name__ == '__main__':
    main(*sys.argv[1:3])
