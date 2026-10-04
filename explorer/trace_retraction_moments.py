"""Row-ID-only withdrawal moments; no private dataset text.

The last marker is a witnessed stale local file, not an endpoint of public serving
or a claim that no later memory retained the withdrawn propositions.
"""
import argparse
import json
from pathlib import Path

MOMENTS = [
    dict(at='2026-07-30T19:20:58.248631Z',label='author retracts 2',
         row='56f9501d-c70a-42bc-9786-2c432a7e8597',channel='chat',color='#4ea8ff',lane=0),
    dict(at='2026-07-30T19:21:15.743861Z',label='first withdrawal relay',
         row='e7a98bf1-f5a1-4b5e-a190-f562e311062b',channel='chat',color='#4ea8ff',lane=3),
    dict(at='2026-07-30T19:38:37.905321Z',label='stale local blog observed',
         row='dbb72309-a238-468a-9515-435c07268467',channel='turn',color='#ff5c6c',lane=4),
]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out',required=True,type=Path)
    a = p.parse_args()
    # Exclusive creation preserves earlier evidence exports.
    with a.out.open('x') as f:
        json.dump(MOMENTS,f,indent=2)
        f.write('\n')


if __name__ == '__main__':
    main()
